"""Fabrique les fichiers d'exemple (samples/) et les fichiers de test (backend/tests/fixtures/).

Toutes les données sont fictives. À relancer seulement si les exemples changent :

    cd backend && . .venv/bin/activate && pip install reportlab
    python ../scripts/samples/make_samples.py

reportlab n'est pas une dépendance de l'application (les fichiers produits sont versionnés).
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "samples"
FIXTURES = ROOT / "backend" / "tests" / "fixtures"


def fr(amount: float) -> str:
    """1234.5 → « 1 234,50 »."""
    whole, dec = f"{abs(amount):,.2f}".split(".")
    return whole.replace(",", " ") + "," + dec


# --- Relevé « Débit / Crédit » avec dates de valeur et libellés sur deux lignes (exemple principal) ----------

OPERATIONS_MARS = [
    ("02/03", "02/03", ["PRLV SEPA EDF ENERGIE", "ECH/020326 ID EMETTEUR/FR12ZZZ000001"], 84.20, None),
    ("03/03", "03/03", ["CARTE X1234 01/03 BOULANGERIE DU PORT"], 7.90, None),
    ("04/03", "04/03", ["VIR SEPA RECU /DE SOCIETE EXEMPLE", "/MOTIF SALAIRE FEVRIER 2026"], None, 2450.00),
    ("05/03", "05/03", ["CARTE X1234 04/03 SUPERMARCHE CENTRE"], 126.43, None),
    ("07/03", "08/03", ["RETRAIT DAB 07/03 PARIS 11E"], 60.00, None),
    ("10/03", "10/03", ["PRLV SEPA ASSURANCE HABITATION"], 23.75, None),
    ("12/03", "12/03", ["VIR SEPA EMIS / LOYER MARS"], 890.00, None),
    ("15/03", "15/03", ["CARTE X1234 14/03 LIBRAIRIE DES ARTS"], 32.50, None),
    ("16/03", "16/03", ["REMISE CHEQUE N 0001234"], None, 150.00),
    ("18/03", "18/03", ["PRLV SEPA OPERATEUR MOBILE"], 19.99, None),
    ("20/03", "20/03", ["CARTE X1234 19/03 PHARMACIE CENTRALE"], 14.60, None),
    ("22/03", "22/03", ["VIR INST RECU /DE CAMILLE MARTIN", "/MOTIF REMBOURSEMENT RESTAURANT"], None, 45.00),
    ("24/03", "24/03", ["CARTE X1234 23/03 STATION SERVICE A6"], 68.12, None),
    ("25/03", "25/03", ["COTISATION CARTE BANCAIRE"], 3.50, None),
    ("27/03", "27/03", ["CARTE X1234 26/03 CINEMA LUMIERE"], 21.00, None),
    ("28/03", "28/03", ["PRLV SEPA ABONNEMENT INTERNET"], 29.99, None),
    ("30/03", "30/03", ["CARTE X1234 29/03 MARCHE BIO"], 41.37, None),
    ("31/03", "31/03", ["INTERETS CREDITEURS"], None, 1.12),
]


def statement_debit_credit(path: Path) -> None:
    c = Canvas(str(path), pagesize=A4)
    width, height = A4
    opening = 1523.40
    debit = sum(d for *_, d, _ in OPERATIONS_MARS if d)
    credit = sum(k for *_, k in OPERATIONS_MARS if k)
    closing = round(opening - debit + credit, 2)

    def page_header(page: int) -> float:
        c.setFont("Helvetica-Bold", 14)
        c.drawString(40, height - 50, "BANQUE EXEMPLE")
        c.setFont("Helvetica", 9)
        c.drawString(40, height - 64, "Agence Centre — 1 place de l'Exemple, 75000 Paris")
        c.setFont("Helvetica-Bold", 11)
        c.drawString(40, height - 95, "RELEVÉ DE COMPTE COURANT")
        c.setFont("Helvetica", 9)
        c.drawString(40, height - 109, "M. DOMINIQUE EXEMPLE — Compte n° 00012345678")
        c.drawString(40, height - 121, "Période du 01/03/2026 au 31/03/2026")
        c.drawRightString(width - 40, height - 95, f"Page {page}/2")
        y = height - 150
        c.setFont("Helvetica-Bold", 9)
        c.drawString(40, y, "Date")
        c.drawString(85, y, "Valeur")
        c.drawString(135, y, "Nature des opérations")
        c.drawRightString(470, y, "Débit")
        c.drawRightString(555, y, "Crédit")
        c.line(40, y - 4, width - 40, y - 4)
        c.setFont("Helvetica", 9)
        return y - 18

    y = page_header(1)
    c.drawString(135, y, "Ancien solde au 28/02/2026")
    c.drawRightString(555, y, fr(opening))
    y -= 18
    for i, (d, v, lines, deb, cred) in enumerate(OPERATIONS_MARS):
        if i == 11:
            c.setFont("Helvetica-Oblique", 8)
            c.drawString(135, y - 4, "À reporter")
            c.showPage()
            y = page_header(2)
        c.drawString(40, y, d)
        c.drawString(85, y, v)
        c.drawString(135, y, lines[0])
        if deb:
            c.drawRightString(470, y, fr(deb))
        if cred:
            c.drawRightString(555, y, fr(cred))
        for extra in lines[1:]:
            y -= 11
            c.drawString(135, y, extra)
        y -= 16
    c.line(40, y + 8, width - 40, y + 8)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(135, y - 4, "Total des opérations")
    c.drawRightString(470, y - 4, fr(debit))
    c.drawRightString(555, y - 4, fr(credit))
    c.drawString(135, y - 20, "Nouveau solde au 31/03/2026 créditeur")
    c.drawRightString(555, y - 20, fr(closing))
    c.setFont("Helvetica", 7)
    c.drawString(40, 40, "Document fictif généré pour Atelier Convert — aucune donnée réelle.")
    c.save()


# --- Relevé « Montant signé + Solde », dates complètes (fixture) ------------------------------------------


def statement_amount_balance(path: Path) -> None:
    c = Canvas(str(path), pagesize=A4)
    width, height = A4
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, height - 50, "Néobanque Exemple — Relevé d'opérations")
    c.setFont("Helvetica-Bold", 9)
    y = height - 90
    c.drawString(40, y, "Date")
    c.drawString(110, y, "Description")
    c.drawRightString(470, y, "Montant")
    c.drawRightString(555, y, "Solde")
    c.setFont("Helvetica", 9)
    balance = 500.00
    rows = [
        ("01/04/2026", "Paiement Café du Coin", -3.80),
        ("02/04/2026", "Virement reçu Alex", 120.00),
        ("03/04/2026", "Paiement Librairie", -18.90),
        ("05/04/2026", "Abonnement musique", -10.99),
        ("06/04/2026", "Remboursement ami", 25.00),
    ]
    y -= 18
    for d, label, amount in rows:
        balance = round(balance + amount, 2)
        c.drawString(40, y, d)
        c.drawString(110, y, label)
        c.drawRightString(470, y, ("-" if amount < 0 else "+") + fr(amount))
        c.drawRightString(555, y, fr(balance))
        y -= 16
    c.save()


# --- Relevé sans en-tête de colonnes : débit et crédit à des positions différentes (fixture) ----------------


def statement_no_header(path: Path) -> None:
    c = Canvas(str(path), pagesize=A4)
    width, height = A4
    c.setFont("Helvetica", 9)
    c.drawString(40, height - 50, "Extrait de compte — janvier 2026")
    rows = [
        ("05.01.26", "PRELEVEMENT MUTUELLE", 45.10, None),
        ("08.01.26", "VIREMENT SALAIRE", None, 1980.00),
        ("12.01.26", "PAIEMENT CB RESTAURANT", 37.40, None),
        ("15.01.26", "PAIEMENT CB 1 234,56 TEST LIBELLE", 1234.56, None),
        ("20.01.26", "VERSEMENT ESPECES", None, 200.00),
    ]
    y = height - 80
    for d, label, deb, cred in rows:
        c.drawString(40, y, d)
        c.drawString(100, y, label)
        if deb:
            c.drawRightString(440, y, fr(deb))
        if cred:
            c.drawRightString(540, y, fr(cred))
        y -= 15
    c.save()


# --- PDF avec un tableau tracé (mode « Tableaux ») -------------------------------------------------------


def ruled_table(path: Path) -> None:
    c = Canvas(str(path), pagesize=A4)
    width, height = A4
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, height - 50, "Inventaire de l'atelier")
    data = [
        ("Article", "Quantité", "Prix unitaire", "Réception"),
        ("Rabot", "3", "45,90", "12/02/2026"),
        ("Ciseau à bois", "12", "8,50", "13/02/2026"),
        ("Serre-joint", "6", "14,00", "15/02/2026"),
        ("Établi", "1", "389,00", "20/02/2026"),
    ]
    xs = [40, 200, 300, 420, 540]
    top = height - 80
    row_h = 20
    for r in range(len(data) + 1):
        c.line(xs[0], top - r * row_h, xs[-1], top - r * row_h)
    for x in xs:
        c.line(x, top, x, top - len(data) * row_h)
    for r, row in enumerate(data):
        c.setFont("Helvetica-Bold" if r == 0 else "Helvetica", 9)
        for i, value in enumerate(row):
            c.drawString(xs[i] + 4, top - r * row_h - 14, value)
    c.save()


# --- Fichiers texte ------------------------------------------------------------------------------------


def bank_csv(path: Path) -> None:
    lines = [
        "Compte courant n° 00012345678;;;;",
        "Titulaire : M. DOMINIQUE EXEMPLE;;;;",
        "Solde au 31/03/2026 : 2 087,15 €;;;;",
        ";;;;",
        "Date;Date de valeur;Libellé;Débit euros;Crédit euros",
    ]
    for d, v, label_lines, deb, cred in OPERATIONS_MARS:
        label = " ".join(label_lines).replace(";", ",")
        lines.append(f"{d}/2026;{v}/2026;{label};{fr(deb) if deb else ''};{fr(cred) if cred else ''}")
    path.write_bytes(("\r\n".join(lines) + "\r\n").encode("cp1252"))


def bank_ofx(path: Path) -> None:
    trns = []
    for i, (d, _v, label_lines, deb, cred) in enumerate(OPERATIONS_MARS, start=1):
        day, month = d.split("/")
        amount = -deb if deb else cred
        trns.append(
            "<STMTTRN>\n"
            f"<TRNTYPE>{'DEBIT' if deb else 'CREDIT'}\n"
            f"<DTPOSTED>2026{month}{day}\n"
            f"<TRNAMT>{amount:.2f}\n"
            f"<FITID>EX2026{month}{day}{i:03d}\n"
            f"<NAME>{label_lines[0][:32]}\n"
            + (f"<MEMO>{' '.join(label_lines[1:])}\n" if len(label_lines) > 1 else "")
            + "</STMTTRN>"
        )
    body = "\n".join(trns)
    text = (
        "OFXHEADER:100\nDATA:OFXSGML\nVERSION:102\nSECURITY:NONE\nENCODING:USASCII\nCHARSET:1252\n"
        "COMPRESSION:NONE\nOLDFILEUID:NONE\nNEWFILEUID:NONE\n\n"
        "<OFX>\n<BANKMSGSRSV1>\n<STMTTRNRS>\n<STMTRS>\n<CURDEF>EUR\n"
        "<BANKACCTFROM>\n<BANKID>99999\n<ACCTID>00012345678\n<ACCTTYPE>CHECKING\n</BANKACCTFROM>\n"
        "<BANKTRANLIST>\n<DTSTART>20260301\n<DTEND>20260331\n"
        f"{body}\n</BANKTRANLIST>\n<LEDGERBAL>\n<BALAMT>2087.15\n<DTASOF>20260331\n</LEDGERBAL>\n"
        "</STMTRS>\n</STMTTRNRS>\n</BANKMSGSRSV1>\n</OFX>\n"
    )
    path.write_bytes(text.encode("cp1252"))


def bank_qif(path: Path) -> None:
    text = "!Type:Bank\nD15/03/2026\nT-32.50\nPLibrairie des Arts\nLLoisirs\n^\nD16/03/2026\nT150.00\nPRemise chèque\nN1234\n^\n"
    path.write_bytes(text.encode("utf-8"))


def scanned(path: Path) -> None:
    """PDF sans texte (comme un document scanné) : seulement des formes."""
    c = Canvas(str(path), pagesize=A4)
    c.rect(60, 500, 300, 200, fill=1)
    c.save()


def main() -> None:
    SAMPLES.mkdir(exist_ok=True)
    FIXTURES.mkdir(parents=True, exist_ok=True)
    statement_debit_credit(SAMPLES / "releve-mars-2026.pdf")
    bank_csv(SAMPLES / "export-banque.csv")
    bank_ofx(SAMPLES / "operations.ofx")
    statement_amount_balance(FIXTURES / "releve-montant-solde.pdf")
    statement_no_header(FIXTURES / "releve-sans-entete.pdf")
    ruled_table(FIXTURES / "tableau.pdf")
    bank_qif(FIXTURES / "export.qif")
    scanned(FIXTURES / "scan.pdf")
    print("Exemples écrits dans", SAMPLES, "et", FIXTURES)


if __name__ == "__main__":
    main()
