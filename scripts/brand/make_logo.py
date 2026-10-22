"""Logo d'Atelier Convert (style « néon holographique 3D » de la suite) et icônes dérivées.

Produit, à partir d'un SVG construit ici :
- frontend/src/assets/logo-atelier-convert.webp (fenêtre « À propos », 576 px) ;
- frontend/public/favicon-64.png et apple-touch-icon.png (tuile de l'étiquette du logo) ;
- scripts/macos/icon.png (1024 px) et scripts/windows/atelier-convert.ico (16 à 256 px) ;
- docs/brand/logo-atelier-convert.svg et .png (source et aperçu).

Rendu par Chromium (Playwright) pour les filtres SVG et la police de marque (Nunito, embarquée en base64).
À relancer seulement si le logo change :  python3 scripts/brand/make_logo.py
"""

from __future__ import annotations

import base64
import io
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
FONT = ROOT / "frontend" / "src" / "styles" / "atelier-brand" / "nunito-latin-wght-normal.woff2"

GOLD = "#C9951D"

ARROWS = '<path d="m16 3 4 4-4 4"/><path d="M20 7H4"/><path d="m8 21-4-4 4-4"/><path d="M4 17h16"/>'
LANDMARK = (
    '<path d="M10 18v-7"/><path d="M11.12 2.198a2 2 0 0 1 1.76.006l7.866 3.847c.476.233.31.949-.22.949H3.474c-.53 0-.695'
    '-.716-.22-.949z"/><path d="M14 18v-7"/><path d="M18 18v-7"/><path d="M3 22h18"/><path d="M6 18v-7"/>'
)


def defs() -> str:
    font = base64.b64encode(FONT.read_bytes()).decode()
    return f"""
  <defs>
    <style>
      @font-face {{ font-family: "Atelier Brand"; src: url(data:font/woff2;base64,{font}) format("woff2"); font-weight: 200 1000; }}
      .brand {{ font-family: "Atelier Brand", sans-serif; }}
    </style>
    <linearGradient id="gold" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#FFF1BF"/><stop offset=".28" stop-color="#F2C45A"/>
      <stop offset=".55" stop-color="{GOLD}"/><stop offset=".8" stop-color="#8E5E0E"/><stop offset="1" stop-color="#F5D27A"/>
    </linearGradient>
    <linearGradient id="goldV" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#FFE9A8"/><stop offset=".45" stop-color="#E0AE3C"/><stop offset="1" stop-color="#8E5E0E"/>
    </linearGradient>
    <linearGradient id="glass" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#16506E"/><stop offset=".55" stop-color="#0B2E44"/><stop offset="1" stop-color="#071C2B"/>
    </linearGradient>
    <linearGradient id="glassLight" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#9BEFFF" stop-opacity=".95"/><stop offset=".5" stop-color="#2FC4EE" stop-opacity=".85"/>
      <stop offset="1" stop-color="#0E7FB0" stop-opacity=".9"/>
    </linearGradient>
    <linearGradient id="cyanBar" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#5BE3FF"/><stop offset="1" stop-color="#1BA9E0"/>
    </linearGradient>
    <linearGradient id="sheen" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#FFFFFF" stop-opacity=".35"/><stop offset=".35" stop-color="#FFFFFF" stop-opacity=".06"/>
      <stop offset="1" stop-color="#FFFFFF" stop-opacity="0"/>
    </linearGradient>
    <radialGradient id="coinTop" cx=".4" cy=".35" r=".8">
      <stop offset="0" stop-color="#FFF4C9"/><stop offset=".5" stop-color="#E7B544"/><stop offset="1" stop-color="#9A6812"/>
    </radialGradient>
    <filter id="glowGold" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur in="SourceGraphic" stdDeviation="10" result="b"/>
      <feColorMatrix in="b" type="matrix" values="1 0 0 0 0.25  0 1 0 0 0.15  0 0 1 0 0  0 0 0 .9 0" result="g"/>
      <feMerge><feMergeNode in="g"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <filter id="glowCyan" x="-40%" y="-40%" width="180%" height="180%">
      <feGaussianBlur in="SourceGraphic" stdDeviation="6" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <filter id="soft" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="18"/>
    </filter>
  </defs>"""


