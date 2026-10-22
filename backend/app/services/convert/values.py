"""Lecture des valeurs : nombres (format français ou anglais), dates, booléens, clés de colonnes, types.

Fonctions pures, sans dépendance : testées dans tests/test_values.py.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Sequence
from datetime import date, datetime

from app.schemas.convert import CellValue, ColumnType

# --- Nombres --------------------------------------------------------------------------------------

_SPACES = "    '"  # espaces (insécable, fine) et apostrophe : séparateurs de milliers
_CURRENCY = re.compile(r"(€|eur|euros?|\$|usd|£|gbp|chf)", re.IGNORECASE)
_NUMBER_CHARS = re.compile(r"^[+-]?[\d.,]+$")

TRUE_WORDS = frozenset({"true", "vrai", "oui", "yes", "x", "✓"})
FALSE_WORDS = frozenset({"false", "faux", "non", "no"})


def strip_accents(text: str) -> str:
    """« Débit » → « Debit »."""
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def norm(text: str) -> str:
    """Forme de comparaison : minuscules, sans accents ni espaces superflus."""
    return " ".join(strip_accents(text).lower().split())


def parse_number(raw: object, decimal: str = "auto") -> float | None:
    """Nombre écrit à la française (« 1 234,56 », « -12,5 € ») ou à l'anglaise (« 1,234.56 »).

    Accepte un signe en fin (« 12,50- »), les parenthèses comptables (« (12,50) ») et les suffixes
    « CR » / « DB » (crédit / débit). `decimal` force le séparateur décimal (« , » ou « . »).
    Renvoie None si le texte n'est pas un nombre.
    """
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, int | float):
        return float(raw)
    text = str(raw).strip()
    if not text:
        return None
    sign = 1.0
    low = text.lower()
    if low.endswith((" cr", "cr")) and re.search(r"\d\s*cr$", low):
        text = text[:-2].strip()
    elif low.endswith((" db", "db", " dr", "dr")) and re.search(r"\d\s*(db|dr)$", low):
        text = text[:-2].strip()
        sign = -1.0
    text = _CURRENCY.sub("", text).strip()
    if text.startswith("(") and text.endswith(")"):
        text, sign = text[1:-1].strip(), -sign
    for ch in _SPACES:
        text = text.replace(ch, "")
    if text.endswith("-") and len(text) > 1:
        text, sign = text[:-1], -sign
    elif text.endswith("+") and len(text) > 1:
        text = text[:-1]
    if text.startswith("+"):
        text = text[1:]
    elif text.startswith("-"):
        text, sign = text[1:], -sign
    if not text or not _NUMBER_CHARS.match(text) or not any(c.isdigit() for c in text):
        return None
    dec = _decimal_separator(text, decimal)
    if dec == ",":
        text = text.replace(".", "").replace(",", ".")
    else:
        text = text.replace(",", "")
    if text.count(".") > 1:
        return None
    try:
        return sign * float(text)
    except ValueError:
        return None


def _decimal_separator(text: str, forced: str) -> str:
    """Séparateur décimal probable d'un nombre sans espaces (« 1.234,56 » → « , »)."""
    if forced in {",", "."}:
        return forced
    has_comma, has_dot = "," in text, "." in text
    if has_comma and has_dot:
        return "," if text.rfind(",") > text.rfind(".") else "."
    if has_comma:
        # « 1,234 » est ambigu ; en France c'est 1,234. Plusieurs virgules = milliers à l'anglaise.
        return "," if text.count(",") == 1 else "."
    if has_dot:
        # « 1.234.567 » = milliers ; « 1.234 » seul reste un décimal (cas le plus courant hors France).
        return "." if text.count(".") == 1 else ","
    return "."


def amount_text(text: str) -> bool:
    """Vrai si le jeton ressemble à un montant à deux décimales (« 1 234,56 », « 12.50- », « 0,99 »)."""
    t = text.strip().replace(" ", " ").replace(" ", " ")
    return bool(re.fullmatch(r"[+-]?\(?\d{1,3}(?:[ .']?\d{3})*[.,]\d{2}\)?[+-]?(?:\s?(?:€|EUR|CR|DB))?", t, re.I))


