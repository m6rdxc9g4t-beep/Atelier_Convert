"""Chaîne de conversion : PDF de relevés (plusieurs mises en page), CSV, TXT, Excel, OFX, QIF, JSON."""

import io
import json
from pathlib import Path

import pytest
from openpyxl import Workbook

from app.schemas.convert import ParseOptions
from app.services.convert.pipeline import ConvertError, convert, detect_kind
from app.services.convert.statement import Line, Word, extract_statement, group_lines, merge_numbers

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "samples"
FIXTURES = Path(__file__).parent / "fixtures"


def run(path: Path, **options: object):
    return convert(path.read_bytes(), path.name, ParseOptions(**options))  # type: ignore[arg-type]


# --- PDF ------------------------------------------------------------------------------------------


def test_pdf_statement_debit_credit_columns() -> None:
    """Relevé sur deux pages : dates sans année, dates de valeur, libellés sur deux lignes, « À reporter »."""
    info, table = run(SAMPLES / "releve-mars-2026.pdf")
    assert info.kind == "pdf" and info.pages == 2
    assert table.detected.startswith("Relevé bancaire · 18 opération(s)")
    assert [c.key for c in table.columns] == ["date", "date_de_valeur", "libelle", "debit", "credit", "montant"]
    first, salary = table.rows[0], table.rows[2]
    assert first["date"] == "2026-03-02" and first["debit"] == 84.2 and first["credit"] is None
    assert first["libelle"] == "PRLV SEPA EDF ENERGIE ECH/020326 ID EMETTEUR/FR12ZZZ000001"
    assert salary["credit"] == 2450.0 and salary["montant"] == 2450.0
    assert "SALAIRE FEVRIER 2026" in str(salary["libelle"])
    s = table.statement
    assert s is not None
    assert (s.opening_balance, s.closing_balance) == (1523.4, 2746.17)
    assert s.balance_check == "ok" and s.balance_gap == 0.0
    assert (s.start, s.end) == ("2026-03-02", "2026-03-31")
    assert not any("reporter" in str(r["libelle"]).lower() for r in table.rows)


def test_pdf_statement_signed_amount_and_balance() -> None:
    _, table = run(FIXTURES / "releve-montant-solde.pdf")
    assert [c.key for c in table.columns][-1] == "solde"
    assert [r["montant"] for r in table.rows] == [-3.8, 120.0, -18.9, -10.99, 25.0]
    assert table.statement is not None and table.statement.balance_check == "ok"
    assert table.statement.opening_balance == 500.0


def test_pdf_statement_without_header_uses_positions() -> None:
    """Sans en-tête : débit et crédit déduits de la position des montants ; un montant dans le libellé y reste."""
    _, table = run(FIXTURES / "releve-sans-entete.pdf")
    assert [r["debit"] for r in table.rows] == [45.1, None, 37.4, 1234.56, None]
    assert [r["credit"] for r in table.rows] == [None, 1980.0, None, None, 200.0]
    assert table.rows[0]["date"] == "2026-01-05"


def test_pdf_tables_mode() -> None:
    _, table = run(FIXTURES / "tableau.pdf")
    assert table.detected.startswith("Tableaux du PDF")
    assert [(c.label, c.type) for c in table.columns] == [
        ("Article", "text"),
        ("Quantité", "number"),
        ("Prix unitaire", "currency"),
        ("Réception", "date"),
    ]
    assert table.rows[1] == {
        "article": "Ciseau à bois",
        "quantite": 12.0,
        "prix_unitaire": 8.5,
        "reception": "2026-02-13",
    }


def test_pdf_text_mode_keeps_text_for_ai() -> None:
    _, table = run(SAMPLES / "releve-mars-2026.pdf", pdf_mode="text")
    assert [c.key for c in table.columns] == ["texte"]
    assert table.raw_text and "RELEVÉ DE COMPTE COURANT" in table.raw_text
    assert any("Structurer avec l'IA" in w for w in table.warnings)


def test_pdf_pages_option() -> None:
    info, table = run(SAMPLES / "releve-mars-2026.pdf", pages="2")
    assert info.pages == 2
    assert all(r["date"] >= "2026-03-22" for r in table.rows)  # type: ignore[operator]
    assert "(pages 2)" in table.detected


