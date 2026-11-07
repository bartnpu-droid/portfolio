import asyncio
import hashlib
import hmac
import json
import time
from datetime import date, datetime, timedelta
from urllib.parse import urlencode

import pytest

from app import booking, scheduler
from app.api import create_app
from app.db import FMT, db, now_local
from app.slots import free_slots
from app.webapp_auth import validate_init_data

TOKEN = "123456:TEST"


# ---------- pure logic ----------
def test_slots_respect_duration_and_busy():
    day = date(2030, 1, 7)
    busy = [(datetime(2030, 1, 7, 11, 0), datetime(2030, 1, 7, 12, 0))]
    slots = free_slots(day, 45, busy, open_time="10:00", close_time="13:00", step_min=15,
                       now=datetime(2030, 1, 1), min_lead_min=30)
    hhmm = [s.strftime("%H:%M") for s in slots]
    assert hhmm == ["10:00", "10:15", "12:00", "12:15"]  # 10:30 would overlap 11:00, 12:30 runs past close


def test_slots_respect_lead_time_and_day_off():
    day = date(2030, 1, 7)
    now = datetime(2030, 1, 7, 10, 20)
    slots = free_slots(day, 30, [], open_time="10:00", close_time="11:30", step_min=15, now=now, min_lead_min=30)
    assert slots[0].strftime("%H:%M") == "11:00"
    assert free_slots(day, 30, [], open_time="10:00", close_time="11:30", step_min=15, now=now,
                      min_lead_min=30, works_today=False) == []


def sign(user: dict, token: str = TOKEN, auth_date: int | None = None) -> str:
    data = {"auth_date": str(auth_date or int(time.time())), "query_id": "AAA", "user": json.dumps(user)}
    check = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    data["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(data)


def test_init_data_validation():
    user = {"id": 42, "first_name": "Ann"}
    assert validate_init_data(sign(user), TOKEN)["id"] == 42
    assert validate_init_data(sign(user), "999:OTHER") is None
    assert validate_init_data(sign(user, auth_date=int(time.time()) - 3 * 86400), TOKEN) is None
    assert validate_init_data(sign(user).replace("Ann", "Bob"), TOKEN) is None


# ---------- database-backed ----------
@pytest.fixture
async def database(tmp_path, monkeypatch):
    db.path = str(tmp_path / "t.db")
    await db.connect()
    # make every day a working day and pin "now" to a quiet morning
    await db.execute("UPDATE masters SET work_days='0123456'")
    fixed = datetime.combine(date.today(), datetime.min.time()).replace(hour=6)
    monkeypatch.setattr(booking, "now_local", lambda: fixed)
    monkeypatch.setattr(scheduler, "now_local", lambda: fixed)
    monkeypatch.setattr("app.db.now_local", lambda: fixed)
    for i in (1, 2):
        await db.upsert_user(i, f"User{i}", None)
        await db.set_lang(i, "en")
    yield fixed
    await db.close()


async def test_double_booking_is_prevented(database):
    day = database.date() + timedelta(days=1)
    await booking.create_booking(1, 1, 1, day, "10:00")
    with pytest.raises(booking.SlotTaken):
        await booking.create_booking(2, 1, 1, day, "10:15")  # overlaps 10:00-10:45
    # concurrent attempts for the same slot: exactly one wins
    results = await asyncio.gather(
        booking.create_booking(1, 1, 2, day, "12:00"),
        booking.create_booking(2, 1, 2, day, "12:00"),
        return_exceptions=True,
    )
    assert sum(isinstance(r, int) for r in results) == 1


async def test_any_barber_picks_free_one(database):
    day = database.date() + timedelta(days=1)
    ids = [await booking.create_booking(i % 2 + 1, 1, 0, day, "10:00") for i in range(3)]
    masters = {(await db.booking(b))["master_id"] for b in ids}
    assert masters == {1, 2, 3}
    with pytest.raises(booking.SlotTaken):
        await booking.create_booking(1, 1, 0, day, "10:00")
    assert "10:00" not in await booking.available_slots(1, 0, day)


async def test_reschedule_frees_old_slot(database):
    day = database.date() + timedelta(days=1)
    old = await booking.create_booking(1, 1, 1, day, "10:00")
    # moving to an overlapping time is allowed because the old slot is excluded
    new = await booking.create_booking(1, 1, 1, day, "10:15", reschedule_id=old)
    assert (await db.booking(old))["status"] == "cancelled"
    assert (await db.booking(new))["start"].endswith("10:15")
    with pytest.raises(booking.BookingError):
        await booking.create_booking(2, 1, 1, day, "14:00", reschedule_id=new)  # not your booking


async def test_day_off_blocks_slots(database):
    day = database.date() + timedelta(days=2)
    await db.add_day_off(1, day)
    assert await booking.available_slots(1, 1, day) == []


class FakeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, **kw):
        self.sent.append((chat_id, text))


