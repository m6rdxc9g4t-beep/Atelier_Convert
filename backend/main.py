"""Point d'entrée de l'API Atelier Convert.

Lancer depuis le dossier backend/ :  uvicorn main:app --reload --port 8010
Documentation interactive :          http://127.0.0.1:8010/docs
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api.deps import build_ai_service
from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.frontend import FrontendFiles
from app.core.local_only import LocalOnlyMiddleware
from app.services.ai import AIProviderError
from app.services.atelier import AtelierError, EventJournal, IdempotencyStore
from app.services.atelier.errors import code_for, is_atelier_path, text_detail, validation_message
from app.services.convert.ocr import OcrEngine
from app.services.convert.pipeline import ConvertError, Limits
from app.services.convert.service import ConversionService
from app.services.convert.store import ConversionNotFound, ConversionStore
from app.services.convert.tab import TabError, TabFolder
from app.services.preferences import PreferencesStore


def create_app(settings: Settings | None = None) -> FastAPI:
    """Fabrique de l'application (permet d'injecter une configuration en test)."""
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        data_dir = settings.data_dir
        app.state.preferences = PreferencesStore(data_dir / "settings.json")
        app.state.ai_service = build_ai_service(
            settings,
            is_online=lambda: app.state.preferences.get().online_mode,
            preferences=app.state.preferences.get,
        )
        # Nœud Atelier (docs/SUITE.md §7) : journal d'événements, idempotence des écritures.
        app.state.journal = EventJournal(data_dir / "atelier_events.jsonl")
        app.state.idempotency = IdempotencyStore(data_dir / "atelier_idempotency.json")
        app.state.tab = TabFolder(settings.tab_dir)
        app.state.ocr = OcrEngine(
            executable=settings.convert_ocr_tesseract,
            languages=settings.convert_ocr_languages,
            dpi=settings.convert_ocr_dpi,
            timeout=settings.convert_ocr_timeout_seconds,
            tessdata=settings.convert_ocr_tessdata,
            enabled=settings.convert_ocr_enabled,
        )
        app.state.conversions = ConversionService(
            ConversionStore(data_dir, preview_rows=settings.convert_preview_rows),
            app.state.tab,
            app.state.journal,
            Limits(
                max_rows=settings.convert_max_rows,
                max_pdf_pages=settings.convert_max_pdf_pages,
                max_ocr_pages=settings.convert_ocr_max_pages,
                ocr=app.state.ocr,
            ),
        )
        yield
        await app.state.ai_service.aclose()

    app = FastAPI(title=settings.app_name, version=__version__, lifespan=lifespan)
    app.state.settings = settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Ajouté en dernier = exécuté en premier : un Host ou une Origin étrangers sont refusés avant tout le reste
    # (CORS compris). Protège contre le DNS rebinding et les écritures d'un autre site (docs/SUITE.md §5.1).
    app.add_middleware(LocalOnlyMiddleware, hosts=settings.allowed_hosts)

    def error(request: Request, status_code: int, detail: str) -> JSONResponse:
        """Erreur métier : `{detail}`, ou `{detail, code}` sur les routes du nœud Atelier (§7.5)."""
        body: dict[str, str] = {"detail": detail}
        if is_atelier_path(request.url.path):
            body["code"] = code_for(status_code)
        return JSONResponse(status_code=status_code, content=body)

    @app.exception_handler(AtelierError)
    async def atelier_error_handler(_: Request, exc: AtelierError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.body())

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        if not is_atelier_path(request.url.path):
            return await http_exception_handler(request, exc)  # type: ignore[return-value]
        body = {"detail": text_detail(exc.detail), "code": code_for(exc.status_code)}
        return JSONResponse(status_code=exc.status_code, content=body, headers=getattr(exc, "headers", None))

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        if not is_atelier_path(request.url.path):
            return await request_validation_exception_handler(request, exc)
        return JSONResponse(
            status_code=422, content={"detail": validation_message(list(exc.errors())), "code": "VALIDATION"}
        )

    @app.exception_handler(AIProviderError)
    async def ai_provider_error_handler(request: Request, exc: AIProviderError) -> JSONResponse:
        body: dict[str, str] = {"detail": exc.message, "provider": exc.provider}
        if is_atelier_path(request.url.path):
            body["code"] = "OFFLINE" if exc.status_code == 403 else code_for(exc.status_code)
        return JSONResponse(status_code=exc.status_code, content=body)

    @app.exception_handler(ConvertError)
    async def convert_error_handler(request: Request, exc: ConvertError) -> JSONResponse:
        return error(request, exc.status_code, exc.message)

    @app.exception_handler(ConversionNotFound)
    async def not_found_handler(request: Request, _: ConversionNotFound) -> JSONResponse:
        return error(request, 404, "Conversion introuvable (supprimée ?).")

    @app.exception_handler(TabError)
    async def tab_error_handler(request: Request, exc: TabError) -> JSONResponse:
        return error(request, exc.status_code, exc.message)

    app.include_router(api_router)

    # Interface compilée (frontend/dist) : l'application complète sur une seule adresse, sans Vite.
    # Montée après l'API : les routes /api/... restent prioritaires.
    dist = settings.frontend_dist
    if settings.serve_frontend and (dist / "index.html").is_file():
        app.mount("/", FrontendFiles(directory=dist, html=True), name="frontend")
    return app


app = create_app()
