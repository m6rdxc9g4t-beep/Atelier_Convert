"""Nœud Atelier (docs/SUITE.md §7) : manifeste, tables d'échange, conversion et envoi vers Tab, événements.

Routes minces : la logique est dans `app/services/`. Erreurs au format `{detail, code}` (§7.5),
posées par les gestionnaires de `main.py` pour tout chemin `/api/atelier/*`.
"""

import asyncio
import base64
import binascii
from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from fastapi import APIRouter, Header, Query, status
from fastapi.responses import JSONResponse

from app.api.deps import ConversionsDep, IdempotencyDep, JournalDep, SettingsDep
from app.schemas.atelier import (
    EVENTS_DEFAULT_LIMIT,
    EVENTS_MAX_LIMIT,
    TABLE_DEFAULT_LIMIT,
    TABLE_MAX_LIMIT,
    AtelierEventsPage,
    AtelierManifest,
    AtelierTable,
    ConvertFileInput,
    ConvertFileResult,
)
from app.schemas.convert import SendToTabRequest, SendToTabResult
from app.services.atelier.errors import AtelierError
from app.services.atelier.idempotency import MAX_KEY_LENGTH, IdempotencyStore, fingerprint
from app.services.atelier.manifest import build_manifest

router = APIRouter(prefix="/atelier", tags=["atelier"])


@router.get("/manifest", response_model=AtelierManifest, response_model_by_alias=True)
async def manifest() -> AtelierManifest:
    """Ce qu'Atelier Convert sait faire dans un workflow (actions, événements) — sans secret ni donnée."""
    return build_manifest()


@router.get("/conversions/{conversion_id}/table", response_model=AtelierTable)
async def conversion_table(
    conversion_id: str,
    service: ConversionsDep,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=TABLE_MAX_LIMIT)] = TABLE_DEFAULT_LIMIT,
) -> AtelierTable:
    """Lignes d'une conversion au format `atelier-table/1` (`truncated` si d'autres lignes existent)."""
    return await asyncio.to_thread(service.table_page, conversion_id, offset, limit)


async def _idempotent(
    store: IdempotencyStore,
    scope: str,
    key: str | None,
    body: Any,
    run: Callable[[], Awaitable[tuple[int, dict[str, Any]]]],
) -> JSONResponse:
    """Exécute une écriture une seule fois par clé (docs/SUITE.md §7.4)."""
    if key is None:
        code, result = await run()
        return JSONResponse(result, status_code=code)
    if not 1 <= len(key) <= MAX_KEY_LENGTH or not key.isprintable():
        raise AtelierError(422, "VALIDATION", f"En-tête Idempotency-Key invalide (1 à {MAX_KEY_LENGTH} caractères).")
    fp = fingerprint(body)
    async with store.lock(scope, key):
        stored = await asyncio.to_thread(store.lookup, scope, key)
        if stored is not None:
            if stored.fingerprint != fp:
                raise AtelierError(
                    409,
                    "IDEMPOTENCY_KEY_REUSED",
                    "Cette clé d'idempotence a déjà servi pour une autre requête : utilisez une nouvelle clé.",
                )
            return JSONResponse(stored.body, status_code=stored.status_code, headers={"Idempotency-Replayed": "true"})
        code, result = await run()
        await asyncio.to_thread(store.save, scope, key, fp, code, result)
        return JSONResponse(result, status_code=code)


@router.post("/conversions", response_model=ConvertFileResult, status_code=status.HTTP_201_CREATED)
async def convert_file(
    body: ConvertFileInput,
    service: ConversionsDep,
    settings: SettingsDep,
    idempotency: IdempotencyDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JSONResponse:
    """Convertit un fichier transmis en base64 et crée une conversion. `Idempotency-Key` accepté (§7.4)."""
    try:
        data = base64.b64decode(body.content_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise AtelierError(422, "VALIDATION", "content_base64 n'est pas du base64 valide.") from exc
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise AtelierError(413, "VALIDATION", f"Fichier trop volumineux (plus de {settings.max_upload_mb} Mo).")

    async def run() -> tuple[int, dict[str, Any]]:
        conv = await asyncio.to_thread(service.create, data, body.filename, body.options, "workflow")
        return 201, service.result(conv).model_dump(mode="json")

    return await _idempotent(
        idempotency, "conversions.convert_file", idempotency_key, body.model_dump(mode="json"), run
    )


@router.post("/conversions/{conversion_id}/send-to-tab", response_model=SendToTabResult)
async def send_to_tab(
    conversion_id: str,
    body: SendToTabRequest,
    service: ConversionsDep,
    idempotency: IdempotencyDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JSONResponse:
    """Crée une table dans Atelier Tab (une seule fois par clé d'idempotence)."""

    async def run() -> tuple[int, dict[str, Any]]:
        result = await asyncio.to_thread(service.send_to_tab, conversion_id, body.project_id, body.table_name)
        return 200, result.model_dump(mode="json")

    payload = {"conversion_id": conversion_id, **body.model_dump(mode="json")}
    return await _idempotent(idempotency, "conversions.send_to_tab", idempotency_key, payload, run)


@router.get("/events", response_model=AtelierEventsPage, response_model_exclude_none=True)
async def events(
    journal: JournalDep,
    since: Annotated[int | None, Query(ge=0, description="Dernier seq déjà lu (exclusif).")] = None,
    limit: Annotated[int, Query(ge=1, le=EVENTS_MAX_LIMIT)] = EVENTS_DEFAULT_LIMIT,
    types: Annotated[str | None, Query(max_length=2000, description="Types séparés par des virgules.")] = None,
) -> AtelierEventsPage:
    """Événements après `since` (ou les plus récents) ; `gap: true` si des événements ont été perdus."""
    wanted = {t.strip() for t in types.split(",") if t.strip()} if types else None
    return await asyncio.to_thread(journal.page, since, limit, wanted)
