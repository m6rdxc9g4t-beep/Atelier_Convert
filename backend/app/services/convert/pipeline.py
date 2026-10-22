"""Chaîne de conversion : un fichier + des options → une table typée (et ce qui a été reconnu).

`convert` choisit le lecteur selon le type de fichier, puis applique la mise en forme « relevé bancaire »
quand elle s'applique (`profile` = auto) ou quand elle est demandée (`statement`).
Fonction pure et synchrone (calcul et lecture en mémoire) : depuis une route, `asyncio.to_thread`.
"""

from __future__ import annotations

import hashlib
import io
import json
from dataclasses import dataclass
from pathlib import PurePath
from typing import Any

from app.schemas.convert import Column, ParseOptions, SourceInfo, SourceKind
from app.services.convert import statement
from app.services.convert.bankfiles import read_ofx, read_qif
from app.services.convert.pdf import PdfError, merge_tables, read_pdf
from app.services.convert.table import Table, rows_to_table
from app.services.convert.text import DELIMITER_NAMES, decode, read_delimited, read_lines, read_spaced, sniff_delimiter
from app.services.convert.values import clean_label, coerce, infer_type, unique_keys

EXTENSIONS: dict[str, SourceKind] = {
    ".pdf": "pdf",
    ".csv": "csv",
    ".tsv": "csv",
    ".txt": "txt",
    ".prn": "txt",
    ".dat": "txt",
    ".xlsx": "xlsx",
    ".xlsm": "xlsx",
    ".xls": "xls",
    ".ofx": "ofx",
    ".qfx": "ofx",
    ".qif": "qif",
    ".json": "json",
}

ACCEPTED = ", ".join(sorted({e.lstrip(".").upper() for e in EXTENSIONS}))


