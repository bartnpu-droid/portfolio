import json
import os
import sys
from pathlib import Path

import pytest
from aiohttp import web

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("LLM_PROVIDER", "mock")

from app import llm  # noqa: E402
from app.assistant import EMERGENCY_REPLY, TOOLS, Assistant  # noqa: E402
from app.kb import KnowledgeBase  # noqa: E402
from app.store import store  # noqa: E402

KB = KnowledgeBase(ROOT / "knowledge")


@pytest.fixture
async def db(tmp_path):
    store.path = str(tmp_path / "t.db")
    await store.connect()
    yield store
    await store.close()


@pytest.mark.parametrize("question,expected", [
    ("how much is a check up", "Check-ups and hygiene"),
    ("are you open on saturday", "Opening hours"),
    ("where can I park", "Address and getting here"),
    ("do you take bupa insurance", "Insurance"),
    ("my son is 5, do you see kids", "Children"),
    ("can I pay monthly", "Interest-free finance"),
    ("I'm scared of the dentist", "Nervous patients"),
    ("tooth knocked out playing football", "Knocked-out adult tooth"),
])
def test_retrieval_finds_the_right_section(question, expected):
    titles = [c.title for c in KB.search(question, k=3)]
    assert any(expected in t for t in titles), titles


def test_system_prompt_contains_context_and_rules():
    a = Assistant(KB, provider=llm.Mock(KB))
    p = a.system_prompt("how much is whitening", [])
    assert "£350" in p["static"] and "Opening hours" in p["static"] and "999" in p["static"]
    assert "Do not diagnose" in p["static"] and "Today is" in p["dynamic"] and p["cache"] is True


async def test_emergency_is_answered_without_the_model(db):
    class Boom:
        async def run(self, *a, **k):
            raise AssertionError("model must not be called")
    a = Assistant(KB, provider=Boom())
    assert await a.reply("web:abc12345", "my face is swelling up to my eye and it's hard to breathe") == EMERGENCY_REPLY
    assert await a.reply("web:abc12346", "My face is swollen up to my eye") == EMERGENCY_REPLY
    assert await a.reply("web:abc12347", "it's hard to swallow since yesterday") == EMERGENCY_REPLY


async def test_mock_books_and_notifies(db):
    leads = []

    async def on_lead(i, kind, data):
        leads.append((kind, data["phone"]))
    a = Assistant(KB, on_lead=on_lead, provider=llm.Mock(KB))
    reply = await a.reply("tg:1", "Hi, I'm Anna Smith, please book an appointment, call me on 07911 123456")
    assert "reception" in reply.lower()
    assert leads == [("appointment", "07911 123456")]
    assert (await store.stats())["leads"] == 1
    csv = (await store.export_leads_csv()).decode("utf-8-sig")
    assert "Anna Smith" in csv and "07911 123456" in csv


async def test_daily_limit(db, monkeypatch):
    from app import assistant as amod
    object.__setattr__(amod.settings, "daily_message_limit", 2)
    try:
        a = Assistant(KB, provider=llm.Mock(KB))
        await a.reply("web:lim12345", "hours?")
        await a.reply("web:lim12345", "prices?")
        assert "limit" in await a.reply("web:lim12345", "parking?")
    finally:
        object.__setattr__(amod.settings, "daily_message_limit", 40)


# ---------------- provider adapters against fake APIs (same JSON shapes as the real ones)
async def fake_server(aiohttp_server, handler):
    app = web.Application()
    app.router.add_post("/v1", handler)
    return await aiohttp_server(app)


