"""Lecture des valeurs : nombres français / anglais, dates, types, clés."""

import pytest

from app.services.convert.values import (
    amount_text,
    coerce,
    infer_type,
    parse_bool,
    parse_date,
    parse_number,
    snake_key,
    unique_keys,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1 234,56", 1234.56),
        ("1 234,56 €", 1234.56),
        ("-12,50", -12.5),
        ("12,50-", -12.5),
        ("(12,50)", -12.5),
        ("+45,00", 45.0),
        ("1.234,56", 1234.56),
        ("1,234.56", 1234.56),
        ("1234.5", 1234.5),
        ("0,99", 0.99),
        ("12,50 CR", 12.5),
        ("12,50 DB", -12.5),
        ("42", 42.0),
        ("1'234.50", 1234.5),
        (12, 12.0),
        ("", None),
        ("abc", None),
        ("12/03", None),
        ("1.2.3,4.5", None),
    ],
)
def test_parse_number(raw: object, expected: float | None) -> None:
    assert parse_number(raw) == expected


def test_parse_number_forced_decimal() -> None:
    assert parse_number("1,234", decimal=".") == 1234.0
    assert parse_number("1.234", decimal=",") == 1234.0


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("15/03/2026", "2026-03-15"),
        ("15.03.26", "2026-03-15"),
        ("15-03-2026", "2026-03-15"),
        ("2026-03-15", "2026-03-15"),
        ("2026-03-15T10:00:00", "2026-03-15"),
        ("20260315", "2026-03-15"),
        ("20260315120000[+1:CET]", "2026-03-15"),
        ("15 mars 2026", "2026-03-15"),
        ("1er janvier 2026", "2026-01-01"),
        ("15/03/2026 10:45", "2026-03-15"),
        ("31/02/2026", None),
        ("15/03", None),
        ("bonjour", None),
    ],
)
def test_parse_date(raw: str, expected: str | None) -> None:
    assert parse_date(raw) == expected


def test_parse_date_orders_and_default_year() -> None:
    assert parse_date("03/15/2026") == "2026-03-15"  # 15 ne peut pas être un mois
    assert parse_date("03/04/2026", order="mdy") == "2026-03-04"
    assert parse_date("03/04/2026") == "2026-04-03"
    assert parse_date("15/03", default_year=2025) == "2025-03-15"


def test_amount_text() -> None:
    assert amount_text("1 234,56")
    assert amount_text("12.50-")
    assert amount_text("0,99 €")
    assert not amount_text("12/03")
    assert not amount_text("2026")
    assert not amount_text("ABC")


def test_infer_type() -> None:
    assert infer_type(["15/03/2026", "16/03/2026"]) == "date"
    assert infer_type(["1 234,56", "12,00"], "Débit") == "currency"
    assert infer_type(["3", "12", "6"], "Quantité") == "number"
    assert infer_type(["12,50", "3,99"], "Prix") == "currency"
    assert infer_type(["oui", "non", "oui"]) == "boolean"
    assert infer_type(["Rabot", "Ciseau"]) == "text"
    assert infer_type([None, ""]) == "text"
    assert infer_type(["2026", "2025"]) == "number"  # des années seules ne sont pas des dates


def test_coerce_keeps_unconvertible_values_as_text() -> None:
    assert coerce("12,50", "currency") == 12.5
    assert coerce("n/a", "currency") == "n/a"
    assert coerce("15/03/2026", "date") == "2026-03-15"
    assert coerce("  plusieurs   espaces ", "text") == "plusieurs espaces"
    assert coerce("", "number") is None
    assert parse_bool("Vrai") is True


def test_keys() -> None:
    assert snake_key("Date de valeur") == "date_de_valeur"
    assert snake_key("Débit (€)") == "debit"
    assert snake_key("2026") == "c_2026"
    assert unique_keys(["Montant", "montant", "Montant"]) == ["montant", "montant_2", "montant_3"]