def framed(x: float, y: float, w: float, h: float, r: float, rim: float = 12) -> str:
    """Panneau de verre cerclé d'or néon (halo + trait métallique + reflet)."""
    return f"""
    <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="none" stroke="{GOLD}" stroke-width="{rim + 14}"
      opacity=".55" filter="url(#soft)"/>
    <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="url(#glass)"/>
    <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="none" stroke="url(#gold)" stroke-width="{rim}"
      filter="url(#glowGold)"/>
    <rect x="{x + rim}" y="{y + rim}" width="{w - 2 * rim}" height="{h - 2 * rim}" rx="{max(r - rim, 4)}" fill="none"
      stroke="#7DE8FF" stroke-opacity=".55" stroke-width="2.5"/>
    <rect x="{x + rim}" y="{y + rim}" width="{w - 2 * rim}" height="{(h - 2 * rim) * .45}" rx="{max(r - rim, 4)}"
      fill="url(#sheen)"/>"""


def pdf_doc(x: float, y: float) -> str:
    """Relevé PDF : feuille de verre, coin plié, lignes d'opérations, montants en or."""
    rows = []
    for i in range(6):
        yy = y + 120 + i * 30
        rows.append(f'<rect x="{x + 22}" y="{yy}" width="34" height="11" rx="5" fill="#7DE8FF" opacity=".75"/>')
        rows.append(f'<rect x="{x + 64}" y="{yy}" width="{70 - (i % 3) * 12}" height="11" rx="5" fill="url(#cyanBar)"/>')
        rows.append(
            f'<rect x="{x + 146}" y="{yy}" width="34" height="11" rx="5" fill="{GOLD if i % 2 else "#F2C45A"}"/>'
        )
    return f"""
    <g filter="url(#glowCyan)">
      <path d="M{x} {y + 14} a14 14 0 0 1 14 -14 h134 l52 52 v214 a14 14 0 0 1 -14 14 h-172 a14 14 0 0 1 -14 -14 z"
        fill="url(#glassLight)" fill-opacity=".28" stroke="#8FEFFF" stroke-width="4"/>
      <path d="M{x + 148} {y} v38 a14 14 0 0 0 14 14 h38" fill="#8FEFFF" fill-opacity=".35" stroke="#8FEFFF" stroke-width="4"/>
    </g>
    <rect x="{x + 20}" y="{y + 26}" width="86" height="40" rx="10" fill="url(#goldV)"/>
    <text x="{x + 63}" y="{y + 56}" text-anchor="middle" class="brand" font-weight="900" font-size="28" fill="#2A1A02">PDF</text>
    <g transform="translate({x + 122} {y + 72}) scale(1.45)" fill="none" stroke="#9BF0FF" stroke-width="2"
      stroke-linecap="round" stroke-linejoin="round">{LANDMARK}</g>
    {"".join(rows)}"""


def sheet(x: float, y: float) -> str:
    """Table de destination : en-tête or, cellules cyan."""
    cells = []
    cols = [x + 16, x + 72, x + 128]
    for c, cx in enumerate(cols):
        cells.append(f'<rect x="{cx}" y="{y + 18}" width="50" height="26" rx="6" fill="url(#goldV)"/>')
        for r in range(6):
            yy = y + 56 + r * 32
            gold = (r == 2 and c == 2) or (r == 4 and c == 1)
            fill = "url(#goldV)" if gold else "url(#cyanBar)"
            opacity = "1" if gold or c != 1 else ".8"
            cells.append(f'<rect x="{cx}" y="{yy}" width="50" height="22" rx="6" fill="{fill}" opacity="{opacity}"/>')
    return f"""
    <g filter="url(#glowCyan)">
      <rect x="{x}" y="{y}" width="194" height="262" rx="16" fill="url(#glassLight)" fill-opacity=".22"
        stroke="#8FEFFF" stroke-width="4"/>
    </g>
    {"".join(cells)}"""


