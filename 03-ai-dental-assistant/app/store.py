"""SQLite storage: conversation history, leads and token usage."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import aiosqlite

from .config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session TEXT NOT NULL,          -- 'tg:<chat id>' or 'web:<random id>'
    role TEXT NOT NULL,             -- user | assistant
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session, id);
CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session TEXT NOT NULL,
    kind TEXT NOT NULL,             -- appointment | callback
    name TEXT, phone TEXT, email TEXT, treatment TEXT, preferred_time TEXT, notes TEXT,
    status TEXT NOT NULL DEFAULT 'new',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session TEXT, input_tokens INTEGER, output_tokens INTEGER, created_at TEXT NOT NULL,
    cache_read_tokens INTEGER NOT NULL DEFAULT 0, cache_write_tokens INTEGER NOT NULL DEFAULT 0
);
"""


def now() -> str:
    return datetime.now(ZoneInfo(settings.timezone)).strftime("%Y-%m-%d %H:%M:%S")


class Store:
    def __init__(self, path: str):
        self.path = path
        self.conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = await aiosqlite.connect(self.path)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.executescript(SCHEMA)
        cur = await self.conn.execute("PRAGMA table_info(usage)")
        cols = {r[1] for r in await cur.fetchall()}
        for col in ("cache_read_tokens", "cache_write_tokens"):  # databases created by older versions
            if col not in cols:
                await self.conn.execute(f"ALTER TABLE usage ADD COLUMN {col} INTEGER NOT NULL DEFAULT 0")
        await self.conn.commit()

    async def close(self) -> None:
        if self.conn:
            await self.conn.close()

    async def add_message(self, session: str, role: str, content: str) -> None:
        await self.conn.execute("INSERT INTO messages (session, role, content, created_at) VALUES (?,?,?,?)",
                                (session, role, content, now()))
        await self.conn.commit()

    async def history(self, session: str, limit: int) -> list[dict]:
        cur = await self.conn.execute(
            "SELECT role, content FROM messages WHERE session=? ORDER BY id DESC LIMIT ?", (session, limit))
        rows = list(reversed(await cur.fetchall()))
        while rows and rows[0]["role"] != "user":  # history must start with the user
            rows.pop(0)
        return [{"role": r["role"], "content": r["content"]} for r in rows]

    async def clear(self, session: str) -> None:
        await self.conn.execute("DELETE FROM messages WHERE session=?", (session,))
        await self.conn.commit()

    async def user_messages_today(self, session: str) -> int:
        cur = await self.conn.execute(
            "SELECT COUNT(*) FROM messages WHERE session=? AND role='user' AND created_at >= ?",
            (session, now()[:10]))
        return (await cur.fetchone())[0]

    async def add_lead(self, session: str, kind: str, data: dict) -> int:
        cur = await self.conn.execute(
            "INSERT INTO leads (session, kind, name, phone, email, treatment, preferred_time, notes, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (session, kind, data.get("name"), data.get("phone"), data.get("email"), data.get("treatment"),
             data.get("preferred_time"), data.get("notes") or data.get("reason"), now()))
        await self.conn.commit()
        return cur.lastrowid

    async def recent_lead(self, session: str, kind: str, minutes: int = 120):
        """The same patient's request of this kind from the last `minutes`, if any."""
        from datetime import timedelta
        since = (datetime.now(ZoneInfo(settings.timezone)) - timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")
        cur = await self.conn.execute(
            "SELECT * FROM leads WHERE session=? AND kind=? AND created_at>=? ORDER BY id DESC LIMIT 1",
            (session, kind, since))
        return await cur.fetchone()

    async def update_lead(self, lead_id: int, data: dict) -> None:
        fields = {"name": data.get("name"), "phone": data.get("phone"), "email": data.get("email"),
                  "treatment": data.get("treatment"), "preferred_time": data.get("preferred_time"),
                  "notes": data.get("notes") or data.get("reason")}
        sets = ", ".join(f"{k}=COALESCE(?, {k})" for k in fields)
        await self.conn.execute(f"UPDATE leads SET {sets} WHERE id=?", (*fields.values(), lead_id))
        await self.conn.commit()

    async def leads(self, limit: int = 20):
        cur = await self.conn.execute("SELECT * FROM leads ORDER BY id DESC LIMIT ?", (limit,))
        return list(await cur.fetchall())

    async def set_lead_status(self, lead_id: int, status: str) -> None:
        await self.conn.execute("UPDATE leads SET status=? WHERE id=?", (status, lead_id))
        await self.conn.commit()

    async def add_usage(self, session: str, tin: int, tout: int, cache_read: int = 0, cache_write: int = 0) -> None:
        await self.conn.execute(
            "INSERT INTO usage (session, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, created_at) "
            "VALUES (?,?,?,?,?,?)", (session, tin, tout, cache_read, cache_write, now()))
        await self.conn.commit()

    async def cost(self, since: str = "") -> float:
        """Estimated USD spent on the AI since a date ('' = all time)."""
        cur = await self.conn.execute(
            "SELECT COALESCE(SUM(input_tokens),0), COALESCE(SUM(output_tokens),0), COALESCE(SUM(cache_read_tokens),0), "
            "COALESCE(SUM(cache_write_tokens),0) FROM usage WHERE created_at >= ?", (since,))
        i, o, cr, cw = await cur.fetchone()
        return (i * settings.price_in_per_m + o * settings.price_out_per_m
                + cr * settings.price_cache_read_per_m + cw * settings.price_cache_write_per_m) / 1e6

    async def cost_today(self) -> float:
        return await self.cost(now()[:10])

    async def stats(self) -> dict:
        async def one(sql, p=()):
            cur = await self.conn.execute(sql, p)
            return (await cur.fetchone())[0] or 0
        week = now()[:10]
        return {
            "conversations": await one("SELECT COUNT(DISTINCT session) FROM messages"),
            "messages": await one("SELECT COUNT(*) FROM messages WHERE role='user'"),
            "messages_today": await one("SELECT COUNT(*) FROM messages WHERE role='user' AND created_at>=?", (week,)),
            "leads": await one("SELECT COUNT(*) FROM leads"),
            "leads_new": await one("SELECT COUNT(*) FROM leads WHERE status='new'"),
            "input_tokens": await one("SELECT SUM(input_tokens) FROM usage"),
            "output_tokens": await one("SELECT SUM(output_tokens) FROM usage"),
            "cache_read_tokens": await one("SELECT SUM(cache_read_tokens) FROM usage"),
            "cost_total": await self.cost(),
            "cost_today": await self.cost_today(),
        }

    async def export_leads_csv(self) -> bytes:
        import csv
        import io
        cur = await self.conn.execute("SELECT * FROM leads ORDER BY id")
        rows = await cur.fetchall()
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["ID", "Created", "Type", "Name", "Phone", "Email", "Treatment", "Preferred time", "Notes",
                    "Status", "Channel"])
        for r in rows:
            w.writerow([r["id"], r["created_at"], r["kind"], r["name"], r["phone"], r["email"], r["treatment"],
                        r["preferred_time"], r["notes"], r["status"], r["session"].split(":")[0]])
        return buf.getvalue().encode("utf-8-sig")


store = Store(settings.db_path)
_json = json  # re-export for handlers that format leads
