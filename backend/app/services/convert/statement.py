"""Relevés bancaires : lecture des lignes d'un PDF et mise en forme normalisée d'une table.

Colonnes normalisées (dans cet ordre) : Date, Date de valeur (si présente), Libellé, Débit, Crédit,
Montant (signé : crédit − débit), Solde (si présent), puis les autres colonnes du fichier.

Lecture d'un PDF (`extract_statement`) : les mots et leur position viennent de pdfplumber (`pdf.py`) ;
tout le reste est ici, sur des structures simples (`Word`, `Line`), donc testable sans PDF.
1. Les mots sont regroupés en lignes ; « 1 234,56 » (deux mots) redevient un seul montant.
2. L'en-tête (« Date … Libellé … Débit … Crédit … Solde ») donne la position des colonnes de montants.
   Sans en-tête, les positions des montants sont regroupées (débit à gauche du crédit, solde à droite).
3. Une ligne qui commence par une date ouvre une opération ; les lignes suivantes sans date ni montant
   complètent son libellé. Les lignes « Ancien solde / Nouveau solde » donnent les soldes du relevé ;
   « Total », « Report », « À reporter » sont ignorées.
4. Les dates sans année (« 15/03 ») prennent l'année de la période du relevé (décembre d'un relevé de
   janvier : année précédente).
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date

from app.schemas.convert import CellValue, Column, ParseOptions, Role, StatementSummary
from app.services.convert.table import Table
from app.services.convert.values import (
    amount_text,
    norm,
    parse_date,
    parse_number,
    short_date,
    unique_keys,
)

# --- Mots et lignes ---------------------------------------------------------------------------------


@dataclass
class Word:
    text: str
    x0: float
    x1: float
    top: float
    page: int = 1

    @property
    def xc(self) -> float:
        return (self.x0 + self.x1) / 2


@dataclass
class Line:
    page: int
    top: float
    words: list[Word]

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)


def group_lines(words: list[Word], tolerance: float = 2.5) -> list[Line]:
    """Mots → lignes (même page, `top` proche), mots triés de gauche à droite, montants recollés."""
    lines: list[Line] = []
    for w in sorted(words, key=lambda w: (w.page, round(w.top, 1), w.x0)):
        last = lines[-1] if lines else None
        if last and last.page == w.page and abs(w.top - last.top) <= tolerance:
            last.words.append(w)
        else:
            lines.append(Line(page=w.page, top=w.top, words=[w]))
    for line in lines:
        line.words.sort(key=lambda w: w.x0)
        line.words = merge_numbers(line.words)
    return lines


_HEAD = re.compile(r"^[+-]?\(?\d{1,3}$")
_TAIL = re.compile(r"^\d{3}([.,]\d{2})?\)?[+-]?$")


def merge_numbers(words: list[Word]) -> list[Word]:
    """Recolle les montants découpés par l'espace des milliers (« 1 » « 234,56 » → « 1 234,56 »)."""
    out: list[Word] = []
    for w in words:
        prev = out[-1] if out else None
        if (
            prev is not None
            and _TAIL.match(w.text)
            and (_HEAD.match(prev.text) or re.match(r"^[+-]?\d{1,3}( \d{3})+$", prev.text))
            and 0 <= w.x0 - prev.x1 <= 6.5
        ):
            out[-1] = Word(f"{prev.text} {w.text}", prev.x0, w.x1, prev.top, prev.page)
        elif (
            prev is not None
            and w.text in {"€", "EUR", "-", "+"}
            and 0 <= w.x0 - prev.x1 <= 4
            and amount_text(prev.text)
        ):
            suffix = w.text if w.text in {"-", "+"} else ""
            out[-1] = Word(f"{prev.text}{suffix}", prev.x0, w.x1, prev.top, prev.page)
        else:
            out.append(w)
    return out


# --- En-tête et colonnes ----------------------------------------------------------------------------

