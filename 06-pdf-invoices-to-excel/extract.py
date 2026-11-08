"""Reads invoice PDFs (normal PDFs and scans) and puts the data into one Excel file.

For every invoice it finds the supplier, invoice number, dates, currency, line items,
subtotal, tax and total, then checks the maths: qty x price = amount, the lines add up
to the subtotal, and subtotal + tax = total. Anything that does not add up is flagged
in the "Check" column, so a person only looks at the invoices that need it.

Usage:
    python extract.py samples/ -o output/invoices.xlsx
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pdfplumber
from dateutil import parser as dateparser

CENT = Decimal("0.01")
CURRENCY_SIGNS = {"£": "GBP", "€": "EUR", "$": "USD"}
CURRENCY_FORMATS = {"GBP": "£#,##0.00", "EUR": "€#,##0.00", "USD": "$#,##0.00"}

AMOUNT = r"(?:[£€$]\s?)?-?\d{1,3}(?:[.,]\d{3})*[.,]\d{2}"
AMOUNT_RE = re.compile(r"(?<![\w.,])" + AMOUNT + r"(?![\d])")
LINE_RE = re.compile(rf"^(?P<desc>.+?)\s+(?P<qty>\d+(?:[.,]\d+)?)\s+(?P<unit>{AMOUNT})\s+(?P<amount>{AMOUNT})\s*$")
# OCR sometimes misreads a small quantity ("1" -> "l", "cf"); keep the line and work the quantity out
LINE_OCR_RE = re.compile(rf"^(?P<desc>.+?)\s+(?P<qty>\S{{1,3}})\s+(?P<unit>{AMOUNT})\s+(?P<amount>{AMOUNT})\s*$")
DATE_RE = re.compile(
    r"(\d{4}-\d{2}-\d{2}|\d{1,2}[/.]\d{1,2}[/.]\d{2,4}|\d{1,2}\s+[A-Za-z]{3,9}\.?\s+\d{4}|[A-Za-z]{3,9}\.?\s+\d{1,2},?\s+\d{4})"
)

LABELS = {
    "number": re.compile(r"\b(?:invoice\s*(?:no\.?|number|#)|inv\.?\s*no\.?)\s*[:#]?\s*(?P<v>[A-Z0-9][A-Z0-9/\-]{2,})", re.IGNORECASE),
    "date": re.compile(r"(?:\b(?:invoice\s*date|date\s*of\s*issue|issue\s*date)|^date)\b\s*:?\s*(?P<v>.*)", re.IGNORECASE),
    "due": re.compile(r"\b(?:due\s*date|payment\s*due|pay\s*by)\b\s*:?\s*(?P<v>.*)", re.IGNORECASE),
}
SUBTOTAL_RE = re.compile(r"\b(?:sub\s*-?\s*total|net\s*total|total\s*net)\b", re.IGNORECASE)
TAX_RE = re.compile(r"\b(?:vat|sales\s*tax|tax|gst)\b", re.IGNORECASE)
TOTAL_RE = re.compile(r"\b(?:total\s*due|amount\s*due|balance\s*due|grand\s*total|total)\b", re.IGNORECASE)
HEADER_RE = re.compile(r"\b(?:description|service|item)s?\b.*\b(?:qty|quantity)\b", re.IGNORECASE)
NOT_SUPPLIER_RE = re.compile(r"^(?:tax\s+)?invoice\b|^page\s+\d|^scanned", re.IGNORECASE)


@dataclass
class Line:
    description: str
    qty: Decimal | None
    unit: Decimal
    amount: Decimal
    note: str = ""


@dataclass
class Invoice:
    file: str
    source: str = "text"
    supplier: str = ""
    number: str = ""
    invoice_date: date | None = None
    due_date: date | None = None
    currency: str = ""
    subtotal: Decimal | None = None
    tax: Decimal | None = None
    total: Decimal | None = None
    lines: list[Line] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)

    @property
    def check(self) -> str:
        return "OK" if not self.issues else "Check: " + "; ".join(self.issues)


# ---------------------------------------------------------------- reading
def read_pdf(path: Path) -> tuple[list[str], str, str]:
    """Text lines of all pages, how they were read ("text" or "OCR") and the supplier name if the layout shows it."""
    with pdfplumber.open(path) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages]
        if sum(len(t.strip()) for t in pages) > 40:
            return [ln for t in pages for ln in t.splitlines()], "text", biggest_line(pdf.pages[0])
        return ocr_pages(pdf), "OCR", ""


def ocr_pages(pdf) -> list[str]:
    import pytesseract
    from PIL import ImageFilter, ImageOps

    lines: list[str] = []
    for page in pdf.pages:
        img = page.to_image(resolution=300).original
        img = ImageOps.grayscale(img).filter(ImageFilter.MedianFilter(3))  # removes scanner dust
        lines += pytesseract.image_to_string(img, lang="eng", config="--psm 6").splitlines()
    return lines


def biggest_line(page) -> str:
    """The supplier name is usually the biggest text near the top of the first page."""
    rows: dict[int, list] = {}
    for w in page.extract_words(extra_attrs=["size"]):
        if w["top"] < page.height * 0.3:
            rows.setdefault(round(w["top"] / 3), []).append(w)
    best, best_size = "", 0.0
    for words in rows.values():
        size = max(w["size"] for w in words)
        # words of the same size, left to right, make one heading
        text = " ".join(w["text"] for w in sorted(words, key=lambda w: w["x0"]) if abs(w["size"] - size) < 0.5)
        if size > best_size and not NOT_SUPPLIER_RE.search(text):
            best, best_size = text, size
    return best


# ---------------------------------------------------------------- parsing
def parse_amount(s: str) -> Decimal:
    s = re.sub(r"[£€$\s]", "", s)
    dec = max(s.rfind("."), s.rfind(","))
    whole, frac = re.sub(r"[.,]", "", s[:dec]), s[dec + 1 :]
    try:
        return Decimal(f"{whole}.{frac}")
    except InvalidOperation as e:
        raise ValueError(f"not an amount: {s!r}") from e


def parse_date(s: str, us: bool) -> date | None:
    m = DATE_RE.search(s)
    if not m:
        return None
    try:
        return dateparser.parse(m.group(1), dayfirst=not us).date()
    except (ValueError, OverflowError):
        return None


def detect_currency(text: str) -> str:
    counts = {code: text.count(sign) + text.count(code) for sign, code in CURRENCY_SIGNS.items()}
    code, n = max(counts.items(), key=lambda kv: kv[1])
    return code if n else ""


def parse_invoice(file: str, lines: list[str], source: str, supplier: str) -> Invoice:
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in lines]
    lines = [ln for ln in lines if ln]
    inv = Invoice(file=file, source=source, supplier=supplier)
    inv.currency = detect_currency("\n".join(lines))
    us = inv.currency == "USD"
    if not inv.supplier:
        inv.supplier = next((ln for ln in lines if not NOT_SUPPLIER_RE.search(ln)), "")

    for ln in lines:
        if not inv.number and (m := LABELS["number"].search(ln)):
            inv.number = m.group("v")
        if not inv.due_date and (m := LABELS["due"].search(ln)):
            inv.due_date = parse_date(m.group("v"), us)
        elif not inv.invoice_date and (m := LABELS["date"].search(ln)):
            inv.invoice_date = parse_date(m.group("v"), us)

    in_table = False
    for ln in lines:
        amounts = AMOUNT_RE.findall(ln)
        if HEADER_RE.search(ln) and not amounts:
            in_table = True  # the header can repeat on every page
            continue
        if amounts and SUBTOTAL_RE.search(ln):
            inv.subtotal, in_table = parse_amount(amounts[-1]), False
        elif amounts and TAX_RE.search(ln) and inv.tax is None and not TOTAL_RE.search(ln):
            inv.tax = parse_amount(amounts[-1])
        elif amounts and TOTAL_RE.search(ln):
            inv.total, in_table = parse_amount(amounts[-1]), False
        elif in_table and len(amounts) >= 2:
            line = parse_line(ln)
            if line:
                inv.lines.append(line)
    check(inv)
    return inv


def parse_line(ln: str) -> Line | None:
    if m := LINE_RE.match(ln):
        qty = Decimal(m.group("qty").replace(",", "."))
        return Line(m.group("desc"), qty, parse_amount(m.group("unit")), parse_amount(m.group("amount")))
    if m := LINE_OCR_RE.match(ln):
        unit, amount = parse_amount(m.group("unit")), parse_amount(m.group("amount"))
        if unit:
            qty = amount / unit
            if qty == qty.to_integral_value():
                return Line(
                    m.group("desc"), qty.quantize(Decimal(1)), unit, amount, f'quantity read as "{m.group("qty")}", taken from the amount'
                )
    return None


# ---------------------------------------------------------------- checks
def check(inv: Invoice) -> None:
    def money(x: Decimal | None) -> str:
        sign = {v: k for k, v in CURRENCY_SIGNS.items()}.get(inv.currency, "")
        return f"{sign}{x:,.2f}" if x is not None else "?"

    for name in ("supplier", "number", "invoice_date", "total"):
        if not getattr(inv, name):
            inv.issues.append(f"{name.replace('_', ' ')} not found")
    if not inv.lines:
        inv.issues.append("no line items found")
    for i, ln in enumerate(inv.lines, 1):
        if ln.qty is not None and abs(ln.qty * ln.unit - ln.amount) > CENT:
            inv.issues.append(f"line {i}: {ln.qty} x {money(ln.unit)} is not {money(ln.amount)}")
    lines_sum = sum((ln.amount for ln in inv.lines), Decimal(0))
    if inv.lines and inv.subtotal is not None and abs(lines_sum - inv.subtotal) > CENT:
        inv.issues.append(f"lines add up to {money(lines_sum)}, subtotal says {money(inv.subtotal)}")
    expected = (inv.subtotal if inv.subtotal is not None else lines_sum) + (inv.tax or 0)
    if inv.total is not None and abs(expected - inv.total) > CENT:
        inv.issues.append(f"subtotal + tax = {money(expected)}, but total says {money(inv.total)}")
    if inv.invoice_date and inv.due_date and inv.due_date < inv.invoice_date:
        inv.issues.append("due date is before the invoice date")


# ---------------------------------------------------------------- output
def write_excel(invoices: list[Invoice], path: Path) -> None:
    from openpyxl import Workbook
    from openpyxl.formatting.rule import FormulaRule
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    head_fill, head_font = PatternFill("solid", fgColor="1F3B5C"), Font(name="Calibri", bold=True, color="FFFFFF")
    bold = Font(name="Calibri", bold=True)
    wb = Workbook()

    def sheet(ws, headers, widths):
        ws.append(headers)
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w
            ws.cell(1, i).fill, ws.cell(1, i).font = head_fill, head_font
            ws.cell(1, i).alignment = Alignment(vertical="center")
        ws.row_dimensions[1].height = 22
        ws.freeze_panes = "A2"

    ws = wb.active
    ws.title = "Invoices"
    sheet(
        ws,
        [
            "File",
            "Supplier",
            "Invoice no.",
            "Invoice date",
            "Due date",
            "Currency",
            "Subtotal",
            "Tax",
            "Total",
            "Lines",
            "Read from",
            "Check",
        ],
        [30, 28, 15, 13, 13, 9, 12, 11, 12, 7, 10, 60],
    )
    for inv in invoices:
        ws.append(
            [
                inv.file,
                inv.supplier,
                inv.number,
                inv.invoice_date,
                inv.due_date,
                inv.currency,
                inv.subtotal,
                inv.tax,
                inv.total,
                len(inv.lines),
                inv.source,
                inv.check,
            ]
        )
        r = ws.max_row
        fmt = CURRENCY_FORMATS.get(inv.currency, "#,##0.00")
        for col in (7, 8, 9):
            ws.cell(r, col).number_format = fmt
        for col in (4, 5):
            ws.cell(r, col).number_format = "dd mmm yyyy"
    last = ws.max_row
    ws.auto_filter.ref = f"A1:L{last}"
    ws.conditional_formatting.add(f"L2:L{last}", FormulaRule(formula=['$L2="OK"'], fill=PatternFill("solid", fgColor="D1E7DD")))
    ws.conditional_formatting.add(f"L2:L{last}", FormulaRule(formula=['$L2<>"OK"'], fill=PatternFill("solid", fgColor="F8D7DA")))

    li = wb.create_sheet("Line items")
    sheet(
        li,
        ["File", "Supplier", "Invoice no.", "#", "Description", "Qty", "Unit price", "Amount", "Note"],
        [30, 28, 15, 5, 40, 7, 12, 12, 45],
    )
    for inv in invoices:
        fmt = CURRENCY_FORMATS.get(inv.currency, "#,##0.00")
        for i, ln in enumerate(inv.lines, 1):
            li.append([inv.file, inv.supplier, inv.number, i, ln.description, ln.qty, ln.unit, ln.amount, ln.note])
            li.cell(li.max_row, 7).number_format = li.cell(li.max_row, 8).number_format = fmt
    li.auto_filter.ref = f"A1:I{li.max_row}"

    sm = wb.create_sheet("Summary")
    sheet(sm, ["Supplier", "Currency", "Invoices", "Total", "Need a check"], [30, 10, 10, 14, 13])
    pairs = sorted({(inv.supplier, inv.currency) for inv in invoices})
    for sup, cur in pairs:
        r = sm.max_row + 1
        sm.append(
            [
                sup,
                cur,
                f"=COUNTIFS(Invoices!B:B,A{r},Invoices!F:F,B{r})",
                f"=SUMIFS(Invoices!I:I,Invoices!B:B,A{r},Invoices!F:F,B{r})",
                f'=COUNTIFS(Invoices!B:B,A{r},Invoices!F:F,B{r},Invoices!L:L,"<>OK")',
            ]
        )
        sm.cell(r, 4).number_format = CURRENCY_FORMATS.get(cur, "#,##0.00")
    r = sm.max_row + 2
    sm.cell(r, 1, "All invoices").font = bold
    sm.cell(r, 3, f"=COUNTA(Invoices!A2:A{last})").font = bold
    sm.cell(r, 5, f'=COUNTIF(Invoices!L2:L{last},"<>OK")').font = bold

    for w in wb.worksheets:  # printable: gridlines and row/column headings, landscape
        w.print_options.gridLines = True
        w.print_options.headings = True
        w.page_setup.orientation = "landscape"
        w.page_setup.fitToWidth, w.page_setup.fitToHeight = 1, 0
        w.sheet_properties.pageSetUpPr.fitToPage = True
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


def write_csv(invoices: list[Invoice], folder: Path) -> None:
    with open(folder / "invoices.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "file",
                "supplier",
                "invoice_no",
                "invoice_date",
                "due_date",
                "currency",
                "subtotal",
                "tax",
                "total",
                "lines",
                "read_from",
                "check",
            ]
        )
        for inv in invoices:
            w.writerow(
                [
                    inv.file,
                    inv.supplier,
                    inv.number,
                    inv.invoice_date,
                    inv.due_date,
                    inv.currency,
                    inv.subtotal,
                    inv.tax,
                    inv.total,
                    len(inv.lines),
                    inv.source,
                    inv.check,
                ]
            )
    with open(folder / "line_items.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["file", "invoice_no", "n", "description", "qty", "unit_price", "amount", "note"])
        for inv in invoices:
            for i, ln in enumerate(inv.lines, 1):
                w.writerow([inv.file, inv.number, i, ln.description, ln.qty, ln.unit, ln.amount, ln.note])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Invoice PDFs -> Excel, with checks")
    ap.add_argument("folder", type=Path, help="folder with PDF invoices")
    ap.add_argument("-o", "--output", type=Path, default=Path("output/invoices.xlsx"))
    args = ap.parse_args(argv)

    files = sorted(args.folder.glob("*.pdf"))
    if not files:
        print(f"No PDF files in {args.folder}")
        return 1
    invoices = []
    for path in files:
        lines, source, supplier = read_pdf(path)
        inv = parse_invoice(path.name, lines, source, supplier)
        invoices.append(inv)
        mark = "OK " if not inv.issues else "!! "
        print(
            f"{mark} {path.name:28} {inv.supplier[:28]:28} {inv.number:13} {inv.currency} {inv.total or 0:>10,.2f}  {len(inv.lines):>2} lines  {source}"
        )
        for issue in inv.issues:
            print(f"      -> {issue}")
    write_excel(invoices, args.output)
    write_csv(invoices, args.output.parent)
    bad = sum(1 for inv in invoices if inv.issues)
    print(f"\n{len(invoices)} invoices, {sum(len(i.lines) for i in invoices)} lines -> {args.output}")
    print(f"{bad} need a check" if bad else "All invoices add up")
    return 0


if __name__ == "__main__":
    sys.exit(main())
