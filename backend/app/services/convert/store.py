"""Historique des conversions, sur le disque de la machine (`data/`).

    data/conversions/<id>.json    conversion : options, colonnes, lignes, envois vers Tab
    data/sources/<id>.<ext>       fichier d'origine (relu quand les options changent)

Écritures atomiques (fichier temporaire puis remplacement) sous un verrou. Méthodes synchrones
(disque) : depuis une route, `asyncio.to_thread`.
"""

from __future__ import annotations

import os
import re
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path, PurePath

from pydantic import ValidationError

from app.schemas.convert import Conversion, ConversionSummary, ConversionView, ParseOptions, SourceInfo
from app.services.convert.table import Table

ID_PATTERN = re.compile(r"^[0-9a-f]{12}$")


def now_iso() -> str:
    return datetime.now(UTC).astimezone().isoformat(timespec="seconds")


def display_name(filename: str) -> str:
    """Nom proposé pour une conversion : nom du fichier sans extension, espaces normalisés."""
    stem = PurePath(filename).stem.replace("_", " ").strip()
    return " ".join(stem.split())[:200] or "Conversion"


class ConversionNotFound(Exception):
    pass


class ConversionStore:
    def __init__(self, data_dir: Path, preview_rows: int = 200) -> None:
        self.root = data_dir / "conversions"
        self.sources = data_dir / "sources"
        self.preview_rows = preview_rows
        self._lock = threading.Lock()

    # --- chemins ---------------------------------------------------------------------------------

    def _path(self, conversion_id: str) -> Path:
        if not ID_PATTERN.match(conversion_id):
            raise ConversionNotFound(conversion_id)
        return self.root / f"{conversion_id}.json"

    def _source(self, conversion_id: str) -> Path | None:
        if not ID_PATTERN.match(conversion_id) or not self.sources.is_dir():
            return None
        for p in self.sources.glob(f"{conversion_id}.*"):
            return p
        return None

    def _write(self, conversion: Conversion) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self._path(conversion.id)
        tmp = path.with_name(f".{path.name}.tmp")
        tmp.write_text(conversion.model_dump_json(), encoding="utf-8")
        os.replace(tmp, path)

    # --- lecture ---------------------------------------------------------------------------------

    def get(self, conversion_id: str) -> Conversion:
        path = self._path(conversion_id)
        try:
            return Conversion.model_validate_json(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ConversionNotFound(conversion_id) from exc
        except ValidationError as exc:
            raise ConversionNotFound(conversion_id) from exc

    def list(self) -> list[ConversionSummary]:
        """Conversions, les plus récentes d'abord (fichiers illisibles ignorés)."""
        if not self.root.is_dir():
            return []
        out: list[ConversionSummary] = []
        for path in self.root.glob("*.json"):
            try:
                conv = Conversion.model_validate_json(path.read_text(encoding="utf-8"))
            except (OSError, ValidationError):
                continue
            out.append(ConversionSummary.model_validate(conv.model_dump(include=set(ConversionSummary.model_fields))))
        return sorted(out, key=lambda c: c.updated_at, reverse=True)

    def source_bytes(self, conversion_id: str) -> bytes:
        path = self._source(conversion_id)
        if path is None:
            raise ConversionNotFound(conversion_id)
        return path.read_bytes()

    def view(self, conv: Conversion) -> ConversionView:
        """Ce que reçoit l'interface : aperçu limité des lignes."""
        data = conv.model_dump(exclude={"table_rows", "raw_text"})
        return ConversionView(
            **data,
            preview=conv.table_rows[: self.preview_rows],
            preview_truncated=len(conv.table_rows) > self.preview_rows,
            has_text=bool(conv.raw_text and conv.raw_text.strip()),
        )

    # --- écriture --------------------------------------------------------------------------------

    def create(self, data: bytes, info: SourceInfo, options: ParseOptions, table: Table) -> Conversion:
        conversion_id = uuid.uuid4().hex[:12]
        suffix = PurePath(info.filename).suffix.lower()
        suffix = suffix if re.fullmatch(r"\.[a-z0-9]{1,6}", suffix) else ".bin"
        stamp = now_iso()
        conv = _conversion(conversion_id, display_name(info.filename), stamp, stamp, info, options, table)
        with self._lock:
            self.sources.mkdir(parents=True, exist_ok=True)
            src = self.sources / f"{conversion_id}{suffix}"
            tmp = src.with_name(f".{src.name}.tmp")
            tmp.write_bytes(data)
            os.replace(tmp, src)
            self._write(conv)
        return conv

    def replace_table(self, conv: Conversion, info: SourceInfo, options: ParseOptions, table: Table) -> Conversion:
        """Nouvelle lecture du même fichier (options changées) : colonnes et lignes remplacées."""
        updated = _conversion(conv.id, conv.name, conv.created_at, now_iso(), info, options, table)
        updated.sent = conv.sent
        with self._lock:
            self._write(updated)
        return updated

    def save(self, conv: Conversion) -> Conversion:
        conv.updated_at = now_iso()
        with self._lock:
            self._write(conv)
        return conv

    def delete(self, conversion_id: str) -> None:
        path = self._path(conversion_id)
        with self._lock:
            if not path.exists():
                raise ConversionNotFound(conversion_id)
            path.unlink()
            src = self._source(conversion_id)
            if src is not None:
                src.unlink(missing_ok=True)


def _conversion(
    conversion_id: str,
    name: str,
    created: str,
    updated: str,
    info: SourceInfo,
    options: ParseOptions,
    table: Table,
) -> Conversion:
    return Conversion(
        id=conversion_id,
        name=name,
        created_at=created,
        updated_at=updated,
        source=info,
        detected=table.detected,
        rows=len(table.rows),
        columns=len(table.included),
        statement=table.statement,
        options=options,
        warnings=table.warnings,
        table_columns=table.columns,
        table_rows=table.rows,
        raw_text=table.raw_text,
    )
