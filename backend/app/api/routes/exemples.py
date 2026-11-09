"""Exemples de la suite : histoires fictives reliées d'une app à l'autre (« Exemples de la suite »)."""

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.api.deps import ConversionsDep, SettingsDep
from app.schemas.convert import ConversionView, ParseOptions
from app.schemas.exemples import ExempleHistoire
from app.services.exemples import ExempleError, ExemplesSuite

router = APIRouter(prefix="/exemples-suite", tags=["exemples"])


def get_exemples(settings: SettingsDep) -> ExemplesSuite:
    return ExemplesSuite(settings.convert_exemples_dir)


ExemplesDep = Annotated[ExemplesSuite, Depends(get_exemples)]


@router.get("", response_model=list[ExempleHistoire])
async def list_exemples(exemples: ExemplesDep) -> list[ExempleHistoire]:
    """Histoires et fichiers à convertir (liste vide si l'installation n'en contient pas)."""
    return await asyncio.to_thread(exemples.histoires)


@router.post("/{histoire}/{index}", response_model=ConversionView, status_code=status.HTTP_201_CREATED)
async def convert_exemple(
    histoire: Annotated[str, Path(max_length=64)],
    index: Annotated[int, Path(ge=0, le=100)],
    exemples: ExemplesDep,
    service: ConversionsDep,
) -> ConversionView:
    """Convertit un fichier de l'histoire comme s'il avait été déposé, sous le nom prévu par l'histoire."""
    try:
        data, filename, name = await asyncio.to_thread(exemples.fichier, histoire, index)
    except ExempleError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    conv = await asyncio.to_thread(service.create, data, filename, ParseOptions())
    conv = await asyncio.to_thread(service.rename, conv.id, name)
    return service.store.view(conv)
