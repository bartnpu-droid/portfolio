"""Client-side bot: menu, prices, contacts, my bookings, cancellation, reviews."""
from __future__ import annotations

from html import escape

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, Message, PreCheckoutQuery

from .. import keyboards as kb
from datetime import timedelta

from ..booking import BookingError, cancel_booking, confirm_payment, refund_policy
from ..config import BASE_DIR, settings
from ..db import FMT, db, loc, money, now_local, parse
from ..i18n import fmt_when, norm_lang, t
from ..notify import (client_label, notify_booked, notify_cancelled, pay_lines, refund_text, safe_send,
                      staff_ids_for, staff_lang)

router = Router(name="client")


class Review(StatesGroup):
    comment = State()


async def user_lang(user) -> str:
    """Register the user if needed and return their language."""
    is_new = await db.upsert_user(user.id, user.first_name, user.username)
    row = await db.get_user(user.id)
    if is_new or not row["lang"]:
        lang = norm_lang(user.language_code)
        await db.set_lang(user.id, lang)
        return lang
    return norm_lang(row["lang"])


BANNER = BASE_DIR / "assets" / "banner.jpg"
_banner_file_id: str | None = None  # re-use the uploaded photo after the first send


async def edit(message: Message, text: str, markup=None) -> None:
    """Edit a menu message whether it is a photo (caption) or plain text."""
    if message.photo:
        await message.edit_caption(caption=text, reply_markup=markup)
    else:
        await message.edit_text(text, reply_markup=markup)


async def show_menu(message: Message, lang: str, edit_existing: bool = False) -> None:
    global _banner_file_id
    text = t(lang, "welcome", shop=settings.shop_name)
    if edit_existing:
        await edit(message, text, kb.main_menu(lang))
        return
    if BANNER.exists():
        sent = await message.answer_photo(_banner_file_id or FSInputFile(BANNER), caption=text,
                                          reply_markup=kb.main_menu(lang))
        _banner_file_id = sent.photo[-1].file_id
    else:
        await message.answer(text, reply_markup=kb.main_menu(lang))


@router.message(CommandStart())
async def start(message: Message, state: FSMContext) -> None:
    await state.clear()
    is_new = (await db.get_user(message.from_user.id)) is None
    lang = await user_lang(message.from_user)
    if is_new and len(settings.languages) > 1:
        await message.answer(t(lang, "choose_lang"), reply_markup=kb.lang_menu())
        return
    await show_menu(message, lang)


@router.message(Command("menu"))
async def menu_cmd(message: Message, state: FSMContext) -> None:
    await state.clear()
    await show_menu(message, await user_lang(message.from_user))


@router.callback_query(F.data == "menu")
async def menu_cb(cb: CallbackQuery) -> None:
    await show_menu(cb.message, await user_lang(cb.from_user), edit_existing=True)
    await cb.answer()


@router.callback_query(F.data == "lang")
async def lang_cb(cb: CallbackQuery) -> None:
    lang = await user_lang(cb.from_user)
    await edit(cb.message, t(lang, "choose_lang"), kb.lang_menu())
    await cb.answer()


@router.callback_query(F.data.startswith("setlang:"))
async def setlang_cb(cb: CallbackQuery) -> None:
    lang = cb.data.split(":", 1)[1]
    if lang in settings.languages:
        await user_lang(cb.from_user)
        await db.set_lang(cb.from_user.id, lang)
    lang = norm_lang(lang)
    await cb.answer(t(lang, "lang_set"))
    await show_menu(cb.message, lang, edit_existing=True)


@router.callback_query(F.data == "prices")
async def prices_cb(cb: CallbackQuery) -> None:
    lang = await user_lang(cb.from_user)
    lines = [t(lang, "prices_title")]
    for s in await db.services():
        lines.append(t(lang, "price_line", name=loc(s, "name", lang), price=money(s["price"]), dur=s["duration_min"]))
    await edit(cb.message, "\n".join(lines), kb.back_menu(lang))
    await cb.answer()


@router.callback_query(F.data == "contacts")
async def contacts_cb(cb: CallbackQuery, bot: Bot) -> None:
    lang = await user_lang(cb.from_user)
    await edit(
        cb.message,
        t(lang, "contacts", shop=settings.shop_name, address=settings.shop_address, open=settings.open_time,
          close=settings.close_time, phone=settings.shop_phone),
        kb.back_menu(lang),
    )
    await bot.send_venue(cb.from_user.id, settings.shop_lat, settings.shop_lon,
                         settings.shop_name, settings.shop_address)
    await cb.answer()


def booking_text(lang: str, b) -> str:
    return t(lang, "booking_line", service=loc(b, "name", lang), master=b["master_name"],
             when=fmt_when(lang, parse(b["start"])), price=money(b["price"])) + pay_lines(lang, b)


@router.message(Command("my"))
@router.callback_query(F.data == "my")
async def my_bookings(event: Message | CallbackQuery) -> None:
    lang = await user_lang(event.from_user)
    message = event.message if isinstance(event, CallbackQuery) else event
    items = await db.user_upcoming(event.from_user.id)
    if isinstance(event, CallbackQuery):
        await event.answer()
    if not items:
        await message.answer(t(lang, "my_empty"), reply_markup=kb.main_menu(lang))
        return
    await message.answer(t(lang, "my_title"))
    for b in items:
        await message.answer(booking_text(lang, b), reply_markup=kb.booking_actions(lang, b["id"]))