HEADER_WORDS: dict[str, Role] = {
    "debit": "debit", "debits": "debit", "debit(eur)": "debit", "sorties": "debit", "retraits": "debit",
    "credit": "credit", "credits": "credit", "credit(eur)": "credit", "entrees": "credit", "versements": "credit",
    "montant": "amount", "montants": "amount",
    "solde": "balance",
    "valeur": "value_date",
    "libelle": "label", "libelles": "label", "operation": "label", "operations": "label", "designation": "label",
    "nature": "label", "detail": "label", "details": "label", "description": "label", "intitule": "label",
    "date": "date",
}  # fmt: skip

AMOUNT_ROLES: tuple[Role, ...] = ("debit", "credit", "amount", "balance")


@dataclass
class Anchor:
    role: Role
    x0: float
    x1: float


def header_anchors(line: Line) -> list[Anchor] | None:
    """Colonnes d'une ligne d'en-tête (au moins une colonne de montant et une date ou un libellé)."""
    anchors: list[Anchor] = []
    for w in line.words:
        key = norm(w.text).strip(".:;")
        role = HEADER_WORDS.get(key)
        if role is None:
            continue
        if role == "date" and any(a.role == "date" for a in anchors):
            continue  # « Date opé. Date valeur » : la seconde date est gérée par « valeur »
        anchors.append(Anchor(role, w.x0, w.x1))
    roles = {a.role for a in anchors}
    has_amount = bool(roles & {"debit", "credit", "amount"})
    if has_amount and (roles & {"date", "label"}) and len(anchors) >= 2:
        return anchors
    return None


def cluster_positions(xs: list[float], gap: float = 22.0) -> list[list[float]]:
    """Regroupe des positions (bords droits des montants) en colonnes."""
    groups: list[list[float]] = []
    for x in sorted(xs):
        if groups and x - groups[-1][-1] <= gap:
            groups[-1].append(x)
        else:
            groups.append([x])
    return groups


# --- Opérations -------------------------------------------------------------------------------------

STOP_WORDS = ("total des operations", "totaux", "total", "a reporter", "report", "sous-total", "sous total")
OPENING_WORDS = (
    "ancien solde",
    "solde precedent",
    "solde initial",
    "solde de depart",
    "solde au debut",
    "solde d'ouverture",
)
CLOSING_WORDS = ("nouveau solde", "solde final", "solde a la fin", "solde de cloture", "solde en fin")
CREDIT_HINTS = (
    "vir recu", "vir sepa recu", "virement recu", "virement de", "vir inst recu", "remise", "versement", "rembourst",
    "remboursement", "avoir", "salaire", "interets", "depot", "prime", "allocation", "caf ", "cpam", "retour",
)  # fmt: skip

BANKS = (
    "Crédit Agricole", "BNP Paribas", "Société Générale", "LCL", "Crédit Mutuel", "CIC", "La Banque Postale",
    "Caisse d'Epargne", "Caisse d'Épargne", "Banque Populaire", "BoursoBank", "Boursorama", "ING", "Hello bank",
    "Fortuneo", "Monabanq", "Revolut", "N26", "Qonto", "Shine", "HSBC", "AXA Banque", "Crédit du Nord",
    "Orange Bank", "Nickel", "BforBank", "Banque Palatine", "Bred", "Crédit Coopératif", "La Nef",
)  # fmt: skip


@dataclass
class Txn:
    date_raw: str
    value_raw: str | None
    label_parts: list[str]
    debit: float | None = None
    credit: float | None = None
    amount: float | None = None
    balance: float | None = None
    guessed_sign: bool = False
    page: int = 1
    placed: list[tuple[Word, float]] = field(default_factory=list)

    @property
    def label(self) -> str:
        return " ".join(" ".join(self.label_parts).split())


def detect_bank(text: str) -> str | None:
    low = norm(text)
    for bank in BANKS:
        name = norm(bank)
        if re.search(rf"(?<![a-z]){re.escape(name)}(?![a-z])", low):
            return bank
    return None