def test_year_option_and_missing_year_warning() -> None:
    words = [
        Word("Date", 40, 60, 100), Word("Libellé", 100, 130, 100), Word("Débit", 400, 430, 100),
        Word("02/03", 40, 62, 120), Word("CAFE", 100, 120, 120), Word("3,50", 410, 430, 120),
        Word("05/03", 40, 62, 135), Word("PAIN", 100, 120, 135), Word("1,20", 410, 430, 135),
    ]  # fmt: skip
    lines = group_lines(words)
    table = extract_statement(lines, "aucune date complète", ParseOptions())
    assert table is not None and table.rows[0]["date"] == "02/03"
    assert any("sans année" in w for w in table.warnings)
    fixed = extract_statement(lines, "", ParseOptions(year=2024))
    assert fixed is not None and fixed.rows[0]["date"] == "2024-03-02"


def test_december_operations_in_january_statement_take_previous_year() -> None:
    words = [
        Word("Date", 40, 60, 100), Word("Opération", 100, 140, 100), Word("Débit", 400, 430, 100),
        Word("30/12", 40, 62, 120), Word("LOYER", 100, 120, 120), Word("500,00", 400, 430, 120),
        Word("03/01", 40, 62, 135), Word("CAFE", 100, 120, 135), Word("2,00", 410, 430, 135),
    ]  # fmt: skip
    table = extract_statement(group_lines(words), "Relevé du 01/01/2026 au 31/01/2026", ParseOptions())
    assert table is not None
    assert [r["date"] for r in table.rows] == ["2025-12-30", "2026-01-03"]


def test_merge_numbers_rejoins_thousands() -> None:
    merged = merge_numbers([Word("1", 400, 405, 10), Word("234,56", 408, 430, 10), Word("€", 432, 438, 10)])
    assert [w.text for w in merged] == ["1 234,56"]
    apart = merge_numbers([Word("12", 100, 110, 10), Word("345,00", 300, 330, 10)])
    assert len(apart) == 2


def test_scanned_pdf_without_text() -> None:
    _, table = run(FIXTURES / "scan.pdf")
    assert table.rows == [] and "OCR" in table.warnings[0]


def test_broken_pdf_is_refused() -> None:
    with pytest.raises(ConvertError):
        convert(b"%PDF-1.4 abime", "abime.pdf", ParseOptions())


# --- Fichiers texte -------------------------------------------------------------------------------


def test_bank_csv_windows_1252_with_preamble() -> None:
    info, table = run(SAMPLES / "export-banque.csv")
    assert (info.encoding, info.delimiter) == ("cp1252", ";")
    assert table.detected == "Relevé bancaire · 18 opération(s)"
    assert any("préambule" in w for w in table.warnings)
    assert table.rows[0]["libelle"] == "PRLV SEPA EDF ENERGIE ECH/020326 ID EMETTEUR/FR12ZZZ000001"
    assert table.rows[0]["date_de_valeur"] == "2026-03-02"


def test_csv_raw_profile_keeps_original_columns() -> None:
    _, table = run(SAMPLES / "export-banque.csv", profile="raw")
    assert [c.label for c in table.columns] == ["Date", "Date de valeur", "Libellé", "Débit euros", "Crédit euros"]
    assert table.columns[3].type == "currency"


def test_csv_english_with_signed_amount() -> None:
    data = b"Date,Description,Amount,Balance\n2026-03-01,Coffee,-3.50,96.50\n2026-03-02,Refund,10.00,106.50\n"
    _, table = convert(data, "export.csv", ParseOptions())
    assert [c.key for c in table.columns] == ["date", "libelle", "debit", "credit", "montant", "solde"]
    assert table.rows[0] == {
        "date": "2026-03-01",
        "libelle": "Coffee",
        "debit": 3.5,
        "credit": None,
        "montant": -3.5,
        "solde": 96.5,
    }
    assert table.statement is not None and table.statement.balance_check == "ok"


def test_generic_csv_not_a_statement() -> None:
    data = b"Nom;Ville;Inscrit\nAda;Lyon;oui\nGrace;Nantes;non\n"
    _, table = convert(data, "liste.csv", ParseOptions())
    assert table.statement is None
    assert [c.type for c in table.columns] == ["text", "text", "boolean"]
    assert table.rows[0] == {"nom": "Ada", "ville": "Lyon", "inscrit": True}


def test_forced_statement_profile_warns_when_impossible() -> None:
    data = b"Nom;Ville\nAda;Lyon\nGrace;Nantes\n"
    _, table = convert(data, "liste.csv", ParseOptions(profile="statement"))
    assert any("impossible" in w for w in table.warnings)


