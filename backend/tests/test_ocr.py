"""Reconnaissance de texte (OCR) : lecture du TSV de Tesseract, découverte du moteur, intégration à la conversion.

Moteur simulé par défaut ; les tests « réels » ne tournent que si Tesseract est installé (sinon ignorés).
"""

import os
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.schemas.convert import ParseOptions
from app.services.convert.ocr import OcrEngine, OcrError, OcrPage, OcrResult, fix_token, parse_tsv
from app.services.convert.pipeline import Limits, convert
from app.services.convert.statement import Word, group_lines
from main import create_app

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).parent / "fixtures"
SCAN = ROOT / "samples" / "releve-scanne.pdf"
TEXT_PDF = ROOT / "samples" / "releve-mars-2026.pdf"

HEADER = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext"


def tsv(*words: tuple[str, int, int, int, int, float, str]) -> str:
    """Lignes TSV de mots : (ligne, left, top, width, height, conf, texte)."""
    rows = [HEADER, "1\t1\t0\t0\t0\t0\t0\t0\t2480\t3508\t-1\t"]
    for i, (line, left, top, width, height, conf, text) in enumerate(words):
        rows.append(f"5\t1\t1\t1\t{line}\t{i}\t{left}\t{top}\t{width}\t{height}\t{conf}\t{text}")
    return "\n".join(rows) + "\n"


# --- TSV et corrections ---------------------------------------------------------------------------


def test_parse_tsv_positions_lines_and_noise() -> None:
    page = parse_tsv(
        tsv(
            (1, 100, 400, 80, 30, 96, "02/03"),
            (1, 400, 404, 300, 30, 91, "PRLV"),
            (1, 1700, 398, 120, 30, 88, "84,2O"),
            (2, 400, 450, 40, 30, 12, "~"),  # bruit : court et peu sûr, retiré
            (2, 400, 452, 200, 30, 90, "ECHEANCE"),
        ),
        page=3,
        points_per_pixel=72 / 300,
    )
    assert [w.text for w in page.words] == ["02/03", "PRLV", "84,20", "ECHEANCE"]
    first = page.words[0]
    assert (first.page, round(first.x0, 2), round(first.x1, 2)) == (3, 24.0, 43.2)
    # Les mots d'une même ligne reconnue partagent la même hauteur (médiane) : regroupés en une ligne.
    assert len({w.top for w in page.words[:3]}) == 1
    assert [ln.text for ln in group_lines(page.words)] == ["02/03 PRLV 84,20", "ECHEANCE"]
    assert page.text.splitlines() == ["02/03 PRLV 84,20", "ECHEANCE"]
    assert page.confidences == [96, 91, 88, 90]


def test_parse_tsv_rejects_unexpected_output() -> None:
    with pytest.raises(OcrError):
        parse_tsv("pas du TSV\n1\t2\n", 1, 1.0)
    assert parse_tsv("", 1, 1.0).words == []


@pytest.mark.parametrize(
    ("raw", "fixed"),
    [
        ("1O,5O", "10,50"),
        ("l2/03", "12/03"),
        ("1 234,5O", "1 234,50"),
        ("84,20", "84,20"),
        ("ORANGE", "ORANGE"),  # un libellé n'est jamais modifié
        ("SOLO", "SOLO"),
        ("O,5", "O,5"),  # pas un montant à deux décimales
    ],
)
def test_fix_token(raw: str, fixed: str) -> None:
    assert fix_token(raw) == fixed


# --- Découverte du moteur --------------------------------------------------------------------------


class Fake:
    """Tesseract simulé : version, langues, reconnaissance (TSV fixe) ; garde les commandes reçues."""

    def __init__(self, langs: list[str], output: str = "", code: int = 0) -> None:
        self.langs = langs
        self.output = output
        self.code = code
        self.calls: list[tuple[list[str], bytes, dict[str, str]]] = []

    def __call__(self, cmd: list[str], data: bytes, timeout: float, env: dict[str, str]) -> tuple[int, bytes, bytes]:
        self.calls.append((cmd, data, env))
        if cmd[1] == "--version":
            return 0, b"tesseract 5.3.4\n leptonica-1.82.0\n", b""
        if cmd[1] == "--list-langs":
            return 0, ("List of available languages (2):\n" + "\n".join(self.langs) + "\n").encode(), b""
        return self.code, self.output.encode(), b"Error: image illisible\n" if self.code else b""


def engine(tmp_path: Path, fake: Fake, **kwargs: object) -> OcrEngine:
    exe = tmp_path / "tesseract"
    exe.write_text("")
    return OcrEngine(executable=str(exe), runner=fake, **kwargs)  # type: ignore[arg-type]


