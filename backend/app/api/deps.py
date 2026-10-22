"""Dépendances FastAPI partagées par les routes."""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request

from app.core.config import Settings
from app.services.ai import AIService, AnthropicProvider, ClaudeCliProvider, OllamaProvider
from app.services.ai.service import ClaudeProvider
from app.services.atelier import EventJournal, IdempotencyStore
from app.services.convert.service import ConversionService
from app.services.convert.tab import TabFolder
from app.services.preferences import Preferences, PreferencesStore


def build_claude_provider(settings: Settings, preferences: Callable[[], Preferences] | None = None) -> ClaudeProvider:
    """CLI Claude Code (abonnement) ou API Anthropic (clé Console), selon `CLAUDE_MODE`.

    En mode CLI, le modèle (Sonnet / Opus / Haiku) est celui choisi par l'utilisateur (`preferences`).
    """
    if settings.claude_mode == "cli":
        return ClaudeCliProvider(
            executable=settings.claude_cli_path,
            model=settings.claude_cli_model,
            timeout=settings.claude_cli_timeout_seconds,
            model_choice=(lambda: preferences().claude_model) if preferences else None,
        )
    api_key = settings.anthropic_api_key.get_secret_value() if settings.anthropic_configured else None
    return AnthropicProvider(
        api_key=api_key,
        model=settings.anthropic_model,
        max_tokens=settings.anthropic_max_tokens,
    )


def build_ai_service(
    settings: Settings,
    is_online: Callable[[], bool] = lambda: True,
    preferences: Callable[[], Preferences] | None = None,
) -> AIService:
    """Construit l'`AIService` à partir de la configuration (et des modèles choisis dans `preferences`)."""
    return AIService(
        ollama=OllamaProvider(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            timeout=settings.ollama_timeout_seconds,
            model_choice=(lambda: preferences().ollama_model) if preferences else None,
        ),
        anthropic=build_claude_provider(settings, preferences),
        allow_cloud_fallback=settings.ai_allow_cloud_fallback,
        is_online=is_online,
    )


def get_app_settings(request: Request) -> Settings:
    """Retourne la configuration avec laquelle l'application a été créée."""
    settings: Settings = request.app.state.settings
    return settings


def get_ai_service(request: Request) -> AIService:
    """Retourne l'instance créée au démarrage de l'application (voir `lifespan`)."""
    service: AIService = request.app.state.ai_service
    return service


def get_preferences(request: Request) -> PreferencesStore:
    prefs: PreferencesStore = request.app.state.preferences
    return prefs


def get_conversions(request: Request) -> ConversionService:
    """Conversions enregistrées (fichiers sources et tables obtenues)."""
    service: ConversionService = request.app.state.conversions
    return service


def get_tab(request: Request) -> TabFolder:
    """Dossier de données d'Atelier Tab (lecture des projets, écriture des tables envoyées)."""
    tab: TabFolder = request.app.state.tab
    return tab


def get_journal(request: Request) -> EventJournal:
    """Journal d'événements du nœud Atelier."""
    journal: EventJournal = request.app.state.journal
    return journal


def get_idempotency(request: Request) -> IdempotencyStore:
    """Réponses enregistrées par clé d'idempotence."""
    store: IdempotencyStore = request.app.state.idempotency
    return store


SettingsDep = Annotated[Settings, Depends(get_app_settings)]
AIServiceDep = Annotated[AIService, Depends(get_ai_service)]
PreferencesDep = Annotated[PreferencesStore, Depends(get_preferences)]
ConversionsDep = Annotated[ConversionService, Depends(get_conversions)]
TabDep = Annotated[TabFolder, Depends(get_tab)]
JournalDep = Annotated[EventJournal, Depends(get_journal)]
IdempotencyDep = Annotated[IdempotencyStore, Depends(get_idempotency)]