def arrows(cx: float, cy: float) -> str:
    """Flèches de conversion (icône arrow-right-left) en néon : or vers la table, cyan au retour.

    Filtres en `userSpaceOnUse` : un trait horizontal a une boîte de hauteur nulle, qu'un filtre relatif efface.
    """
    left, right = cx - 62, cx + 62
    top, bottom = cy - 34, cy + 34
    region = f'x="{left - 60}" y="{top - 60}" width="{right - left + 120}" height="{bottom - top + 120}"'
    return f"""
    <filter id="arrowGlowGold" filterUnits="userSpaceOnUse" {region}>
      <feGaussianBlur stdDeviation="9" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <filter id="arrowGlowCyan" filterUnits="userSpaceOnUse" {region}>
      <feGaussianBlur stdDeviation="8" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <g fill="none" stroke-linecap="round" stroke-linejoin="round">
      <g stroke="#F2C45A" stroke-width="15" filter="url(#arrowGlowGold)">
        <path d="M{left} {top} H{right}"/><path d="M{right - 26} {top - 26} L{right} {top} L{right - 26} {top + 26}"/>
      </g>
      <g stroke="#7DE8FF" stroke-width="15" filter="url(#arrowGlowCyan)">
        <path d="M{right} {bottom} H{left}"/><path d="M{left + 26} {bottom - 26} L{left} {bottom} L{left + 26} {bottom + 26}"/>
      </g>
    </g>"""


def coins(x: float, y: float) -> str:
    """Pile de pièces dorées (le relevé bancaire), comme le cylindre de données du logo de Viz."""
    parts = []
    for i in range(4):
        top = y - i * 34
        parts.append(
            f'<path d="M{x - 78} {top} v22 a78 26 0 0 0 156 0 v-22" fill="url(#goldV)" stroke="#7A4E08" stroke-width="2"/>'
        )
        parts.append(f'<ellipse cx="{x}" cy="{top}" rx="78" ry="26" fill="url(#coinTop)" stroke="#FFF1BF" stroke-width="2"/>')
    parts.append(
        f'<text x="{x}" y="{y - 3 * 34 + 11}" text-anchor="middle" class="brand" font-weight="900" font-size="32"'
        ' fill="#7A4E08">€</text>'
    )
    return f'<g filter="url(#glowGold)">{"".join(parts)}</g>'


def csv_card(x: float, y: float) -> str:
    """Fichier CSV flottant (sortie), cerclé d'or comme la fiche du logo de Viz."""
    return f"""
    {framed(x, y, 150, 176, 22, rim=8)}
    <text x="{x + 75}" y="{y + 70}" text-anchor="middle" class="brand" font-weight="900" font-size="38"
      fill="#9BF0FF" filter="url(#glowCyan)">CSV</text>
    <rect x="{x + 26}" y="{y + 92}" width="98" height="12" rx="6" fill="url(#cyanBar)"/>
    <rect x="{x + 26}" y="{y + 114}" width="70" height="12" rx="6" fill="url(#goldV)"/>
    <rect x="{x + 26}" y="{y + 136}" width="86" height="12" rx="6" fill="url(#cyanBar)"/>"""


def tile(x: float, y: float, size: float) -> str:
    """Tuile de l'étiquette : verre cyan cerclé, flèches de conversion."""
    s = size / 24
    return f"""
    <rect x="{x}" y="{y}" width="{size}" height="{size}" rx="{size * .24}" fill="url(#glassLight)" fill-opacity=".4"
      stroke="#9BF0FF" stroke-width="{size * .045}" filter="url(#glowCyan)"/>
    <rect x="{x + size * .06}" y="{y + size * .06}" width="{size * .88}" height="{size * .4}" rx="{size * .18}"
      fill="url(#sheen)"/>
    <g transform="translate({x + size * .19} {y + size * .19}) scale({s * .62})" fill="none" stroke="#E9FCFF"
      stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" filter="url(#glowCyan)">{ARROWS}</g>"""


def badge(x: float, y: float, w: float, h: float) -> str:
    return f"""
    {framed(x, y, w, h, h / 2, rim=12)}
    {tile(x + 42, y + (h - 92) / 2, 92)}
    <text x="{x + 158}" y="{y + h / 2 + 26}" class="brand" font-weight="900" font-size="76" fill="#BDF4FF"
      filter="url(#glowCyan)">atelier_Convert</text>"""


