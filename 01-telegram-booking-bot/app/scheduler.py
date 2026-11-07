"""Background loop: reminders 24h / 2h before a visit and review requests after it."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from aiogram import Bot

from . import keyboards as kb
from .booking import expire_holds
from .config import settings
from .db import FMT, db, loc, now_local, parse
from .i18n import fmt_when, t
from .notify import safe_send

log = logging.getLogger(__name__)
REVIEW_DELAY = timedelta(hours=1)


async def tick(bot: Bot) -> None:
    await expire_holds()  # free slots whose payment was never completed
    now = now_local()
    rows = await db.fetchall(
        "SELECT b.*, s.name_en, m.name AS master_name, u.lang FROM bookings b "
        "JOIN services s ON s.id=b.service_id JOIN masters m ON m.id=b.master_id "
        "JOIN users u ON u.tg_id=b.user_id "
        "WHERE b.status IN ('booked','done') AND b.start BETWEEN ? AND ?",
        ((now - timedelta(days=1)).strftime(FMT), (now + timedelta(hours=24)).strftime(FMT)),
    )
    for b in rows:
        start, end, created = parse(b["start"]), parse(b["end"]), parse(b["created_at"])
        lang = b["lang"]
        left = start - now
        args = dict(service=loc(b, "name", lang), master=b["master_name"],
                    when=fmt_when(lang, start), time=start.strftime("%H:%M"), address=settings.shop_address)

        if b["status"] == "booked":
            # 24h reminder only for bookings made well in advance
            if not b["reminded_24"] and timedelta(hours=2) < left <= timedelta(hours=24) \
                    and start - created > timedelta(hours=24):
                await safe_send(bot, b["user_id"], t(lang, "remind_24", **args),
                                reply_markup=kb.booking_actions(lang, b["id"]))
                await db.execute("UPDATE bookings SET reminded_24=1 WHERE id=?", (b["id"],))
            if not b["reminded_2"] and timedelta(0) < left <= timedelta(hours=2) \
                    and start - created > timedelta(hours=2):
                await safe_send(bot, b["user_id"], t(lang, "remind_2", **args))
                await db.execute("UPDATE bookings SET reminded_2=1 WHERE id=?", (b["id"],))

        # After the visit: mark as done (unless staff marked no-show) and ask for a review
        if not b["review_asked"] and end + REVIEW_DELAY <= now:
            if b["status"] == "booked":
                await db.set_status(b["id"], "done")
            await safe_send(bot, b["user_id"], t(lang, "review_ask", master=b["master_name"]),
                            reply_markup=kb.rating_kb(b["id"]))
            await db.execute("UPDATE bookings SET review_asked=1 WHERE id=?", (b["id"],))


async def run(bot: Bot, every_sec: int = 60) -> None:
    while True:
        try:
            await tick(bot)
        except Exception:
            log.exception("scheduler tick failed")
        await asyncio.sleep(every_sec)
