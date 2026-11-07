"""Messages sent to clients, barbers and admins about bookings."""
from __future__ import annotations

import logging
from html import escape

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .config import settings
from .db import db, loc, money, parse
from .i18n import fmt_when, t

log = logging.getLogger(__name__)


def client_label(b) -> str:
    """HTML-safe client name for staff messages."""
    name = escape(b["user_name"] or "Client")
    return f"{name} (@{escape(b['username'])})" if b["username"] else name


async def safe_send(bot: Bot, chat_id: int, text: str, **kw) -> bool:
    try:
        await bot.send_message(chat_id, text, **kw)
        return True
    except Exception as e:  # blocked bot, deleted chat, etc.
        log.warning("send to %s failed: %s", chat_id, e)
        return False


async def staff_ids_for(b) -> set[int]:
    ids = set(settings.admin_ids)
    if b["master_tg"]:
        ids.add(b["master_tg"])
    return ids


async def staff_lang(chat_id: int) -> str | None:
    u = await db.get_user(chat_id)
    return u["lang"] if u else None


def pay_lines(lang: str | None, b) -> str:
    """Extra lines for a client message about an online payment."""
    if b["pay_status"] not in ("paid",) or not b["paid_amount"]:
        return ""
    lines = "\n" + t(lang, "pay_line", amount=money(b["paid_amount"]))
    rest = round(b["price"] - b["paid_amount"], 2)
    if rest > 0:
        lines += "\n" + t(lang, "pay_rest", amount=money(rest))
    return lines


async def notify_booked(bot: Bot, booking_id: int, rescheduled: bool = False) -> None:
    b = await db.booking(booking_id)
    lang = b["lang"]
    when = fmt_when(lang, parse(b["start"]))
    key = "rescheduled" if rescheduled else "confirmed"
    await safe_send(
        bot, b["user_id"],
        t(lang, key, service=loc(b, "name", lang), master=b["master_name"], when=when,
          price=money(b["price"]), address=settings.shop_address) + pay_lines(lang, b),
    )
    staff_key = "a_rescheduled_booking" if rescheduled else "a_new_booking"
    for sid in await staff_ids_for(b):
        sl = await staff_lang(sid)
        paid = ("\n" + t(sl, "a_paid_tag", amount=money(b["paid_amount"]))) if b["pay_status"] == "paid" else ""
        await safe_send(
            bot, sid,
            t(sl, staff_key, service=loc(b, "name", sl), master=b["master_name"],
              when=fmt_when(sl, parse(b["start"])), client=client_label(b), paid=paid),
        )


def refund_text(lang: str | None, b) -> str:
    """Line for the client after cancelling, based on the refund decision stored on the booking."""
    if b["pay_status"] == "refund_due":
        return t(lang, "refund_yes", amount=money(b["paid_amount"]))
    if b["pay_status"] == "kept":
        return t(lang, "refund_no", amount=money(b["paid_amount"]), hours=settings.refund_free_hours)
    return ""


async def notify_cancelled(bot: Bot, b) -> None:
    """`b` is the booking row as it was before cancelling; status is re-read for refunds."""
    if b["status"] == "pending":
        return  # an unpaid hold was released, nothing to tell the staff
    fresh = await db.booking(b["id"])
    for sid in await staff_ids_for(b):
        sl = await staff_lang(sid)
        when = fmt_when(sl, parse(b["start"]))
        await safe_send(
            bot, sid,
            t(sl, "a_cancelled_booking", service=loc(b, "name", sl), master=b["master_name"],
              when=when, client=client_label(b)),
        )
        if fresh["pay_status"] == "refund_due" and sid in settings.admin_ids:
            await safe_send(
                bot, sid,
                t(sl, "a_refund_due", amount=money(fresh["paid_amount"]), service=loc(b, "name", sl),
                  when=when, client=client_label(b)),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text=t(sl, "a_refunded"), callback_data=f"adm:refunded:{b['id']}")]]),
            )