async def test_anthropic_tool_loop(aiohttp_server):
    calls = []

    async def handler(request):
        body = await request.json()
        calls.append(body)
        assert request.headers["x-api-key"] == "k" and body["tools"][0]["name"] == "request_appointment"
        if len(calls) == 1:
            return web.json_response({"stop_reason": "tool_use", "usage": {"input_tokens": 100, "output_tokens": 20},
                                      "content": [{"type": "text", "text": "One moment."},
                                                  {"type": "tool_use", "id": "tu_1", "name": "request_appointment",
                                                   "input": {"name": "Ann", "phone": "07911", "treatment": "check-up"}}]})
        last = body["messages"][-1]
        assert last["role"] == "user" and last["content"][0]["type"] == "tool_result"
        assert last["content"][0]["tool_use_id"] == "tu_1" and "#7" in last["content"][0]["content"]
        return web.json_response({"stop_reason": "end_turn", "usage": {"input_tokens": 150, "output_tokens": 30},
                                  "content": [{"type": "text", "text": "Done! Reception will call you."}]})

    srv = await fake_server(aiohttp_server, handler)
    p = llm.Anthropic("k", "claude-test", url=str(srv.make_url("/v1")))
    executed = []

    async def execute(name, args):
        executed.append((name, args["name"]))
        return "Saved as request #7."
    res = await p.run("sys", [{"role": "user", "content": "book me"}], TOOLS, execute)
    assert res.text == "Done! Reception will call you."
    assert executed == [("request_appointment", "Ann")]
    assert (res.input_tokens, res.output_tokens) == (250, 50)
    assert calls[0]["system"] == "sys" and calls[0]["thinking"] == {"type": "disabled"}


async def test_openai_tool_loop(aiohttp_server):
    calls = []

    async def handler(request):
        body = await request.json()
        calls.append(body)
        assert request.headers["Authorization"] == "Bearer k" and body["messages"][0]["role"] == "system"
        if len(calls) == 1:
            return web.json_response({"usage": {"prompt_tokens": 90, "completion_tokens": 10}, "choices": [{"message": {
                "role": "assistant", "content": None,
                "tool_calls": [{"id": "call_1", "type": "function", "function": {
                    "name": "request_callback", "arguments": json.dumps({"name": "Bo", "phone": "1", "reason": "x"})}}]}}]})
        tool_msg = body["messages"][-1]
        assert tool_msg == {"role": "tool", "tool_call_id": "call_1", "content": "ok #3"}
        return web.json_response({"usage": {"prompt_tokens": 120, "completion_tokens": 15},
                                  "choices": [{"message": {"role": "assistant", "content": "We'll call you back."}}]})

    srv = await fake_server(aiohttp_server, handler)
    p = llm.OpenAI("k", "gpt-test", url=str(srv.make_url("/v1")))

    async def execute(name, args):
        assert name == "request_callback"
        return "ok #3"
    res = await p.run("sys", [{"role": "user", "content": "call me"}], TOOLS, execute)
    assert res.text == "We'll call you back." and (res.input_tokens, res.output_tokens) == (210, 25)


async def test_api_errors_become_a_polite_reply(db, aiohttp_server):
    async def handler(request):
        return web.json_response({"error": {"message": "invalid x-api-key"}}, status=401)
    srv = await fake_server(aiohttp_server, handler)
    a = Assistant(KB, provider=llm.Anthropic("bad", "m", url=str(srv.make_url("/v1"))))
    assert "technical problem" in await a.reply("web:err12345", "hello")


async def test_web_chat_endpoint(db, aiohttp_client):
    from app.web import create_app
    client = await aiohttp_client(create_app(Assistant(KB, provider=llm.Mock(KB))))
    r = await client.post("/api/chat", json={"session": "abcdef123456", "message": "Are you open on Saturday?"})
    assert r.status == 200 and "15:00" in (await r.json())["reply"]
    assert r.headers["Access-Control-Allow-Origin"] == "*"
    assert (await client.post("/api/chat", json={"session": "x", "message": "hi"})).status == 400
    assert (await client.get("/")).status == 200
    assert (await client.get("/static/widget.js")).status == 200


