"""Lecture des PDF (pdfplumber) : mots positionnés, tableaux détectés, texte brut.

Rien ne quitte la machine : pdfplumber lit le fichier localement. Les PDF scannés (images sans texte)
ne contiennent pas de texte : un avertissement le dit (pas d'OCR dans cette version).
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass

import pdfplumber
from pdfminer.pdfdocument import PDFPasswordIncorrect

from app.services.convert.statement import Line, Word, group_lines


class PdfError(Exception):
    """PDF illisible (chiffré, abîmé)."""


@dataclass
class PdfContent:
    pages: int
    read_pages: list[int]
    lines: list[Line]
    text: str
    tables: list[list[list[str | None]]]


def parse_pages(spec: str | None, count: int, limit: int) -> list[int]:
    """« 1-3,5 » → [1, 2, 3, 5] (pages existantes, au plus `limit`)."""
    if not spec or not spec.strip():
        return list(range(1, min(count, limit) + 1))
    pages: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        m = re.fullmatch(r"(\d+)\s*-\s*(\d+)", part)
        if m:
            a, b = int(m[1]), int(m[2])
            pages.extend(range(min(a, b), max(a, b) + 1))
        elif part.isdigit():
            pages.append(int(part))
    seen = sorted({p for p in pages if 1 <= p <= count})
    return seen[:limit]


def read_pdf(data: bytes, pages_spec: str | None, max_pages: int, want_tables: bool) -> PdfContent:
    """Mots, lignes, texte et (si demandé) tableaux des pages choisies."""
    try:
        pdf = pdfplumber.open(io.BytesIO(data))
    except PDFPasswordIncorrect as exc:
        raise PdfError("PDF protégé par un mot de passe : ouvrez-le et enregistrez-le sans protection.") from exc
    except Exception as exc:  # pdfminer lève des erreurs variées sur un fichier abîmé
        raise PdfError(f"PDF illisible : {exc}") from exc
    with pdf:
        count = len(pdf.pages)
        chosen = parse_pages(pages_spec, count, max_pages)
        words: list[Word] = []
        texts: list[str] = []
        tables: list[list[list[str | None]]] = []
        for number in chosen:
            page = pdf.pages[number - 1]
            for w in page.extract_words(x_tolerance=1.5, y_tolerance=2.0, keep_blank_chars=False, use_text_flow=False):
                words.append(
                    Word(text=w["text"], x0=float(w["x0"]), x1=float(w["x1"]), top=float(w["top"]), page=number)
                )
            texts.append(page.extract_text(x_tolerance=1.5, y_tolerance=2.0) or "")
            if want_tables:
                for table in page.extract_tables():
                    if table and len(table) >= 2:
                        tables.append(table)
            page.flush_cache()
        return PdfContent(
            pages=count, read_pages=chosen, lines=group_lines(words), text="\n".join(texts).strip(), tables=tables
        )


def merge_tables(tables: list[list[list[str | None]]]) -> list[list[object]]:
    """Tableaux de plusieurs pages réunis : même largeur que le premier, en-têtes répétés retirés."""
    if not tables:
        return []
    width = max(len(t[0]) for t in tables)
    main = [t for t in tables if len(t[0]) == width]
    header = [(_cell(c)) for c in main[0][0]]
    rows: list[list[object]] = [header]
    for t in main:
        for r in t:
            cells = [_cell(c) for c in r]
            if cells == header:
                continue
            rows.append(cells)
    return rows


def _cell(value: str | None) -> str:
    return " ".join((value or "").split())
