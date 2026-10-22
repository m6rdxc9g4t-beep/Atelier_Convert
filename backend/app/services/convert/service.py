"""Service des conversions : lecture, relecture, colonnes, exports, envoi vers Atelier Tab, événements.

Les routes restent minces ; toute écriture passe par ici, qui publie l'événement correspondant au journal
du nœud Atelier (docs/SUITE.md §7.3). Méthodes synchrones (disque, calcul) : `asyncio.to_thread`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.schemas.atelier import AtelierTable, ConvertFileResult
from app.schemas.convert import (
    CellEdit,
    CellValue,
    Column,
    Conversion,
    ExportFormat,
    ParseOptions,
    SendToTabResult,
    TabSend,
)
from app.services.atelier.journal import EventJournal
from app.services.convert import statement
from app.services.convert.pipeline import ConvertError, Limits, convert
from app.services.convert.store import ConversionStore, now_iso
from app.services.convert.tab import TabFolder
from app.services.convert.table import Table
from app.services.convert.values import coerce, snake_key
from app.services.convert.writers import EXTENSION, MEDIA_TYPES, to_atelier_table, to_delimited, to_xlsx


@dataclass
class Export:
    content: bytes
    filename: str
    media_type: str


class ConversionService:
    def __init__(self, store: ConversionStore, tab: TabFolder, journal: EventJournal, limits: Limits) -> None:
        self.store = store
        self.tab = tab
        self.journal = journal
        self.limits = limits

    # --- lecture d'un fichier ----------------------------------------------------------------------

    def create(self, data: bytes, filename: str, options: ParseOptions, origin: str = "interface") -> Conversion:
        info, table = convert(data, filename, options, self.limits)
        conv = self.store.create(data, info, options, table)
        self.journal.emit(
            "convert.conversion.created",
            conv.id,
            conv.name,
            {
                "name": conv.name,
                "format": info.kind,
                "rows": conv.rows,
                "columns": conv.columns,
                "statement": table.statement is not None,
                "ocr": info.ocr,
                "origin": origin,
            },
        )
        return conv

    def reparse(self, conversion_id: str, options: ParseOptions) -> Conversion:
        """Relit le fichier d'origine avec de nouvelles options (colonnes recalculées)."""
        conv = self.store.get(conversion_id)
        data = self.store.source_bytes(conversion_id)
        info, table = convert(data, conv.source.filename, options, self.limits)
        updated = self.store.replace_table(conv, info, options, table)
        self._updated(updated, "options")
        return updated

    def apply_table(self, conversion_id: str, table: Table, reason: str) -> Conversion:
        """Remplace la table (IA) en gardant le fichier et les options."""
        conv = self.store.get(conversion_id)
        updated = self.store.replace_table(conv, conv.source, conv.options, table)
        if conv.raw_text and not updated.raw_text:
            updated.raw_text = conv.raw_text
            self.store.save(updated)
        self._updated(updated, reason)
        return updated

    def _updated(self, conv: Conversion, reason: str) -> None:
        self.journal.emit(
            "convert.conversion.updated",
            conv.id,
            conv.name,
            {"rows": conv.rows, "columns": conv.columns, "reason": reason},
        )

    # --- colonnes et nom ---------------------------------------------------------------------------

    def update_columns(self, conversion_id: str, columns: list[Column]) -> Conversion:
        """Libellés, types, ordre et inclusion. Un changement de type reconvertit les valeurs de la colonne."""
        conv = self.store.get(conversion_id)
        current = {c.key: c for c in conv.table_columns}
        if {c.key for c in columns} != set(current) or len(columns) != len(current):
            raise ConvertError(
                "Les colonnes envoyées ne correspondent pas à celles de la conversion : rechargez la page.", 409
            )
        labels = [c.label.strip() for c in columns if c.include]
        if any(not label for label in labels):
            raise ConvertError("Chaque colonne incluse doit avoir un nom.")
        if len({label.lower() for label in labels}) != len(labels):
            raise ConvertError("Deux colonnes incluses portent le même nom : renommez l'une d'elles.")
        for col in columns:
            before = current[col.key]
            if col.type != before.type:
                for row in conv.table_rows:
                    row[col.key] = coerce(row.get(col.key), col.type, conv.options.decimal, conv.options.date_order)
        conv.table_columns = [c.model_copy(update={"label": c.label.strip()}) for c in columns]
        conv.columns = len([c for c in columns if c.include])
        _resummarize(conv)
        saved = self.store.save(conv)
        self._updated(saved, "columns")
        return saved

    # --- cellules ----------------------------------------------------------------------------------

    def edit_cells(self, conversion_id: str, edits: list[CellEdit]) -> tuple[Conversion, list[int]]:
        """Corrige des cellules (libellé, date, montant…) ; renvoie la conversion et les lignes touchées.

        La valeur saisie est convertie dans le type de la colonne ; une saisie qui ne s'y convertit pas est
        refusée (422) plutôt que gardée en texte. Dans un relevé, Débit / Crédit restent positifs et Montant
        (signé) les suit — et inversement. La valeur lue dans le fichier est gardée dans `edited` (« ligne:clé »).
        """
        conv = self.store.get(conversion_id)
        columns = {c.key: c for c in conv.table_columns}
        by_role = {c.role: c.key for c in conv.table_columns if c.role in ("debit", "credit", "amount")}
        order = "dmy" if conv.options.date_order == "auto" else conv.options.date_order
        changed: dict[int, str] = {}  # ligne → « debit_credit » ou « amount » : ce qui commande les autres
        for edit in edits:
            if edit.row >= len(conv.table_rows):
                raise ConvertError("Cette ligne n'existe plus : rechargez la page.", 409)
            col = columns.get(edit.key)
            if col is None:
                raise ConvertError("Cette colonne n'existe plus : rechargez la page.", 409)
            value = entered_value(edit.value, col, conv.options.decimal, order)
            if col.role in ("debit", "credit") and isinstance(value, float):
                value = abs(value)
            _set_cell(conv, edit.row, edit.key, value)
            if col.role in ("debit", "credit"):
                changed[edit.row] = "debit_credit"
            elif col.role == "amount":
                changed.setdefault(edit.row, "amount")
        for row, driver in changed.items():
            _reconcile(conv, row, by_role, driver)
        if len(conv.edited) > MAX_EDITED:
            raise ConvertError(f"Trop de cellules corrigées (plus de {MAX_EDITED}) : corrigez plutôt le fichier.")
        _resummarize(conv)
        saved = self.store.save(conv)
        self._updated(saved, "cells")
        return saved, sorted({e.row for e in edits})

    def rename(self, conversion_id: str, name: str) -> Conversion:
        conv = self.store.get(conversion_id)
        conv.name = " ".join(name.split())[:200]
        saved = self.store.save(conv)
        self._updated(saved, "rename")
        return saved

    def delete(self, conversion_id: str) -> None:
        conv = self.store.get(conversion_id)
        self.store.delete(conversion_id)
        self.journal.emit("convert.conversion.deleted", conv.id, conv.name, {})

    # --- sorties -----------------------------------------------------------------------------------

    def export(self, conversion_id: str, fmt: ExportFormat) -> Export:
        conv = self.store.get(conversion_id)
        base = safe_filename(conv.name)
        if fmt == "xlsx":
            content = to_xlsx(conv.table_columns, conv.table_rows, conv.name)
        elif fmt == "json":
            import json

            table = to_atelier_table(snake_key(conv.name, "conversion"), conv.name, conv.table_columns, conv.table_rows)
            content = json.dumps(table, ensure_ascii=False, indent=2).encode("utf-8")
        else:
            content = to_delimited(conv.table_columns, conv.table_rows, fmt)
        return Export(content=content, filename=f"{base}.{EXTENSION[fmt]}", media_type=MEDIA_TYPES[fmt])

    def table_page(self, conversion_id: str, offset: int, limit: int) -> AtelierTable:
        conv = self.store.get(conversion_id)
        rows = conv.table_rows[offset : offset + limit]
        table = to_atelier_table(snake_key(conv.name, "conversion"), conv.name, conv.table_columns, rows)
        table["total"] = len(conv.table_rows)
        table["truncated"] = offset + len(rows) < len(conv.table_rows) or offset > 0
        return AtelierTable.model_validate(table)

    def send_to_tab(self, conversion_id: str, project_id: str, table_name: str | None) -> SendToTabResult:
        conv = self.store.get(conversion_id)
        name = " ".join((table_name or conv.name).split())[:200] or conv.name
        table_id, project_name, relative = self.tab.write_table(project_id, name, conv.table_columns, conv.table_rows)
        conv.sent.append(
            TabSend(
                at=now_iso(),
                table_id=table_id,
                table_name=name,
                project_id=project_id,
                project_name=project_name,
                rows=len(conv.table_rows),
            )
        )
        self.store.save(conv)
        self.journal.emit(
            "convert.conversion.sent_to_tab",
            conv.id,
            conv.name,
            {"table_id": table_id, "table_name": name, "project_id": project_id, "rows": len(conv.table_rows)},
        )
        return SendToTabResult(
            table_id=table_id,
            table_name=name,
            project_id=project_id,
            project_name=project_name,
            rows=len(conv.table_rows),
            columns=len([c for c in conv.table_columns if c.include]),
            file=relative,
        )

    @staticmethod
    def result(conv: Conversion) -> ConvertFileResult:
        return ConvertFileResult(
            conversion_id=conv.id,
            name=conv.name,
            detected=conv.detected,
            rows=conv.rows,
            columns=conv.columns,
            warnings=conv.warnings,
        )


