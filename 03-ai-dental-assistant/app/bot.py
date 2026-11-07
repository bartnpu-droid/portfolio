"""Telegram channel: patient chat + staff admin panel."""
from __future__ import annotations

import io
import logging
import re
from html import escape
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.enums import ChatAction, ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import (BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
                           KeyboardButton, Message, ReplyKeyboardMarkup)

from .config import settings
from .store import store

log = logging.getLogger(__name__)
router = Router(name="patients")
admin = Router(name="admin")
admin.message.filter(F.from_user.id.in_(settings.admin_ids))
admin.callback_query.filter(F.from_user.id.in_(settings.admin_ids))

QUICK = ["💷 Prices", "🕒 Opening hours", "📅 Book an appointment", "🦷 I have toothache"]
QUICK_TEXT = {
    "💷 Prices": "What are your prices for check-ups and hygiene?",
    "🕒 Opening hours": "What are your opening hours and where are you?",
    "📅 Book an appointment": "I'd like to book an appointment.",
    "🦷 I have toothache": "I have toothache. What should I do?",
}
HTML = {"parse_mode": ParseMode.HTML}


def quick_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=QUICK[0]), KeyboardButton(text=QUICK[1])],
                                         [KeyboardButton(text=QUICK[2]), KeyboardButton(text=QUICK[3])]],
                               resize_keyboard=True, input_field_placeholder="Ask anything about the clinic…")


_assistant = None


def setup(assistant) -> None:
    global _assistant
    _assistant = assistant


# ---------------------------------------------------------------- patients
@router.message(CommandStart())
async def start(message: Message) -> None:
    await store.clear(f"tg:{message.chat.id}")
    await message.answer(
        f"Hi {message.from_user.first_name or 'there'}! 👋 I'm the virtual receptionist at {settings.clinic_name}.\n\n"
        "I can tell you about treatments and prices, opening hours and how to find us, "
        "and request an appointment for you — any time, day or night.\n\n"
        "How can I help?",
        reply_markup=quick_kb(),
    )


@router.message(Command("reset"))
async def reset(message: Message) -> None:
    await store.clear(f"tg:{message.chat.id}")
    await message.answer("Started a new conversation. How can I help?", reply_markup=quick_kb())


@router.message(F.text & ~F.text.startswith("/"))
async def chat(message: Message, bot: Bot) -> None:
    text = QUICK_TEXT.get(message.text, message.text)
    await bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    answer = await _assistant.reply(f"tg:{message.chat.id}", text)
    await message.answer(answer, reply_markup=quick_kb())


# ---------------------------------------------------------------- staff
def lead_text(r) -> str:
    kind = "📅 Appointment request" if r["kind"] == "appointment" else "📞 Callback request"
    lines = [f"<b>{kind} #{r['id']}</b>  ·  {escape(r['status'])}", f"👤 {escape(r['name'] or '—')}",
             f"📞 {escape(r['phone'] or '—')}"]
    if r["email"]:
        lines.append(f"✉️ {escape(r['email'])}")
    if r["treatment"]:
        lines.append(f"🦷 {escape(r['treatment'])}")
    if r["preferred_time"]:
        lines.append(f"🕒 {escape(r['preferred_time'])}")
    if r["notes"]:
        lines.append(f"📝 {escape(r['notes'])}")
    lines.append(f"<i>{r['created_at']} · via {r['session'].split(':')[0]}</i>")
    return "\n".join(lines)


def lead_kb(lead_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Contacted", callback_data=f"lead:{lead_id}:contacted"),
        InlineKeyboardButton(text="🗓 Booked", callback_data=f"lead:{lead_id}:booked"),
    ]])


async def notify_lead(bot: Bot, lead_id: int, kind: str, data: dict) -> None:
    rows = [r for r in await store.leads(50) if r["id"] == lead_id]
    if not rows:
        return
    for admin_id in settings.admin_ids:
        try:
            source = "the website form" if rows[0]["session"].startswith("form:") else "the AI receptionist"
            await bot.send_message(admin_id, f"🔔 New request from {source}\n\n" + lead_text(rows[0]),
                                   reply_markup=lead_kb(lead_id), **HTML)
        except Exception as e:
            log.info("notify %s failed: %s", admin_id, e)


