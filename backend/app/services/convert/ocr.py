"""Reconnaissance de texte (OCR) des PDF scannés et des images, avec Tesseract, **sur la machine**.

- Pages PDF rendues en image par pypdfium2 (déjà installé avec pdfplumber), images ouvertes par Pillow.
- Tesseract est lancé sans shell, image sur l'entrée standard, sortie TSV sur la sortie standard :
  `tesseract stdin stdout -l fra+eng --psm 6 --dpi 300 -c tessedit_create_tsv=1`. Aucune donnée en argument,
  aucun fichier temporaire, aucun réseau. Délai borné par page ; arrêt forcé au-delà.
- Les mots reconnus deviennent des `Word` (texte + position en points PDF, 72 par pouce), exactement comme ceux
  d'un PDF texte : la lecture des relevés (`statement.py`) est la même.
- Langues : celles demandées (`CONVERT_OCR_LANGUAGES`, « fra+eng » par défaut) parmi celles installées ; à défaut,
  ce qui est installé, avec un avertissement.
- Exécutable : `CONVERT_OCR_TESSERACT` (chemin absolu), sinon le PATH, puis les emplacements habituels (Homebrew,
  /usr/local/bin, Program Files) — une app lancée depuis le Finder n'hérite pas du PATH du terminal.
"""

from __future__ import annotations

import io
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median

from pydantic import BaseModel, Field

from app.services.convert.statement import Line, Word, group_lines

A4_WIDTH_POINTS = 595.0
"""Largeur d'une page A4 en points : échelle des images (dont on ignore la résolution réelle)."""

INSTALL_HELP = (
    "Installez Tesseract avec la langue française : macOS « brew install tesseract tesseract-lang », "
    "Windows « winget install UB-Mannheim.TesseractOCR » (cocher French), Linux « sudo apt install tesseract-ocr "
    "tesseract-ocr-fra ». Puis relancez Atelier Convert."
)

Runner = Callable[[list[str], bytes, float, dict[str, str]], tuple[int, bytes, bytes]]


class OcrError(Exception):
    """OCR impossible (Tesseract absent, en échec ou trop long)."""


class OcrStatus(BaseModel):
    """État de la reconnaissance de texte (Réglages)."""

    available: bool
    enabled: bool
    executable: str | None = None
    version: str | None = None
    languages: list[str] = Field(default_factory=list, description="Langues installées.")
    requested: str
    used: str | None = Field(default=None, description="Langues qui seront utilisées.")
    detail: str | None = None


@dataclass
class OcrPage:
    words: list[Word]
    text: str
    confidences: list[float] = field(default_factory=list)


@dataclass
class OcrResult:
    lines: list[Line]
    text: str
    pages: int
    confidence: float | None
    languages: str