def _starts_with_date(line: Line) -> tuple[str, str | None, int] | None:
    """Date d'opération (et de valeur) en tête de ligne : (date, date de valeur, nombre de mots consommés)."""
    words = line.words
    if not words:
        return None
    first = words[0].text
    if not (short_date(first) or _full_date(first)):
        # « 15 mars » / « 15 MAR » en deux mots
        if (
            len(words) >= 2
            and re.fullmatch(r"\d{1,2}", first)
            and parse_date(f"{first} {words[1].text}", default_year=2000)
        ):
            second = (
                words[2].text if len(words) > 2 and (short_date(words[2].text) or _full_date(words[2].text)) else None
            )
            return f"{first} {words[1].text}", second, 3 if second else 2
        return None
    if len(words) > 1 and (short_date(words[1].text) or _full_date(words[1].text)):
        return first, words[1].text, 2
    return first, None, 1


def _full_date(text: str) -> bool:
    return bool(re.fullmatch(r"\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}", text)) and parse_date(text) is not None


def _amount_value(text: str) -> float | None:
    return parse_number(text) if amount_text(text) else None


def statement_year_hint(text: str) -> date | None:
    """Fin de période probable : la date complète la plus fréquente parmi les plus récentes du document."""
    found = []
    for m in re.finditer(r"\b(\d{1,2})[/.](\d{1,2})[/.](\d{4}|\d{2})\b", text):
        iso = parse_date(m.group(0))
        if iso:
            found.append(date.fromisoformat(iso))
    if not found:
        return None
    years = Counter(d.year for d in found)
    main_year = years.most_common(1)[0][0]
    same = [d for d in found if abs(d.year - main_year) <= 1]
    return max(same) if same else max(found)


def _resolve_date(raw: str, end: date | None, forced_year: int | None) -> str | None:
    if not short_date(raw) and not re.fullmatch(r"\d{1,2}\s+\S+", raw):
        return parse_date(raw)
    if forced_year:
        return parse_date(raw, default_year=forced_year)
    if end is None:
        return None
    iso = parse_date(raw, default_year=end.year)
    if iso and date.fromisoformat(iso) > end and (date.fromisoformat(iso) - end).days > 31:
        iso = parse_date(raw, default_year=end.year - 1)
    return iso