MAX_EDITED = 20_000
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_EXPECTED = {
    "number": "un nombre",
    "currency": "un montant (ex. 21,73)",
    "date": "une date (JJ/MM/AAAA)",
    "boolean": "oui ou non",
}


def entered_value(value: CellValue, col: Column, decimal: str, order: str) -> CellValue:
    """Valeur saisie convertie dans le type de la colonne ; vide → None ; saisie incompatible → ConvertError."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if col.type == "text":
        return " ".join(str(value).split())
    if col.type in ("number", "currency") and isinstance(value, bool):
        raise ConvertError(f"« {value} » n'est pas {_EXPECTED[col.type]} pour la colonne {col.label}.")
    out = coerce(value, col.type, decimal, order)
    if not _converted(out, col.type):
        shown = str(out) if len(str(out)) <= 40 else str(out)[:39] + "…"
        raise ConvertError(f"« {shown} » n'est pas {_EXPECTED[col.type]} pour la colonne {col.label}.")
    if isinstance(out, float):
        out = round(out, 2) if col.type == "currency" else out
    return out


def _converted(value: CellValue, type_: str) -> bool:
    """Vrai si `coerce` a bien converti la valeur dans le type (sinon il l'a gardée en texte)."""
    if type_ in ("number", "currency"):
        return isinstance(value, int | float) and not isinstance(value, bool)
    if type_ == "date":
        return isinstance(value, str) and ISO_DATE.match(value) is not None
    if type_ == "boolean":
        return isinstance(value, bool)
    return True


def _set_cell(conv: Conversion, row: int, key: str, value: CellValue) -> None:
    """Écrit une cellule en gardant la valeur lue dans le fichier ; revenir à celle-ci efface la marque."""
    current = conv.table_rows[row].get(key)
    if current == value and type(current) is type(value):
        return
    ref = f"{row}:{key}"
    if ref not in conv.edited:
        conv.edited[ref] = current
    conv.table_rows[row][key] = value
    original = conv.edited[ref]
    if original == value and type(original) is type(value):
        del conv.edited[ref]


def _reconcile(conv: Conversion, row: int, by_role: dict[object, str], driver: str) -> None:
    """Relevé : Montant = Crédit − Débit, ou Débit / Crédit déduits du Montant saisi."""
    values = conv.table_rows[row]

    def num(key: str | None) -> float | None:
        v = values.get(key) if key else None
        return float(v) if isinstance(v, int | float) and not isinstance(v, bool) else None

    debit, credit, amount = by_role.get("debit"), by_role.get("credit"), by_role.get("amount")
    if driver == "debit_credit" and amount and (debit or credit):
        d, c = num(debit), num(credit)
        _set_cell(conv, row, amount, None if d is None and c is None else round((c or 0.0) - (d or 0.0), 2))
    elif driver == "amount" and amount and debit and credit:
        a = num(amount)
        _set_cell(conv, row, debit, round(-a, 2) if a is not None and a < 0 else None)
        _set_cell(conv, row, credit, round(a, 2) if a is not None and a > 0 else None)


def _resummarize(conv: Conversion) -> None:
    """Synthèse du relevé (totaux, contrôle des soldes) recalculée sur les lignes."""
    if conv.statement is not None:
        conv.statement = statement.summarize(
            Table(columns=conv.table_columns, rows=conv.table_rows),
            conv.statement.opening_balance,
            conv.statement.closing_balance,
            conv.statement.bank,
        )


def safe_filename(name: str) -> str:
    """Nom de fichier sûr pour un téléchargement (accents gardés, séparateurs retirés)."""
    cleaned = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', " ", name).strip(" .")
    return " ".join(cleaned.split())[:120] or "conversion"