class ConvertError(Exception):
    """Fichier refusé ou illisible (message en français pour l'utilisateur)."""

    def __init__(self, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class Limits:
    max_rows: int = 200_000
    max_pdf_pages: int = 300


def detect_kind(filename: str, data: bytes) -> SourceKind:
    """Type de fichier d'après le contenu (signature) puis l'extension."""
    head = data[:2048].lstrip()
    if data.startswith(b"%PDF"):
        return "pdf"
    if data.startswith(b"PK\x03\x04") and PurePath(filename).suffix.lower() in {".xlsx", ".xlsm", ""}:
        return "xlsx"
    if data.startswith(b"\xd0\xcf\x11\xe0"):
        return "xls"
    upper = head.upper()
    if b"OFXHEADER" in upper or b"<OFX>" in upper:
        return "ofx"
    if head.startswith(b"!TYPE") or head.startswith(b"!Type") or head.startswith(b"!Account"):
        return "qif"
    kind = EXTENSIONS.get(PurePath(filename).suffix.lower())
    if kind is None:
        if head[:1] in {b"[", b"{"}:
            return "json"
        raise ConvertError(f"Format non pris en charge : « {filename} ». Formats acceptés : {ACCEPTED}.", 415)
    return kind


def convert(
    data: bytes, filename: str, options: ParseOptions, limits: Limits | None = None
) -> tuple[SourceInfo, Table]:
    """Lit le fichier et renvoie sa description et la table obtenue."""
    limits = limits or Limits()
    if not data:
        raise ConvertError("Le fichier est vide.")
    kind = detect_kind(filename, data)
    info = SourceInfo(filename=filename, kind=kind, size=len(data), sha256=hashlib.sha256(data).hexdigest())

    if kind == "pdf":
        table = _from_pdf(data, options, limits, info)
    elif kind in {"csv", "txt"}:
        table = _from_text(data, options, limits, info)
    elif kind in {"xlsx", "xls"}:
        table = _from_excel(data, options, limits, info)
    elif kind == "ofx":
        text, info.encoding = decode(data, options.encoding)
        table = read_ofx(text)
        table.detected = f"Fichier OFX · {len(table.rows)} opération(s)"
    elif kind == "qif":
        text, info.encoding = decode(data, options.encoding)
        table = read_qif(text, options.date_order)
        table.detected = f"Fichier QIF · {len(table.rows)} opération(s)"
    else:
        table = _from_json(data, options, limits)
    return info, table


# --- Lecteurs ---------------------------------------------------------------------------------------


def _apply_profile(table: Table, options: ParseOptions, label: str) -> Table:
    """Mise en forme « relevé » si elle s'applique (auto) ou si elle est demandée."""
    if options.profile == "raw":
        table.detected = label
        return table
    normalized = statement.normalize(table)
    if normalized is None:
        if options.profile == "statement":
            table.warnings.append(
                "Mise en forme « relevé bancaire » impossible : colonnes Date, Libellé et Débit / Crédit / Montant "
                "introuvables. Renommez-les ou choisissez « Telle quelle »."
            )
        table.detected = label
        return table
    normalized.detected = f"Relevé bancaire · {len(normalized.rows)} opération(s)"
    return normalized


def _from_text(data: bytes, options: ParseOptions, limits: Limits, info: SourceInfo) -> Table:
    text, info.encoding = decode(data, options.encoding)
    delimiter = options.delimiter or sniff_delimiter(text)
    if delimiter:
        info.delimiter = delimiter
        rows = read_delimited(text, delimiter)
        label = f"Texte délimité ({DELIMITER_NAMES.get(delimiter, delimiter)})"
    else:
        spaced = read_spaced(text)
        if spaced is not None:
            info.delimiter = " "
            rows, label = spaced, "Texte aligné en colonnes"
        else:
            rows, label = read_lines(text), "Texte libre (une ligne par ligne)"
    table = rows_to_table(rows, options, detected=label, max_rows=limits.max_rows)
    if not delimiter and info.delimiter is None:
        table.columns[0].label = "Texte"
        table.columns[0].key = "texte"
        table.rows = [{"texte": next(iter(r.values()), None)} for r in table.rows]
        table.raw_text = text[:500_000]
        table.warnings.append("Aucune colonne trouvée : essayez « Structurer avec l'IA » ou indiquez le séparateur.")
        table.detected = label
        return table
    table.raw_text = text[:500_000] if info.kind == "txt" else None
    return _apply_profile(table, options, label)


def _from_excel(data: bytes, options: ParseOptions, limits: Limits, info: SourceInfo) -> Table:
    import pandas as pd

    engine = "xlrd" if info.kind == "xls" else "openpyxl"
    try:
        book = pd.ExcelFile(io.BytesIO(data), engine=engine)
    except Exception as exc:  # openpyxl / xlrd : erreurs variées sur un fichier abîmé ou chiffré
        raise ConvertError(f"Classeur illisible : {exc}") from exc
    info.sheets = [str(s) for s in book.sheet_names]
    sheet = options.sheet if options.sheet in info.sheets else info.sheets[0]
    frame = book.parse(sheet, header=None, dtype=object)
    rows: list[list[object]] = [[None if _blank(v) else v for v in r] for r in frame.itertuples(index=False)]
    table = rows_to_table(rows, options, detected="", max_rows=limits.max_rows)
    label = f"Classeur Excel · feuille « {sheet} »"
    if len(info.sheets) > 1:
        table.warnings.append(
            f"{len(info.sheets)} feuilles dans le classeur : « {sheet} » est lue (choix dans les options)."
        )
    return _apply_profile(table, options, label)


def _blank(v: object) -> bool:
    try:
        import pandas as pd

        return bool(pd.isna(v))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False


def _from_pdf(data: bytes, options: ParseOptions, limits: Limits, info: SourceInfo) -> Table:
    try:
        content = read_pdf(
            data, options.pages, limits.max_pdf_pages, want_tables=options.pdf_mode in {"auto", "tables"}
        )
    except PdfError as exc:
        raise ConvertError(str(exc)) from exc
    info.pages = content.pages
    if not content.lines:
        table = Table(
            columns=[Column(key="texte", label="Texte")],
            rows=[],
            detected="PDF sans texte",
            warnings=[
                "Ce PDF ne contient pas de texte (document scanné ou image) : la reconnaissance de caractères (OCR) "
                "n'est pas disponible. Demandez à votre banque un relevé PDF « texte », un export CSV ou OFX."
            ],
        )
        return table
    pages_note = "" if len(content.read_pages) == content.pages else f" (pages {_ranges(content.read_pages)})"
    warnings: list[str] = []
    if content.pages > limits.max_pdf_pages and not options.pages:
        warnings.append(f"Seules les {limits.max_pdf_pages} premières pages sont lues.")

    if options.pdf_mode in {"auto", "statement"}:
        found = statement.extract_statement(content.lines, content.text, options)
        if found is not None:
            found.detected = f"Relevé bancaire · {len(found.rows)} opération(s){pages_note}"
            if found.statement and found.statement.bank:
                found.detected = f"Relevé {found.statement.bank} · {len(found.rows)} opération(s){pages_note}"
            found.warnings = warnings + found.warnings
            found.raw_text = content.text
            return found
        if options.pdf_mode == "statement":
            warnings.append("Aucune opération datée avec un montant n'a été reconnue : lecture des tableaux du PDF.")

    if options.pdf_mode in {"auto", "tables", "statement"} and content.tables:
        rows = merge_tables(content.tables)
        table = rows_to_table(rows, options, detected="", max_rows=limits.max_rows)
        table = _apply_profile(table, options, f"Tableaux du PDF · {len(content.tables)} tableau(x){pages_note}")
        table.warnings = warnings + table.warnings
        table.raw_text = content.text
        return table

    lines = [[ln] for ln in content.text.splitlines() if ln.strip()]
    table = rows_to_table(
        lines, options.model_copy(update={"header": False, "skip_rows": 0}), detected="", max_rows=limits.max_rows
    )
    table.columns = [Column(key="texte", label="Texte", type="text")]
    table.rows = [{"texte": " ".join(str(r[0]).split())} for r in lines[: limits.max_rows]]
    table.detected = f"Texte du PDF · {len(table.rows)} ligne(s){pages_note}"
    table.warnings = warnings + [
        "Aucun relevé ni tableau reconnu : le texte est lu ligne à ligne. "
        "« Structurer avec l'IA » peut en faire une table."
    ]
    table.raw_text = content.text
    return table


def _ranges(pages: list[int]) -> str:
    out: list[str] = []
    start = prev = pages[0]
    for p in pages[1:] + [None]:  # type: ignore[list-item]
        if p is not None and p == prev + 1:
            prev = p
            continue
        out.append(str(start) if start == prev else f"{start}-{prev}")
        if p is not None:
            start = prev = p
    return ",".join(out)


def _from_json(data: bytes, options: ParseOptions, limits: Limits) -> Table:
    text, _ = decode(data, options.encoding)
    try:
        doc: Any = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ConvertError(f"JSON invalide : {exc.msg} (ligne {exc.lineno}).") from exc
    label = "JSON"
    columns_hint: list[tuple[str, str]] | None = None
    records: Any = doc
    if isinstance(doc, dict) and doc.get("format") == "atelier-table/1" and isinstance(doc.get("rows"), list):
        columns_hint = [(str(c.get("key")), str(c.get("label") or c.get("key"))) for c in doc.get("columns", [])]
        records, label = doc["rows"], "Table d'échange atelier-table/1"
    elif isinstance(doc, dict):
        lists = [(k, v) for k, v in doc.items() if isinstance(v, list) and v and isinstance(v[0], dict)]
        if lists:
            key, records = max(lists, key=lambda kv: len(kv[1]))
            label = f"JSON · liste « {key} »"
        else:
            records = [doc]
    if not isinstance(records, list) or not all(isinstance(r, dict) for r in records):
        raise ConvertError("JSON non tabulaire : attendu une liste d'objets (ou un objet qui en contient une).")
    records = records[: limits.max_rows]
    if columns_hint is None:
        keys: list[str] = []
        for r in records:
            for k in _flat(r):
                if k not in keys:
                    keys.append(k)
        columns_hint = [(k, k) for k in keys]
    flat = [_flat(r) for r in records]
    labels = [clean_label(lab, i) for i, (_, lab) in enumerate(columns_hint)]
    new_keys = unique_keys(labels)
    columns = []
    for (src, _), key, lab in zip(columns_hint, new_keys, labels, strict=True):
        values = [r.get(src) for r in flat]
        columns.append(Column(key=key, label=lab, type=infer_type(values, lab, options.decimal, options.date_order)))
    rows = [
        {
            col.key: coerce(r.get(src), col.type, options.decimal, options.date_order)
            for (src, _), col in zip(columns_hint, columns, strict=True)
        }
        for r in flat
    ]
    table = Table(columns=columns or [Column(key="colonne_1", label="Colonne 1")], rows=rows, detected="")
    return _apply_profile(table, options, f"{label} · {len(rows)} ligne(s)")


def _flat(record: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """Objet aplati sur un niveau (« adresse.ville ») ; les listes deviennent du texte JSON."""
    out: dict[str, Any] = {}
    for k, v in record.items():
        name = f"{prefix}{k}"
        if isinstance(v, dict) and not prefix:
            out.update(_flat(v, f"{name}."))
        elif isinstance(v, list | dict):
            out[name] = json.dumps(v, ensure_ascii=False)
        else:
            out[name] = v
    return out
