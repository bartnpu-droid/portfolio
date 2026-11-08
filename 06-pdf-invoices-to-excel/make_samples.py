"""Creates the sample invoices in samples/: five made-up suppliers, five different layouts.

The companies, people and numbers are invented for the demo. One invoice is a scan
(an image inside the PDF, no text layer), and one has a total that does not match
its lines, so the checks in extract.py have something to catch.

Run: python make_samples.py
"""

from __future__ import annotations

import io
import random
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, LETTER
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

OUT = Path(__file__).parent / "samples"
FONTS = Path("/usr/share/fonts/truetype")

for name, file in [
    ("Sans", "dejavu/DejaVuSans.ttf"),
    ("Sans-Bold", "dejavu/DejaVuSans-Bold.ttf"),
    ("Serif", "liberation/LiberationSerif-Regular.ttf"),
    ("Serif-Bold", "liberation/LiberationSerif-Bold.ttf"),
    ("Arial", "liberation/LiberationSans-Regular.ttf"),
    ("Arial-Bold", "liberation/LiberationSans-Bold.ttf"),
]:
    pdfmetrics.registerFont(TTFont(name, str(FONTS / file)))

CENT = Decimal("0.01")
BUYER = ["Brightway Cleaning Ltd", "14 Example Road", "London N1 0AA", "United Kingdom"]


def money(x: Decimal) -> Decimal:
    return x.quantize(CENT, rounding=ROUND_HALF_UP)


def uk(x: Decimal, sign: str = "£") -> str:
    return f"{sign}{money(x):,.2f}"


def eu(x: Decimal) -> str:
    s = f"{money(x):,.2f}".replace(",", " ").replace(".", ",").replace(" ", ".")
    return f"€ {s}"


def lines_total(items):
    return sum((money(Decimal(q) * Decimal(p)) for _, q, p in items), Decimal(0))


