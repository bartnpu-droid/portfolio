"""SQLite storage. All times are stored as local shop time 'YYYY-MM-DD HH:MM'."""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
from pathlib import Path

import aiosqlite

from .config import settings

FMT = "%Y-%m-%d %H:%M"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    tg_id INTEGER PRIMARY KEY,
    name TEXT,
    username TEXT,
    lang TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name_en TEXT NOT NULL,
    desc_en TEXT,
    duration_min INTEGER NOT NULL,
    price REAL NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    sort INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS masters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    title_en TEXT,
    photo TEXT,
    tg_id INTEGER,
    work_days TEXT NOT NULL DEFAULT '0123456',
    active INTEGER NOT NULL DEFAULT 1,
    sort INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS days_off (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    master_id INTEGER NOT NULL REFERENCES masters(id),
    day TEXT NOT NULL,
    UNIQUE (master_id, day)
);
CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(tg_id),
    master_id INTEGER NOT NULL REFERENCES masters(id),
    service_id INTEGER NOT NULL REFERENCES services(id),
    start TEXT NOT NULL,
    end TEXT NOT NULL,
    price REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'booked',   -- pending | booked | cancelled | expired | done | no_show
    created_at TEXT NOT NULL,
    reminded_24 INTEGER NOT NULL DEFAULT 0,
    reminded_2 INTEGER NOT NULL DEFAULT 0,
    review_asked INTEGER NOT NULL DEFAULT 0,
    rating INTEGER,
    review_text TEXT
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_bookings_master_start ON bookings(master_id, start);
CREATE INDEX IF NOT EXISTS idx_bookings_user ON bookings(user_id);
"""

SEED_SERVICES = [
    # name, description, duration, price
    ("Classic Haircut", "Scissor & clipper cut, wash and styling", 45, 30),
    ("Skin Fade", "Sharp fade down to the skin, finished with a razor", 60, 35),
    ("Beard Trim & Shape", "Beard shaping, razor line-up, hot towel", 30, 20),
    ("Haircut + Beard", "Our most popular combo: full haircut and beard care", 75, 45),
    ("Hot Towel Shave", "Traditional straight razor shave with hot towels", 45, 30),
    ("Kids Haircut", "For kids under 12", 30, 20),
]

SEED_MASTERS = [
    # name, title, photo, work_days (Mon=0)
    ("James", "Senior Barber · 9 years", "img/james.svg", "012345"),
    ("Marco", "Fade Specialist", "img/marco.svg", "123456"),
    ("Daniel", "Beard Expert", "img/daniel.svg", "023456"),
]


class DB:
    def __init__(self, path: str):
        self.path = path
        self.conn: aiosqlite.Connection | None = None
        self.lock = asyncio.Lock()  # serialises booking writes

    async def connect(self) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = await aiosqlite.connect(self.path)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.execute("PRAGMA foreign_keys = ON")
        await self.conn.execute("PRAGMA journal_mode = WAL")
        await self.conn.executescript(SCHEMA)
        await self._migrate()
        await self.conn.commit()
        await self._seed()

    async def _migrate(self) -> None:
        """Add columns introduced after the first release (safe to run every start)."""
        cur = await self.conn.execute("PRAGMA table_info(bookings)")
        cols = {r[1] for r in await cur.fetchall()}
        for name, ddl in [
            ("hold_until", "TEXT"),
            ("pay_status", "TEXT NOT NULL DEFAULT 'none'"),   # none | paid | refund_due | refunded | kept
            ("paid_amount", "REAL NOT NULL DEFAULT 0"),
            ("charge_id", "TEXT"),
        ]:
            if name not in cols:
                await self.conn.execute(f"ALTER TABLE bookings ADD COLUMN {name} {ddl}")

    async def close(self) -> None:
        if self.conn:
            await self.conn.close()

    async def _seed(self) -> None:
        cur = await self.conn.execute("SELECT COUNT(*) FROM services")
        if (await cur.fetchone())[0] == 0:
            await self.conn.executemany(
                "INSERT INTO services (name_en, desc_en, duration_min, price, sort) VALUES (?,?,?,?,?)",
                [(*s, i) for i, s in enumerate(SEED_SERVICES)],
            )
        cur = await self.conn.execute("SELECT COUNT(*) FROM masters")
        if (await cur.fetchone())[0] == 0:
            await self.conn.executemany(
                "INSERT INTO masters (name, title_en, photo, work_days, sort) VALUES (?,?,?,?,?)",
                [(*m, i) for i, m in enumerate(SEED_MASTERS)],
            )
        await self.conn.commit()

    # ---------- helpers ----------
    async def fetchall(self, sql: str, params: tuple = ()) -> list[aiosqlite.Row]:
        cur = await self.conn.execute(sql, params)
        return list(await cur.fetchall())

    async def fetchone(self, sql: str, params: tuple = ()):
        cur = await self.conn.execute(sql, params)
        return await cur.fetchone()

    async def execute(self, sql: str, params: tuple = ()) -> int:
        cur = await self.conn.execute(sql, params)
        await self.conn.commit()
        return cur.lastrowid

    # ---------- users ----------
    async def upsert_user(self, tg_id: int, name: str | None, username: str | None) -> bool:
        """Returns True if the user is new."""
        row = await self.fetchone("SELECT tg_id FROM users WHERE tg_id=?", (tg_id,))
        if row:
            await self.execute("UPDATE users SET name=?, username=? WHERE tg_id=?", (name, username, tg_id))
            return False
        await self.execute(
            "INSERT INTO users (tg_id, name, username, created_at) VALUES (?,?,?,?)",
            (tg_id, name, username, now_local().strftime(FMT)),
        )
        return True

    async def get_user(self, tg_id: int):
        return await self.fetchone("SELECT * FROM users WHERE tg_id=?", (tg_id,))

    async def set_lang(self, tg_id: int, lang: str) -> None:
        await self.execute("UPDATE users SET lang=? WHERE tg_id=?", (lang, tg_id))

    async def all_user_ids(self) -> list[int]:
        return [r["tg_id"] for r in await self.fetchall("SELECT tg_id FROM users")]

    # ---------- catalog ----------
    async def services(self, only_active: bool = True):
        sql = "SELECT * FROM services" + (" WHERE active=1" if only_active else "") + " ORDER BY sort, id"
        return await self.fetchall(sql)

    async def service(self, sid: int):
        return await self.fetchone("SELECT * FROM services WHERE id=?", (sid,))

    async def masters(self, only_active: bool = True):
        sql = "SELECT * FROM masters" + (" WHERE active=1" if only_active else "") + " ORDER BY sort, id"
        return await self.fetchall(sql)

    async def master(self, mid: int):
        return await self.fetchone("SELECT * FROM masters WHERE id=?", (mid,))

    async def master_rating(self, mid: int) -> tuple[float | None, int]:
        row = await self.fetchone(
            "SELECT AVG(rating) AS r, COUNT(rating) AS n FROM bookings WHERE master_id=? AND rating IS NOT NULL",
            (mid,),
        )
        return (round(row["r"], 1) if row["r"] else None), row["n"]

    async def days_off(self, mid: int, from_day: date | None = None) -> set[str]:
        from_day = from_day or now_local().date()
        rows = await self.fetchall(
            "SELECT day FROM days_off WHERE master_id=? AND day>=? ORDER BY day", (mid, from_day.isoformat())
        )
        return {r["day"] for r in rows}

    async def add_day_off(self, mid: int, day: date) -> None:
        await self.execute("INSERT OR IGNORE INTO days_off (master_id, day) VALUES (?,?)", (mid, day.isoformat()))

    # ---------- settings ----------
    async def get_setting(self, key: str, default: str) -> str:
        row = await self.fetchone("SELECT value FROM settings WHERE key=?", (key,))
        return row["value"] if row else default

    async def set_setting(self, key: str, value: str) -> None:
        await self.execute(
            "INSERT INTO settings (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )

    # ---------- bookings ----------
    async def busy_intervals(self, mid: int, day: date, exclude_id: int | None = None):
        """Booked visits plus unexpired payment holds."""
        rows = await self.fetchall(
            "SELECT id, start, end FROM bookings WHERE master_id=? AND start LIKE ? AND "
            "(status='booked' OR (status='pending' AND hold_until >= ?))",
            (mid, f"{day.isoformat()}%", now_local().strftime(FMT)),
        )
        return [
            (datetime.strptime(r["start"], FMT), datetime.strptime(r["end"], FMT))
            for r in rows
            if r["id"] != exclude_id
        ]

    async def booking(self, bid: int):
        return await self.fetchone(BOOKING_SELECT + " WHERE b.id=?", (bid,))

    async def user_upcoming(self, uid: int):
        return await self.fetchall(
            BOOKING_SELECT + " WHERE b.user_id=? AND b.status='booked' AND b.start>=? ORDER BY b.start",
            (uid, now_local().strftime(FMT)),
        )

    async def bookings_on(self, day: date):
        return await self.fetchall(
            BOOKING_SELECT + " WHERE b.start LIKE ? AND b.status IN ('booked','done','no_show') ORDER BY b.start",
            (f"{day.isoformat()}%",),
        )

    async def set_status(self, bid: int, status: str) -> None:
        await self.execute("UPDATE bookings SET status=? WHERE id=?", (status, bid))


BOOKING_SELECT = """
SELECT b.*, s.name_en, s.duration_min, m.name AS master_name, m.tg_id AS master_tg,
       u.name AS user_name, u.username, u.lang
FROM bookings b
JOIN services s ON s.id = b.service_id
JOIN masters m ON m.id = b.master_id
JOIN users u ON u.tg_id = b.user_id
"""


def now_local() -> datetime:
    """Current shop-local time as a naive datetime (minutes precision)."""
    return datetime.now(settings.timezone).replace(tzinfo=None, second=0, microsecond=0)


def parse(s: str) -> datetime:
    return datetime.strptime(s, FMT)


def loc(row, field: str, lang: str | None) -> str:
    """Localised column (name_<lang>, title_<lang>...) with English fallback."""
    keys = row.keys()
    value = row[f"{field}_{lang}"] if f"{field}_{lang}" in keys else None
    return value or row[f"{field}_en"]


def money(value: float) -> str:
    value = round(float(value), 2)
    v = f"{int(value)}" if value.is_integer() else f"{value:.2f}"
    return f"{settings.currency}{v}"


db = DB(settings.db_path)