def test_status_languages(tmp_path: Path) -> None:
    ok = engine(tmp_path, Fake(["eng", "fra", "osd"])).status()
    assert ok.available and ok.used == "fra+eng" and ok.version == "5.3.4" and ok.languages == ["eng", "fra"]
    assert ok.detail is None
    english = engine(tmp_path, Fake(["eng"])).status()
    assert english.available and english.used == "eng" and "fra" in (english.detail or "")
    none = engine(tmp_path, Fake([])).status()
    assert not none.available and "Aucune langue" in (none.detail or "")


def test_status_missing_or_disabled(tmp_path: Path) -> None:
    missing = OcrEngine(executable=str(tmp_path / "absent"), runner=Fake(["fra"])).status()
    assert not missing.available and "brew install tesseract" in (missing.detail or "")
    assert OcrEngine(executable="dossier/tesseract").find() is None  # chemin relatif refusé
    off = engine(tmp_path, Fake(["fra"]), enabled=False).status()
    assert not off.available and "désactivé" in (off.detail or "")


def test_recognize_sends_image_on_stdin(tmp_path: Path) -> None:
    from PIL import Image

    fake = Fake(["fra", "eng"], output=tsv((1, 300, 300, 120, 30, 95, "Bonjour")))
    eng = engine(tmp_path, fake, tessdata=tmp_path / "tessdata", dpi=300)
    page = eng.recognize(Image.new("RGB", (600, 400), "white"), 1, 72 / 300)
    assert [w.text for w in page.words] == ["Bonjour"]
    cmd, data, env = fake.calls[-1]
    assert cmd[1:] == ["stdin", "stdout", "-l", "fra+eng", "--psm", "6", "--dpi", "300", "-c", "tessedit_create_tsv=1"]
    assert data.startswith(b"\x89PNG")  # l'image passe par l'entrée standard, jamais en argument
    assert env["TESSDATA_PREFIX"] == str(tmp_path / "tessdata")
    failing = engine(tmp_path, Fake(["fra"], code=1))
    with pytest.raises(OcrError, match="image illisible"):
        failing.recognize(Image.new("L", (10, 10)), 1, 1.0)


# --- Conversion -----------------------------------------------------------------------------------


class Recorder(OcrEngine):
    """Moteur dont la reconnaissance renvoie des mots fixes (relevé de deux opérations)."""

    def __init__(self, available: bool = True) -> None:
        super().__init__(executable="tesseract")
        self.ok = available
        self.calls: list[str] = []

    def status(self, refresh: bool = False):  # type: ignore[no-untyped-def]
        from app.services.convert.ocr import OcrStatus

        return OcrStatus(
            available=self.ok, enabled=True, requested="fra+eng", used="fra+eng" if self.ok else None,
            detail=None if self.ok else "Tesseract introuvable. Installez Tesseract…",
        )  # fmt: skip

    def _result(self) -> OcrResult:
        words = [
            Word("Date", 40, 70, 100), Word("Libellé", 100, 140, 100), Word("Débit", 400, 430, 100),
            Word("Crédit", 470, 500, 100),
            Word("05/01/2026", 40, 90, 120), Word("PRLV", 100, 130, 120), Word("12,50", 405, 430, 120),
            Word("06/01/2026", 40, 90, 135), Word("VIREMENT", 100, 150, 135), Word("100,00", 470, 500, 135),
        ]  # fmt: skip
        return OcrResult(
            lines=group_lines(words), text="Date Libellé Débit Crédit", pages=1, confidence=91.0, languages="fra+eng"
        )

    def pdf(self, data: bytes, pages: list[int]) -> OcrResult:
        self.calls.append(f"pdf:{pages}")
        return self._result()

    def images(self, data: bytes) -> OcrResult:
        self.calls.append("image")
        return self._result()


def test_scanned_pdf_goes_through_ocr() -> None:
    rec = Recorder()
    info, table = convert(SCAN.read_bytes(), SCAN.name, ParseOptions(), Limits(ocr=rec))
    assert rec.calls == ["pdf:[1, 2]"]
    assert (info.ocr, info.ocr_confidence, info.ocr_languages) == (True, 91.0, "fra+eng")
    assert table.detected == "Relevé bancaire · 2 opération(s) · OCR"
    assert [r["montant"] for r in table.rows] == [-12.5, 100.0]
    assert "confiance moyenne 91 %" in table.warnings[0]