# --- Dates ----------------------------------------------------------------------------------------

MONTHS = {
    "janvier": 1, "janv": 1, "jan": 1, "january": 1,
    "fevrier": 2, "fevr": 2, "fev": 2, "feb": 2, "february": 2,
    "mars": 3, "mar": 3, "march": 3,
    "avril": 4, "avr": 4, "apr": 4, "april": 4,
    "mai": 5, "may": 5,
    "juin": 6, "jun": 6, "june": 6,
    "juillet": 7, "juil": 7, "jul": 7, "july": 7,
    "aout": 8, "aou": 8, "aug": 8, "august": 8,
    "septembre": 9, "sept": 9, "sep": 9, "september": 9,
    "octobre": 10, "oct": 10, "october": 10,
    "novembre": 11, "nov": 11, "november": 11,
    "decembre": 12, "dec": 12, "december": 12,
}  # fmt: skip

_NUMERIC_DATE = re.compile(r"^(\d{1,4})[/.\-](\d{1,2})(?:[/.\-](\d{2,4}))?$")
_COMPACT_DATE = re.compile(r"^(\d{4})(\d{2})(\d{2})(?:\d{6})?(?:\.\d+)?(?:\[.*\])?$")  # OFX : 20260315120000[+1:CET]
_WORD_DATE = re.compile(r"^(\d{1,2})(?:er)?\s+([a-zéèûô]+)\.?(?:\s+(\d{2,4}))?$", re.IGNORECASE)


def _year(y: int) -> int:
    return y + 2000 if y < 70 else (y + 1900 if y < 100 else y)


def _iso(y: int, m: int, d: int) -> str | None:
    try:
        return date(y, m, d).isoformat()
    except ValueError:
        return None


def parse_date(raw: object, order: str = "auto", default_year: int | None = None) -> str | None:
    """Date lue (« 15/03/2026 », « 15.03.26 », « 2026-03-15 », « 15 mars 2026 », « 15/03 ») → « AAAA-MM-JJ ».

    `order` : « dmy » (défaut français), « mdy », « ymd » ou « auto » (jour d'abord sauf si impossible).
    Une date sans année prend `default_year` (sinon None).
    """
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw.date().isoformat()
    if isinstance(raw, date):
        return raw.isoformat()
    text = str(raw).strip()
    if not text or len(text) > 40:
        return None
    text = text.split("T")[0] if re.match(r"^\d{4}-\d{2}-\d{2}T", text) else text
    text = re.sub(r"\s+\d{1,2}:\d{2}(:\d{2})?$", "", text)  # heure éventuelle
    m = _COMPACT_DATE.match(text)
    if m:
        return _iso(int(m[1]), int(m[2]), int(m[3]))
    m = _NUMERIC_DATE.match(text)
    if m:
        a, b, c = m[1], m[2], m[3]
        if len(a) == 4:  # AAAA-MM-JJ
            return _iso(int(a), int(b), int(c)) if c else None
        if c is None:
            if default_year is None:
                return None
            y = default_year
        else:
            if len(c) == 3:
                return None
            y = _year(int(c))
        first, second = int(a), int(b)
        if order == "mdy":
            return _iso(y, first, second)
        if order == "auto" and second > 12 and first <= 12:
            return _iso(y, first, second)
        return _iso(y, second, first)
    m = _WORD_DATE.match(norm(text).replace(".", ""))
    if m:
        month = MONTHS.get(m[2].rstrip("."))
        if month is None:
            return None
        y = _year(int(m[3])) if m[3] else default_year
        return _iso(y, month, int(m[1])) if y else None
    return None


def short_date(text: str) -> bool:
    """Vrai pour « 15/03 », « 15.03 » (jour / mois sans année), fréquent dans les relevés."""
    return bool(re.fullmatch(r"\d{1,2}[/.]\d{1,2}", text.strip()))


def date_token(text: str) -> bool:
    """Vrai si le jeton est une date (avec ou sans année)."""
    t = text.strip()
    return short_date(t) or parse_date(t, default_year=2000) is not None and bool(re.match(r"^\d", t))


