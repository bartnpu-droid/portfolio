"""HTTP API used by the Mini App + static file serving."""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from aiohttp import web

from aiogram.types import LabeledPrice

from .booking import (BookingError, SlotTaken, amount_due, available_slots, bookable_days, cancel_booking,
                      create_booking, open_days, pay_config)
from .config import BASE_DIR, settings
from .db import db, loc, money, parse
from .i18n import fmt_when, norm_lang, t
from .notify import notify_booked, notify_cancelled
from .webapp_auth import validate_init_data

log = logging.getLogger(__name__)
WEBAPP_DIR = BASE_DIR / "webapp"


@web.middleware
async def auth_middleware(request: web.Request, handler):
    if not request.path.startswith("/api/"):
        return await handler(request)
    user = validate_init_data(request.headers.get("X-Telegram-Init-Data", ""), settings.bot_token)
    if not user and settings.dev_mode:
        dev_id = request.headers.get("X-Dev-User") or request.query.get("dev_user")
        if dev_id:
            user = {"id": int(dev_id), "first_name": "Demo", "language_code": "en"}
    if not user:
        return web.json_response({"error": "unauthorized"}, status=401)
    is_new = await db.upsert_user(user["id"], user.get("first_name"), user.get("username"))
    row = await db.get_user(user["id"])
    if is_new or not row["lang"]:
        lang = norm_lang(user.get("language_code"))
        await db.set_lang(user["id"], lang)
    request["user_id"] = user["id"]
    request["lang"] = norm_lang((await db.get_user(user["id"]))["lang"])
    return await handler(request)


def _booking_json(b, lang: str) -> dict:
    start = parse(b["start"])
    return {
        "id": b["id"],
        "service": loc(b, "name", lang),
        "service_id": b["service_id"],
        "master": b["master_name"],
        "master_id": b["master_id"],
        "date": start.date().isoformat(),
        "time": start.strftime("%H:%M"),
        "price": money(b["price"]),
        "duration": b["duration_min"],
        "paid": money(b["paid_amount"]) if b["pay_status"] == "paid" and b["paid_amount"] else None,
    }


async def bootstrap(request: web.Request) -> web.Response:
    lang = request["lang"]
    mode, pct = await pay_config()
    services = []
    for s in await db.services():
        now_amount = amount_due(s["price"], mode, pct)
        services.append({
            "id": s["id"], "name": loc(s, "name", lang), "desc": loc(s, "desc", lang),
            "duration": s["duration_min"], "price": money(s["price"]),
            "pay_now": money(now_amount) if now_amount else None,
            "pay_later": money(round(s["price"] - now_amount, 2)) if 0 < now_amount < s["price"] else None,
        })
    masters = []
    for m in await db.masters():
        rating, count = await db.master_rating(m["id"])
        masters.append({
            "id": m["id"], "name": m["name"], "title": loc(m, "title", lang), "photo": m["photo"],
            "rating": rating, "reviews": count, "work_days": m["work_days"],
            "days_off": sorted(await db.days_off(m["id"])),
        })
    upcoming = [_booking_json(b, lang) for b in await db.user_upcoming(request["user_id"])]
    return web.json_response({
        "lang": lang,
        "languages": list(settings.languages),
        "shop": {
            "name": settings.shop_name, "address": settings.shop_address, "phone": settings.shop_phone,
            "open": settings.open_time, "close": settings.close_time,
        },
        "services": services,
        "masters": masters,
        "days": [d.isoformat() for d in bookable_days()],
        "payment": {"mode": mode, "percent": pct, "currency": settings.currency,
                    "free_cancel_hours": settings.refund_free_hours},
        "upcoming": upcoming,
    })


def _int(v, name: str) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        raise web.HTTPBadRequest(text=f"bad {name}")


def _day(v) -> date:
    try:
        return date.fromisoformat(v)
    except (TypeError, ValueError):
        raise web.HTTPBadRequest(text="bad date")


