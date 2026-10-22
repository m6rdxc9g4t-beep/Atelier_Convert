"""Service des conversions : lecture, relecture, colonnes, exports, envoi vers Atelier Tab, événements.

Les routes restent minces ; toute écriture passe par ici, qui publie l'événement correspondant au journal
du nœud Atelier (docs/SUITE.md §7.3). Méthodes synchrones (disque, calcul) : `asyncio.to_thread`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.schemas.atelier import AtelierTable, ConvertFileResult
from app.schemas.convert import (
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
        if conv.statement is not None:
            conv.statement = statement.summarize(
                Table(columns=conv.table_columns, rows=conv.table_rows),
                conv.statement.opening_balance,
                conv.statement.closing_balance,
                conv.statement.bank,
            )
        saved = self.store.save(conv)
        self._updated(saved, "columns")
        return saved

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


def safe_filename(name: str) -> str:
    """Nom de fichier sûr pour un téléchargement (accents gardés, séparateurs retirés)."""
    cleaned = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', " ", name).strip(" .")
    return " ".join(cleaned.split())[:120] or "conversion"