def extract_statement(lines: list[Line], full_text: str, options: ParseOptions) -> Table | None:
    """Opérations d'un relevé bancaire lues dans les lignes d'un PDF (None si trop peu d'opérations)."""
    anchors: list[Anchor] | None = None
    txns: list[Txn] = []
    opening: float | None = None
    closing: float | None = None
    current: Txn | None = None
    last_top: tuple[int, float] | None = None
    in_table = False

    for line in lines:
        found = header_anchors(line)
        if found:
            anchors = found
            in_table = True
            current = None
            continue
        low = norm(line.text)
        amounts = [(w, v) for w in line.words if (v := _amount_value(w.text)) is not None]
        start = _starts_with_date(line)

        if any(low.startswith(k) or f" {k}" in low[:40] for k in OPENING_WORDS) and amounts:
            if opening is None:
                opening = _signed_balance(line, amounts, anchors)
            current = None
            continue
        if any(k in low for k in CLOSING_WORDS) and amounts:
            closing = _signed_balance(line, amounts, anchors)
            current = None
            continue
        if start is None and amounts and re.match(r"^solde\b", low) and not txns:
            opening = _signed_balance(line, amounts, anchors)
            continue
        if start is None and amounts and re.match(r"^solde\b", low):
            closing = _signed_balance(line, amounts, anchors)
            current = None
            continue
        if start is None and any(low.startswith(k) for k in STOP_WORDS):
            current = None
            continue

        if start is not None and amounts:
            date_raw, value_raw, used = start
            amount_words = {id(w) for w, _ in amounts}
            label = [w.text for w in line.words[used:] if id(w) not in amount_words or not _in_amount_zone(w, anchors)]
            # Montants à l'intérieur du libellé (ex. « FRAIS 2,50 ») : gardés dans le libellé si loin des colonnes.
            placed = [(w, v) for w, v in amounts if _in_amount_zone(w, anchors)]
            txn = Txn(date_raw=date_raw, value_raw=value_raw, label_parts=label, page=line.page, placed=placed)
            txns.append(txn)
            current = txn
            in_table = True
            last_top = (line.page, line.top)
            continue
        if start is not None and not amounts:
            # Date sans montant sur la ligne : opération dont le montant est sur la ligne suivante.
            date_raw, value_raw, used = start
            txn = Txn(
                date_raw=date_raw, value_raw=value_raw, label_parts=[w.text for w in line.words[used:]], page=line.page
            )
            txns.append(txn)
            current = txn
            last_top = (line.page, line.top)
            continue
        if current is not None and in_table and last_top is not None and last_top[0] == line.page:
            gap = line.top - last_top[1]
            if 0 < gap <= 30:
                placed = [(w, v) for w, v in amounts if _in_amount_zone(w, anchors)]
                if placed and not current.placed:
                    current.placed = placed
                    rest = [w.text for w in line.words if all(w is not p for p, _ in placed)]
                    current.label_parts.extend(rest)
                elif not amounts and len(line.text) <= 120:
                    current.label_parts.append(line.text)
                else:
                    current = None
                last_top = (line.page, line.top)
                continue
        current = None

    txns = [t for t in txns if t.placed]
    if len(txns) < 2:
        return None

    columns_found = _assign_amounts(txns, anchors)
    end = statement_year_hint(full_text)
    warnings: list[str] = []
    if any(t.guessed_sign for t in txns):
        warnings.append("Sens de certains montants déduit du libellé (pas de colonnes Débit / Crédit) : à vérifier.")
    has_value = any(t.value_raw for t in txns)
    has_balance = "balance" in columns_found

    rows: list[dict[str, CellValue]] = []
    unresolved = 0
    for t in txns:
        iso = _resolve_date(t.date_raw, end, options.year)
        if iso is None:
            unresolved += 1
        row: dict[str, CellValue] = {
            "date": iso or t.date_raw,
            "libelle": t.label or None,
            "debit": round(t.debit, 2) if t.debit is not None else None,
            "credit": round(t.credit, 2) if t.credit is not None else None,
            "montant": round((t.credit or 0.0) - (t.debit or 0.0), 2),
        }
        if has_value:
            row["date_de_valeur"] = (
                (_resolve_date(t.value_raw, end, options.year) or t.value_raw) if t.value_raw else None
            )
        if has_balance:
            row["solde"] = round(t.balance, 2) if t.balance is not None else None
        rows.append(row)
    if unresolved:
        warnings.append(
            f"{unresolved} date(s) sans année n'ont pas pu être complétées : indiquez l'année dans les options."
        )

    columns = standard_columns(has_value, has_balance)
    table = Table(columns=columns, rows=rows, warnings=warnings, detected="")
    table.statement = summarize(table, opening, closing, detect_bank(full_text))
    return table


def _in_amount_zone(word: Word, anchors: list[Anchor] | None) -> bool:
    """Vrai si le montant est dans une colonne de montants (ou à droite du libellé quand il n'y a pas d'en-tête)."""
    if not anchors:
        return True
    zones = [a for a in anchors if a.role in AMOUNT_ROLES]
    if not zones:
        return True
    leftmost = min(a.x0 for a in zones)
    return word.x1 >= leftmost - 40


def _nearest(word: Word, anchors: list[Anchor]) -> Anchor:
    zones = [a for a in anchors if a.role in AMOUNT_ROLES]
    # Montants alignés à droite (le plus souvent) : bord droit ; sinon centre.
    return min(zones, key=lambda a: min(abs(word.x1 - a.x1), abs(word.xc - (a.x0 + a.x1) / 2)))