def logo_svg() -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024" width="1024" height="1024">
  {defs()}
  {framed(176, 120, 640, 560, 52, rim=14)}
  <circle cx="234" cy="176" r="11" fill="#7DE8FF"/><circle cx="268" cy="176" r="11" fill="#7DE8FF"/>
  <circle cx="302" cy="176" r="11" fill="#7DE8FF"/>
  <rect x="340" y="168" width="200" height="16" rx="8" fill="#7DE8FF" opacity=".35"/>
  {pdf_doc(214, 232)}
  {arrows(496, 372)}
  {sheet(586, 232)}
  <g filter="url(#glowCyan)">
    <rect x="300" y="548" width="480" height="76" rx="20" fill="url(#glassLight)" fill-opacity=".16" stroke="#8FEFFF"
      stroke-opacity=".7" stroke-width="3"/>
  </g>
  <circle cx="346" cy="586" r="22" fill="none" stroke="url(#gold)" stroke-width="6" filter="url(#glowGold)"/>
  <path d="M335 586 l8 8 l15 -16" fill="none" stroke="#F2C45A" stroke-width="6" stroke-linecap="round"
    stroke-linejoin="round"/>
  <rect x="386" y="572" width="150" height="12" rx="6" fill="url(#cyanBar)"/>
  <rect x="386" y="594" width="96" height="10" rx="5" fill="#7DE8FF" opacity=".55"/>
  <rect x="566" y="576" width="186" height="20" rx="10" fill="#0B2E44" stroke="#8FEFFF" stroke-opacity=".5" stroke-width="2"/>
  <rect x="569" y="579" width="180" height="14" rx="7" fill="url(#goldV)"/>
  {csv_card(812, 210)}
  {coins(168, 700)}
  {badge(70, 772, 884, 168)}
</svg>"""


def tile_svg(size: int) -> str:
    """Favicon : la tuile de l'étiquette, sur un fond sombre arrondi cerclé d'or (lisible sur un onglet clair)."""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" width="{size}" height="{size}">
  {defs()}
  <rect x="6" y="6" width="116" height="116" rx="30" fill="url(#glass)" stroke="url(#gold)" stroke-width="8"/>
  {tile(18, 18, 92)}
</svg>"""


def render(svg: str, size: int, transparent: bool = True) -> Image.Image:
    html = f"<html><body style='margin:0;background:transparent'>{svg}</body></html>"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": size, "height": size}, device_scale_factor=1)
        page.set_content(html)
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(300)
        png = page.locator("svg").screenshot(omit_background=transparent)
        browser.close()
    return Image.open(io.BytesIO(png)).convert("RGBA")


def crop_to_content(img: Image.Image, margin: int) -> Image.Image:
    box = img.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
    if not box:
        return img
    left, top, right, bottom = box
    side = max(right - left, bottom - top) + 2 * margin
    out = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    out.paste(img.crop(box), ((side - (right - left)) // 2, (side - (bottom - top)) // 2))
    return out


def main() -> None:
    svg = logo_svg().replace('width="1024" height="1024"', 'width="2048" height="2048"')
    big = crop_to_content(render(svg, 2048), margin=40)
    docs = ROOT / "docs" / "brand"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "logo-atelier-convert.svg").write_text(logo_svg(), encoding="utf-8")
    big.resize((1024, 1024), Image.LANCZOS).save(docs / "logo-atelier-convert.png", optimize=True)

    assets = ROOT / "frontend" / "src" / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    big.resize((576, 576), Image.LANCZOS).save(assets / "logo-atelier-convert.webp", quality=92, method=6)

    mac = ROOT / "scripts" / "macos" / "icon.png"
    big.resize((1024, 1024), Image.LANCZOS).save(mac, optimize=True)
    ico = ROOT / "scripts" / "windows" / "atelier-convert.ico"
    big.resize((256, 256), Image.LANCZOS).save(ico, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])

    public = ROOT / "frontend" / "public"
    public.mkdir(parents=True, exist_ok=True)
    tile_img = render(tile_svg(512), 512)
    tile_img.resize((64, 64), Image.LANCZOS).save(public / "favicon-64.png", optimize=True)
    touch = Image.new("RGB", (180, 180), (7, 28, 43))
    touch.paste(tile_img.resize((180, 180), Image.LANCZOS), (0, 0), tile_img.resize((180, 180), Image.LANCZOS))
    touch.save(public / "apple-touch-icon.png", optimize=True)
    print("Logo et icônes écrits.")


if __name__ == "__main__":
    main()