def test_small_kb_is_sent_whole_and_large_kb_search_ignores_old_topics():
    from app.config import settings
    a = Assistant(KB, provider=llm.Mock(KB))
    assert len(a.select_context("bupa?", [])) == len(KB.chunks)       # demo KB is small
    object.__setattr__(settings, "full_context_chars", 100)           # pretend it's huge
    try:
        history = [{"role": "user", "content": "how much is a check-up and hygiene"},
                   {"role": "assistant", "content": "Check-up £55, hygiene £85, combined £125 " * 5}]
        titles = [c.title for c in a.select_context("Do you take Bupa insurance? Can I pay monthly?", history)]
        assert any("Insurance" in t for t in titles) and any("finance" in t for t in titles), titles
    finally:
        object.__setattr__(settings, "full_context_chars", 30000)


async def test_repeated_request_updates_instead_of_duplicating(db):
    leads = []

    async def on_lead(i, kind, data):
        leads.append(i)
    a = Assistant(KB, on_lead=on_lead, provider=llm.Mock(KB))
    await a.reply("web:dup12345", "I'm Anna Smith, book an appointment please, 07911 123456")
    await a.reply("web:dup12345", "yes book it, my number is 07911 654321")
    assert len(leads) == 1 and (await store.stats())["leads"] == 1
    assert (await store.leads())[0]["phone"] == "07911 654321"   # details updated


def test_markdown_is_stripped_for_chat_windows():
    from app.assistant import plain_text
    md = "## Help\n- **Booking appointments:** we text you\n* __Prices__ and more"
    assert plain_text(md) == "Help\n- Booking appointments: we text you\n- Prices and more"


async def test_anthropic_prompt_caching_and_cost(aiohttp_server):
    seen = {}

    async def handler(request):
        body = await request.json()
        seen.update(body)
        return web.json_response({"stop_reason": "end_turn", "content": [{"type": "text", "text": "Hi"}],
                                  "usage": {"input_tokens": 40, "output_tokens": 10,
                                            "cache_read_input_tokens": 4000, "cache_creation_input_tokens": 0}})
    srv = await fake_server(aiohttp_server, handler)
    p = llm.Anthropic("k", "m", url=str(srv.make_url("/v1")))

    async def execute(n, a):
        return ""
    res = await p.run({"static": "RULES+KB", "dynamic": "Today is X", "cache": True},
                      [{"role": "user", "content": "hi"}], TOOLS, execute)
    assert seen["system"][0] == {"type": "text", "text": "RULES+KB", "cache_control": {"type": "ephemeral"}}
    assert seen["system"][1] == {"type": "text", "text": "Today is X"}
    assert (res.input_tokens, res.cache_read_tokens) == (40, 4000)


async def test_daily_budget_cap_stops_ai_calls(db):
    from app.config import settings
    calls, alerts = [], []

    class Counting(llm.Mock):
        async def run(self, *a, **k):
            calls.append(1)
            # exactly $0.10 per call, whatever prices are configured
            return llm.Result("ok", input_tokens=round(0.10 / settings.price_in_per_m * 1e6), output_tokens=0)
    async def on_alert(text):
        alerts.append(text)
    object.__setattr__(settings, "daily_budget_usd", 0.25)
    try:
        a = Assistant(KB, provider=Counting(KB), on_alert=on_alert)
        replies = [await a.reply(f"web:spam{i:06d}", "hello") for i in range(6)]
    finally:
        object.__setattr__(settings, "daily_budget_usd", 3.0)
    assert len(calls) == 3                       # $0.30 spent, then the cap kicks in
    assert "very busy" in replies[-1] and len(alerts) == 1
    assert round(await store.cost_today(), 2) == 0.30


def test_ip_daily_limit_survives_new_sessions():
    from app import web as w
    from app.config import settings
    w.DAILY.clear(); w.RATE.clear()
    object.__setattr__(settings, "ip_daily_limit", 3)
    try:
        results = [w._limited("1.2.3.4") for _ in range(4)]
    finally:
        object.__setattr__(settings, "ip_daily_limit", 100)
    assert results[:3] == [None, None, None] and "limit" in results[3]
