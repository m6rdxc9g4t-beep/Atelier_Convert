"""Fichiers texte (CSV, TXT) : encodage, séparateur, découpage en lignes et colonnes."""

from __future__ import annotations

import csv
import io
import re
from collections import Counter

from charset_normalizer import from_bytes

CANDIDATES = [";", ",", "\t", "|"]
DELIMITER_NAMES = {";": "point-virgule", ",": "virgule", "\t": "tabulation", "|": "barre verticale", " ": "espaces"}


def decode(data: bytes, encoding: str | None = None) -> tuple[str, str]:
    """Texte et encodage retenu : forcé, sinon UTF-8 (avec ou sans BOM), sinon détection (Windows-1252…)."""
    if encoding:
        return data.decode(encoding, errors="replace"), encoding
    if data.startswith(b"\xef\xbb\xbf"):
        return data[3:].decode("utf-8", errors="replace"), "utf-8-sig"
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", errors="replace"), "utf-16"
    try:
        return data.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        pass
    # Les exports français non UTF-8 sont presque toujours en Windows-1252 (sur-ensemble de Latin-1) :
    # il est retenu dès qu'il décode tout le fichier, plutôt qu'une détection hésitante (cp1250, mac_roman…).
    try:
        return data.decode("cp1252"), "cp1252"
    except UnicodeDecodeError:
        pass
    best = from_bytes(data[:200_000]).best()
    name = best.encoding if best else "cp1252"
    if name in {"latin_1", "iso8859_1", "iso8859_15", "ascii"}:
        name = "cp1252"
    try:
        return data.decode(name, errors="replace"), name
    except LookupError:
        return data.decode("cp1252", errors="replace"), "cp1252"


def sniff_delimiter(text: str) -> str | None:
    """Séparateur le plus régulier sur les 50 premières lignes non vides (None = aucun : texte libre)."""
    lines = [ln for ln in text.splitlines() if ln.strip()][:50]
    if not lines:
        return None
    best: tuple[float, str] | None = None
    sample = "\n".join(lines)
    for delim in CANDIDATES:
        if delim == ",":
            # Texte aligné par des espaces avec des virgules décimales (« ABONNEMENT     -12,99 ») :
            # la virgule n'y sépare pas des colonnes.
            total = sample.count(",")
            aligned = sum(1 for ln in lines if "  " in ln.strip()) >= len(lines) / 2
            if aligned and total and len(re.findall(r"\d,\d", sample)) / total >= 0.5:
                continue
        counts = [len(_split(ln, delim)) for ln in lines]
        many = [c for c in counts if c >= 2]
        if len(many) < max(1, len(lines) // 3):
            continue
        mode, freq = Counter(many).most_common(1)[0]
        # Régularité (part des lignes à la largeur la plus fréquente) × largeur : favorise le vrai séparateur.
        score = (freq / len(lines)) * min(mode, 12)
        if best is None or score > best[0]:
            best = (score, delim)
    return best[1] if best else None


def _split(line: str, delim: str) -> list[str]:
    try:
        return next(csv.reader([line], delimiter=delim))
    except (csv.Error, StopIteration):
        return line.split(delim)


def read_delimited(text: str, delimiter: str) -> list[list[object]]:
    """Lignes d'un CSV (guillemets gérés, sauts de ligne dans les champs compris)."""
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    return [list(row) for row in reader]


_COLUMNS_GAP = re.compile(r"\s{2,}|\t")


def read_spaced(text: str) -> list[list[object]] | None:
    """Texte aligné en colonnes par des espaces (export « TXT » de banques) : découpé sur 2 espaces ou plus.

    Renvoie None si le découpage n'est pas régulier (le texte est alors lu ligne à ligne).
    """
    lines = [ln.rstrip() for ln in text.splitlines()]
    rows = [[c for c in _COLUMNS_GAP.split(ln.strip()) if c != ""] for ln in lines if ln.strip()]
    widths = [len(r) for r in rows]
    multi = [w for w in widths if w >= 2]
    if len(multi) < max(3, len(rows) // 2):
        return None
    return [list(r) for r in rows]


def read_lines(text: str) -> list[list[object]]:
    """Une ligne de texte par ligne de table (colonne unique « Texte »)."""
    return [[ln.rstrip()] for ln in text.splitlines() if ln.strip()]
