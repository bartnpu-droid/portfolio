"""The assistant: retrieval + system prompt + tools + guardrails."""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Awaitable, Callable
from zoneinfo import ZoneInfo

from .config import settings
from .kb import KnowledgeBase
from .llm import LLMError, Tool, make_provider
from .store import store

log = logging.getLogger(__name__)
LeadCallback = Callable[[int, str, dict], Awaitable[None]]
AlertCallback = Callable[[str], Awaitable[None]]

TOOLS = [
    Tool(
        name="request_appointment",
        description=("Send an appointment request to the clinic reception. Call it only after the patient has "
                     "given their name, phone number and what the visit is for, and has agreed to be contacted. "
                     "Reception will call or text to confirm the exact time."),
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Patient's full name"},
                "phone": {"type": "string", "description": "Phone number to call back"},
                "email": {"type": "string", "description": "E-mail, if given"},
                "treatment": {"type": "string", "description": "Reason for the visit, e.g. check-up, whitening"},
                "preferred_time": {"type": "string", "description": "Days/times that suit the patient"},
                "new_patient": {"type": "boolean"},
                "notes": {"type": "string", "description": "Anything else useful, e.g. nervous patient"},
            },
            "required": ["name", "phone", "treatment"],
        },
    ),
    Tool(
        name="request_callback",
        description=("Ask a staff member to call the patient back, for questions the knowledge base does not "
                     "answer or when the patient wants to speak to a person. Needs name and phone."),
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "phone": {"type": "string"},
                "reason": {"type": "string", "description": "What the patient needs help with"},
            },
            "required": ["name", "phone", "reason"],
        },
    ),
]

SYSTEM = """You are the virtual receptionist of {clinic}, a private dental clinic in London.

How to answer:
- Use ONLY the clinic information below. If the answer is not there, say you don't know and offer a callback
  from the team. Never invent prices, times, treatments or staff.
- Be warm, clear and brief: 1–4 short sentences or a short list. Plain text only: no Markdown (no **bold**,
  no # headings, no tables). Lists may use "- " at the start of a line.
- Address the patient by their name exactly as they wrote it; never correct its spelling.
- Reply in the language the patient writes in.
- Quote prices exactly as written, in £, and mention that a written plan is given before treatment when relevant.

Booking:
- To request an appointment, collect: name, phone number, reason for the visit and preferred days/times.
  Ask for missing details one or two at a time. Confirm the details back, then call request_appointment.
- Never promise a specific slot: reception confirms the time by phone or text.
- Send each request only once. After it is sent, don't send it again when the patient says "ok", "thanks" or "yes".
- If the patient wants a person, or you can't help, collect name + phone + reason and call request_callback.

Safety (very important):
- You are not a dentist. Do not diagnose, do not say what a symptom means, do not recommend medicines or doses.
  For pain or problems, suggest an emergency appointment and share the relevant general information.
- If the patient mentions swelling affecting the eye or neck, difficulty breathing or swallowing, heavy bleeding
  that won't stop, or a serious injury: tell them to call 999 or go to A&E now, before anything else.
- For other urgent dental problems out of hours: NHS 111 (or the clinic emergency line for registered patients).
- Don't ask for or store medical history, card details or other sensitive data in chat.

Clinic information:
{context}
"""

NOW = "Today is {today}. Current time in London: {time}."

EMERGENCY_RE = re.compile(
    r"(can'?t breathe|cannot breathe|difficulty breathing|hard to breathe|trouble breathing|"
    r"can'?t swallow|hard to swallow|difficulty swallowing|(swelling|swollen|swells?).{0,40}(eye|neck)|"
    r"(eye|neck).{0,40}(swell|swollen)|bleeding (won'?t|will not|doesn'?t|does not) stop|heavy bleeding|unconscious)",
    re.I)
EMERGENCY_REPLY = ("⚠️ This could be serious. Please call 999 or go to your nearest A&E now. "
                   "Swelling around the eye or neck, trouble breathing or swallowing, or bleeding that won't stop "
                   "need urgent hospital care. Once you're safe, we're here to help with follow-up dental care.")