# ---------------------------------------------------------------- 1. classic UK invoice with a ruled table
def northwind():
    items = [
        ("A4 copy paper, 80 gsm (box of 5 reams)", 4, "21.50"),
        ("Microfibre cloths, pack of 24", 6, "9.80"),
        ("Heavy-duty bin liners, roll of 50", 10, "4.25"),
    ]
    sub = lines_total(items)
    vat = money(sub * Decimal("0.20"))
    c = canvas.Canvas(str(OUT / "northwind-NW-2026-0417.pdf"), pagesize=A4)
    w, h = A4
    c.setTitle("Invoice NW-2026-0417")
    c.setFont("Sans-Bold", 20)
    c.drawString(20 * mm, h - 25 * mm, "Northwind Office Supply Ltd")
    c.setFont("Sans", 9)
    for i, t in enumerate(["8 Sample Street, Leeds LS1 0AA", "VAT no. GB 000 0000 00 (sample)"]):
        c.drawString(20 * mm, h - 31 * mm - i * 4.5 * mm, t)
    c.setFont("Sans-Bold", 26)
    c.drawRightString(w - 20 * mm, h - 25 * mm, "INVOICE")
    c.setFont("Sans", 10)
    for i, (k, v) in enumerate([("Invoice No.:", "NW-2026-0417"), ("Invoice date:", "02/11/2026"), ("Due date:", "16/11/2026")]):
        y = h - 34 * mm - i * 5.5 * mm
        c.drawRightString(w - 50 * mm, y, k)
        c.drawRightString(w - 20 * mm, y, v)
    c.setFont("Sans-Bold", 10)
    c.drawString(20 * mm, h - 55 * mm, "Bill to")
    c.setFont("Sans", 10)
    for i, t in enumerate(BUYER):
        c.drawString(20 * mm, h - 61 * mm - i * 5 * mm, t)

    x = [20 * mm, 120 * mm, 140 * mm, 165 * mm, w - 20 * mm]
    y = h - 95 * mm
    c.setFillColor(colors.HexColor("#1f3b5c"))
    c.rect(x[0], y - 2.5 * mm, x[-1] - x[0], 8 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Sans-Bold", 9.5)
    c.drawString(x[0] + 2 * mm, y, "Description")
    c.drawRightString(x[2] - 2 * mm, y, "Qty")
    c.drawRightString(x[3] - 2 * mm, y, "Unit price")
    c.drawRightString(x[4] - 2 * mm, y, "Amount")
    c.setFillColor(colors.black)
    c.setFont("Sans", 9.5)
    c.setStrokeColor(colors.HexColor("#c7ced6"))
    for desc, q, p in items:
        y -= 9 * mm
        c.drawString(x[0] + 2 * mm, y, desc)
        c.drawRightString(x[2] - 2 * mm, y, str(q))
        c.drawRightString(x[3] - 2 * mm, y, uk(Decimal(p)))
        c.drawRightString(x[4] - 2 * mm, y, uk(Decimal(q) * Decimal(p)))
        c.line(x[0], y - 3 * mm, x[-1], y - 3 * mm)
    for i, (k, v, bold) in enumerate([("Subtotal", uk(sub), False), ("VAT (20%)", uk(vat), False), ("Total", uk(sub + vat), True)]):
        yy = y - 12 * mm - i * 6.5 * mm
        c.setFont("Sans-Bold" if bold else "Sans", 10.5 if bold else 10)
        c.drawRightString(x[3] - 2 * mm, yy, k)
        c.drawRightString(x[4] - 2 * mm, yy, v)
    c.setFont("Sans", 8.5)
    c.setFillColor(colors.HexColor("#5b6670"))
    c.drawString(20 * mm, 20 * mm, "Payment by bank transfer within 14 days. Please use the invoice number as the reference.")
    c.save()


# ---------------------------------------------------------------- 2. EU invoice, comma decimals, no table lines
def bluepeak():
    items = [
        ("Managed WordPress hosting, November", 1, "29.00"),
        ("Daily off-site backups", 1, "9.00"),
        ("Extra mailbox (5 GB)", 7, "7.00"),
    ]
    sub = lines_total(items)
    vat = money(sub * Decimal("0.21"))
    c = canvas.Canvas(str(OUT / "bluepeak-BP-58213.pdf"), pagesize=A4)
    w, h = A4
    c.setTitle("Invoice BP-58213")
    c.setFillColor(colors.HexColor("#2457d6"))
    c.rect(0, h - 38 * mm, w, 38 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Arial-Bold", 22)
    c.drawString(18 * mm, h - 20 * mm, "Bluepeak Hosting B.V.")
    c.setFont("Arial", 9)
    c.drawString(18 * mm, h - 27 * mm, "Voorbeeldstraat 1, 1000 AA Amsterdam · BTW NL000000000B00 (sample)")
    c.setFillColor(colors.black)
    c.setFont("Arial-Bold", 13)
    c.drawString(18 * mm, h - 52 * mm, "Invoice #BP-58213")
    c.setFont("Arial", 10)
    c.drawString(18 * mm, h - 59 * mm, "Date of issue: 1 November 2026")
    c.drawString(18 * mm, h - 65 * mm, "Payment due: 15 November 2026")
    c.setFont("Arial", 10)
    c.drawString(120 * mm, h - 52 * mm, "Customer")
    for i, t in enumerate(BUYER):
        c.drawString(120 * mm, h - 58 * mm - i * 5 * mm, t)
    y = h - 95 * mm
    c.setFont("Arial-Bold", 9.5)
    c.setFillColor(colors.HexColor("#5b6670"))
    c.drawString(18 * mm, y, "DESCRIPTION")
    c.drawRightString(135 * mm, y, "QUANTITY")
    c.drawRightString(160 * mm, y, "PRICE")
    c.drawRightString(w - 18 * mm, y, "TOTAL")
    c.setFillColor(colors.black)
    c.setFont("Arial", 10)
    for desc, q, p in items:
        y -= 8 * mm
        c.drawString(18 * mm, y, desc)
        c.drawRightString(135 * mm, y, str(q))
        c.drawRightString(160 * mm, y, eu(Decimal(p)))
        c.drawRightString(w - 18 * mm, y, eu(Decimal(q) * Decimal(p)))
    y -= 14 * mm
    for i, (k, v) in enumerate([("Net total", eu(sub)), ("VAT 21%", eu(vat)), ("Amount due", eu(sub + vat))]):
        c.setFont("Arial-Bold" if i == 2 else "Arial", 10.5 if i == 2 else 10)
        c.drawRightString(160 * mm, y - i * 6.5 * mm, k)
        c.drawRightString(w - 18 * mm, y - i * 6.5 * mm, v)
    c.setFont("Arial", 8.5)
    c.setFillColor(colors.HexColor("#5b6670"))
    c.drawString(18 * mm, 18 * mm, "Thank you for hosting with us. This invoice is paid automatically from your card on file.")
    c.save()


# ---------------------------------------------------------------- 3. two pages, 18 lines, serif font
def greenleaf():
    items = [
        ("Breakfast pastries platter", 4, "24.00"),
        ("Fresh fruit platter", 3, "22.50"),
        ("Mini quiches (dozen)", 4, "14.40"),
        ("Smoked salmon blinis (dozen)", 3, "18.00"),
        ("Vegan wraps platter", 2, "26.00"),
        ("Chicken skewers (dozen)", 4, "16.80"),
        ("Mixed salad bowl", 3, "12.50"),
        ("Cheese board", 2, "32.00"),
        ("Sourdough rolls (dozen)", 3, "6.60"),
        ("Brownie bites (dozen)", 4, "9.60"),
        ("Lemon tarts (dozen)", 2, "13.20"),
        ("Orange juice, 1 litre", 8, "3.20"),
        ("Sparkling water, 750 ml", 12, "1.90"),
        ("Coffee service per person", 40, "2.20"),
        ("Tea service per person", 15, "1.80"),
        ("Waiting staff, per hour", 6, "18.50"),
        ("Crockery hire, per guest", 40, "0.90"),
        ("Delivery and set-up", 1, "35.00"),
    ]
    sub = lines_total(items)
    vat = money(sub * Decimal("0.20"))
    c = canvas.Canvas(str(OUT / "greenleaf-GL-26-1093.pdf"), pagesize=A4)
    w, h = A4
    c.setTitle("Invoice GL/26/1093")

    def header(page):
        c.setFillColor(colors.HexColor("#2f6b3a"))
        c.setFont("Serif-Bold", 22)
        c.drawString(20 * mm, h - 24 * mm, "Green Leaf Catering")
        c.setFillColor(colors.black)
        c.setFont("Serif", 10)
        c.drawString(20 * mm, h - 30 * mm, "Events and office catering · 3 Demo Lane, Bristol BS1 0AA")
        c.drawRightString(w - 20 * mm, h - 24 * mm, f"Page {page} of 2")

    header(1)
    c.setFont("Serif", 11)
    meta = [("Inv. no.", "GL/26/1093"), ("Date", "28 Oct 2026"), ("Pay by", "27 Nov 2026")]
    for i, (k, v) in enumerate(meta):
        c.drawString(20 * mm, h - 45 * mm - i * 6 * mm, f"{k} {v}")
    c.drawString(120 * mm, h - 45 * mm, "Client: " + BUYER[0])
    c.drawString(120 * mm, h - 51 * mm, "Event: staff breakfast, 26 Oct")

    def table_head(y):
        c.setFont("Serif-Bold", 10.5)
        c.drawString(20 * mm, y, "Description")
        c.drawRightString(130 * mm, y, "Qty")
        c.drawRightString(158 * mm, y, "Price")
        c.drawRightString(w - 20 * mm, y, "Total")
        c.line(20 * mm, y - 2 * mm, w - 20 * mm, y - 2 * mm)
        c.setFont("Serif", 10.5)

    y = h - 75 * mm
    table_head(y)
    for n, (desc, q, p) in enumerate(items):
        if n == 12:
            c.setFont("Serif", 9)
            c.drawRightString(w - 20 * mm, 20 * mm, "continued on page 2")
            c.showPage()
            header(2)
            y = h - 45 * mm
            table_head(y)
        y -= 7.5 * mm
        c.drawString(20 * mm, y, desc)
        c.drawRightString(130 * mm, y, str(q))
        c.drawRightString(158 * mm, y, uk(Decimal(p)))
        c.drawRightString(w - 20 * mm, y, uk(Decimal(q) * Decimal(p)))
    y -= 14 * mm
    for i, (k, v) in enumerate([("Subtotal", uk(sub)), ("VAT 20%", uk(vat)), ("Total due", uk(sub + vat))]):
        c.setFont("Serif-Bold" if i == 2 else "Serif", 11)
        c.drawRightString(158 * mm, y - i * 6.5 * mm, k)
        c.drawRightString(w - 20 * mm, y - i * 6.5 * mm, v)
    c.save()


# ---------------------------------------------------------------- 4. US invoice, US dates, wrong total on purpose
def atlas():
    items = [
        ("Same-day courier, central zone", 14, "38.00"),
        ("Next-day parcels (up to 5 kg)", 22, "19.50"),
        ("Fuel surcharge", 1, "47.50"),
    ]
    sub = lines_total(items)
    tax = money(sub * Decimal("0.08875"))
    printed_total = sub + tax + Decimal("36.00")  # the supplier's typo: the demo should flag it
    c = canvas.Canvas(str(OUT / "atlas-ATL-77812.pdf"), pagesize=LETTER)
    w, h = LETTER
    c.setTitle("Invoice ATL-77812")
    c.setFont("Arial-Bold", 18)
    c.drawString(0.8 * 72, h - 0.9 * 72, "ATLAS COURIER INC.")
    c.setFont("Arial", 9)
    c.drawString(0.8 * 72, h - 1.1 * 72, "200 Sample Ave, Suite 4, New York, NY 10000")
    c.setFont("Arial", 10)
    rows = [("Invoice Number", "ATL-77812"), ("Invoice Date", "Nov 3, 2026"), ("Due Date", "Dec 3, 2026")]
    for i, (k, v) in enumerate(rows):
        c.drawString(w - 3.4 * 72, h - 0.9 * 72 - i * 15, k)
        c.drawRightString(w - 0.8 * 72, h - 0.9 * 72 - i * 15, v)
    c.drawString(0.8 * 72, h - 1.6 * 72, "Bill To: " + BUYER[0] + ", London office")
    y = h - 2.4 * 72
    c.setFillColor(colors.HexColor("#f2b134"))
    c.rect(0.8 * 72, y - 5, w - 1.6 * 72, 18, fill=1, stroke=0)
    c.setFillColor(colors.black)
    c.setFont("Arial-Bold", 10)
    c.drawString(0.9 * 72, y, "Service")
    c.drawRightString(5.2 * 72, y, "Quantity")
    c.drawRightString(6.4 * 72, y, "Rate")
    c.drawRightString(w - 0.9 * 72, y, "Line Total")
    c.setFont("Arial", 10)
    for desc, q, p in items:
        y -= 20
        c.drawString(0.9 * 72, y, desc)
        c.drawRightString(5.2 * 72, y, str(q))
        c.drawRightString(6.4 * 72, y, uk(Decimal(p), "$"))
        c.drawRightString(w - 0.9 * 72, y, uk(Decimal(q) * Decimal(p), "$"))
    y -= 34
    for i, (k, v) in enumerate([("Subtotal", uk(sub, "$")), ("Sales Tax (8.875%)", uk(tax, "$")), ("Amount Due", uk(printed_total, "$"))]):
        c.setFont("Arial-Bold" if i == 2 else "Arial", 11 if i == 2 else 10)
        c.drawRightString(6.4 * 72, y - i * 16, k)
        c.drawRightString(w - 0.9 * 72, y - i * 16, v)
    c.save()


# ---------------------------------------------------------------- 5. a scan: image only, no text layer
def harbor_scan():
    items = [("Business cards, 500 pcs", 2, "38.00"), ("A5 flyers, 1000 pcs", 1, "96.00"), ("Pull-up banner 85x200 cm", 1, "79.00")]
    sub = lines_total(items)
    vat = money(sub * Decimal("0.20"))
    W, H = 1654, 2339  # A4 at 200 dpi
    img = Image.new("RGB", (W, H), (250, 249, 245))
    d = ImageDraw.Draw(img)
    f = lambda s, b=False: ImageFont.truetype(str(FONTS / ("dejavu/DejaVuSans-Bold.ttf" if b else "dejavu/DejaVuSans.ttf")), s)
    d.text((130, 140), "Harbor Print Co.", font=f(60, True), fill=(20, 20, 20))
    d.text((130, 225), "5 Quay Sample Road, Plymouth PL1 0AA", font=f(30), fill=(40, 40, 40))
    y = 380
    for k, v in [("Invoice No:", "HP-3391"), ("Invoice date:", "05/11/2026"), ("Due date:", "19/11/2026")]:
        d.text((130, y), f"{k} {v}", font=f(34), fill=(20, 20, 20))
        y += 52
    d.text((130, y + 30), "Bill to: " + BUYER[0], font=f(34), fill=(20, 20, 20))
    y += 150
    d.text((130, y), "Description", font=f(32, True), fill=(20, 20, 20))
    for x, t in [(1010, "Qty"), (1200, "Unit price"), (1450, "Amount")]:
        d.text((x, y), t, font=f(32, True), fill=(20, 20, 20), anchor="ra" if False else None)
    d.line((130, y + 50, 1530, y + 50), fill=(60, 60, 60), width=3)
    for desc, q, p in items:
        y += 80
        d.text((130, y), desc, font=f(32), fill=(20, 20, 20))
        d.text((1040, y), str(q), font=f(32), fill=(20, 20, 20))
        d.text((1200, y), uk(Decimal(p)), font=f(32), fill=(20, 20, 20))
        d.text((1430, y), uk(Decimal(q) * Decimal(p)), font=f(32), fill=(20, 20, 20))
    y += 140
    for k, v in [("Subtotal", uk(sub)), ("VAT (20%)", uk(vat)), ("Total due", uk(sub + vat))]:
        d.text((1010, y), k, font=f(34, k == "Total due"), fill=(20, 20, 20))
        d.text((1300, y), v, font=f(34, k == "Total due"), fill=(20, 20, 20))
        y += 60
    d.text((130, 2150), "Scanned copy", font=f(26), fill=(120, 120, 120))
    # make it look scanned: slight rotation, blur and noise
    img = img.rotate(0.6, resample=Image.BICUBIC, expand=False, fillcolor=(250, 249, 245)).filter(ImageFilter.GaussianBlur(0.6))
    rng = random.Random(3)
    px = img.load()
    for _ in range(9000):
        x, yy = rng.randrange(W), rng.randrange(H)
        g = rng.randrange(170, 235)
        px[x, yy] = (g, g, g)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=72)
    buf.seek(0)
    c = canvas.Canvas(str(OUT / "harbor-scan-HP-3391.pdf"), pagesize=A4)
    from reportlab.lib.utils import ImageReader

    c.drawImage(ImageReader(buf), 0, 0, width=A4[0], height=A4[1])
    c.save()


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for make in (northwind, bluepeak, greenleaf, atlas, harbor_scan):
        make()
    print("Sample invoices:", ", ".join(sorted(p.name for p in OUT.glob("*.pdf"))))