def format_date_fr(iso: str) -> str:
    """« 2026-03-15 » → « 15/03/2026 »."""
    parts = iso.split("-")
    return f"{parts[2]}/{parts[1]}/{parts[0]}" if len(parts) == 3 else iso


# --- Booléens -------------------------------------------------------------------------------------


def parse_bool(raw: object) -> bool | None:
    if isinstance(raw, bool):
        return raw
    if raw is None:
        return None
    t = norm(str(raw))
    if t in TRUE_WORDS:
        return True
    if t in FALSE_WORDS:
        return False
    return None


# --- Clés et libellés -----------------------------------------------------------------------------


def snake_key(label: str, fallback: str = "colonne") -> str:
    """Clé `snake_case` sans accent (« Date de valeur » → « date_de_valeur »)."""
    key = re.sub(r"[^a-z0-9]+", "_", strip_accents(label).lower()).strip("_")
    if not key:
        key = fallback
    if key[0].isdigit():
        key = f"c_{key}"
    return key[:60]


def unique_keys(labels: Sequence[str]) -> list[str]:
    """Clés uniques pour une suite de libellés (suffixes _2, _3…)."""
    seen: dict[str, int] = {}
    keys = []
    for i, label in enumerate(labels):
        base = snake_key(label, f"colonne_{i + 1}")
        n = seen.get(base, 0) + 1
        seen[base] = n
        keys.append(base if n == 1 else f"{base}_{n}")
    return keys


def clean_label(text: object, index: int) -> str:
    """Libellé d'en-tête lisible (espaces normalisés), « Colonne N » s'il est vide."""
    label = " ".join(str(text or "").split())
    return label[:200] if label else f"Colonne {index + 1}"


# --- Types ----------------------------------------------------------------------------------------

AMOUNT_WORDS = (
    "montant", "debit", "credit", "solde", "prix", "total", "somme", "amount", "balance", "eur", "€",
    "ttc", "ht", "tva", "paiement", "depense", "recette", "valeur",
)  # fmt: skip


def infer_type(values: Iterable[object], label: str = "", decimal: str = "auto", order: str = "auto") -> ColumnType:
    """Type d'une colonne d'après ses valeurs non vides (≥ 90 % doivent correspondre)."""
    sample = [v for v in values if v is not None and str(v).strip() != ""][:500]
    if not sample:
        return "text"

    def share(test) -> float:
        return sum(1 for v in sample if test(v)) / len(sample)

    if share(lambda v: parse_date(v, order) is not None and not _plain_int(v)) >= 0.9:
        return "date"
    if share(lambda v: parse_number(v, decimal) is not None) >= 0.9:
        name = norm(label)
        money = any(w in name.split() or w in name for w in AMOUNT_WORDS if len(w) > 3) or any(
            w in name.split() for w in AMOUNT_WORDS
        )
        two_decimals = share(lambda v: isinstance(v, str) and amount_text(v)) >= 0.6
        has_symbol = share(lambda v: isinstance(v, str) and "€" in v) >= 0.3
        return "currency" if money or two_decimals or has_symbol else "number"
    if share(lambda v: parse_bool(v) is not None) >= 0.95 and len({norm(str(v)) for v in sample}) <= 2:
        return "boolean"
    return "text"


def _plain_int(value: object) -> bool:
    return isinstance(value, int | float) or bool(re.fullmatch(r"\d{1,8}", str(value).strip()))


def coerce(value: object, type_: ColumnType, decimal: str = "auto", order: str = "auto") -> CellValue:
    """Valeur stockée pour un type : nombre (float), date ISO, booléen ou texte. Vide → None.

    Une valeur qui ne se convertit pas est gardée en texte (rien n'est perdu).
    """
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    if type_ in {"number", "currency"}:
        n = parse_number(value, decimal)
        if n is None:
            return str(value).strip()
        return round(n, 10)
    if type_ == "date":
        d = parse_date(value, order)
        return d if d is not None else str(value).strip()
    if type_ == "boolean":
        b = parse_bool(value)
        return b if b is not None else str(value).strip()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, datetime | date):
        return value.isoformat()
    return " ".join(str(value).split()) if isinstance(value, str) else str(value)
