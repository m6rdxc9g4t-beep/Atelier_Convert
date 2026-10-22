"""Agrégation de toutes les routes sous le préfixe /api."""

from fastapi import APIRouter

from app.api.routes import ai, atelier, conversions, health, samples, settings

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(settings.router)
api_router.include_router(ai.router)
api_router.include_router(conversions.router)
api_router.include_router(samples.router)
api_router.include_router(atelier.router)