def _default_runner(cmd: list[str], data: bytes, timeout: float, env: dict[str, str]) -> tuple[int, bytes, bytes]:
    """Lance Tesseract sans shell ni console ; arrêt forcé au-delà du délai."""
    flags = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
    proc = subprocess.Popen(  # noqa: S603 — commande fixe, chemin absolu, sans shell
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        creationflags=flags,
    )
    try:
        out, err = proc.communicate(data, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        proc.kill()
        proc.communicate()
        raise OcrError(
            f"OCR trop long (plus de {int(timeout)} s pour une page) : réessayez avec moins de pages."
        ) from exc
    return proc.returncode, out, err


def search_dirs(platform: str | None = None, env: dict[str, str] | None = None) -> list[Path]:
    """Emplacements habituels de Tesseract hors du PATH."""
    platform = platform or sys.platform
    env = dict(os.environ) if env is None else env
    if platform == "win32":
        dirs = [env.get("ProgramFiles", r"C:\Program Files"), env.get("ProgramFiles(x86)", r"C:\Program Files (x86)")]
        out = [Path(d) / "Tesseract-OCR" for d in dirs if d]
        if env.get("LOCALAPPDATA"):
            out.append(Path(env["LOCALAPPDATA"]) / "Programs" / "Tesseract-OCR")
        return out
    return [Path("/opt/homebrew/bin"), Path("/usr/local/bin"), Path("/usr/bin"), Path.home() / ".homebrew" / "bin"]


class OcrEngine:
    """Tesseract sur cette machine. `runner` est remplacé dans les tests (jamais le vrai binaire requis)."""

    def __init__(
        self,
        executable: str = "tesseract",
        languages: str = "fra+eng",
        dpi: int = 300,
        timeout: float = 120.0,
        tessdata: Path | None = None,
        enabled: bool = True,
        runner: Runner | None = None,
        psm: int = 6,
    ) -> None:
        self.executable = executable
        self.languages = languages
        self.dpi = dpi
        self.timeout = timeout
        self.tessdata = tessdata
        self.enabled = enabled
        self.runner = runner or _default_runner
        self.psm = psm
        self._lock = threading.Lock()
        self._cache: tuple[float, OcrStatus] | None = None

    # --- découverte ------------------------------------------------------------------------------

    def find(self) -> str | None:
        """Chemin absolu de Tesseract, ou None."""
        name = self.executable.strip() or "tesseract"
        candidate = Path(name).expanduser()
        if candidate.is_absolute():
            return str(candidate) if candidate.is_file() else None
        if os.sep in name or (os.altsep and os.altsep in name):
            return None  # chemin relatif : refusé (on ne lance jamais un programme du dossier courant)
        exe = name + (".exe" if sys.platform == "win32" and not name.lower().endswith(".exe") else "")
        for entry in os.environ.get("PATH", "").split(os.pathsep):
            if entry and Path(entry).is_absolute() and (Path(entry) / exe).is_file():
                return str(Path(entry) / exe)
        for d in search_dirs():
            if (d / exe).is_file():
                return str(d / exe)
        found = shutil.which(exe)
        return found if found and Path(found).is_absolute() else None

    def _env(self) -> dict[str, str]:
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith("TESSDATA")}
        if self.tessdata:
            env["TESSDATA_PREFIX"] = str(self.tessdata.expanduser())
        elif os.environ.get("TESSDATA_PREFIX"):
            env["TESSDATA_PREFIX"] = os.environ["TESSDATA_PREFIX"]
        env["OMP_THREAD_LIMIT"] = env.get("OMP_THREAD_LIMIT", "2")
        return env

    def status(self, refresh: bool = False) -> OcrStatus:
        """Tesseract trouvé, sa version et ses langues (gardé 60 s)."""
        with self._lock:
            if self._cache and not refresh and time.monotonic() - self._cache[0] < 60:
                return self._cache[1]
            status = self._probe()
            self._cache = (time.monotonic(), status)
            return status

    def _probe(self) -> OcrStatus:
        base = {"enabled": self.enabled, "requested": self.languages}
        if not self.enabled:
            return OcrStatus(available=False, detail="OCR désactivé (CONVERT_OCR_ENABLED=false).", **base)
        exe = self.find()
        if exe is None:
            return OcrStatus(available=False, detail=f"Tesseract introuvable. {INSTALL_HELP}", **base)
        env = self._env()
        try:
            code, out, err = self.runner([exe, "--version"], b"", 15, env)
            version_text = (out or err).decode("utf-8", "replace")
            version = version_text.split("\n", 1)[0].replace("tesseract", "").strip() or None
            code, out, err = self.runner([exe, "--list-langs"], b"", 15, env)
        except (OSError, OcrError) as exc:
            return OcrStatus(available=False, executable=exe, detail=f"Tesseract ne répond pas : {exc}", **base)
        langs = [ln.strip() for ln in (out or err).decode("utf-8", "replace").splitlines()[1:] if ln.strip()]
        langs = [lang for lang in langs if lang not in {"osd", "equ"}]
        used = self.pick_languages(langs)
        if used is None:
            detail = f"Aucune langue installée pour Tesseract. {INSTALL_HELP}"
            return OcrStatus(available=False, executable=exe, version=version, languages=langs, detail=detail, **base)
        missing = [lang for lang in self.languages.split("+") if lang and lang not in langs]
        detail = f"Langue(s) manquante(s) : {', '.join(missing)}. {INSTALL_HELP}" if missing else None
        return OcrStatus(
            available=True, executable=exe, version=version, languages=langs, used=used, detail=detail, **base
        )

    def pick_languages(self, installed: list[str]) -> str | None:
        wanted = [lang for lang in self.languages.split("+") if lang in installed]
        if wanted:
            return "+".join(wanted)
        for fallback in ("fra", "eng"):
            if fallback in installed:
                return fallback
        return installed[0] if installed else None

    # --- reconnaissance --------------------------------------------------------------------------

    def recognize(self, image: object, page: int, points_per_pixel: float) -> OcrPage:
        """Mots d'une image (PIL) avec leur position en points ; `page` numérote les pages du document."""
        status = self.status()
        if not status.available or not status.executable or not status.used:
            raise OcrError(status.detail or f"OCR indisponible. {INSTALL_HELP}")
        buf = io.BytesIO()
        image.convert("L").save(buf, "PNG")  # type: ignore[attr-defined]
        cmd = [
            status.executable,
            "stdin",
            "stdout",
            "-l",
            status.used,
            "--psm",
            str(self.psm),
            "--dpi",
            str(self.dpi),
            "-c",
            "tessedit_create_tsv=1",
        ]
        code, out, err = self.runner(cmd, buf.getvalue(), self.timeout, self._env())
        if code != 0:
            message = err.decode("utf-8", "replace").strip().splitlines()[-1:] or ["erreur inconnue"]
            raise OcrError(f"Tesseract a échoué : {message[0]}")
        return parse_tsv(out.decode("utf-8", "replace"), page, points_per_pixel)

    def pdf(self, data: bytes, pages: list[int]) -> OcrResult:
        """OCR des pages choisies d'un PDF (rendues à `dpi`)."""
        import pypdfium2 as pdfium

        doc = pdfium.PdfDocument(data)
        try:
            scale = self.dpi / 72
            results = []
            for number in pages:
                bitmap = doc[number - 1].render(scale=scale)
                results.append(self.recognize(bitmap.to_pil(), number, 1 / scale))
        finally:
            doc.close()
        return self._combine(results)

    def images(self, data: bytes) -> OcrResult:
        """OCR d'une image (PNG, JPEG, TIFF multipage, WebP, BMP)."""
        from PIL import Image, ImageOps

        try:
            img = Image.open(io.BytesIO(data))
        except Exception as exc:  # Pillow : erreurs variées sur un fichier abîmé
            raise OcrError(f"Image illisible : {exc}") from exc
        results = []
        for number, frame in enumerate(_frames(img), start=1):
            frame = ImageOps.exif_transpose(frame) or frame
            if frame.width < 1600:  # photo ou capture petite : agrandie pour l'OCR
                ratio = 2480 / frame.width
                frame = frame.resize((2480, max(1, round(frame.height * ratio))), Image.Resampling.LANCZOS)
            results.append(self.recognize(frame, number, A4_WIDTH_POINTS / frame.width))
        return self._combine(results)

    def _combine(self, pages: list[OcrPage]) -> OcrResult:
        words = [w for p in pages for w in p.words]
        confs = [c for p in pages for c in p.confidences]
        return OcrResult(
            lines=group_lines(words),
            text="\n".join(p.text for p in pages).strip(),
            pages=len(pages),
            confidence=round(sum(confs) / len(confs), 1) if confs else None,
            languages=self.status().used or "",
        )