@router.callback_query(F.data.startswith("cancel:"))
async def cancel_ask(cb: CallbackQuery) -> None:
    lang = await user_lang(cb.from_user)
    bid = int(cb.data.split(":")[1])
    b = await db.booking(bid)
    if not b or b["user_id"] != cb.from_user.id or b["status"] != "booked":
        await cb.answer(t(lang, "error_generic"), show_alert=True)
        return
    text = t(lang, "cancel_confirm", line=booking_text(lang, b))
    policy = refund_policy(b)
    if policy:
        key = "refund_yes" if policy == "refund" else "refund_no"
        text += "\n\n" + t(lang, key, amount=money(b["paid_amount"]), hours=settings.refund_free_hours)
    await cb.message.edit_text(text, reply_markup=kb.cancel_confirm(lang, bid))
    await cb.answer()


@router.callback_query(F.data.startswith("cancelyes:"))
async def cancel_yes(cb: CallbackQuery, bot: Bot) -> None:
    lang = await user_lang(cb.from_user)
    try:
        b = await cancel_booking(cb.from_user.id, int(cb.data.split(":")[1]))
    except BookingError:
        await cb.answer(t(lang, "error_generic"), show_alert=True)
        return
    extra = refund_text(lang, await db.booking(b["id"]))
    await cb.message.edit_text(t(lang, "cancelled") + (("\n\n" + extra) if extra else ""))
    await cb.answer()
    await notify_cancelled(bot, b)


@router.callback_query(F.data == "keep")
async def keep(cb: CallbackQuery) -> None:
    lang = await user_lang(cb.from_user)
    await cb.message.edit_text(t(lang, "kept"))
    await cb.answer()


# ---------- reviews ----------
@router.callback_query(F.data.startswith("rate:"))
async def rate(cb: CallbackQuery, state: FSMContext) -> None:
    lang = await user_lang(cb.from_user)
    _, bid, n = cb.data.split(":")
    b = await db.booking(int(bid))
    if not b or b["user_id"] != cb.from_user.id:
        await cb.answer()
        return
    n = max(1, min(5, int(n)))
    await db.execute("UPDATE bookings SET rating=? WHERE id=?", (n, b["id"]))
    await state.set_state(Review.comment)
    await state.update_data(bid=b["id"])
    await cb.message.edit_text(t(lang, "review_comment", stars="⭐" * n), reply_markup=kb.skip_kb(lang))
    await cb.answer()


async def finish_review(bot: Bot, bid: int, comment: str | None) -> None:
    if comment:
        await db.execute("UPDATE bookings SET review_text=? WHERE id=?", (comment[:1000], bid))
    b = await db.booking(bid)
    for sid in await staff_ids_for(b):
        sl = await staff_lang(sid)
        await safe_send(bot, sid, t(sl, "a_new_review", stars="⭐" * (b["rating"] or 0),
                                    master=escape(b["master_name"]), client=client_label(b),
                                    comment=escape(comment or "")))


@router.callback_query(Review.comment, F.data == "rskip")
async def review_skip(cb: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    lang = await user_lang(cb.from_user)
    data = await state.get_data()
    await state.clear()
    await cb.message.edit_text(t(lang, "review_thanks"))
    await cb.answer()
    await finish_review(bot, data["bid"], None)


@router.message(Review.comment, F.text)
async def review_comment(message: Message, state: FSMContext, bot: Bot) -> None:
    lang = await user_lang(message.from_user)
    data = await state.get_data()
    await state.clear()
    await message.answer(t(lang, "review_thanks"), reply_markup=kb.main_menu(lang))
    await finish_review(bot, data["bid"], message.text)


# ---------- payments ----------
def _booking_id(payload: str) -> int | None:
    if payload.startswith("booking:"):
        try:
            return int(payload.split(":", 1)[1])
        except ValueError:
            return None
    return None


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery) -> None:
    """Telegram asks us to confirm right before charging the card."""
    lang = await user_lang(query.from_user)
    bid = _booking_id(query.invoice_payload)
    b = await db.booking(bid) if bid else None
    now = now_local()
    ok = bool(b and b["user_id"] == query.from_user.id and b["status"] == "pending"
              and b["hold_until"] and parse(b["hold_until"]) >= now)
    if ok:  # give the client a little extra time to finish 3-D Secure etc.
        await db.execute("UPDATE bookings SET hold_until=? WHERE id=?",
                         ((now + timedelta(minutes=5)).strftime(FMT), bid))
        await query.answer(ok=True)
    else:
        await query.answer(ok=False, error_message=t(lang, "pay_expired"))


@router.message(F.successful_payment)
async def payment_done(message: Message, bot: Bot) -> None:
    sp = message.successful_payment
    bid = _booking_id(sp.invoice_payload)
    if not bid:
        return
    await confirm_payment(bid, sp.total_amount / 100, sp.provider_payment_charge_id)
    await notify_booked(bot, bid)
