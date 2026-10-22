"""Nœud Atelier (docs/SUITE.md §7, contrat `atelier-node/1`) : manifeste, table d'échange, événements.

Ces schémas décrivent ce qu'Atelier Nexus peut enchaîner dans un workflow ; les `input_schema` et
`data_schema` du manifeste sont générés à partir d'eux (JSON Schema draft 2020-12, propriétés en snake_case).
"""

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.convert import ParseOptions

CONTRACT = "atelier-node/1"
TABLE_FORMAT = "atelier-table/1"
ACTION_ID_PATTERN = r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$"
EVENT_TYPE_PATTERN = r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$"
CONVERSION_ID_PATTERN = r"^[0-9a-f]{12}$"

TABLE_DEFAULT_LIMIT = 1000
TABLE_MAX_LIMIT = 5000
EVENTS_DEFAULT_LIMIT = 100
EVENTS_MAX_LIMIT = 500
CONVERT_MAX_BASE64 = 70_000_000  # ≈ 50 Mo de fichier

AtelierType = Literal["string", "number", "date", "datetime", "boolean"]


# --- Table d'échange `atelier-table/1` (§7.2) -------------------------------------------------------


class AtelierColumn(BaseModel):
    key: str = Field(min_length=1, max_length=200)
    label: str = Field(min_length=1, max_length=200)
    type: AtelierType


class AtelierTable(BaseModel):
    format: Literal["atelier-table/1"] = TABLE_FORMAT
    name: str = Field(min_length=1, max_length=200)
    label: str | None = Field(default=None, max_length=200)
    columns: list[AtelierColumn] = Field(min_length=1)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    total: int | None = Field(default=None, ge=0)
    truncated: bool = False

    @field_validator("columns")
    @classmethod
    def _unique_keys(cls, columns: list[AtelierColumn]) -> list[AtelierColumn]:
        keys = [c.key for c in columns]
        if len(set(keys)) != len(keys):
            raise ValueError("Clés de colonnes en double.")
        return columns


# --- Entrées des actions ----------------------------------------------------------------------------


class NoInput(BaseModel):
    """Action sans paramètre."""


class ConversionIdInput(BaseModel):
    conversion_id: str = Field(
        pattern=CONVERSION_ID_PATTERN, description="Identifiant de la conversion (12 caractères hexadécimaux)."
    )


class TablePageInput(ConversionIdInput):
    offset: int = Field(default=0, ge=0, description="Première ligne (0 = début).")
    limit: int = Field(default=TABLE_DEFAULT_LIMIT, ge=1, le=TABLE_MAX_LIMIT, description="Nombre de lignes.")


class ConvertFileInput(BaseModel):
    """Convertit un fichier transmis en base64 (jamais un chemin : le nœud ne lit pas le disque à la demande)."""

    filename: str = Field(min_length=1, max_length=255, description="Nom du fichier, avec son extension (.pdf, .csv…).")
    content_base64: str = Field(
        min_length=1, max_length=CONVERT_MAX_BASE64, description="Contenu du fichier en base64."
    )
    options: ParseOptions = Field(
        default_factory=ParseOptions, description="Options de lecture (détection automatique par défaut)."
    )

    @field_validator("filename")
    @classmethod
    def _filename(cls, value: str) -> str:
        name = value.replace("\\", "/").rsplit("/", 1)[-1].strip()
        if not name or any(ord(c) < 32 for c in name):
            raise ValueError("Nom de fichier invalide.")
        return name


class SendToTabInput(ConversionIdInput):
    project_id: str = Field(
        min_length=1, max_length=200, description="Projet d'Atelier Tab (identifiant, ex. « proj_… »)."
    )
    table_name: str | None = Field(default=None, max_length=200, description="Nom de la nouvelle table.")


class ConvertFileResult(BaseModel):
    conversion_id: str
    name: str
    detected: str
    rows: int
    columns: int
    warnings: list[str]


# --- Manifeste (§7.1) -----------------------------------------------------------------------------


class ManifestHttp(BaseModel):
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    path: str


class ManifestOutput(BaseModel):
    format: Literal["atelier-table/1", "json"]
    schema_: dict[str, Any] = Field(alias="schema", default_factory=dict)

    model_config = {"populate_by_name": True}


class ManifestAction(BaseModel):
    id: str = Field(pattern=ACTION_ID_PATTERN)
    label: str
    description: str
    kind: Literal["read", "write", "destructive"]
    http: ManifestHttp | None = None
    mcp_tool: str | None = None
    input_schema: dict[str, Any]
    output: ManifestOutput
    idempotency: Literal["header", "field", "natural", "none"]

    @model_validator(mode="after")
    def _one_transport(self) -> "ManifestAction":
        if (self.http is None) == (self.mcp_tool is None):
            raise ValueError("Une action a exactement un transport : `http` ou `mcp_tool`.")
        return self


class ManifestEvent(BaseModel):
    type: str = Field(pattern=EVENT_TYPE_PATTERN)
    label: str
    data_schema: dict[str, Any]


class AtelierManifest(BaseModel):
    contract: Literal["atelier-node/1"] = CONTRACT
    app: Literal["convert"] = "convert"
    name: str
    version: str
    transport: Literal["http", "mcp"]
    actions: list[ManifestAction]
    events: list[ManifestEvent]


# --- Événements (§7.3) ----------------------------------------------------------------------------


class EventSubject(BaseModel):
    kind: str
    id: str
    label: str | None = None


class AtelierEvent(BaseModel):
    seq: int = Field(ge=1)
    type: str
    at: str
    subject: EventSubject
    data: dict[str, Any] = Field(default_factory=dict)


class AtelierEventsPage(BaseModel):
    events: list[AtelierEvent]
    next: int
    oldest: int
    gap: bool = False


# `data` des événements : identifiants, libellés, formats et nombres — jamais de lignes ni de chemin.


class ConversionCreatedData(BaseModel):
    name: str
    format: str = Field(description="Format du fichier source (pdf, csv, txt, xlsx, xls, ofx, qif, json).")
    rows: int
    columns: int
    statement: bool = Field(description="Relevé bancaire reconnu (colonnes normalisées).")
    ocr: bool = Field(default=False, description="Texte obtenu par reconnaissance de caractères (OCR).")
    origin: Literal["interface", "workflow", "ai"] = "interface"


class ConversionUpdatedData(BaseModel):
    rows: int
    columns: int
    reason: Literal["options", "columns", "ai", "rename"]


class ConversionSentData(BaseModel):
    table_id: str
    table_name: str
    project_id: str
    rows: int


class ConversionDeletedData(BaseModel):
    pass


EVENT_TYPES: dict[str, tuple[str, str, type[BaseModel]]] = {
    "convert.conversion.created": ("Conversion créée", "conversion", ConversionCreatedData),
    "convert.conversion.updated": ("Conversion modifiée", "conversion", ConversionUpdatedData),
    "convert.conversion.sent_to_tab": ("Table envoyée dans Atelier Tab", "conversion", ConversionSentData),
    "convert.conversion.deleted": ("Conversion supprimée", "conversion", ConversionDeletedData),
}
"""Types d'événements publiés par Atelier Convert : libellé, `subject.kind`, schéma de `data`."""