def _frames(img: object) -> Iterator[object]:
    count = getattr(img, "n_frames", 1)
    for i in range(count):
        img.seek(i)  # type: ignore[attr-defined]
        yield img.copy()  # type: ignore[attr-defined]


_DIGITISH = re.compile(r"^[+\-(]?[\dOoIl|]{1,3}(?:[ .\u00a0]?[\dOoIl|]{3})*[.,][\dOoIl|]{2}\)?[+\-]?$")
_DATEISH = re.compile(r"^[\dOoIl|]{2}[/.\-][\dOoIl|]{2}(?:[/.\-][\dOoIl|]{2,4})?$")


def fix_token(text: str) -> str:
    """Corrige les confusions de l'OCR dans un montant ou une date (« 1O,5O » → « 10,50 », « l2/03 » → « 12/03 »).

    Seulement si le jeton a la forme d'un montant à deux décimales ou d'une date et contient au moins deux chiffres :
    un libellé n'est jamais modifié.
    """
    if sum(c.isdigit() for c in text) < 2 or not (_DIGITISH.match(text) or _DATEISH.match(text)):
        return text
    return text.translate(str.maketrans({"O": "0", "o": "0", "I": "1", "l": "1", "|": "1"}))


def parse_tsv(tsv: str, page: int, points_per_pixel: float) -> OcrPage:
    """Sortie TSV de Tesseract → mots positionnés (points), une même hauteur pour les mots d'une ligne reconnue."""
    rows = tsv.splitlines()
    if not rows:
        return OcrPage(words=[], text="")
    header = rows[0].split("\t")
    index = {name: i for i, name in enumerate(header)}
    needed = ["level", "block_num", "par_num", "line_num", "left", "top", "width", "height", "conf", "text"]
    if any(name not in index for name in needed):
        raise OcrError("Sortie de Tesseract inattendue (TSV).")
    lines: dict[tuple[str, str, str], list[tuple[float, float, float, str, float]]] = {}
    for row in rows[1:]:
        cells = row.split("\t")
        if len(cells) < len(header) or cells[index["level"]] != "5":
            continue
        text = cells[index["text"]].strip()
        try:
            conf = float(cells[index["conf"]])
        except ValueError:
            continue
        if not text or conf < 0 or (conf < 40 and len(text) <= 3):
            continue  # bruit (traits, taches) : mots courts reconnus sans assurance
        left, top = float(cells[index["left"]]), float(cells[index["top"]])
        width = float(cells[index["width"]])
        key = (cells[index["block_num"]], cells[index["par_num"]], cells[index["line_num"]])
        lines.setdefault(key, []).append((left, left + width, top, fix_token(text), conf))
    words: list[Word] = []
    texts: list[str] = []
    confs: list[float] = []
    for items in lines.values():
        line_top = median(t for _, _, t, _, _ in items) * points_per_pixel
        items.sort(key=lambda i: i[0])
        texts.append(" ".join(i[3] for i in items))
        for x0, x1, _, text, conf in items:
            words.append(Word(text=text, x0=x0 * points_per_pixel, x1=x1 * points_per_pixel, top=line_top, page=page))
            confs.append(conf)
    return OcrPage(words=words, text="\n".join(texts), confidences=confs)
