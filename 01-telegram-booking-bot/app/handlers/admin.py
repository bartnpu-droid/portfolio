"""Staff panel: day schedule, stats, services, barbers, days off, broadcast, export."""
from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from html import escape

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery
from aiogram.types import InlineKeyboardButton as Btn
from aiogram.types import InlineKeyboardMarkup, Message

from ..config import settings
from ..db import db, loc, money, now_local, parse
from ..booking import pay_config
from ..export import export_csv, export_to_sheets, sheets_enabled
from ..i18n import WEEKDAYS, fmt_date, norm_lang, t
from ..notify import client_label

log = logging.getLogger(__name__)
router = Router(name="admin")
router.message.filter(F.from_user.id.in_(settings.admin_ids))
router.callback_query.filter(F.from_user.id.in_(settings.admin_ids))

STATUS_ICON = {"booked": "🟢", "done": "✅", "no_show": "🚫"}


class Adm(StatesGroup):
    price = State()
    add_name = State()
    add_dur = State()
    add_price = State()
    day_off = State()
    link = State()
    broadcast = State()


def kbd(rows) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def lang_of(user) -> str:
    row = await db.get_user(user.id)
    if not row:
        await db.upsert_user(user.id, user.first_name, user.username)
        await db.set_lang(user.id, norm_lang(user.language_code))
        row = await db.get_user(user.id)
    return norm_lang(row["lang"])


def menu_kb(lang: str) -> InlineKeyboardMarkup:
    return kbd([
        [Btn(text=t(lang, "a_today"), callback_data="adm:day:0"),
         Btn(text=t(lang, "a_tomorrow"), callback_data="adm:day:1")],
        [Btn(text=t(lang, "a_stats"), callback_data="adm:stats")],
        [Btn(text=t(lang, "a_services"), callback_data="adm:svcs"),
         Btn(text=t(lang, "a_masters"), callback_data="adm:ms")],
        [Btn(text=t(lang, "a_payments"), callback_data="adm:pay")],
        [Btn(text=t(lang, "a_broadcast"), callback_data="adm:bc"),
         Btn(text=t(lang, "a_export"), callback_data="adm:export")],
    ])


def back_kb(lang: str, to: str = "adm:menu") -> InlineKeyboardMarkup:
    return kbd([[Btn(text=t(lang, "btn_back"), callback_data=to)]])


@router.message(Command("admin"))
async def admin_cmd(message: Message, state: FSMContext) -> None:
    await state.clear()
    lang = await lang_of(message.from_user)
    await message.answer(t(lang, "admin_title", shop=settings.shop_name), reply_markup=menu_kb(lang))


