"""Fichiers d'exemple livrés avec le dépôt (« Essayer avec un exemple »)."""

import asyncio

from fastapi import APIRouter, HTTPException, status

from app.api.deps import ConversionsDep, SettingsDep
from app.schemas.convert import ConversionView, ParseOptions, SampleInfo

router = APIRouter(prefix="/samples", tags=["samples"])

SAMPLES: dict[str, tuple[str, str]] = {
    "releve-mars-2026.pdf": (
        "Relevé bancaire (PDF)",
        "Relevé de compte fictif : colonnes Date, Libellé, Débit, Crédit.",
    ),
    "export-banque.csv": (
        "Export de banque (CSV)",
        "Export « ; » en Windows-1252 avec préambule, comme ceux des banques.",
    ),
    "operations.ofx": ("Fichier OFX", "Format d'échange Money / Quicken."),
    "releve-scanne.pdf": ("Relevé scanné (OCR)", "PDF d'images sans texte : lu par reconnaissance de caractères."),
}


@router.get("", response_model=list[SampleInfo])
async def list_samples(settings: SettingsDep) -> list[SampleInfo]:
    return [
        SampleInfo(name=name, label=label, description=desc)
        for name, (label, desc) in SAMPLES.items()
        if (settings.samples_dir / name).is_file()
    ]


@router.post("/{name}", response_model=ConversionView, status_code=status.HTTP_201_CREATED)
async def load_sample(name: str, settings: SettingsDep, service: ConversionsDep) -> ConversionView:
    """Convertit un fichier d'exemple comme s'il avait été déposé."""
    if name not in SAMPLES or not (settings.samples_dir / name).is_file():
        raise HTTPException(404, "Exemple introuvable.")
    data = await asyncio.to_thread((settings.samples_dir / name).read_bytes)
    conv = await asyncio.to_thread(service.create, data, name, ParseOptions())
    return service.store.view(conv)
