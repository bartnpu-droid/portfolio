from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

import extract

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


def load(name):
    lines, source, supplier = extract.read_pdf(SAMPLES / name)
    return extract.parse_invoice(name, lines, source, supplier)


@pytest.fixture(scope="module")
def invoices():
    return {p.name.split("-")[0]: load(p.name) for p in SAMPLES.glob("*.pdf")}


def test_uk_invoice_with_ruled_table(invoices):
    inv = invoices["northwind"]
    assert inv.supplier == "Northwind Office Supply Ltd"  # the bigger "INVOICE" heading is skipped
    assert (inv.number, inv.invoice_date, inv.due_date, inv.currency) == ("NW-2026-0417", date(2026, 11, 2), date(2026, 11, 16), "GBP")
    assert (inv.subtotal, inv.tax, inv.total) == (Decimal("187.30"), Decimal("37.46"), Decimal("224.76"))
    assert len(inv.lines) == 3 and inv.check == "OK"


def test_eu_invoice_with_comma_decimals(invoices):
    inv = invoices["bluepeak"]
    assert (inv.number, inv.currency) == ("BP-58213", "EUR")
    assert (inv.invoice_date, inv.due_date) == (date(2026, 11, 1), date(2026, 11, 15))
    assert (inv.subtotal, inv.tax, inv.total) == (Decimal("87.00"), Decimal("18.27"), Decimal("105.27"))
    assert inv.lines[2].qty == 7 and inv.lines[2].amount == Decimal("49.00")
    assert inv.check == "OK"


def test_two_page_invoice_keeps_all_lines(invoices):
    inv = invoices["greenleaf"]
    assert inv.number == "GL/26/1093"
    assert len(inv.lines) == 18
    assert inv.lines[-1].description == "Delivery and set-up"
    assert sum(ln.amount for ln in inv.lines) == inv.subtotal
    assert inv.check == "OK"


def test_wrong_total_is_flagged(invoices):
    inv = invoices["atlas"]
    assert (inv.invoice_date, inv.due_date, inv.currency) == (date(2026, 11, 3), date(2026, 12, 3), "USD")
    assert inv.check.startswith("Check:")
    assert "subtotal + tax = $1,098.00, but total says $1,134.00" in inv.check


def test_scan_is_read_with_ocr(invoices):
    inv = invoices["harbor"]
    assert inv.source == "OCR"
    assert (inv.supplier, inv.number, inv.invoice_date) == ("Harbor Print Co.", "HP-3391", date(2026, 11, 5))
    assert inv.total == Decimal("301.20") and len(inv.lines) == 3
    assert inv.check == "OK"


@pytest.mark.parametrize(
    "text,value",
    [
        ("£1,147.70", "1147.70"),
        ("€ 1.234,56", "1234.56"),
        ("$47.50", "47.50"),
        ("105,27", "105.27"),
        ("-12.00", "-12.00"),
    ],
)
def test_amounts_in_uk_and_eu_format(text, value):
    assert extract.parse_amount(text) == Decimal(value)


def test_dates_follow_the_currency():
    assert extract.parse_date("Invoice date: 02/11/2026", us=False) == date(2026, 11, 2)
    assert extract.parse_date("Invoice date: 11/02/2026", us=True) == date(2026, 11, 2)
    assert extract.parse_date("Date of issue: 1 November 2026", us=False) == date(2026, 11, 1)
    assert extract.parse_date("no date here", us=False) is None


def test_ocr_misread_quantity_is_worked_out_from_the_amount():
    line = extract.parse_line("A5 flyers, 1000 pcs cf £96.00 £96.00")
    assert line.qty == 1 and line.amount == Decimal("96.00") and "taken from the amount" in line.note
    assert extract.parse_line("Some text without prices") is None


def test_checks_catch_line_and_subtotal_errors():
    inv = extract.parse_invoice(
        "x.pdf",
        [
            "Acme Ltd",
            "Invoice No: A-100",
            "Invoice date: 01/11/2026",
            "Due date: 01/10/2026",
            "Description Qty Unit price Amount",
            "Widget 2 £10.00 £25.00",
            "Subtotal £20.00",
            "VAT (20%) £4.00",
            "Total £24.00",
        ],
        "text",
        "",
    )
    assert "line 1: 2 x £10.00 is not £25.00" in inv.check
    assert "lines add up to £25.00, subtotal says £20.00" in inv.check
    assert "due date is before the invoice date" in inv.check


def test_excel_and_csv_output(invoices, tmp_path):
    from openpyxl import load_workbook

    out = tmp_path / "invoices.xlsx"
    extract.write_excel(list(invoices.values()), out)
    extract.write_csv(list(invoices.values()), tmp_path)
    wb = load_workbook(out)
    assert wb.sheetnames == ["Invoices", "Line items", "Summary"]
    assert wb["Invoices"].max_row == 6 and wb["Line items"].max_row == 31
    assert wb["Summary"]["C2"].value.startswith("=COUNTIFS(")
    assert (tmp_path / "invoices.csv").read_text().count("\n") == 6
