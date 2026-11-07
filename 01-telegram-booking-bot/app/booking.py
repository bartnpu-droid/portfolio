"""Booking rules: availability, create, cancel, reschedule."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from .config import settings
from .db import FMT, db, now_local, parse
from .slots import free_slots


class SlotTaken(Exception):
    pass


class BookingError(Exception):
    pass


async def master_slots(master, service, day: date, exclude_id: int | None = None) -> list[datetime]:
    off = await db.days_off(master["id"], day)
    works = str(day.weekday()) in master["work_days"] and day.isoformat() not in off
    busy = await db.busy_intervals(master["id"], day, exclude_id=exclude_id)
    return free_slots(
        day,
        service["duration_min"],
        busy,
        open_time=settings.open_time,
        close_time=settings.close_time,
        step_min=settings.slot_step_min,
        now=now_local(),
        min_lead_min=settings.min_lead_min,
        works_today=works,
    )


async def available_slots(service_id: int, master_id: int, day: date, exclude_id: int | None = None):
    """master_id == 0 means 'any barber'. Returns sorted list of 'HH:MM'."""
    service = await db.service(service_id)
    if not service or not service["active"]:
        raise BookingError("service")
    masters = await db.masters() if master_id == 0 else [await db.master(master_id)]
    times: set[str] = set()
    for m in masters:
        if m and m["active"]:
            times |= {s.strftime("%H:%M") for s in await master_slots(m, service, day, exclude_id)}
    return sorted(times)


async def open_days(service_id: int, master_id: int, exclude_id: int | None = None) -> list[str]:
    """Bookable days (ISO) that still have at least one free slot."""
    result = []
    for day in bookable_days():
        if await available_slots(service_id, master_id, day, exclude_id):
            result.append(day.isoformat())
    return result


def bookable_days() -> list[date]:
    today = now_local().date()
    return [today + timedelta(days=i) for i in range(settings.booking_days_ahead)]


async def create_booking(
    user_id: int, service_id: int, master_id: int, day: date, hhmm: str, reschedule_id: int | None = None
) -> int:
    if day not in bookable_days():
        raise BookingError("date")
    service = await db.service(service_id)
    if not service or not service["active"]:
        raise BookingError("service")

    old = None
    if reschedule_id:
        old = await db.booking(reschedule_id)
        if not old or old["user_id"] != user_id or old["status"] != "booked":  # unpaid holds can't be moved
            raise BookingError("reschedule")

    start = datetime.combine(day, datetime.strptime(hhmm, "%H:%M").time())
    end = start + timedelta(minutes=service["duration_min"])

    async with db.lock:  # no two people can grab the same slot
        candidates = await db.masters() if master_id == 0 else [await db.master(master_id)]
        chosen = None
        # For "any barber" pick the least busy one that day to spread the load.
        scored = []
        for m in candidates:
            if not m or not m["active"]:
                continue
            slots = await master_slots(m, service, day, exclude_id=reschedule_id)
            if start in slots:
                load = len(await db.busy_intervals(m["id"], day))
                scored.append((load, m["sort"], m))
        if scored:
            chosen = sorted(scored, key=lambda x: (x[0], x[1]))[0][2]
        if not chosen:
            raise SlotTaken()

        now = now_local()
        if old:
            # A move keeps the original payment and needs no new one.
            status, hold = "booked", None
            pay = (old["pay_status"], old["paid_amount"], old["charge_id"])
        else:
            mode, _ = await pay_config()
            status = "pending" if mode != "off" else "booked"
            hold = (now + timedelta(minutes=settings.payment_hold_min)).strftime(FMT) if status == "pending" else None
            pay = ("none", 0, None)
        bid = await db.execute(
            "INSERT INTO bookings (user_id, master_id, service_id, start, end, price, created_at, status, hold_until, "
            "pay_status, paid_amount, charge_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (user_id, chosen["id"], service_id, start.strftime(FMT), end.strftime(FMT),
             service["price"], now.strftime(FMT), status, hold, *pay),
        )
        if old:
            await db.set_status(old["id"], "cancelled")
            await db.execute("UPDATE bookings SET pay_status='moved' WHERE id=? AND pay_status!='none'", (old["id"],))
    return bid


# ---------- payments ----------
async def pay_config() -> tuple[str, int]:
    """Returns (mode, deposit_percent). mode: off | deposit | full. Off when no payment token is set."""
    if not settings.payment_token:
        return "off", 0
    mode = await db.get_setting("pay_mode", "deposit")
    pct = int(await db.get_setting("pay_deposit_pct", "30"))
    return (mode if mode in ("off", "deposit", "full") else "off"), pct


def amount_due(price: float, mode: str, pct: int) -> float:
    if mode == "full":
        return round(price, 2)
    if mode == "deposit":
        return round(price * pct / 100, 2)
    return 0.0


async def confirm_payment(booking_id: int, amount: float, charge_id: str | None) -> None:
    await db.execute(
        "UPDATE bookings SET status='booked', hold_until=NULL, pay_status='paid', paid_amount=?, charge_id=? WHERE id=?",
        (amount, charge_id, booking_id),
    )


async def expire_holds() -> int:
    cur = await db.conn.execute(
        "UPDATE bookings SET status='expired' WHERE status='pending' AND hold_until < ?",
        (now_local().strftime(FMT),),
    )
    await db.conn.commit()
    return cur.rowcount


def refund_policy(b) -> str | None:
    """For a paid booking being cancelled: 'refund' if early enough, 'keep' if too late."""
    if b["pay_status"] != "paid" or not b["paid_amount"]:
        return None
    hours_left = (parse(b["start"]) - now_local()).total_seconds() / 3600
    return "refund" if hours_left >= settings.refund_free_hours else "keep"


async def cancel_booking(user_id: int, booking_id: int):
    b = await db.booking(booking_id)
    if not b or b["user_id"] != user_id or b["status"] not in ("booked", "pending"):
        raise BookingError("cancel")
    if b["status"] == "booked" and parse(b["start"]) < now_local():
        raise BookingError("past")
    await db.set_status(booking_id, "cancelled")
    policy = refund_policy(b)
    if policy:
        await db.execute("UPDATE bookings SET pay_status=? WHERE id=?",
                         ("refund_due" if policy == "refund" else "kept", booking_id))
    return b
