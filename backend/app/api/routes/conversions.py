"""Conversions : import d'un fichier, relecture, colonnes, exports, envoi vers Atelier Tab, IA."""

import asyncio
import json
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from pydantic import ValidationError

from app.api.deps import AIServiceDep, ConversionsDep, SettingsDep, TabDep
from app.schemas.convert import (
    ColumnsUpdate,
    ConversionSummary,
    ConversionView,
    ExportFormat,
    ParseOptions,
    RenameRequest,
    SendToTabRequest,
    SendToTabResult,
    StructureRequest,
    StructureResult,
    TabStatus,
)
from app.services.convert.ai_structure import excerpt, structure
from app.services.convert.pipeline import ConvertError

router = APIRouter(tags=["conversions"])


async def read_upload(file: UploadFile, max_mb: int) -> bytes:
    """Contenu d'un fichier envoyé, refusé au-delà de `max_mb` Mo (413)."""
    limit = max_mb * 1024 * 1024
    chunks: list[bytes] = []
    size = 0
    while chunk := await file.read(1024 * 1024):
        size += len(chunk)
        if size > limit:
            raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, f"Fichier trop volumineux (plus de {max_mb} Mo).")
        chunks.append(chunk)
    return b"".join(chunks)


def parse_options(raw: str | None) -> ParseOptions:
    if not raw:
        return ParseOptions()
    try:
        return ParseOptions.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise HTTPException(422, "Options de lecture invalides.") from exc


@router.get("/conversions", response_model=list[ConversionSummary])
async def list_conversions(service: ConversionsDep) -> list[ConversionSummary]:
    """Historique des conversions, les plus récentes d'abord."""
    return await asyncio.to_thread(service.store.list)


@router.post("/conversions", response_model=ConversionView, status_code=status.HTTP_201_CREATED)
async def create_conversion(
    service: ConversionsDep,
    settings: SettingsDep,
    file: Annotated[UploadFile, File(description="Fichier à convertir.")],
    options: Annotated[str | None, Form(description="Options de lecture (JSON).")] = None,
) -> ConversionView:
    """Lit le fichier envoyé (tout reste sur la machine) et enregistre la conversion."""
    data = await read_upload(file, settings.max_upload_mb)
    conv = await asyncio.to_thread(service.create, data, file.filename or "fichier", parse_options(options))
    return service.store.view(conv)


@router.get("/conversions/{conversion_id}", response_model=ConversionView)
async def get_conversion(conversion_id: str, service: ConversionsDep) -> ConversionView:
    conv = await asyncio.to_thread(service.store.get, conversion_id)
    return service.store.view(conv)


@router.get("/conversions/{conversion_id}/rows")
async def get_rows(
    conversion_id: str,
    service: ConversionsDep,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=5000)] = 500,
) -> dict[str, object]:
    """Lignes de la table, par pages (aperçu complet dans l'interface)."""
    conv = await asyncio.to_thread(service.store.get, conversion_id)
    return {"rows": conv.table_rows[offset : offset + limit], "total": len(conv.table_rows), "offset": offset}


@router.put("/conversions/{conversion_id}/options", response_model=ConversionView)
async def set_options(conversion_id: str, options: ParseOptions, service: ConversionsDep) -> ConversionView:
    """Relit le fichier d'origine avec ces options (les colonnes sont recalculées)."""
    conv = await asyncio.to_thread(service.reparse, conversion_id, options)
    return service.store.view(conv)


@router.put("/conversions/{conversion_id}/columns", response_model=ConversionView)
async def set_columns(conversion_id: str, body: ColumnsUpdate, service: ConversionsDep) -> ConversionView:
    """Noms, types, ordre et colonnes incluses."""
    conv = await asyncio.to_thread(service.update_columns, conversion_id, body.columns)
    return service.store.view(conv)


@router.put("/conversions/{conversion_id}/name", response_model=ConversionView)
async def rename(conversion_id: str, body: RenameRequest, service: ConversionsDep) -> ConversionView:
    conv = await asyncio.to_thread(service.rename, conversion_id, body.name)
    return service.store.view(conv)


@router.delete("/conversions/{conversion_id}")
async def delete_conversion(conversion_id: str, service: ConversionsDep) -> dict[str, bool]:
    """Supprime la conversion et son fichier source (les tables déjà envoyées dans Tab restent)."""
    await asyncio.to_thread(service.delete, conversion_id)
    return {"deleted": True}


@router.get("/conversions/{conversion_id}/export")
async def export(
    conversion_id: str,
    service: ConversionsDep,
    format: Annotated[ExportFormat, Query(description="csv-fr, csv, txt, xlsx ou json (atelier-table/1).")] = "csv-fr",
) -> Response:
    """Fichier exporté (colonnes incluses seulement)."""
    out = await asyncio.to_thread(service.export, conversion_id, format)
    ascii_name = out.filename.encode("ascii", "ignore").decode() or "conversion"
    disposition = f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(out.filename)}"
    return Response(out.content, media_type=out.media_type, headers={"Content-Disposition": disposition})


@router.post("/conversions/{conversion_id}/send-to-tab", response_model=SendToTabResult)
async def send_to_tab(conversion_id: str, body: SendToTabRequest, service: ConversionsDep) -> SendToTabResult:
    """Crée une table dans le projet choisi d'Atelier Tab (fichier `tables/<id>.json`, sans réseau)."""
    return await asyncio.to_thread(service.send_to_tab, conversion_id, body.project_id, body.table_name)


@router.post("/conversions/{conversion_id}/structure", response_model=StructureResult)
async def structure_with_ai(
    conversion_id: str, body: StructureRequest, service: ConversionsDep, ai: AIServiceDep, settings: SettingsDep
) -> StructureResult:
    """Envoie le texte extrait (premières lignes) au moteur choisi, qui propose une table.

    Hors ligne, seul Ollama (local) est utilisé ; Claude est refusé (403).
    """
    conv = await asyncio.to_thread(service.store.get, conversion_id)
    if not conv.raw_text or not conv.raw_text.strip():
        raise ConvertError("Aucun texte extrait pour ce fichier : rien à envoyer à l'IA.")
    text = excerpt(conv.raw_text, settings.ai_max_lines, settings.ai_max_chars)
    provider, table = await structure(
        ai, body.provider, text, body.instructions, conv.options, settings.convert_max_rows
    )
    updated = await asyncio.to_thread(service.apply_table, conversion_id, table, "ai")
    return StructureResult(
        provider=provider.name,
        model=provider.model,
        sent_lines=len(text.splitlines()),
        sent_chars=len(text),
        conversion=service.store.view(updated),
    )


@router.get("/tab", response_model=TabStatus)
async def tab_status(tab: TabDep) -> TabStatus:
    """Projets d'Atelier Tab (lus dans son dossier de données)."""
    return await asyncio.to_thread(tab.status)