@router.callback_query(F.data == "adm:menu")
async def admin_menu(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    lang = await lang_of(cb.from_user)
    await cb.message.edit_text(t(lang, "admin_title", shop=settings.shop_name), reply_markup=menu_kb(lang))
    await cb.answer()


# ---------- day schedule ----------
async def send_day(message: Message, lang: str, offset: int) -> None:
    day = now_local().date() + timedelta(days=offset)
    items = await db.bookings_on(day)
    label = fmt_date(lang, day)
    if not items:
        await message.answer(t(lang, "a_day_empty", date=label), reply_markup=back_kb(lang))
        return
    await message.answer(t(lang, "a_day_title", date=label))
    for b in items:
        text = t(lang, "a_booking", icon=STATUS_ICON.get(b["status"], "•"), time=b["start"][11:],
                 service=escape(loc(b, "name", lang)), master=escape(b["master_name"]), client=client_label(b))
        if b["pay_status"] == "paid":
            text += "\n" + t(lang, "a_paid_tag", amount=money(b["paid_amount"]))
        markup = None
        if b["status"] == "booked":
            markup = kbd([[Btn(text=t(lang, "a_done"), callback_data=f"adm:st:{b['id']}:done"),
                           Btn(text=t(lang, "a_noshow"), callback_data=f"adm:st:{b['id']}:no_show")]])
        await message.answer(text, reply_markup=markup)
    await message.answer("⬆️", reply_markup=back_kb(lang))


@router.callback_query(F.data.startswith("adm:day:"))
async def day_cb(cb: CallbackQuery) -> None:
    await cb.answer()
    await send_day(cb.message, await lang_of(cb.from_user), int(cb.data.split(":")[2]))


@router.callback_query(F.data.startswith("adm:st:"))
async def status_cb(cb: CallbackQuery) -> None:
    lang = await lang_of(cb.from_user)
    _, _, bid, status = cb.data.split(":")
    if status not in ("done", "no_show"):
        return await cb.answer()
    await db.set_status(int(bid), status)
    b = await db.booking(int(bid))
    await cb.message.edit_text(t(lang, "a_booking", icon=STATUS_ICON[status], time=b["start"][11:],
                                 service=escape(loc(b, "name", lang)), master=escape(b["master_name"]),
                                 client=client_label(b)))
    await cb.answer(t(lang, "a_marked"))


# ---------- stats ----------
@router.callback_query(F.data == "adm:stats")
async def stats_cb(cb: CallbackQuery) -> None:
    lang = await lang_of(cb.from_user)
    today = now_local().date()
    since, until = (today - timedelta(days=6)).isoformat(), (today + timedelta(days=1)).isoformat()
    period = "b.start >= ? AND b.start < ?"
    p = (since, until)

    counts = {r["status"]: r["n"] for r in await db.fetchall(
        f"SELECT status, COUNT(*) n FROM bookings b WHERE {period} AND status NOT IN ('pending','expired') "
        f"GROUP BY status", p)}
    paid_online = (await db.fetchone(
        f"SELECT COALESCE(SUM(paid_amount),0) s FROM bookings b WHERE {period} AND pay_status IN ('paid','kept')", p))["s"]
    revenue = (await db.fetchone(
        f"SELECT COALESCE(SUM(price),0) s FROM bookings b WHERE {period} AND status='done'", p))["s"]
    new_users = (await db.fetchone(
        "SELECT COUNT(*) n FROM users WHERE created_at >= ? AND created_at < ?", p))["n"]
    top_s = await db.fetchone(
        f"SELECT s.name_en, COUNT(*) n FROM bookings b JOIN services s ON s.id=b.service_id "
        f"WHERE {period} AND b.status!='cancelled' GROUP BY s.id ORDER BY n DESC LIMIT 1", p)
    top_m = await db.fetchone(
        f"SELECT m.name, COUNT(*) n FROM bookings b JOIN masters m ON m.id=b.master_id "
        f"WHERE {period} AND b.status!='cancelled' GROUP BY m.id ORDER BY n DESC LIMIT 1", p)
    rating = (await db.fetchone(
        f"SELECT AVG(rating) r FROM bookings b WHERE {period} AND rating IS NOT NULL", p))["r"]

    no = t(lang, "no")
    text = t(lang, "a_stats_text",
             total=sum(counts.values()), done=counts.get("done", 0), cancelled=counts.get("cancelled", 0),
             noshow=counts.get("no_show", 0), revenue=money(revenue), new_users=new_users,
             paid_online=t(lang, "a_paid_online", amount=money(paid_online)),
             top_service=f"{escape(loc(top_s, 'name', lang))} ({top_s['n']})" if top_s else no,
             top_master=f"{escape(top_m['name'])} ({top_m['n']})" if top_m else no,
             rating=f"{rating:.1f}" if rating else no)
    await cb.message.edit_text(text, reply_markup=back_kb(lang))
    await cb.answer()


# ---------- services ----------
async def services_view(lang: str):
    rows = [[Btn(text=("" if s["active"] else "🙈 ") + f"{loc(s, 'name', lang)} · {money(s['price'])}",
                 callback_data=f"adm:svc:{s['id']}")] for s in await db.services(only_active=False)]
    rows.append([Btn(text=t(lang, "a_add_service"), callback_data="adm:svcadd")])
    rows.append([Btn(text=t(lang, "btn_back"), callback_data="adm:menu")])
    return t(lang, "a_services_title"), kbd(rows)


@router.callback_query(F.data == "adm:svcs")
async def services_cb(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    text, markup = await services_view(await lang_of(cb.from_user))
    await cb.message.edit_text(text, reply_markup=markup)
    await cb.answer()


def service_card(lang: str, s):
    text = t(lang, "a_service_card", name=escape(loc(s, "name", lang)), dur=s["duration_min"],
             price=money(s["price"]), status=t(lang, "a_active" if s["active"] else "a_hidden"))
    markup = kbd([
        [Btn(text=t(lang, "a_edit_price"), callback_data=f"adm:svcprice:{s['id']}"),
         Btn(text=t(lang, "a_toggle"), callback_data=f"adm:svctog:{s['id']}")],
        [Btn(text=t(lang, "btn_back"), callback_data="adm:svcs")],
    ])
    return text, markup


@router.callback_query(F.data.startswith("adm:svc:"))
async def service_cb(cb: CallbackQuery) -> None:
    lang = await lang_of(cb.from_user)
    s = await db.service(int(cb.data.split(":")[2]))
    text, markup = service_card(lang, s)
    await cb.message.edit_text(text, reply_markup=markup)
    await cb.answer()


@router.callback_query(F.data.startswith("adm:svctog:"))
async def service_toggle(cb: CallbackQuery) -> None:
    lang = await lang_of(cb.from_user)
    sid = int(cb.data.split(":")[2])
    await db.execute("UPDATE services SET active = 1 - active WHERE id=?", (sid,))
    text, markup = service_card(lang, await db.service(sid))
    await cb.message.edit_text(text, reply_markup=markup)
    await cb.answer(t(lang, "a_saved"))


@router.callback_query(F.data.startswith("adm:svcprice:"))
async def service_price_ask(cb: CallbackQuery, state: FSMContext) -> None:
    lang = await lang_of(cb.from_user)
    await state.set_state(Adm.price)
    await state.update_data(sid=int(cb.data.split(":")[2]))
    await cb.message.answer(t(lang, "a_ask_price"), reply_markup=back_kb(lang, "adm:svcs"))
    await cb.answer()


def parse_number(text: str | None) -> float | None:
    try:
        v = float((text or "").replace(",", ".").strip().lstrip("$€£"))
        return v if v > 0 else None
    except ValueError:
        return None


@router.message(Adm.price)
async def service_price_set(message: Message, state: FSMContext) -> None:
    lang = await lang_of(message.from_user)
    value = parse_number(message.text)
    if value is None:
        return await message.answer(t(lang, "a_bad_number"))
    sid = (await state.get_data())["sid"]
    await state.clear()
    await db.execute("UPDATE services SET price=? WHERE id=?", (value, sid))
    text, markup = service_card(lang, await db.service(sid))
    await message.answer(t(lang, "a_saved") + "\n\n" + text, reply_markup=markup)


@router.callback_query(F.data == "adm:svcadd")
async def service_add(cb: CallbackQuery, state: FSMContext) -> None:
    lang = await lang_of(cb.from_user)
    await state.set_state(Adm.add_name)
    await cb.message.answer(t(lang, "a_ask_service_name"), reply_markup=back_kb(lang, "adm:svcs"))
    await cb.answer()


@router.message(Adm.add_name, F.text)
async def service_add_name(message: Message, state: FSMContext) -> None:
    lang = await lang_of(message.from_user)
    await state.update_data(name=message.text.strip()[:60])
    await state.set_state(Adm.add_dur)
    await message.answer(t(lang, "a_ask_service_duration"))


@router.message(Adm.add_dur)
async def service_add_dur(message: Message, state: FSMContext) -> None:
    lang = await lang_of(message.from_user)
    value = parse_number(message.text)
    if value is None or value > 480:
        return await message.answer(t(lang, "a_bad_number"))
    await state.update_data(dur=int(value))
    await state.set_state(Adm.add_price)
    await message.answer(t(lang, "a_ask_service_price"))


@router.message(Adm.add_price)
async def service_add_price(message: Message, state: FSMContext) -> None:
    lang = await lang_of(message.from_user)
    value = parse_number(message.text)
    if value is None:
        return await message.answer(t(lang, "a_bad_number"))
    data = await state.get_data()
    await state.clear()
    sort = (await db.fetchone("SELECT COALESCE(MAX(sort),0)+1 s FROM services"))["s"]
    await db.execute(
        "INSERT INTO services (name_en, duration_min, price, sort) VALUES (?,?,?,?)",
        (data["name"], data["dur"], value, sort))
    text, markup = await services_view(lang)
    await message.answer(t(lang, "a_saved") + "\n\n" + text, reply_markup=markup)


# ---------- barbers ----------
@router.callback_query(F.data == "adm:ms")
async def masters_cb(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    lang = await lang_of(cb.from_user)
    rows = [[Btn(text=("" if m["active"] else "🙈 ") + m["name"], callback_data=f"adm:m:{m['id']}")]
            for m in await db.masters(only_active=False)]
    rows.append([Btn(text=t(lang, "btn_back"), callback_data="adm:menu")])
    await cb.message.edit_text(t(lang, "a_masters_title"), reply_markup=kbd(rows))
    await cb.answer()


async def master_card(lang: str, mid: int):
    m = await db.master(mid)
    offs = sorted(await db.days_off(mid))
    days = ", ".join(WEEKDAYS[lang][int(d)] for d in m["work_days"])
    text = t(lang, "a_master_card", name=escape(m["name"]), title=escape(loc(m, "title", lang) or ""),
             days=days, linked="✅" if m["tg_id"] else "❌",
             status=t(lang, "a_active" if m["active"] else "a_hidden"),
             offs=", ".join(fmt_date(lang, date.fromisoformat(d)) for d in offs[:5]) or t(lang, "no"))
    markup = kbd([
        [Btn(text=t(lang, "a_day_off"), callback_data=f"adm:moff:{mid}"),
         Btn(text=t(lang, "a_link_tg"), callback_data=f"adm:mlink:{mid}")],
        [Btn(text=t(lang, "a_toggle"), callback_data=f"adm:mtog:{mid}")],
        [Btn(text=t(lang, "btn_back"), callback_data="adm:ms")],
    ])
    return text, markup


@router.callback_query(F.data.startswith("adm:m:"))
async def master_cb(cb: CallbackQuery) -> None:
    lang = await lang_of(cb.from_user)
    text, markup = await master_card(lang, int(cb.data.split(":")[2]))
    await cb.message.edit_text(text, reply_markup=markup)
    await cb.answer()


@router.callback_query(F.data.startswith("adm:mtog:"))
async def master_toggle(cb: CallbackQuery) -> None:
    lang = await lang_of(cb.from_user)
    mid = int(cb.data.split(":")[2])
    await db.execute("UPDATE masters SET active = 1 - active WHERE id=?", (mid,))
    text, markup = await master_card(lang, mid)
    await cb.message.edit_text(text, reply_markup=markup)
    await cb.answer(t(lang, "a_saved"))


@router.callback_query(F.data.startswith("adm:moff:"))
async def day_off_ask(cb: CallbackQuery, state: FSMContext) -> None:
    lang = await lang_of(cb.from_user)
    await state.set_state(Adm.day_off)
    await state.update_data(mid=int(cb.data.split(":")[2]))
    await cb.message.answer(t(lang, "a_ask_date"))
    await cb.answer()


@router.message(Adm.day_off)
async def day_off_set(message: Message, state: FSMContext) -> None:
    lang = await lang_of(message.from_user)
    try:
        day = date.fromisoformat((message.text or "").strip())
    except ValueError:
        return await message.answer(t(lang, "a_bad_date"))
    mid = (await state.get_data())["mid"]
    await state.clear()
    await db.add_day_off(mid, day)
    text, markup = await master_card(lang, mid)
    await message.answer(t(lang, "a_saved") + "\n\n" + text, reply_markup=markup)


@router.callback_query(F.data.startswith("adm:mlink:"))
async def link_ask(cb: CallbackQuery, state: FSMContext) -> None:
    lang = await lang_of(cb.from_user)
    await state.set_state(Adm.link)
    await state.update_data(mid=int(cb.data.split(":")[2]))
    await cb.message.answer(t(lang, "a_ask_tg"))
    await cb.answer()


@router.message(Adm.link)
async def link_set(message: Message, state: FSMContext) -> None:
    lang = await lang_of(message.from_user)
    text = (message.text or "").strip()
    if not text.isdigit():
        return await message.answer(t(lang, "a_bad_number"))
    mid = (await state.get_data())["mid"]
    await state.clear()
    await db.execute("UPDATE masters SET tg_id=? WHERE id=?", (int(text), mid))
    card, markup = await master_card(lang, mid)
    await message.answer(t(lang, "a_saved") + "\n\n" + card, reply_markup=markup)


# ---------- broadcast ----------
@router.callback_query(F.data == "adm:bc")
async def broadcast_ask(cb: CallbackQuery, state: FSMContext) -> None:
    lang = await lang_of(cb.from_user)
    await state.set_state(Adm.broadcast)
    await cb.message.answer(t(lang, "a_broadcast_ask"), reply_markup=back_kb(lang))
    await cb.answer()


@router.message(Adm.broadcast, F.text)
async def broadcast_preview(message: Message, state: FSMContext) -> None:
    lang = await lang_of(message.from_user)
    await state.update_data(text=message.html_text)
    n = len(await db.all_user_ids())
    await message.answer(
        t(lang, "a_broadcast_preview", text=message.html_text, n=n),
        reply_markup=kbd([[Btn(text=t(lang, "a_send"), callback_data="adm:bcsend"),
                           Btn(text=t(lang, "a_cancel"), callback_data="adm:menu")]]),
    )


@router.callback_query(Adm.broadcast, F.data == "adm:bcsend")
async def broadcast_send(cb: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    lang = await lang_of(cb.from_user)
    text = (await state.get_data()).get("text")
    await state.clear()
    if not text:
        return await cb.answer()
    await cb.answer()
    ids = await db.all_user_ids()
    ok = 0
    for uid in ids:
        try:
            await bot.send_message(uid, text)
            ok += 1
        except Exception as e:
            log.info("broadcast to %s failed: %s", uid, e)
        await asyncio.sleep(0.05)  # stay well under Telegram limits
    await cb.message.edit_text(t(lang, "a_broadcast_done", ok=ok, n=len(ids)), reply_markup=back_kb(lang))


# ---------- export ----------
@router.callback_query(F.data == "adm:export")
async def export_cb(cb: CallbackQuery) -> None:
    lang = await lang_of(cb.from_user)
    await cb.answer()
    if sheets_enabled():
        try:
            n = await export_to_sheets()
            return await cb.message.answer(t(lang, "a_export_done", n=n), reply_markup=back_kb(lang))
        except Exception:
            log.exception("Google Sheets export failed, falling back to CSV")
    data, n = await export_csv()
    stamp = now_local().strftime("%Y-%m-%d")
    await cb.message.answer_document(BufferedInputFile(data, filename=f"bookings-{stamp}.csv"),
                                     caption=t(lang, "a_export_csv", n=n), reply_markup=back_kb(lang))


# ---------- payments ----------
async def payments_view(lang: str):
    mode, pct = await pay_config()
    stored_pct = int(await db.get_setting("pay_deposit_pct", "30"))
    names = {"off": t(lang, "a_mode_off"), "deposit": t(lang, "a_mode_deposit"), "full": t(lang, "a_mode_full")}
    text = t(lang, "a_pay_title", connected="✅" if settings.payment_token else "❌", mode=names[mode],
             pct=stored_pct, hold=settings.payment_hold_min, hours=settings.refund_free_hours)
    if not settings.payment_token:
        return text + "\n\n" + t(lang, "a_pay_no_token"), back_kb(lang)
    mark = lambda m: ("● " if m == mode else "") + names[m]
    rows = [
        [Btn(text=mark("off"), callback_data="adm:paymode:off")],
        [Btn(text=mark("deposit"), callback_data="adm:paymode:deposit"),
         Btn(text=mark("full"), callback_data="adm:paymode:full")],
        [Btn(text=("● " if stored_pct == p else "") + f"{p}%", callback_data=f"adm:paypct:{p}") for p in (20, 30, 50)],
        [Btn(text=t(lang, "btn_back"), callback_data="adm:menu")],
    ]
    return text, kbd(rows)


@router.callback_query(F.data == "adm:pay")
async def payments_cb(cb: CallbackQuery) -> None:
    text, markup = await payments_view(await lang_of(cb.from_user))
    await cb.message.edit_text(text, reply_markup=markup)
    await cb.answer()


@router.callback_query(F.data.startswith("adm:paymode:") | F.data.startswith("adm:paypct:"))
async def payments_set(cb: CallbackQuery) -> None:
    lang = await lang_of(cb.from_user)
    _, kind, value = cb.data.split(":")
    if kind == "paymode" and value in ("off", "deposit", "full"):
        await db.set_setting("pay_mode", value)
    elif kind == "paypct" and value in ("20", "30", "50"):
        await db.set_setting("pay_deposit_pct", value)
    text, markup = await payments_view(lang)
    try:
        await cb.message.edit_text(text, reply_markup=markup)
    except Exception:
        pass  # "message is not modified"
    await cb.answer(t(lang, "a_saved"))


@router.callback_query(F.data.startswith("adm:refunded:"))
async def refunded_cb(cb: CallbackQuery) -> None:
    lang = await lang_of(cb.from_user)
    bid = int(cb.data.split(":")[2])
    await db.execute("UPDATE bookings SET pay_status='refunded' WHERE id=? AND pay_status='refund_due'", (bid,))
    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.answer(t(lang, "a_refund_marked"), show_alert=True)