async def test_scheduler_reminders_and_review(database, monkeypatch):
    now = database
    start = now + timedelta(hours=20)
    await db.execute(
        "INSERT INTO bookings (user_id, master_id, service_id, start, end, price, created_at) VALUES (1,1,1,?,?,30,?)",
        (start.strftime(FMT), (start + timedelta(minutes=45)).strftime(FMT),
         (now - timedelta(days=3)).strftime(FMT)))
    bot = FakeBot()
    await scheduler.tick(bot)
    await scheduler.tick(bot)  # second tick must not repeat
    assert len(bot.sent) == 1 and "Reminder" in bot.sent[0][1]

    later = start + timedelta(hours=2)
    monkeypatch.setattr(scheduler, "now_local", lambda: later)
    await scheduler.tick(bot)
    assert "How was your visit" in bot.sent[-1][1]
    assert (await db.fetchone("SELECT status FROM bookings"))["status"] == "done"


async def test_api_flow(database, aiohttp_client, monkeypatch):
    client = await aiohttp_client(create_app())
    h = {"X-Telegram-Init-Data": sign({"id": 77, "first_name": "Kate", "language_code": "de"})}

    assert (await client.get("/api/bootstrap")).status == 401
    boot = await (await client.get("/api/bootstrap", headers=h)).json()
    assert boot["lang"] == "en" and len(boot["services"]) == 6 and len(boot["masters"]) == 3

    day = boot["days"][1]
    slots = (await (await client.get(f"/api/slots?service_id=2&master_id=0&date={day}", headers=h)).json())["slots"]
    assert slots[0] == "10:00"
    r = await client.post("/api/book", headers=h, json={"service_id": 2, "master_id": 2, "date": day, "time": "10:00"})
    assert r.status == 200
    bid = (await r.json())["booking"]["id"]
    r = await client.post("/api/book", headers=h, json={"service_id": 2, "master_id": 2, "date": day, "time": "10:30"})
    assert r.status == 409
    assert (await client.post("/api/cancel", headers=h, json={"booking_id": bid})).status == 200
    upcoming = (await (await client.get("/api/bootstrap", headers=h)).json())["upcoming"]
    assert upcoming == []


async def test_open_days_skip_fully_booked(database):
    day = database.date() + timedelta(days=1)
    await db.add_day_off(2, day)
    await db.add_day_off(3, day)
    days = await booking.open_days(1, 0)
    assert day.isoformat() in days
    await db.add_day_off(1, day)
    assert day.isoformat() not in await booking.open_days(1, 0)


@pytest.fixture
def payments_on():
    from app.config import settings
    object.__setattr__(settings, "payment_token", "1:TEST:x")
    yield settings
    object.__setattr__(settings, "payment_token", "")


async def test_payment_hold_confirm_and_expiry(database, payments_on, monkeypatch):
    day = database.date() + timedelta(days=1)
    bid = await booking.create_booking(1, 1, 1, day, "10:00")
    b = await db.booking(bid)
    assert b["status"] == "pending" and b["hold_until"]
    # the held slot is not offered to others
    assert "10:00" not in await booking.available_slots(1, 1, day)
    await booking.confirm_payment(bid, 9.0, "ch_1")
    b = await db.booking(bid)
    assert (b["status"], b["pay_status"], b["paid_amount"]) == ("booked", "paid", 9.0)

    # an unpaid hold expires and frees the slot
    bid2 = await booking.create_booking(2, 1, 1, day, "12:00")
    later = database + timedelta(minutes=payments_on.payment_hold_min + 1)
    monkeypatch.setattr(booking, "now_local", lambda: later)
    from app import db as dbmod
    monkeypatch.setattr(dbmod, "now_local", lambda: later)
    assert await booking.expire_holds() == 1
    assert (await db.booking(bid2))["status"] == "expired"
    assert "12:00" in await booking.available_slots(1, 1, day)


async def test_amounts_and_refund_policy(database, payments_on):
    assert booking.amount_due(45, "deposit", 30) == 13.5
    assert booking.amount_due(45, "full", 30) == 45
    assert booking.amount_due(45, "off", 30) == 0
    assert await booking.pay_config() == ("deposit", 30)

    early = await booking.create_booking(1, 1, 1, database.date() + timedelta(days=3), "10:00")
    await booking.confirm_payment(early, 9.0, "c")
    await booking.cancel_booking(1, early)
    assert (await db.booking(early))["pay_status"] == "refund_due"

    late = await booking.create_booking(1, 1, 1, database.date(), "18:00")  # same day -> under 24h
    await booking.confirm_payment(late, 9.0, "c")
    await booking.cancel_booking(1, late)
    assert (await db.booking(late))["pay_status"] == "kept"


async def test_reschedule_keeps_payment(database, payments_on):
    day = database.date() + timedelta(days=2)
    bid = await booking.create_booking(1, 1, 1, day, "10:00")
    await booking.confirm_payment(bid, 9.0, "c")
    new = await booking.create_booking(1, 1, 1, day, "15:00", reschedule_id=bid)
    nb = await db.booking(new)
    assert (nb["status"], nb["pay_status"], nb["paid_amount"]) == ("booked", "paid", 9.0)