def test_ocr_modes_on_a_text_pdf() -> None:
    rec = Recorder()
    _, table = convert(TEXT_PDF.read_bytes(), TEXT_PDF.name, ParseOptions(), Limits(ocr=rec))
    assert rec.calls == [] and len(table.rows) == 18  # PDF texte : pas d'OCR en automatique
    info, forced = convert(TEXT_PDF.read_bytes(), TEXT_PDF.name, ParseOptions(ocr="always", pages="2"), Limits(ocr=rec))
    assert rec.calls == ["pdf:[2]"] and info.ocr and len(forced.rows) == 2
    _, never = convert(SCAN.read_bytes(), SCAN.name, ParseOptions(ocr="never"), Limits(ocr=rec))
    assert never.rows == [] and never.detected == "PDF sans texte"


def test_ocr_page_limit() -> None:
    rec = Recorder()
    _, table = convert(SCAN.read_bytes(), SCAN.name, ParseOptions(), Limits(ocr=rec, max_ocr_pages=1))
    assert rec.calls == ["pdf:[1]"]
    assert any("limité aux 1 premières pages" in w for w in table.warnings)


def test_ocr_unavailable_explains_how_to_install() -> None:
    _, table = convert(SCAN.read_bytes(), SCAN.name, ParseOptions(), Limits(ocr=Recorder(available=False)))
    assert table.rows == [] and "Tesseract introuvable" in table.warnings[0]
    _, image = convert((FIXTURES / "releve-photo.jpg").read_bytes(), "photo.jpg", ParseOptions(), Limits())
    assert image.detected == "Image sans texte" and "brew install tesseract" in image.warnings[0]
    _, forced = convert(TEXT_PDF.read_bytes(), "x.pdf", ParseOptions(ocr="always"), Limits(ocr=Recorder(False)))
    assert len(forced.rows) == 18 and any("OCR demandé mais indisponible" in w for w in forced.warnings)


def test_image_goes_through_ocr() -> None:
    rec = Recorder()
    info, table = convert((FIXTURES / "releve-photo.jpg").read_bytes(), "photo.jpg", ParseOptions(), Limits(ocr=rec))
    assert info.kind == "image" and info.ocr and rec.calls == ["image"]
    assert table.detected.endswith("· OCR")


def test_ocr_route_and_upload(settings: Settings) -> None:
    with TestClient(create_app(settings)) as client:
        status = client.get("/api/ocr").json()
        assert status["available"] is False and "désactivé" in status["detail"]
        r = client.post("/api/conversions", files={"file": ("photo.jpg", (FIXTURES / "releve-photo.jpg").read_bytes())})
        assert r.status_code == 201 and r.json()["source"]["kind"] == "image"
        assert "OCR" in r.json()["warnings"][0]


def test_unreadable_amount_is_kept_and_flagged() -> None:
    from app.services.convert.statement import extract_statement

    words = [
        Word("Date", 40, 60, 100), Word("Opération", 100, 150, 100), Word("Débit", 400, 430, 100),
        Word("Crédit", 470, 500, 100),
        Word("30/03/2026", 40, 90, 120), Word("MARCHE", 100, 140, 120), Word("41,37", 405, 430, 120),
        Word("31/03/2026", 40, 90, 135), Word("INTERETS", 100, 150, 135), Word("412", 482, 500, 135),
    ]  # fmt: skip
    table = extract_statement(group_lines(words), "", ParseOptions())
    assert table is not None and len(table.rows) == 2
    last = table.rows[1]
    assert (last["libelle"], last["debit"], last["credit"], last["montant"]) == ("INTERETS", None, None, None)
    assert any("sans montant lisible" in w and "« 412 »" in w for w in table.warnings)


def test_page_dataclass() -> None:
    assert OcrPage(words=[], text="").confidences == []


# --- Tesseract réel (si installé) -----------------------------------------------------------------

REAL = OcrEngine(tessdata=Path(os.environ["TESSDATA_PREFIX"]) if os.environ.get("TESSDATA_PREFIX") else None)
real = pytest.mark.skipif(shutil.which("tesseract") is None or not REAL.status().available, reason="Tesseract absent")


@real
def test_real_tesseract_scanned_statement() -> None:
    info, table = convert(SCAN.read_bytes(), SCAN.name, ParseOptions(), Limits(ocr=REAL))
    assert info.ocr and (info.ocr_confidence or 0) > 80
    assert len(table.rows) == 18
    assert table.rows[2]["credit"] == 2450.0
    assert table.statement is not None
    if "fra" in (info.ocr_languages or ""):
        assert table.statement.balance_check == "ok"
    else:  # anglais seul : un petit montant peut être mal lu, la ligne reste et le contrôle le signale
        assert table.statement.balance_check in {"ok", "mismatch"}


@real
def test_real_tesseract_photo() -> None:
    _, table = convert((FIXTURES / "releve-photo.jpg").read_bytes(), "photo.jpg", ParseOptions(), Limits(ocr=REAL))
    assert len(table.rows) >= 10 and table.rows[0]["debit"] == 84.2