def admin_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Latest requests", callback_data="adm:leads")],
        [InlineKeyboardButton(text="📤 Export requests (CSV)", callback_data="adm:export")],
        [InlineKeyboardButton(text="📚 Knowledge base", callback_data="adm:kb"),
         InlineKeyboardButton(text="🔄 Reload", callback_data="adm:reload")],
    ])


async def admin_text() -> str:
    s = await store.stats()
    return (f"🛠 <b>{escape(settings.clinic_name)} — AI receptionist</b>\n\n"
            f"Model: <code>{escape(settings.llm_provider)} / {escape(settings.model)}</code>\n"
            f"Conversations: <b>{s['conversations']}</b>\n"
            f"Patient messages: <b>{s['messages']}</b> (today {s['messages_today']})\n"
            f"Requests: <b>{s['leads']}</b> (new {s['leads_new']})\n"
            f"AI cost: today <b>${s['cost_today']:.2f}</b> of ${settings.daily_budget_usd:.2f} daily cap · "
            f"total ${s['cost_total']:.2f}\n"
            f"Tokens: {s['input_tokens']:,} in · {s['cache_read_tokens']:,} cached · {s['output_tokens']:,} out\n\n"
            "To update the knowledge base, send a .md or .txt file here, or edit the files in the "
            "<code>knowledge</code> folder and press Reload.")


@admin.message(Command("admin"))
async def admin_cmd(message: Message) -> None:
    await message.answer(await admin_text(), reply_markup=admin_kb(), **HTML)


@admin.callback_query(F.data == "adm:leads")
async def admin_leads(cb: CallbackQuery) -> None:
    await cb.answer()
    rows = await store.leads(10)
    if not rows:
        await cb.message.answer("No requests yet.")
        return
    for r in reversed(rows):
        await cb.message.answer(lead_text(r), reply_markup=lead_kb(r["id"]) if r["status"] == "new" else None, **HTML)


@admin.callback_query(F.data.startswith("lead:"))
async def lead_status(cb: CallbackQuery) -> None:
    _, lead_id, status = cb.data.split(":")
    if status in ("contacted", "booked"):
        await store.set_lead_status(int(lead_id), status)
        rows = [r for r in await store.leads(200) if r["id"] == int(lead_id)]
        if rows:
            await cb.message.edit_text(lead_text(rows[0]), **HTML)
    await cb.answer("Updated")


@admin.callback_query(F.data == "adm:export")
async def admin_export(cb: CallbackQuery) -> None:
    await cb.answer()
    await cb.message.answer_document(BufferedInputFile(await store.export_leads_csv(), filename="requests.csv"))


@admin.callback_query(F.data == "adm:kb")
async def admin_kb_list(cb: CallbackQuery) -> None:
    await cb.answer()
    kb = _assistant.kb
    files = {}
    for c in kb.chunks:
        files[c.source] = files.get(c.source, 0) + 1
    lines = [f"📚 <b>Knowledge base</b> — {len(kb.chunks)} sections"] + \
            [f"• <code>{escape(f)}</code> ({n})" for f, n in files.items()]
    await cb.message.answer("\n".join(lines), **HTML)


@admin.callback_query(F.data == "adm:reload")
async def admin_reload(cb: CallbackQuery) -> None:
    n = _assistant.kb.reload()
    await cb.answer(f"Reloaded: {n} sections", show_alert=True)


@admin.message(F.document)
async def admin_upload(message: Message, bot: Bot) -> None:
    doc = message.document
    name = Path(doc.file_name or "upload.md").name
    if not re.search(r"\.(md|txt)$", name, re.I):
        await message.answer("Please send a .md or .txt file.")
        return
    if doc.file_size and doc.file_size > 500_000:
        await message.answer("File is too big (max 500 KB).")
        return
    buf = io.BytesIO()
    await bot.download(doc, destination=buf)
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    Path(settings.knowledge_dir, safe).write_bytes(buf.getvalue())
    n = _assistant.kb.reload()
    await message.answer(f"✅ Saved <code>{escape(safe)}</code>. Knowledge base now has {n} sections.", **HTML)
