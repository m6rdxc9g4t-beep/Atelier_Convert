"""Formats bancaires d'échange : OFX / QFX (Money, Quicken) et QIF.

Les deux donnent directement des opérations : date, montant signé, libellé, référence.
"""

from __future__ import annotations

import re

from app.schemas.convert import CellValue, Column
from app.services.convert.statement import standard_columns, summarize
from app.services.convert.table import Table
from app.services.convert.values import parse_date, parse_number


def _tag(block: str, name: str) -> str | None:
    """Valeur d'une balise OFX, fermée (XML) ou non (SGML : la valeur s'arrête à la fin de ligne ou à « < »)."""
    m = re.search(rf"<{name}>\s*([^<\r\n]*)", block, re.IGNORECASE)
    return m.group(1).strip() if m else None


def read_ofx(text: str) -> Table:
    """Opérations `<STMTTRN>` d'un relevé OFX ; soldes `<LEDGERBAL>` si présents."""
    blocks = re.findall(r"<STMTTRN>(.*?)(?:</STMTTRN>|(?=<STMTTRN>)|(?=</BANKTRANLIST>))", text, re.IGNORECASE | re.S)
    rows: list[dict[str, CellValue]] = []
    for b in blocks:
        amount = parse_number(_tag(b, "TRNAMT"), decimal=".") if _tag(b, "TRNAMT") else None
        if amount is None:
            raw = _tag(b, "TRNAMT")
            amount = parse_number(raw) if raw else None
        name = _tag(b, "NAME") or ""
        memo = _tag(b, "MEMO") or ""
        label = name if not memo or memo in name else (f"{name} — {memo}" if name else memo)
        rows.append(
            {
                "date": parse_date(_tag(b, "DTPOSTED") or ""),
                "libelle": " ".join(label.split()) or None,
                "debit": round(-amount, 2) if amount is not None and amount < 0 else None,
                "credit": round(amount, 2) if amount is not None and amount > 0 else None,
                "montant": round(amount, 2) if amount is not None else None,
                "type": _tag(b, "TRNTYPE"),
                "reference": _tag(b, "FITID"),
            }
        )
    columns = standard_columns(False, False) + [
        Column(key="type", label="Type", type="text"),
        Column(key="reference", label="Référence", type="text", role="reference"),
    ]
    table = Table(columns=columns, rows=rows, detected="")
    closing = None
    ledger = re.search(r"<LEDGERBAL>(.*?)(?:</LEDGERBAL>|<AVAILBAL>|$)", text, re.IGNORECASE | re.S)
    if ledger and _tag(ledger.group(1), "BALAMT"):
        closing = parse_number(_tag(ledger.group(1), "BALAMT"), decimal=".")
    table.statement = summarize(table)
    if closing is not None:
        table.statement.closing_balance = closing
    if not rows:
        table.warnings.append("Aucune opération (<STMTTRN>) trouvée dans le fichier OFX.")
    return table


def read_qif(text: str, date_order: str = "auto") -> Table:
    """Opérations d'un fichier QIF (lignes D, T/U, P, M, N, L, terminées par « ^ »)."""
    rows: list[dict[str, CellValue]] = []
    record: dict[str, str] = {}
    order = "dmy" if date_order == "auto" else date_order
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("!"):
            continue
        if line == "^":
            if record:
                rows.append(_qif_row(record, order))
            record = {}
            continue
        code, value = line[0], line[1:].strip()
        if code in {"D", "T", "U", "P", "M", "N", "L"} and code not in record:
            record[code] = value
    if record:
        rows.append(_qif_row(record, order))
    columns = standard_columns(False, False) + [
        Column(key="categorie", label="Catégorie", type="text", role="category"),
        Column(key="reference", label="Référence", type="text", role="reference"),
    ]
    table = Table(columns=columns, rows=rows, detected="")
    table.statement = summarize(table)
    if not rows:
        table.warnings.append("Aucune opération trouvée dans le fichier QIF.")
    return table


def _qif_row(record: dict[str, str], order: str) -> dict[str, CellValue]:
    raw_date = record.get("D", "").replace("'", "/").replace(" ", "")
    amount = parse_number(record.get("T") or record.get("U") or "")
    label = record.get("P") or record.get("M") or ""
    memo = record.get("M", "")
    if memo and memo != label and memo not in label:
        label = f"{label} — {memo}" if label else memo
    return {
        "date": parse_date(raw_date, order) or raw_date or None,
        "libelle": label or None,
        "debit": round(-amount, 2) if amount is not None and amount < 0 else None,
        "credit": round(amount, 2) if amount is not None and amount > 0 else None,
        "montant": round(amount, 2) if amount is not None else None,
        "categorie": record.get("L") or None,
        "reference": record.get("N") or None,
    }