async def slots(request: web.Request) -> web.Response:
    q = request.query
    reschedule = q.get("reschedule_id")
    try:
        times = await available_slots(
            _int(q.get("service_id"), "service_id"), _int(q.get("master_id", 0), "master_id"),
            _day(q.get("date")), exclude_id=_int(reschedule, "reschedule_id") if reschedule else None,
        )
    except BookingError:
        return web.json_response({"slots": []})
    return web.json_response({"slots": times})


async def days(request: web.Request) -> web.Response:
    q = request.query
    reschedule = q.get("reschedule_id")
    try:
        result = await open_days(
            _int(q.get("service_id"), "service_id"), _int(q.get("master_id", 0), "master_id"),
            exclude_id=_int(reschedule, "reschedule_id") if reschedule else None,
        )
    except BookingError:
        result = []
    return web.json_response({"open": result})


async def book(request: web.Request) -> web.Response:
    data = await request.json()
    reschedule_id = data.get("reschedule_id")
    try:
        bid = await create_booking(
            request["user_id"], _int(data.get("service_id"), "service_id"),
            _int(data.get("master_id", 0), "master_id"), _day(data.get("date")), str(data.get("time")),
            reschedule_id=_int(reschedule_id, "reschedule_id") if reschedule_id else None,
        )
    except SlotTaken:
        return web.json_response({"error": "slot_taken"}, status=409)
    except (BookingError, ValueError):
        return web.json_response({"error": "invalid"}, status=400)
    bot = request.app.get("bot")
    b = await db.booking(bid)
    lang = request["lang"]
    if b["status"] == "pending":
        mode, pct = await pay_config()
        amount = amount_due(b["price"], mode, pct)
        try:
            link = await bot.create_invoice_link(
                title=t(lang, "invoice_title", service=loc(b, "name", lang))[:32],
                description=t(lang, "invoice_desc", service=loc(b, "name", lang), master=b["master_name"],
                              when=fmt_when(lang, parse(b["start"])))[:255],
                payload=f"booking:{bid}",
                provider_token=settings.payment_token,
                currency=settings.payment_currency,
                prices=[LabeledPrice(
                    label=t(lang, "invoice_deposit", pct=pct) if mode == "deposit" else t(lang, "invoice_full"),
                    amount=int(round(amount * 100)))],
            )
        except Exception:
            log.exception("invoice link failed")
            await db.set_status(bid, "cancelled")
            return web.json_response({"error": "payment_unavailable"}, status=502)
        return web.json_response({"booking": _booking_json(b, lang), "invoice_url": link, "pay_amount": money(amount)})
    if bot:
        await notify_booked(bot, bid, rescheduled=bool(reschedule_id))
    return web.json_response({"booking": _booking_json(b, lang)})


async def cancel(request: web.Request) -> web.Response:
    data = await request.json()
    try:
        b = await cancel_booking(request["user_id"], _int(data.get("booking_id"), "booking_id"))
    except BookingError:
        return web.json_response({"error": "invalid"}, status=400)
    bot = request.app.get("bot")
    if bot:
        await notify_cancelled(bot, b)
    return web.json_response({"ok": True})


async def set_lang(request: web.Request) -> web.Response:
    data = await request.json()
    lang = data.get("lang")
    if lang not in settings.languages:
        return web.json_response({"error": "invalid"}, status=400)
    await db.set_lang(request["user_id"], lang)
    return web.json_response({"ok": True})


async def index(request: web.Request) -> web.FileResponse:
    return web.FileResponse(WEBAPP_DIR / "index.html", headers={"Cache-Control": "no-cache"})


async def health(request: web.Request) -> web.Response:
    return web.json_response({"ok": True})


def create_app(bot=None) -> web.Application:
    app = web.Application(middlewares=[auth_middleware])
    if bot:
        app["bot"] = bot
    app.router.add_get("/", index)
    app.router.add_get("/health", health)
    app.router.add_get("/api/bootstrap", bootstrap)
    app.router.add_get("/api/slots", slots)
    app.router.add_get("/api/days", days)
    app.router.add_post("/api/book", book)
    app.router.add_post("/api/cancel", cancel)
    app.router.add_post("/api/lang", set_lang)
    app.router.add_static("/static", WEBAPP_DIR, show_index=False)
    return app
