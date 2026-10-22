"""Configuration de l'application, lue depuis les variables d'environnement et `.env`."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Paramètres globaux. Chaque champ correspond à une variable d'environnement en MAJUSCULES."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", populate_by_name=True)

    app_name: str = "Atelier Convert API"
    app_env: Literal["development", "test", "production"] = "development"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5176"])
    # Garde « requêtes locales » (docs/SUITE.md §5.1, app/core/local_only.py) : hôtes acceptés en plus de
    # 127.0.0.1, localhost et [::1]. Liste séparée par des virgules : ALLOWED_HOSTS=convert.local,autre.local
    allowed_hosts: Annotated[list[str], NoDecode] = Field(default_factory=list)

    # Ollama (local)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    ollama_timeout_seconds: float = 120.0

    # Claude : "cli" = CLI Claude Code (abonnement claude.ai), "api" = API Anthropic (clé Console)
    claude_mode: Literal["cli", "api"] = "cli"
    # Exécutable : CLAUDE_CLI (docs/SUITE.md §5.3) ou CLAUDE_CLI_PATH ;
    # sinon PATH, ~/.local/bin, /opt/homebrew/bin, /usr/local/bin
    claude_cli_path: str = Field(default="claude", validation_alias=AliasChoices("claude_cli", "claude_cli_path"))
    # Modèle par défaut ; l'utilisateur choisit Sonnet / Opus / Haiku dans l'interface (préférences)
    claude_cli_model: str = "sonnet"
    claude_cli_timeout_seconds: float = 180.0

    # Claude (API Anthropic, si claude_mode = "api")
    anthropic_api_key: SecretStr | None = None
    anthropic_model: str = "claude-sonnet-5-5"
    anthropic_max_tokens: int = 4096

    # Routage IA
    ai_allow_cloud_fallback: bool = False
    # Texte extrait envoyé à l'IA pour « Structurer avec l'IA » (lignes et caractères au plus).
    ai_max_lines: int = Field(default=200, ge=10, le=2000)
    ai_max_chars: int = Field(default=24_000, ge=1000, le=200_000)

    # Données locales : conversions (JSON), fichiers sources, préférences (tout reste sur la machine)
    data_dir: Path = Path("data")
    max_upload_mb: int = 50
    # Interface compilée (npm run build) servie par l'API : une seule adresse, utilisée par l'application de bureau.
    frontend_dist: Path = Path(__file__).resolve().parents[3] / "frontend" / "dist"
    serve_frontend: bool = True
    # Fichiers d'exemple livrés avec le dépôt (bouton « Essayer avec un exemple »)
    samples_dir: Path = Path(__file__).resolve().parents[3] / "samples"

    # Conversion
    convert_max_rows: int = Field(default=200_000, ge=100, le=5_000_000)
    convert_max_pdf_pages: int = Field(default=300, ge=1, le=5000)
    convert_preview_rows: int = Field(default=200, ge=10, le=5000)

    # Reconnaissance de texte (OCR) des PDF scannés et des images : Tesseract, sur la machine.
    convert_ocr_enabled: bool = True
    # Exécutable : chemin absolu, ou « tesseract » (PATH, puis Homebrew, /usr/local/bin, Program Files).
    convert_ocr_tesseract: str = "tesseract"
    # Dossier des langues (TESSDATA_PREFIX) si Tesseract ne trouve pas les siennes ; vide = celui de Tesseract.
    convert_ocr_tessdata: Path | None = None
    convert_ocr_languages: str = "fra+eng"
    convert_ocr_dpi: int = Field(default=300, ge=100, le=600)
    convert_ocr_max_pages: int = Field(default=50, ge=1, le=1000)
    convert_ocr_timeout_seconds: float = Field(default=120.0, ge=5.0, le=1800.0)

    # Suite Atelier (docs/SUITE.md §4.4) : dossier de données d'Atelier Tab, où « Envoyer dans Atelier Tab »
    # écrit la table (tables/<id>.json). Tab surveille ce dossier et l'affiche aussitôt.
    atelier_tab_data_dir: Path = Path("~/Atelier_Tab")

    @field_validator("allowed_hosts", mode="before")
    @classmethod
    def _split_hosts(cls, value: Any) -> Any:
        """`ALLOWED_HOSTS` : « a,b » ou liste JSON « ["a","b"] »."""
        if isinstance(value, str):
            text = value.strip()
            if text.startswith("["):
                return json.loads(text)
            return [h.strip() for h in text.split(",") if h.strip()]
        return value

    @field_validator("convert_ocr_tessdata", mode="before")
    @classmethod
    def _empty_path(cls, value: Any) -> Any:
        """`CONVERT_OCR_TESSDATA=` (vide) = dossier de Tesseract, jamais le dossier courant."""
        return None if isinstance(value, str) and not value.strip() else value

    @property
    def anthropic_configured(self) -> bool:
        """Vrai si une clé API Anthropic non vide est disponible."""
        return bool(self.anthropic_api_key and self.anthropic_api_key.get_secret_value().strip())

    @property
    def tab_dir(self) -> Path:
        """Dossier de données d'Atelier Tab, `~` développé."""
        return self.atelier_tab_data_dir.expanduser()


@lru_cache
def get_settings() -> Settings:
    """Retourne l'instance unique (mise en cache) des paramètres."""
    return Settings()
