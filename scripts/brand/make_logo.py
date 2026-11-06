"""Icône d'Atelier Convert (charte v2 « Linear » de la suite, docs/SUITE.md §1.6) et fichiers dérivés.

L'icône est celle de la marque commune (`.atelier-brand__tile` d'atelier-brand.css, `.at-appicon` du portail) :
carré arrondi (rayon 22 %) rempli d'un dégradé vertical de la signature (en haut 78 % de la signature mêlée de blanc
dans l'espace OKLab, en bas la signature pure), liseré intérieur, glyphe Lucide `arrow-left-right` en trait blanc.

Produit :
- frontend/public/favicon-64.png et apple-touch-icon.png (180 px, fond plein, iOS arrondit lui-même) ;
- scripts/macos/icon.png (1024 px, grille des icônes macOS : carré de 824 px centré) ;
- scripts/windows/atelier-convert.ico (16 à 256 px) ;
- docs/brand/logo-atelier-convert.svg et .png (source et aperçu).

Rendu par Chromium (Playwright). À relancer seulement si l'icône change :  python3 scripts/brand/make_logo.py
"""

from __future__ import annotations

import io
import math
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]

# Signature d'Atelier Convert (atelier-brand.css : --atelier-sig-convert).
SIGNATURE = "#9d6d1c"
# Lucide `arrow-left-right` (ISC), même dessin que le symbole `app-convert` du portail.
GLYPH = '<path d="M8 3 4 7l4 4"/><path d="M4 7h16"/><path d="m16 21 4-4-4-4"/><path d="M20 17H4"/>'


def _hex(color: str) -> tuple[float, float, float]:
    color = color.lstrip("#")
    return tuple(int(color[i : i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def _to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _to_srgb(c: float) -> float:
    c = max(0.0, min(1.0, c))
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def _oklab(rgb: tuple[float, float, float]) -> tuple[float, float, float]:
    r, g, b = (_to_linear(c) for c in rgb)
    lms = (
        0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b,
        0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b,
        0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b,
    )
    l_, m_, s_ = (math.copysign(abs(v) ** (1 / 3), v) for v in lms)
    return (
        0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
    )


def _from_oklab(lab: tuple[float, float, float]) -> str:
    L, a, b = lab
    l_ = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    rgb = (
        4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
        -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
        -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_,
    )
    return "#" + "".join(f"{round(_to_srgb(c) * 255):02x}" for c in rgb)


def mix(color: str, other: str, weight: float) -> str:
    """`color-mix(in oklab, color weight, other)`."""
    a, b = _oklab(_hex(color)), _oklab(_hex(other))
    return _from_oklab(tuple(weight * x + (1 - weight) * y for x, y in zip(a, b, strict=True)))  # type: ignore[arg-type]


TOP = mix(SIGNATURE, "#ffffff", 0.78)


def icon_svg(size: int = 1024, inset: float = 0) -> str:
    """Icône carrée (viewBox 100) ; `inset` : marge transparente autour du carré, en unités de la vue."""
    side = 100 - 2 * inset
    r = side * 0.22
    glyph = side * 0.62
    scale = glyph / 24
    offset = inset + (side - glyph) / 2
    hair = side / 100  # liseré fin (0,5 px à 50 px), reflet clair en haut
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="{size}" height="{size}">
  <defs>
    <linearGradient id="sig" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{TOP}"/><stop offset="1" stop-color="{SIGNATURE}"/>
    </linearGradient>
    <clipPath id="shape"><rect x="{inset}" y="{inset}" width="{side}" height="{side}" rx="{r:.3f}"/></clipPath>
  </defs>
  <rect x="{inset}" y="{inset}" width="{side}" height="{side}" rx="{r:.3f}" fill="url(#sig)"/>
  <g clip-path="url(#shape)" fill="none">
    <rect x="{inset}" y="{inset}" width="{side}" height="{side}" rx="{r:.3f}" stroke="#000" stroke-opacity=".14"
      stroke-width="{hair:.3f}"/>
    <rect x="{inset}" y="{inset + hair * 0.6:.3f}" width="{side}" height="{side}" rx="{r:.3f}" stroke="#fff"
      stroke-opacity=".22" stroke-width="{hair * 0.6:.3f}"/>
  </g>
  <g transform="translate({offset:.3f} {offset:.3f}) scale({scale:.4f})" fill="none" stroke="#fff" stroke-width="2.1"
    stroke-linecap="round" stroke-linejoin="round">{GLYPH}</g>
</svg>"""


def render(svg: str, size: int) -> Image.Image:
    html = f"<html><body style='margin:0;background:transparent'>{svg}</body></html>"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": size, "height": size}, device_scale_factor=1)
        page.set_content(html)
        png = page.locator("svg").screenshot(omit_background=True)
        browser.close()
    return Image.open(io.BytesIO(png)).convert("RGBA")


def main() -> None:
    full = render(icon_svg(1024), 1024)

    docs = ROOT / "docs" / "brand"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "logo-atelier-convert.svg").write_text(icon_svg(1024) + "\n", encoding="utf-8")
    full.save(docs / "logo-atelier-convert.png", optimize=True)

    # macOS : carré de 824 px centré sur 1024 (marge de 100 px), comme les icônes du système.
    render(icon_svg(1024, inset=100 / 1024 * 100), 1024).save(ROOT / "scripts" / "macos" / "icon.png", optimize=True)
    ico = ROOT / "scripts" / "windows" / "atelier-convert.ico"
    full.resize((256, 256), Image.LANCZOS).save(
        ico, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    )

    public = ROOT / "frontend" / "public"
    public.mkdir(parents=True, exist_ok=True)
    full.resize((64, 64), Image.LANCZOS).save(public / "favicon-64.png", optimize=True)
    # Écran d'accueil iOS : carré plein (iOS applique son propre arrondi), dégradé jusqu'aux bords.
    square = render(icon_svg(1024).replace(f'rx="{100 * 0.22:.3f}"', 'rx="0"'), 1024)
    square.convert("RGB").resize((180, 180), Image.LANCZOS).save(public / "apple-touch-icon.png", optimize=True)
    print("Icônes écrites.")


if __name__ == "__main__":
    main()