def _assign_amounts(txns: list[Txn], anchors: list[Anchor] | None) -> set[str]:
    """Range chaque montant en débit, crédit, montant signé ou solde ; renvoie les colonnes trouvées."""
    found: set[str] = set()
    zones = [a for a in anchors or [] if a.role in AMOUNT_ROLES]
    if zones:
        for t in txns:
            for w, v in t.placed:
                role = _nearest(w, zones).role
                _put(t, role, v)
                found.add(role)
    else:
        xs = [w.x1 for t in txns for w, _ in t.placed]
        groups = [g for g in cluster_positions(xs) if len(g) >= max(2, len(txns) // 20)]
        centers = [sum(g) / len(g) for g in groups]
        per_line = Counter(len(t.placed) for t in txns).most_common(1)[0][0]
        if len(centers) >= 3:
            roles: list[Role] = ["debit", "credit", "balance"]
            centers = centers[-3:]
        elif len(centers) == 2 and per_line >= 2:
            roles = ["amount", "balance"]
        elif len(centers) == 2:
            roles = ["debit", "credit"]
        else:
            roles = ["amount"]
        for t in txns:
            for w, v in t.placed:
                i = min(range(len(centers)), key=lambda k: abs(w.x1 - centers[k])) if centers else 0
                _put(t, roles[min(i, len(roles) - 1)], v)
                found.add(roles[min(i, len(roles) - 1)])
    for t in txns:
        if t.debit is None and t.credit is None and t.amount is not None:
            if t.amount < 0:
                t.debit = -t.amount
            elif _has_sign(t):
                t.credit = t.amount
            else:
                low = " " + norm(t.label) + " "
                if any(h in low for h in CREDIT_HINTS):
                    t.credit = t.amount
                else:
                    t.debit = t.amount
                t.guessed_sign = True
        t.debit = abs(t.debit) if t.debit is not None else None
        t.credit = abs(t.credit) if t.credit is not None else None
    if "balance" in found:
        _fix_signs_with_balance(txns)
    return found


def _has_sign(t: Txn) -> bool:
    return any(w.text.strip().startswith("+") or w.text.strip().endswith("+") for w, _ in t.placed)


def _put(t: Txn, role: Role, value: float) -> None:
    if role == "debit":
        t.debit = abs(value) if t.debit is None else t.debit
    elif role == "credit":
        t.credit = abs(value) if t.credit is None else t.credit
    elif role == "balance":
        t.balance = value
    else:
        t.amount = value if t.amount is None else t.amount


def _fix_signs_with_balance(txns: list[Txn]) -> None:
    """Avec une colonne Solde : le sens d'un montant deviné est corrigé par la variation du solde."""
    prev: float | None = None
    for t in txns:
        if t.balance is None:
            prev = None
            continue
        if prev is not None:
            delta = round(t.balance - prev, 2)
            value = t.debit if t.debit is not None else t.credit
            if value is not None and abs(abs(delta) - value) < 0.005:
                if delta > 0 and t.debit is not None:
                    t.credit, t.debit, t.guessed_sign = t.debit, None, False
                elif delta < 0 and t.credit is not None:
                    t.debit, t.credit, t.guessed_sign = t.credit, None, False
                else:
                    t.guessed_sign = False
        prev = t.balance


def _signed_balance(line: Line, amounts: list[tuple[Word, float]], anchors: list[Anchor] | None) -> float:
    """Solde lu sur une ligne « Ancien / Nouveau solde » : négatif s'il est débiteur ou dans la colonne Débit."""
    word, value = amounts[-1]
    low = norm(line.text)
    if "debiteur" in low or "negatif" in low:
        return -abs(value)
    if "crediteur" in low:
        return abs(value)
    zones = [a for a in anchors or [] if a.role in AMOUNT_ROLES]
    if zones and _nearest(word, zones).role == "debit":
        return -abs(value)
    return value


# --- Colonnes normalisées et synthèse ---------------------------------------------------------------


def standard_columns(has_value: bool, has_balance: bool) -> list[Column]:
    cols = [Column(key="date", label="Date", type="date", role="date")]
    if has_value:
        cols.append(Column(key="date_de_valeur", label="Date de valeur", type="date", role="value_date"))
    cols += [
        Column(key="libelle", label="Libellé", type="text", role="label"),
        Column(key="debit", label="Débit", type="currency", role="debit"),
        Column(key="credit", label="Crédit", type="currency", role="credit"),
        Column(key="montant", label="Montant", type="currency", role="amount"),
    ]
    if has_balance:
        cols.append(Column(key="solde", label="Solde", type="currency", role="balance"))
    return cols


def _num(v: CellValue) -> float | None:
    return float(v) if isinstance(v, int | float) and not isinstance(v, bool) else None


def summarize(
    table: Table, opening: float | None = None, closing: float | None = None, bank: str | None = None
) -> StatementSummary:
    """Synthèse : période, totaux, soldes et contrôle « solde initial + opérations = solde final »."""
    by_role = {c.role: c.key for c in table.columns if c.role}
    dates = sorted(str(r[by_role["date"]]) for r in table.rows if "date" in by_role and _is_iso(r.get(by_role["date"])))
    debit = sum(_num(r.get(by_role.get("debit", ""), None)) or 0.0 for r in table.rows)
    credit = sum(_num(r.get(by_role.get("credit", ""), None)) or 0.0 for r in table.rows)
    if "amount" in by_role and "debit" not in by_role:
        amounts = [_num(r.get(by_role["amount"])) or 0.0 for r in table.rows]
        debit = -sum(a for a in amounts if a < 0)
        credit = sum(a for a in amounts if a > 0)
    net = round(credit - debit, 2)
    if opening is None and closing is None and "balance" in by_role and "amount" in by_role:
        opening, closing = _balances_from_column(table, by_role["amount"], by_role["balance"])
    check: str = "unknown"
    gap: float | None = None
    if opening is not None and closing is not None:
        gap = round(closing - (opening + net), 2)
        check = "ok" if abs(gap) < 0.01 else "mismatch"
    return StatementSummary(
        transactions=len(table.rows),
        start=dates[0] if dates else None,
        end=dates[-1] if dates else None,
        total_debit=round(debit, 2),
        total_credit=round(credit, 2),
        opening_balance=opening,
        closing_balance=closing,
        balance_check=check,  # type: ignore[arg-type]
        balance_gap=gap,
        bank=bank,
    )


def _is_iso(v: CellValue) -> bool:
    return isinstance(v, str) and bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", v))


def _balances_from_column(table: Table, amount_key: str, balance_key: str) -> tuple[float | None, float | None]:
    """Soldes initial et final d'une colonne Solde, dans l'ordre du fichier (croissant ou décroissant)."""
    pairs = [(_num(r.get(amount_key)), _num(r.get(balance_key))) for r in table.rows]
    pairs = [(a, b) for a, b in pairs if a is not None and b is not None]
    if len(pairs) < 2:
        return None, None

    def consistent(seq: list[tuple[float, float]]) -> bool:
        ok = sum(1 for (_, b0), (a1, b1) in zip(seq, seq[1:], strict=False) if abs(b0 + a1 - b1) < 0.01)
        return ok >= (len(seq) - 1) * 0.8

    for seq in (pairs, pairs[::-1]):
        if consistent(seq):
            first_amount, first_balance = seq[0]
            return round(first_balance - first_amount, 2), seq[-1][1]
    return None, None


# --- Normalisation d'une table déjà lue (CSV, Excel, tableaux de PDF) --------------------------------

ROLE_PATTERNS: list[tuple[Role, re.Pattern[str]]] = [
    ("value_date", re.compile(r"^(date )?(de )?valeur$|value date|date valeur")),
    ("date", re.compile(r"^date\b|^jour$|booking|date comptable|date d.operation|^le$|^posted")),
    ("debit", re.compile(r"^debits?\b|depenses?|retraits?|sorties?|withdrawal|paid out|^debit")),
    ("credit", re.compile(r"^credits?\b|recettes?|versements?|entrees?|deposit|paid in|^credit")),
    ("balance", re.compile(r"^solde|balance")),
    ("amount", re.compile(r"^montant|amount|^somme|^valeur \(?eur|^eur$|^euros?$")),
    ("category", re.compile(r"categor")),
    ("reference", re.compile(r"^ref|reference|^numero|^n°|fitid|cheque")),
    (
        "label",
        re.compile(r"libel|description|designation|operation|^detail|^nature|intitule|beneficiaire|payee|memo|tiers"),
    ),
]


def guess_roles(columns: list[Column]) -> dict[Role, Column]:
    """Rôles de relevé reconnus dans les libellés de colonnes (le premier qui correspond l'emporte)."""
    found: dict[Role, Column] = {}
    for col in columns:
        name = norm(col.label)
        for role, pattern in ROLE_PATTERNS:
            if pattern.search(name) and role not in found:
                if role in {"date", "value_date"} and col.type != "date":
                    continue
                if role in {"debit", "credit", "amount", "balance"} and col.type not in {"number", "currency"}:
                    continue
                found[role] = col
                break
    return found


def is_statement(roles: dict[Role, Column]) -> bool:
    return "date" in roles and "label" in roles and bool({"debit", "credit", "amount"} & roles.keys())


def normalize(table: Table) -> Table | None:
    """Mise en forme normalisée d'une table qui ressemble à un relevé ; None sinon."""
    roles = guess_roles(table.columns)
    if not is_statement(roles):
        return None
    used = {col.key for role, col in roles.items() if role not in ("category", "reference")}
    has_value = "value_date" in roles
    has_balance = "balance" in roles
    rows: list[dict[str, CellValue]] = []
    for r in table.rows:
        debit = _num(r.get(roles["debit"].key)) if "debit" in roles else None
        credit = _num(r.get(roles["credit"].key)) if "credit" in roles else None
        amount = _num(r.get(roles["amount"].key)) if "amount" in roles else None
        if debit is None and credit is None and amount is None:
            # Ligne sans montant (total, sous-titre) : ignorée seulement si elle n'a pas de date non plus.
            if not _is_iso(r.get(roles["date"].key)):
                continue
        if "debit" in roles or "credit" in roles:
            debit = abs(debit) if debit else None
            credit = abs(credit) if credit else None
            if amount is None:
                amount = (credit or 0.0) - (debit or 0.0)
        elif amount is not None:
            debit = -amount if amount < 0 else None
            credit = amount if amount > 0 else None
        row: dict[str, CellValue] = {
            "date": r.get(roles["date"].key),
            "libelle": r.get(roles["label"].key),
            "debit": round(debit, 2) if debit is not None else None,
            "credit": round(credit, 2) if credit is not None else None,
            "montant": round(amount, 2) if amount is not None else None,
        }
        if has_value:
            row["date_de_valeur"] = r.get(roles["value_date"].key)
        if has_balance:
            row["solde"] = r.get(roles["balance"].key)
        rows.append(row)
    columns = standard_columns(has_value, has_balance)
    # Autres colonnes du fichier : gardées après les colonnes normalisées (clés rendues uniques).
    others = [c for c in table.columns if c.key not in used]
    taken = [c.key for c in columns]
    new_keys = unique_keys([*taken, *[c.key for c in others]])[len(taken) :]
    extra: list[Column] = []
    for col, key in zip(others, new_keys, strict=True):
        extra.append(col.model_copy(update={"key": key}))
    if extra:
        source_rows = [r for r in table.rows if _kept(r, roles)]
        for row, src in zip(rows, source_rows, strict=False):
            for col, old in zip(extra, others, strict=True):
                row[col.key] = src.get(old.key)
    if "label" in roles:
        # Libellé : texte multi-lignes ramené à une ligne.
        for row in rows:
            if isinstance(row["libelle"], str):
                row["libelle"] = " ".join(row["libelle"].split())
    result = Table(columns=columns + extra, rows=rows, detected="", warnings=list(table.warnings))
    result.statement = summarize(result)
    return result


def _kept(r: dict[str, CellValue], roles: dict[Role, Column]) -> bool:
    keys = [roles[k].key for k in ("debit", "credit", "amount") if k in roles]
    if any(_num(r.get(k)) is not None for k in keys):
        return True
    return _is_iso(r.get(roles["date"].key))
