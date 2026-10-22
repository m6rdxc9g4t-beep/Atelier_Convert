"""État des moteurs d'IA (Ollama local, Claude en ligne)."""

from fastapi import APIRouter

from app.api.deps import AIServiceDep
from app.schemas.ai import ProvidersResponse

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/providers", response_model=ProvidersResponse)
async def providers(service: AIServiceDep, refresh: bool = False) -> ProvidersResponse:
    """Disponibilité d'Ollama (serveur + modèle installé) et de Claude (mode en ligne + CLI connectée ou clé API).

    L'état de la CLI Claude est gardé 60 s ; `?refresh=true` le revérifie tout de suite (au plus toutes les 10 s).
    """
    return await service.providers_status(refresh)
