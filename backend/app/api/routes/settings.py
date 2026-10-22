"""Préférences utilisateur (mode hors ligne / en ligne, moteur et modèles d'IA) et limites de l'application."""

import asyncio

from fastapi import APIRouter
from pydantic import BaseModel

from app import __version__
from app.api.deps import PreferencesDep, SettingsDep
from app.services.convert.pipeline import EXTENSIONS
from app.services.preferences import Preferences

router = APIRouter(prefix="/settings", tags=["settings"])


class AppInfo(BaseModel):
    """Ce que l'interface affiche des réglages de l'application (aucun secret)."""

    version: str
    max_upload_mb: int
    ai_max_lines: int
    ai_max_chars: int
    tab_directory: str
    extensions: list[str]


@router.get("", response_model=Preferences)
async def get_preferences(prefs: PreferencesDep) -> Preferences:
    return prefs.get()


@router.put("", response_model=Preferences)
async def set_preferences(value: Preferences, prefs: PreferencesDep) -> Preferences:
    """Modifie les préférences envoyées (les champs absents sont gardés). Pris en compte immédiatement.

    `online_mode` active ou désactive Claude ; `ai_provider`, `claude_model` et `ollama_model` mémorisent
    le choix du moteur d'IA (docs/SUITE.md §5).
    """
    return await asyncio.to_thread(prefs.update, value.model_dump(exclude_unset=True))


@router.get("/info", response_model=AppInfo)
async def info(settings: SettingsDep) -> AppInfo:
    return AppInfo(
        version=__version__,
        max_upload_mb=settings.max_upload_mb,
        ai_max_lines=settings.ai_max_lines,
        ai_max_chars=settings.ai_max_chars,
        tab_directory=str(settings.tab_dir),
        extensions=sorted(EXTENSIONS),
    )