def test_txt_aligned_columns() -> None:
    text = (
        "DATE        LIBELLE                      MONTANT\n"
        "01/03/2026  ABONNEMENT                   -12,99\n"
        "02/03/2026  VIREMENT RECU                250,00\n"
        "03/03/2026  CARTE SUPERMARCHE            -45,10\n"
    )
    info, table = convert(text.encode(), "releve.txt", ParseOptions())
    assert info.delimiter == " "
    assert [r["montant"] for r in table.rows] == [-12.99, 250.0, -45.1]


def test_txt_free_text_single_column() -> None:
    info, table = convert(b"Bonjour\nCeci n'est pas une table\n", "note.txt", ParseOptions())
    assert [c.key for c in table.columns] == ["texte"]
    assert table.raw_text


def test_options_delimiter_header_skip() -> None:
    data = b"titre a ignorer\n1|2|3\n4|5|6\n"
    _, table = convert(data, "x.txt", ParseOptions(delimiter="|", header=False, skip_rows=1))
    assert [c.label for c in table.columns] == ["Colonne 1", "Colonne 2", "Colonne 3"]
    assert table.rows[1] == {"colonne_1": 4.0, "colonne_2": 5.0, "colonne_3": 6.0}


# --- Excel, OFX, QIF, JSON -------------------------------------------------------------------------


def test_xlsx_with_two_sheets() -> None:
    from datetime import datetime

    wb = Workbook()
    ws = wb.active
    ws.title = "Opérations"
    ws.append(["Date", "Libellé", "Montant"])
    ws.append([datetime(2026, 3, 1), "Loyer", -890])
    ws.append([datetime(2026, 3, 4), "Salaire", 2450.5])
    other = wb.create_sheet("Notes")
    other.append(["Texte"])
    other.append(["bonjour"])
    buf = io.BytesIO()
    wb.save(buf)
    info, table = convert(buf.getvalue(), "comptes.xlsx", ParseOptions())
    assert info.sheets == ["Opérations", "Notes"]
    assert table.rows[1]["credit"] == 2450.5 and table.rows[0]["date"] == "2026-03-01"
    _, notes = convert(buf.getvalue(), "comptes.xlsx", ParseOptions(sheet="Notes"))
    assert notes.rows == [{"texte": "bonjour"}]


def test_ofx() -> None:
    info, table = run(SAMPLES / "operations.ofx")
    assert info.kind == "ofx" and len(table.rows) == 18
    assert table.rows[2]["credit"] == 2450.0 and table.rows[2]["reference"] == "EX20260304003"
    assert table.statement is not None and table.statement.closing_balance == 2087.15


def test_qif() -> None:
    _, table = run(FIXTURES / "export.qif")
    assert table.rows[0]["categorie"] == "Loisirs" and table.rows[0]["debit"] == 32.5
    assert table.rows[1]["reference"] == "1234"


def test_json_atelier_table_and_list() -> None:
    doc = {
        "format": "atelier-table/1",
        "name": "x",
        "columns": [
            {"key": "titre", "label": "Titre", "type": "string"},
            {"key": "h", "label": "Heures", "type": "number"},
        ],
        "rows": [{"titre": "A", "h": 2}, {"titre": "B", "h": 3.5}],
    }
    _, table = convert(json.dumps(doc).encode(), "t.json", ParseOptions())
    assert [c.label for c in table.columns] == ["Titre", "Heures"] and table.rows[1]["heures"] == 3.5
    _, nested = convert(json.dumps({"items": [{"a": 1, "b": {"c": "x"}}]}).encode(), "n.json", ParseOptions())
    assert [c.key for c in nested.columns] == ["a", "b_c"]
    with pytest.raises(ConvertError):
        convert(b"{bad json", "x.json", ParseOptions())


def test_detect_kind() -> None:
    assert detect_kind("x.bin", b"%PDF-1.7") == "pdf"
    assert detect_kind("x.txt", b"OFXHEADER:100") == "ofx"
    assert detect_kind("x", b"!Type:Bank\n") == "qif"
    assert detect_kind("scan.bin", b"\x89PNG\r\n") == "image"
    assert detect_kind("photo.jpg", b"\xff\xd8\xff\xe0") == "image"
    assert detect_kind("x", b"RIFF\x00\x00\x00\x00WEBPVP8") == "image"
    with pytest.raises(ConvertError) as err:
        detect_kind("video.mp4", b"\x00\x00\x00 ftypisom")
    assert err.value.status_code == 415


def test_lines_are_grouped_by_position() -> None:
    lines = group_lines([Word("b", 50, 60, 100.8), Word("a", 10, 20, 100), Word("c", 10, 20, 120)])
    assert [ln.text for ln in lines] == ["a b", "c"]
    assert isinstance(lines[0], Line)
