import asyncio
import json
import sys
from pathlib import Path

import pytest
from aiohttp import web

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import leadgen as lg  # noqa: E402


def test_phone_and_url_normalisation():
    assert lg.norm_phone("020 7946 0123") == "+44 20 7946 0123"
    assert lg.norm_phone("+44 7911 123456") == "+44 7911 123456"
    assert lg.norm_phone("0044 20 7946 0123;020 1111 2222") == "+44 20 7946 0123"
    assert lg.norm_url("www.example.co.uk/") == "https://www.example.co.uk"
    assert lg.norm_url("not a url") == ""


def test_email_extraction_filters_junk_and_ranks_same_domain():
    html = """
      <a href="mailto:hello@fadehouse.co.uk">mail</a> booking@gmail.com
      logo@2x.png  test@example.com  user@sentry.io  someone@wixpress.com
      <a href="mailto:">empty</a> <a href="mailto:%20">space</a> <a href="mailto:Bookings%40fadehouse.co.uk">enc</a>
    """
    assert lg.extract_emails(html, "fadehouse.co.uk") == ["bookings@fadehouse.co.uk", "hello@fadehouse.co.uk", "booking@gmail.com"]


def test_socials_and_booking_detection():
    html = ('<a href="https://www.instagram.com/fadehouse/">ig</a>'
            '<a href="https://www.facebook.com/sharer/sharer.php">x</a>'
            '<a href="https://www.fresha.com/book-now/fadehouse">Book</a>')
    ig, fb = lg.extract_socials(html)
    assert ig == "https://instagram.com/fadehouse" and fb == ""
    assert lg.detect_booking(html) == "Fresha"


def el(i, name, **tags):
    return {"type": "node", "id": i, "lat": 51.5, "lon": -0.1, "tags": {"name": name, **tags}}


def test_dedupe_and_chains():
    leads = [lg.element_to_lead(e, "44") for e in [
        el(1, "Fade House", phone="020 7946 0001", **{"addr:postcode": "E2 8HL"}),
        el(2, "Fade House Barbers", website="fadehouse.co.uk", phone="+44 20 7946 0001"),  # same phone
        el(3, "Ruffians Shoreditch", website="ruffians.co.uk"),
        el(4, "Kings Cuts", **{"addr:postcode": "n1 1aa"}),
        el(5, "Kings Cuts", **{"addr:postcode": "N1 1AA"}, website="kingscuts.com"),  # same name+postcode
    ]]
    kept, dupes = lg.dedupe(leads)
    assert dupes == 2
    fade = next(l for l in kept if l.name.startswith("Fade"))
    assert fade.website == "https://fadehouse.co.uk" and fade.postcode == "E2 8HL"  # merged
    indep, chains = lg.split_chains(kept, ["ruffians"])
    assert [c.name for c in chains] == ["Ruffians Shoreditch"]
    assert len(indep) == 2


def test_masking():
    assert lg.mask_phone("+44 20 7946 0123") == "+44 20 •••• ••23"
    assert lg.mask_email("hello@fadehouse.co.uk") == "h•••@f•••.co.uk"


async def test_end_to_end_with_local_sites(tmp_path):
    async def home(request):
        return web.Response(text='<a href="/contact-us">Contact</a><a href="https://booksy.com/en-gb/1">Book</a>',
                            content_type="text/html")

    async def contact(request):
        return web.Response(text='Write to <a href="mailto:Info@Fade.test">us</a> '
                                 '<a href="https://instagram.com/fade_ldn">IG</a>', content_type="text/html")

    app = web.Application()
    app.router.add_get("/", home)
    app.router.add_get("/contact-us", contact)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]

    osm = {"elements": [
        el(1, "Fade LDN", website=f"http://127.0.0.1:{port}", phone="02079460001"),
        el(2, "No Site Barbers", phone="07911 123456"),
        el(3, "Dead Site Barbers", website="http://127.0.0.1:1"),
        el(4, "Murdock Soho", website="murdocklondon.com"),
        {"type": "way", "id": 9, "center": {"lat": 51.5, "lon": -0.1}, "tags": {"shop": "hairdresser"}},  # no name
    ]}
    f = tmp_path / "osm.json"
    f.write_text(json.dumps(osm))
    cfg = {"area_name": "Test", "exclude_chains": ["murdock"], "output_dir": str(tmp_path / "out"),
           "file_name": "t", "timeout_sec": 3}
    stats = await lg.run(cfg, str(f))
    await runner.cleanup()

    rows = dict(stats["rows"])
    assert rows["Places found in OpenStreetMap"] == 4
    assert rows["Chain locations excluded"] == 1
    assert rows["Independent businesses"] == 3
    assert rows["With e-mail"] == 1
    assert dict(stats["booking"]) == {"Booksy": 1}

    from openpyxl import load_workbook
    wb = load_workbook(tmp_path / "out" / "t.xlsx")
    ws = wb["Leads"]
    first = [c.value for c in ws[2]]
    assert first[0] == "Fade LDN" and first[5] == "info@fade.test" and first[7] == "https://instagram.com/fade_ldn"
    assert {r[0].value for r in wb["Excluded (chains)"].iter_rows(min_row=2)} == {"Murdock Soho"}
    masked = load_workbook(tmp_path / "out" / "t_sample_masked.xlsx")["Leads"]
    assert "•" in masked.cell(2, 6).value
    assert (tmp_path / "out" / "t.csv").exists()


def test_socials_skip_theme_links_and_fbml():
    html = ('<html xmlns:fb="http://www.facebook.com/2008/fbml">'
            '<a href="https://instagram.com/axiom_themes">t</a><a href="https://instagram.com/sevencut_barbers">ig</a>'
            '<a href="https://www.facebook.com/profile.php?id=1">p</a>')
    assert lg.extract_socials(html, "7Cut Barbers")[1] == ""
    assert lg.extract_socials(html, "Seven Cut Barbers")[0] == "https://instagram.com/sevencut_barbers"
    assert lg.extract_emails("info@yoursite.com hello@real.co.uk") == ["hello@real.co.uk"]


def test_socials_skip_platform_accounts():
    html = ('<footer><a href="https://www.instagram.com/squarespace/">Made with Squarespace</a>'
            '<a href="https://www.facebook.com/people/Choppers-Barbers/100063526880281/">fb</a></footer>')
    assert lg.extract_socials(html, "East Central Barbering") == ("", "")
    html += '<a href="https://instagram.com/eastcentralbarbering">ig</a>'
    assert lg.extract_socials(html, "East Central Barbering")[0] == "https://instagram.com/eastcentralbarbering"
