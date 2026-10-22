"""Schémas des conversions. Miroir TypeScript : frontend/src/types/convert.ts.

Une conversion = un fichier source (PDF, CSV, TXT, XLSX, OFX, QIF, JSON) + des options de lecture
→ une table typée (colonnes + lignes) que l'on exporte (CSV, TXT, XLSX, `atelier-table/1`)
ou que l'on envoie dans Atelier Tab.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

ColumnType = Literal["text", "number", "currency", "date", "boolean"]
"""Type d'une colonne : texte, nombre, montant (devise), date (AAAA-MM-JJ), case à cocher."""

SourceKind = Literal["pdf", "csv", "txt", "xlsx", "xls", "ofx", "qif", "json"]

PdfMode = Literal["auto", "statement", "tables", "text"]
"""Lecture d'un PDF : relevé bancaire (lignes datées + montants), tableaux détectés, ou texte brut ligne à ligne."""

Profile = Literal["auto", "statement", "raw"]
"""Mise en forme : `statement` = colonnes normalisées d'un relevé (Date, Libellé, Débit, Crédit, Montant, Solde)."""

Role = Literal["date", "value_date", "label", "debit", "credit", "amount", "balance", "reference", "category"]
"""Rôle d'une colonne dans un relevé bancaire."""

ExportFormat = Literal["csv-fr", "csv", "txt", "xlsx", "json"]
"""csv-fr : « ; », virgule décimale, JJ/MM/AAAA, UTF-8 avec BOM (Excel FR) ; csv : « , », point, ISO ;
txt : tabulations ; json : table d'échange `atelier-table/1`."""

CellValue = str | float | int | bool | None


class ParseOptions(BaseModel):
    """Options de lecture. `None` = détection automatique."""

    pdf_mode: PdfMode = "auto"
    profile: Profile = "auto"
    delimiter: str | None = Field(default=None, max_length=1, description="Séparateur (CSV / TXT), ex. « ; ».")
    encoding: str | None = Field(default=None, max_length=40, description="Encodage (utf-8, cp1252, latin-1…).")
    header: bool | None = Field(default=None, description="Première ligne utile = en-tête.")
    skip_rows: int = Field(default=0, ge=0, le=10_000, description="Lignes ignorées au début (préambule).")
    sheet: str | None = Field(default=None, max_length=200, description="Feuille d'un classeur Excel.")
    decimal: Literal["auto", ",", "."] = "auto"
    date_order: Literal["auto", "dmy", "mdy", "ymd"] = "auto"
    pages: str | None = Field(default=None, max_length=100, description="Pages d'un PDF : « 1-3,5 ».")
    year: int | None = Field(default=None, ge=1900, le=2200, description="Année des dates sans année (relevé).")

    @field_validator("delimiter")
    @classmethod
    def _delimiter(cls, value: str | None) -> str | None:
        if value is not None and value in {"\n", "\r", '"'}:
            raise ValueError("Séparateur refusé.")
        return value or None


class Column(BaseModel):
    """Colonne de la table obtenue."""

    key: str = Field(min_length=1, max_length=200, description="Clé snake_case sans accent, unique.")
    label: str = Field(min_length=1, max_length=200)
    type: ColumnType = "text"
    include: bool = Field(default=True, description="Exportée et envoyée (sinon gardée de côté).")
    role: Role | None = None


class StatementSummary(BaseModel):
    """Synthèse d'un relevé bancaire (calculée sur les lignes obtenues)."""

    transactions: int
    start: str | None = None
    end: str | None = None
    total_debit: float = 0.0
    total_credit: float = 0.0
    opening_balance: float | None = Field(default=None, description="Solde initial lu dans le document.")
    closing_balance: float | None = Field(default=None, description="Solde final lu dans le document.")
    balance_check: Literal["ok", "mismatch", "unknown"] = "unknown"
    balance_gap: float | None = Field(default=None, description="Écart : solde final − (initial + crédits − débits).")
    bank: str | None = Field(default=None, description="Banque reconnue dans le document, si possible.")


class SourceInfo(BaseModel):
    """Fichier d'origine."""

    filename: str
    kind: SourceKind
    size: int
    sha256: str
    pages: int | None = None
    encoding: str | None = None
    delimiter: str | None = None
    sheets: list[str] = Field(default_factory=list)


class TabSend(BaseModel):
    """Envoi d'une conversion dans Atelier Tab."""

    at: str
    table_id: str
    table_name: str
    project_id: str
    project_name: str
    rows: int


class ConversionSummary(BaseModel):
    """Entrée de l'historique."""

    id: str
    name: str
    created_at: str
    updated_at: str
    source: SourceInfo
    detected: str = Field(description="Ce qui a été reconnu (« Relevé bancaire · 42 opérations »).")
    rows: int
    columns: int
    statement: StatementSummary | None = None
    sent: list[TabSend] = Field(default_factory=list)


class Conversion(ConversionSummary):
    """Conversion complète (lignes comprises)."""

    options: ParseOptions
    warnings: list[str] = Field(default_factory=list)
    table_columns: list[Column]
    table_rows: list[dict[str, CellValue]]
    raw_text: str | None = Field(default=None, description="Texte extrait (PDF / TXT), pour « Structurer avec l'IA ».")


class ConversionView(ConversionSummary):
    """Ce que reçoit l'interface : colonnes, aperçu des lignes et avertissements."""

    options: ParseOptions
    warnings: list[str]
    table_columns: list[Column]
    preview: list[dict[str, CellValue]]
    preview_truncated: bool
    has_text: bool = Field(description="Un texte extrait est disponible pour « Structurer avec l'IA ».")


class ColumnsUpdate(BaseModel):
    """Libellés, types, ordre et inclusion des colonnes (même ensemble de clés, ordre libre)."""

    columns: list[Column] = Field(min_length=1, max_length=500)


class RenameRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class TabProject(BaseModel):
    id: str
    name: str
    workspace: str
    tables: int


class TabStatus(BaseModel):
    """Dossier de données d'Atelier Tab vu par Convert."""

    found: bool
    directory: str
    projects: list[TabProject] = Field(default_factory=list)
    detail: str | None = None


class SendToTabRequest(BaseModel):
    """Envoi dans Atelier Tab : une nouvelle table dans le projet choisi."""

    project_id: str = Field(min_length=1, max_length=200)
    table_name: str | None = Field(
        default=None, max_length=200, description="Nom de la table (défaut : la conversion)."
    )


class SendToTabResult(BaseModel):
    table_id: str
    table_name: str
    project_id: str
    project_name: str
    rows: int
    columns: int
    file: str = Field(description="Fichier écrit (chemin relatif au dossier d'Atelier Tab).")


class StructureRequest(BaseModel):
    """« Structurer avec l'IA » : le texte extrait part vers le moteur choisi, qui propose colonnes et lignes."""

    provider: Literal["auto", "ollama", "anthropic"] = "auto"
    instructions: str | None = Field(default=None, max_length=2000, description="Précision de l'utilisateur.")


class StructureResult(BaseModel):
    provider: Literal["ollama", "anthropic"]
    model: str
    sent_lines: int
    sent_chars: int
    conversion: ConversionView


class SampleInfo(BaseModel):
    name: str
    label: str
    description: str


def cell(value: Any) -> CellValue:
    """Valeur de cellule sûre (types JSON simples)."""
    if value is None or isinstance(value, str | bool | int | float):
        return value
    return str(value)
