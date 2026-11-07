"""Clinic website: pages, booking form API, SEO files, and that the site says what the AI says."""
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("LLM_PROVIDER", "mock")

from app import llm  # noqa: E402
from app import web as w  # noqa: E402
from app.assistant import Assistant  # noqa: E402
from app.config import settings  # noqa: E402
from app.kb import KnowledgeBase  # noqa: E402
from app.store import store  # noqa: E402

KB = KnowledgeBase(ROOT / "knowledge")
VALID = {"name": "Anna Smith", "phone": "07911 123456", "email": "", "treatment": "Implants",
         "preferred_time": "Weekday mornings", "notes": "", "new_patient": "yes", "consent": "yes", "elapsed": "9000"}


@pytest.fixture
async def client(tmp_path, aiohttp_client):
    store.path = str(tmp_path / "t.db")
    await store.connect()
    notified = []

    async def on_lead(lead_id, kind, data):
        notified.append((lead_id, kind, data["name"]))
    w.FORM_RATE.clear(), w.RATE.clear(), w.DAILY.clear()
    c = await aiohttp_client(w.create_app(Assistant(KB, on_lead=on_lead, provider=llm.Mock(KB))))
    c.notified = notified
    yield c
    await store.close()


async def test_every_page_is_served_with_absolute_urls(client):
    for path in w.SITEMAP:
        r = await client.get(path)
        html = await r.text()
        assert r.status == 200, path
        assert "__ORIGIN__" not in html and re.search(r'<link rel="canonical" href="http://[^"]+' + re.escape(path), html)
        assert '<script src="/static/widget.js?v=' in html and "<title>" in html
    home = await (await client.get("/")).text()
    assert 'data-target="#ai-chat"' in home and '"@type": "Dentist"' in home and "data-sequence=\"hero\"" in home


async def test_404_page_and_clean_url_redirects(client):
    r = await client.get("/no-such-page")
    assert r.status == 404 and "Page not found" in await r.text()
    r = await client.get("/treatments/", allow_redirects=False)
    assert r.status == 308 and r.headers["Location"] == "/treatments"
    r = await client.get("/index.html", allow_redirects=False)
    assert r.headers["Location"] == "/"
    r = await client.get("/static/missing.js")
    assert r.status == 404 and "Page not found" not in await r.text()


async def test_demo_site_stays_out_of_search_engines(client):
    assert "Disallow: /" in await (await client.get("/robots.txt")).text()
    assert (await client.get("/")).headers.get("X-Robots-Tag") == "noindex"
    sitemap = await (await client.get("/sitemap.xml")).text()
    assert sitemap.count("<loc>") == len(w.SITEMAP)


async def test_booking_form_saves_request_and_notifies_clinic(client):
    r = await client.post("/api/contact", json=VALID)
    body = await r.json()
    assert r.status == 200 and body["ok"] and "07911 123456" in body["message"]
    lead = (await store.leads())[0]
    assert lead["session"].startswith("form:") and lead["kind"] == "appointment"
    assert (lead["name"], lead["treatment"], lead["notes"]) == ("Anna Smith", "Implants", "New patient.")
    assert client.notified == [(lead["id"], "appointment", "Anna Smith")]


@pytest.mark.parametrize("change,field", [
    ({"name": ""}, "name"), ({"phone": "12"}, "phone"), ({"phone": "call me maybe"}, "phone"),
    ({"email": "anna@"}, "email"), ({"treatment": ""}, "treatment"), ({"consent": ""}, "consent"),
])
async def test_booking_form_validation(client, change, field):
    r = await client.post("/api/contact", json={**VALID, **change})
    assert r.status == 400 and (await r.json())["field"] == field
    assert (await store.stats())["leads"] == 0


async def test_booking_form_ignores_bots_and_limits_each_network(client):
    for bot in ({**VALID, "company": "Spam Ltd"}, {**VALID, "elapsed": "400"}):
        r = await client.post("/api/contact", json=bot)
        assert (await r.json())["ok"]               # the bot sees success...
    assert (await store.stats())["leads"] == 0      # ...but nothing is saved
    for _ in range(settings.form_hourly_limit - 2):
        assert (await client.post("/api/contact", json=VALID)).status == 200
    r = await client.post("/api/contact", json=VALID)
    assert r.status == 429 and "call us" in (await r.json())["error"]


async def test_booking_form_works_without_javascript(client):
    form = {k: v for k, v in VALID.items() if k != "elapsed"}
    r = await client.post("/api/contact", data=form, allow_redirects=False)
    assert r.status == 303 and r.headers["Location"] == "/contact?sent=1#book"
    r = await client.post("/api/contact", data={**form, "phone": "1"}, allow_redirects=False)
    assert r.status == 303 and "error=" in r.headers["Location"]


async def test_chat_rejects_huge_messages(client):
    r = await client.post("/api/chat", json={"session": "abcdef123456", "message": "x" * 2001})
    assert r.status == 400


def test_built_pages_match_their_sources(tmp_path):
    sys.path.insert(0, str(ROOT / "site"))
    import build
    for out in build.build(tmp_path):
        assert out.read_text() == (ROOT / "webapp" / out.name).read_text(), f"run: python site/build.py ({out.name})"


def test_website_prices_are_the_ones_the_ai_knows():
    """Every price on the site must be in the knowledge base, so the AI never contradicts the website."""
    kb_text = "\n".join(c.text for c in KB.chunks)
    for page in ("index", "treatments", "implants", "patients", "team", "contact"):
        html = (ROOT / "webapp" / f"{page}.html").read_text()
        for price in set(re.findall(r"£\d{1,3}(?:,\d{3})*(?:\.\d\d)?", html)):
            assert price in kb_text, f"{price} on {page}.html is missing from knowledge/"
