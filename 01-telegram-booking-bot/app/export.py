"""Bookings export: Google Sheets if configured, otherwise CSV."""
from __future__ import annotations

import asyncio
import csv
import io

from .config import settings
from .db import db

HEADER = ["ID", "Date", "Start", "End", "Service", "Barber", "Client", "Username",
          "Price", "Status", "Paid online", "Payment", "Rating", "Review", "Created"]


async def rows() -> list[list]:
    data = await db.fetchall(
        "SELECT b.*, s.name_en, m.name AS master_name, u.name AS user_name, u.username "
        "FROM bookings b JOIN services s ON s.id=b.service_id JOIN masters m ON m.id=b.master_id "
        "JOIN users u ON u.tg_id=b.user_id WHERE b.status NOT IN ('pending','expired') ORDER BY b.start DESC"
    )
    return [[
        r["id"], r["start"][:10], r["start"][11:], r["end"][11:], r["name_en"], r["master_name"],
        r["user_name"] or "", ("@" + r["username"]) if r["username"] else "", r["price"], r["status"],
        r["paid_amount"] or "", r["pay_status"], r["rating"] or "", r["review_text"] or "", r["created_at"],
    ] for r in data]


def sheets_enabled() -> bool:
    return bool(settings.google_sheet_id and settings.google_credentials)


def _push_to_sheets(table: list[list]) -> None:
    import gspread  # optional dependency

    gc = gspread.service_account(filename=settings.google_credentials)
    ws = gc.open_by_key(settings.google_sheet_id).sheet1
    ws.clear()
    ws.update([HEADER] + table, "A1")
    ws.format("A1:O1", {"textFormat": {"bold": True}})
    ws.freeze(rows=1)


async def export_to_sheets() -> int:
    table = await rows()
    await asyncio.to_thread(_push_to_sheets, table)
    return len(table)


async def export_csv() -> tuple[bytes, int]:
    table = await rows()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(HEADER)
    w.writerows(table)
    return buf.getvalue().encode("utf-8-sig"), len(table)
