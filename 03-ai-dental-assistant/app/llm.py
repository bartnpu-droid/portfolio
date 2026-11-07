"""LLM providers with tool calling: Anthropic (Claude), OpenAI, and an offline mock.

Each provider runs the full tool loop: model → tool call → our function → result → model → answer.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Awaitable, Callable

import aiohttp

from .config import settings

log = logging.getLogger(__name__)
ToolExec = Callable[[str, dict], Awaitable[str]]
MAX_TOOL_ROUNDS = 3


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict  # JSON Schema


@dataclass
class Result:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    tools_used: list[str] | None = None
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


def system_text(system) -> str:
    """System prompt as one string. `system` is a str or {"static", "dynamic", "cache"}."""
    if isinstance(system, str):
        return system
    return system["static"] + "\n\n" + system["dynamic"]


def anthropic_system(system):
    """Static part (rules + knowledge base) first and marked for prompt caching, so repeated questions
    reuse it at ~10% of the input price; the dynamic part (date/time) goes after it."""
    if isinstance(system, str):
        return system
    static = {"type": "text", "text": system["static"]}
    if system.get("cache"):
        static["cache_control"] = {"type": "ephemeral"}
    return [static, {"type": "text", "text": system["dynamic"]}]


class LLMError(Exception):
    pass


async def _post(url: str, headers: dict, payload: dict, timeout: int = 60) -> dict:
    async with aiohttp.ClientSession() as s:
        async with s.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=timeout)) as r:
            body = await r.text()
            if r.status != 200:
                raise LLMError(f"HTTP {r.status}: {body[:300]}")
            return json.loads(body)


class Anthropic:
    url = "https://api.anthropic.com/v1/messages"

    def __init__(self, api_key: str, model: str, url: str | None = None):
        self.api_key, self.model = api_key, model
        if url:
            self.url = url

    async def run(self, system: str, messages: list[dict], tools: list[Tool], execute: ToolExec) -> Result:
        msgs = [dict(m) for m in messages]
        res = Result("", tools_used=[])
        headers = {"x-api-key": self.api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
        spec = [{"name": t.name, "description": t.description, "input_schema": t.parameters} for t in tools]
        for _ in range(MAX_TOOL_ROUNDS + 1):
            payload = {"model": self.model, "max_tokens": settings.max_output_tokens,
                       "system": anthropic_system(system), "messages": msgs, "tools": spec}
            if not settings.anthropic_thinking:
                payload["thinking"] = {"type": "disabled"}
            data = await _post(self.url, headers, payload)
            usage = data.get("usage", {})
            res.input_tokens += usage.get("input_tokens", 0)
            res.output_tokens += usage.get("output_tokens", 0)
            res.cache_read_tokens += usage.get("cache_read_input_tokens", 0) or 0
            res.cache_write_tokens += usage.get("cache_creation_input_tokens", 0) or 0
            content = data.get("content", [])
            calls = [b for b in content if b.get("type") == "tool_use"]
            if data.get("stop_reason") == "tool_use" and calls:
                msgs.append({"role": "assistant", "content": content})
                results = []
                for c in calls:
                    res.tools_used.append(c["name"])
                    results.append({"type": "tool_result", "tool_use_id": c["id"],
                                    "content": await execute(c["name"], c.get("input") or {})})
                msgs.append({"role": "user", "content": results})
                continue
            res.text = "".join(b.get("text", "") for b in content if b.get("type") == "text").strip()
            if data.get("stop_reason") == "max_tokens":
                log.warning("reply hit MAX_OUTPUT_TOKENS (%s) — consider raising it", settings.max_output_tokens)
                if res.text and res.text[-1] not in ".!?…":
                    res.text += "…"
            return res
        res.text = res.text or ""
        return res


class OpenAI:
    url = "https://api.openai.com/v1/chat/completions"

    def __init__(self, api_key: str, model: str, url: str | None = None):
        self.api_key, self.model = api_key, model
        if url:
            self.url = url

    async def run(self, system: str, messages: list[dict], tools: list[Tool], execute: ToolExec) -> Result:
        msgs = [{"role": "system", "content": system_text(system)}] + [dict(m) for m in messages]
        res = Result("", tools_used=[])
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        spec = [{"type": "function", "function": {"name": t.name, "description": t.description,
                                                  "parameters": t.parameters}} for t in tools]
        for _ in range(MAX_TOOL_ROUNDS + 1):
            data = await _post(self.url, headers, {
                "model": self.model, "messages": msgs, "tools": spec,
                "max_completion_tokens": settings.max_output_tokens,
            })
            usage = data.get("usage", {})
            cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0) or 0
            res.input_tokens += usage.get("prompt_tokens", 0) - cached
            res.cache_read_tokens += cached
            res.output_tokens += usage.get("completion_tokens", 0)
            msg = data["choices"][0]["message"]
            calls = msg.get("tool_calls") or []
            if calls:
                msgs.append({"role": "assistant", "content": msg.get("content"), "tool_calls": calls})
                for c in calls:
                    fn = c["function"]
                    res.tools_used.append(fn["name"])
                    try:
                        args = json.loads(fn.get("arguments") or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    msgs.append({"role": "tool", "tool_call_id": c["id"], "content": await execute(fn["name"], args)})
                continue
            res.text = (msg.get("content") or "").strip()
            return res
        return res


class Mock:
    """Offline demo: answers with the best matching knowledge-base passage.
    Lets you try the whole system (and run tests) without an API key."""

    def __init__(self, kb):
        self.kb = kb

    async def run(self, system: str, messages: list[dict], tools: list[Tool], execute: ToolExec) -> Result:
        q = messages[-1]["content"] if isinstance(messages[-1]["content"], str) else ""
        phone = re.search(r"(\+?\d[\d\s]{8,}\d)", q)
        if phone and re.search(r"\b(book|appointment|call me|callback)\b", q, re.I):
            name = re.search(r"(?i:i am|i'm|my name is|name:)\s+([A-Z][a-z]+(?: [A-Z][a-z]+)?)", q)
            await execute("request_appointment", {
                "name": name.group(1) if name else "Unknown", "phone": phone.group(1).strip(),
                "treatment": "from chat", "preferred_time": "not specified"})
            return Result("Thank you! I've passed your request to our reception team. "
                          "They'll call you to confirm the time.", tools_used=["request_appointment"])
        hits = self.kb.search(q, k=1)
        if not hits:
            return Result(f"I'm not sure about that. Please call us on {settings.clinic_phone}.")
        c = hits[0]
        return Result(f"{c.title.split(' › ')[-1]}:\n{c.text[:700]}\n\n(Demo mode — connect an AI key for "
                      f"natural answers.)")


def make_provider(kb):
    p = settings.llm_provider
    if p == "anthropic" and settings.anthropic_api_key:
        return Anthropic(settings.anthropic_api_key, settings.model)
    if p == "openai" and settings.openai_api_key:
        return OpenAI(settings.openai_api_key, settings.model)
    if p not in ("mock",):
        log.warning("No API key for provider %r — running in offline demo mode", p)
    return Mock(kb)