def plain_text(text: str) -> str:
    """Chat windows show raw text, so strip Markdown the model may still add."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text, flags=re.S)
    text = re.sub(r"__(.+?)__", r"\1", text, flags=re.S)
    text = re.sub(r"(?m)^#{1,6}\s*", "", text)
    text = re.sub(r"(?m)^(\s*)[*•]\s+", r"\1- ", text)
    return text.strip()


class Assistant:
    def __init__(self, kb: KnowledgeBase, on_lead: LeadCallback | None = None, provider=None,
                 on_alert: AlertCallback | None = None):
        self.kb = kb
        self.on_lead = on_lead
        self.on_alert = on_alert
        self.provider = provider or make_provider(kb)
        self._alerted_on = ""

    async def _budget_alert(self) -> None:
        today = datetime.now(ZoneInfo(settings.timezone)).strftime("%Y-%m-%d")
        if self._alerted_on == today:
            return
        self._alerted_on = today
        log.warning("Daily AI budget of $%.2f reached — assistant paused until tomorrow", settings.daily_budget_usd)
        if self.on_alert:
            try:
                await self.on_alert(f"⚠️ The AI receptionist reached today's budget (${settings.daily_budget_usd:.2f}). "
                                    "It now asks patients to call until midnight. Unusual traffic? Check /admin. "
                                    "Raise DAILY_BUDGET_USD in .env if this was genuine demand.")
            except Exception:
                log.exception("budget alert failed")

    def select_context(self, question: str, history: list[dict]) -> list:
        """Small knowledge base (a typical clinic): give the model all of it — nothing can be missed.
        Large knowledge base: BM25 search, mostly on the current question so earlier topics
        in the conversation don't push the relevant sections out."""
        total = sum(len(c.text) for c in self.kb.chunks)
        if total <= settings.full_context_chars:
            return list(self.kb.chunks)
        recent_user = " ".join(m["content"] for m in history[-4:]
                               if m["role"] == "user" and isinstance(m["content"], str))
        hits = self.kb.search(question, k=6) + self.kb.search(question + " " + recent_user, k=2)
        always = [c for c in self.kb.chunks if "Opening hours" in c.title or "Contact" in c.title]
        chosen, seen = [], set()
        for c in hits + always:
            if c.ref not in seen:
                chosen.append(c)
                seen.add(c.ref)
        return chosen

    def system_prompt(self, question: str, history: list[dict]) -> dict:
        chunks = self.select_context(question, history)
        context = "\n\n".join(f"[{c.title}]\n{c.text}" for c in chunks)
        now = datetime.now(ZoneInfo(settings.timezone))
        return {
            "static": SYSTEM.format(clinic=settings.clinic_name, context=context),
            "dynamic": NOW.format(today=now.strftime("%A %d %B %Y"), time=now.strftime("%H:%M")),
            # the whole knowledge base is identical for every question -> worth caching
            "cache": len(chunks) == len(self.kb.chunks),
        }

    async def reply(self, session: str, text: str) -> str:
        text = text.strip()[:2000]
        if not text:
            return "Please type your question."
        if await store.user_messages_today(session) >= settings.daily_message_limit:
            return (f"You've reached today's message limit for the chat. Please call us on "
                    f"{settings.clinic_phone} and we'll be happy to help.")
        history = await store.history(session, settings.history_messages)
        await store.add_message(session, "user", text)

        if EMERGENCY_RE.search(text):  # deterministic safety net, no model needed
            await store.add_message(session, "assistant", EMERGENCY_REPLY)
            return EMERGENCY_REPLY

        if await store.cost_today() >= settings.daily_budget_usd:  # hard cap, whatever the traffic
            await self._budget_alert()
            busy = (f"Our online assistant is very busy right now. Please call us on {settings.clinic_phone} "
                    f"and our team will be happy to help.")
            await store.add_message(session, "assistant", busy)
            return busy

        async def execute(name: str, args: dict) -> str:
            if name not in ("request_appointment", "request_callback"):
                return "Unknown tool."
            if not args.get("name") or not args.get("phone"):
                return "Missing name or phone — ask the patient for them first."
            kind = "appointment" if name == "request_appointment" else "callback"
            existing = await store.recent_lead(session, kind)
            if existing:  # the model sometimes re-sends after "yes"/"thanks" — update instead of duplicating
                await store.update_lead(existing["id"], args)
                return (f"This request was already sent as #{existing['id']}; its details are updated. "
                        "Do not send it again. Just confirm to the patient that it is with reception.")
            lead_id = await store.add_lead(session, kind, args)
            if self.on_lead:
                try:
                    await self.on_lead(lead_id, kind, args)
                except Exception:
                    log.exception("lead notification failed")
            return f"Saved as request #{lead_id}. Reception will contact the patient, usually within 2 working hours."

        try:
            result = await self.provider.run(self.system_prompt(text, history),
                                             history + [{"role": "user", "content": text}], TOOLS, execute)
        except (LLMError, Exception) as e:
            log.warning("LLM error: %s", e)
            return (f"Sorry, I'm having a technical problem right now. Please call us on {settings.clinic_phone} "
                    f"or try again in a minute.")
        await store.add_usage(session, result.input_tokens, result.output_tokens,
                              result.cache_read_tokens, result.cache_write_tokens)
        answer = plain_text(result.text) or f"Sorry, could you say that another way? You can also call us on {settings.clinic_phone}."
        await store.add_message(session, "assistant", answer)
        return answer
