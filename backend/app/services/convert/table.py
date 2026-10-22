"""Table obtenue d'une conversion, et passage de lignes brutes (CSV, Excel, PDF) à une table typée."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field

from app.schemas.convert import CellValue, Column, ParseOptions, StatementSummary
from app.services.convert.values import clean_label, coerce, infer_type, parse_date, parse_number, unique_keys


@dataclass
class Table:
    """Colonnes + lignes (dictionnaires indexés par la clé de colonne)."""

    columns: list[Column]
    rows: list[dict[str, CellValue]]
    detected: str = ""
    warnings: list[str] = field(default_factory=list)
    statement: StatementSummary | None = None
    raw_text: str | None = None

    @property
    def included(self) -> list[Column]:
        return [c for c in self.columns if c.include]


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _non_empty(row: Sequence[object]) -> int:
    return sum(1 for v in row if _text(v))


def trim_rows(rows: list[list[object]]) -> list[list[object]]:
    """Retire les lignes entièrement vides et les colonnes vides en fin de ligne."""
    out = []
    for row in rows:
        cells = list(row)
        while cells and not _text(cells[-1]):
            cells.pop()
        if cells:
            out.append(cells)
    return out


def table_start(rows: list[list[object]]) -> int:
    """Indice de la première ligne de la table, après un éventuel préambule (n° de compte, titulaire…).

    La largeur « normale » est la plus fréquente parmi les lignes d'au moins deux cellules ; la table
    commence à la première ligne de cette largeur suivie d'au moins une autre ligne de même largeur.
    """
    widths = [_non_empty(r) for r in rows]
    counted = Counter(w for w in widths if w >= 2)
    if not counted:
        return 0
    target = counted.most_common(1)[0][0]
    for i, w in enumerate(widths):
        if w >= max(2, target - 1) and any(x >= max(2, target - 1) for x in widths[i + 1 : i + 4]):
            return i
    return 0


def looks_like_header(row: Sequence[object], following: Sequence[Sequence[object]]) -> bool:
    """Vrai si la ligne ressemble à un en-tête : du texte là où les lignes suivantes ont des nombres ou des dates."""
    cells = [_text(v) for v in row]
    if not any(cells):
        return False
    typed_in_row = sum(1 for v in cells if v and (parse_number(v) is not None or parse_date(v) is not None))
    if typed_in_row > len([c for c in cells if c]) / 2:
        return False
    if not following:
        return typed_in_row == 0
    score = 0
    for col, value in enumerate(cells):
        below = [_text(r[col]) for r in following if col < len(r) and _text(r[col])]
        if not below or not value:
            continue
        typed = sum(1 for v in below if parse_number(v) is not None or parse_date(v) is not None)
        if typed / len(below) >= 0.6 and parse_number(value) is None and parse_date(value) is None:
            score += 1
    # Table entièrement textuelle : impossible de trancher par les types ; une première ligne pleine,
    # sans doublon ni valeur typée, est le plus souvent un en-tête.
    filled = [c for c in cells if c]
    distinct = len({c.lower() for c in filled}) == len(filled)
    return score >= 1 or (
        typed_in_row == 0 and distinct and len(filled) == len(cells) and all(len(c) <= 60 for c in filled)
    )


def rows_to_table(
    raw: list[list[object]],
    options: ParseOptions,
    *,
    detected: str,
    max_rows: int,
    labels: list[str] | None = None,
) -> Table:
    """Lignes brutes → table typée : préambule ignoré, en-tête détecté (ou imposé), types déduits."""
    rows = trim_rows(raw)
    warnings: list[str] = []
    if options.skip_rows:
        rows = rows[options.skip_rows :]
    elif labels is None:
        start = table_start(rows)
        if start:
            warnings.append(f"{start} ligne(s) de préambule ignorée(s) au début du fichier.")
            rows = rows[start:]
    if not rows:
        return Table(
            columns=[Column(key="colonne_1", label="Colonne 1")],
            rows=[],
            detected=detected,
            warnings=["Aucune donnée trouvée dans le fichier."],
        )

    width = max(len(r) for r in rows)
    if labels is None:
        header = options.header if options.header is not None else looks_like_header(rows[0], rows[1:20])
        if header:
            labels = [clean_label(v, i) for i, v in enumerate(rows[0])]
            rows = rows[1:]
        else:
            labels = []
    labels = labels + [f"Colonne {i + 1}" for i in range(len(labels), width)]
    labels = labels[:width] if width else labels
    keys = unique_keys(labels)

    if len(rows) > max_rows:
        warnings.append(f"Fichier tronqué : {max_rows:,} lignes gardées sur {len(rows):,}.".replace(",", " "))
        rows = rows[:max_rows]

    columns: list[Column] = []
    for i, (key, label) in enumerate(zip(keys, labels, strict=True)):
        values = [r[i] if i < len(r) else None for r in rows]
        columns.append(
            Column(key=key, label=label, type=infer_type(values, label, options.decimal, options.date_order))
        )

    table_rows: list[dict[str, CellValue]] = []
    for r in rows:
        table_rows.append(
            {
                col.key: coerce(r[i] if i < len(r) else None, col.type, options.decimal, options.date_order)
                for i, col in enumerate(columns)
            }
        )
    # Colonnes entièrement vides : gardées de côté (non exportées).
    for col in columns:
        if all(row.get(col.key) is None for row in table_rows):
            col.include = False
    return Table(columns=columns, rows=table_rows, detected=detected, warnings=warnings)
