#!/usr/bin/env python3
"""
SlamPoetryFabric — Event Scraper
Uses Playwright (headless Chromium) to scrape Eventbrite, which is JavaScript-rendered.
Upserts results into Supabase. Runs via GitHub Actions every 30 minutes.
"""

import os
import re
import time
import logging
from datetime import datetime, date, timedelta

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from supabase import create_client, Client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── Supabase client ──────────────────────────────────────────────────────────
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ── Scrape targets ───────────────────────────────────────────────────────────
SEARCH_URLS = [
    ("San Francisco", "https://www.eventbrite.com/d/ca--san-francisco/poetry/"),
    ("Oakland",       "https://www.eventbrite.com/d/ca--oakland/poetry/"),
    ("Berkeley",      "https://www.eventbrite.com/d/ca--berkeley/poetry/"),
    ("San Jose",      "https://www.eventbrite.com/d/ca--san-jose/poetry/"),
    ("San Rafael",    "https://www.eventbrite.com/d/ca--san-rafael/poetry/"),
]

# ── Coordinates lookup ───────────────────────────────────────────────────────
VENUE_COORDS = {
    "muddy waters":                      (37.7616, -122.4194),
    "sf main public library":            (37.7792, -122.4151),
    "san francisco main public library": (37.7792, -122.4151),
    "barrel proof":                      (37.7796, -122.3891),
    "cavallo point":                     (37.8325, -122.4793),
    "civic center":                      (37.7792, -122.4191),
    "lush vine":                         (37.7816, -122.3960),
    "community music center":            (37.7537, -122.4169),
    "california institute of integral":  (37.7724, -122.4158),
    "bookshop west portal":              (37.7376, -122.4682),
    "saint joseph":                      (37.7748, -122.4037),
    "jung institute":                    (37.7621, -122.4147),
    "city lights":                       (37.7976, -122.4064),
    "starry plough":                     (37.8499, -122.2679),
    "donkey & goat":                     (37.8784, -122.2907),
    "nefeli":                            (37.8756, -122.2605),
    "awaken":                            (37.8044, -122.2712),
    "geoffrey":                          (37.8025, -122.2700),
    "falkirk":                           (37.9735, -122.5311),
}

CITY_COORDS = {
    "San Francisco": (37.7749, -122.4194),
    "Oakland":       (37.8044, -122.2712),
    "Berkeley":      (37.8716, -122.2727),
    "San Jose":      (37.3382, -121.8863),
    "San Rafael":    (37.9735, -122.5311),
    "Walnut Creek":  (37.9058, -122.0651),
    "Palo Alto":     (37.4419, -122.1430),
}

TYPE_KEYWORDS = {
    "slam":     ["slam", "slam poetry"],
    "open_mic": ["open mic", "open-mic", "open mike"],
    "workshop": ["workshop", "class", "write ", "writing", "meditation"],
    "festival": ["festival", "gala", "anniversary", "fundraiser"],
}


def classify_type(name: str) -> str:
    nl = name.lower()
    for t, keywords in TYPE_KEYWORDS.items():
        if any(k in nl for k in keywords):
            return t
    return "reading"


def get_coords(venue: str, city: str) -> tuple:
    vl = (venue or "").lower()
    for key, coords in VENUE_COORDS.items():
        if key in vl:
            return coords
    return CITY_COORDS.get(city, (37.7749, -122.4194))


def parse_price(text: str) -> str:
    tl = text.lower().strip()
    if not tl or "free" in tl or "0.00" in tl:
        return "Free"
    m = re.search(r"\$[\d.]+", text)
    return m.group(0) if m else "TBD"


def parse_date(text: str) -> str | None:
    now = datetime.now()
    t = text.strip()
    if not t:
        return None
    if t.lower() == "today":
        return now.strftime("%Y-%m-%d")
    days = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]
    if t.lower() in days:
        idx = days.index(t.lower())
        offset = (idx - now.weekday()) % 7 or 7
        return (now + timedelta(days=offset)).strftime("%Y-%m-%d")
    for fmt in ("%a, %b %d", "%A, %B %d", "%b %d", "%B %d"):
        try:
            dt = datetime.strptime(t, fmt).replace(year=now.year)
            if dt.date() < date.today():
                dt = dt.replace(year=now.year + 1)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def scrape_city(page, city: str, url: str) -> list[dict]:
    log.info("Scraping %s — %s", city, url)
    try:
        page.goto(url, wait_until="networkidle", timeout=30000)
    except PWTimeout:
        log.warning("Timeout loading %s, using whatever loaded", url)

    # Wait for event cards to appear
    try:
        page.wait_for_selector("article, h2, h3", timeout=10000)
    except PWTimeout:
        pass

    # Extract via page.evaluate — runs inside the browser (has full JS)
    raw = page.evaluate("""() => {
        const results = [];
        // Eventbrite renders event cards as <article> elements
        document.querySelectorAll('article').forEach(card => {
            const nameEl = card.querySelector('h2, h3, [class*="EventName"], [class*="event-name"]');
            if (!nameEl) return;
            const name = nameEl.innerText.trim();
            if (name.length < 5) return;

            // Date line often appears as a <p> or <time> near the title
            const dateEl = card.querySelector('p, time, [class*="date"], [class*="Date"]');
            const dateText = dateEl ? dateEl.innerText.trim() : '';

            // Venue / location
            const locEl = card.querySelectorAll('p');
            let venue = '';
            locEl.forEach(p => {
                const t = p.innerText.trim();
                if (t && t !== name && t !== dateText && t.length < 80) venue = t;
            });

            // Price
            const priceEl = card.querySelector('[class*="price"], [class*="Price"]');
            const price = priceEl ? priceEl.innerText.trim() : '';

            // Link
            const link = card.querySelector('a');
            const href = link ? link.href : '';

            results.push({ name, dateText, venue, price, href });
        });
        return results;
    }""")

    events = []
    for r in raw:
        date_str = parse_date(r.get("dateText", ""))
        venue = r.get("venue", "")
        lat, lng = get_coords(venue, city)
        # Parse time from dateText
        time_match = re.search(r"\d{1,2}:\d{2}\s*[AP]M", r.get("dateText", ""), re.IGNORECASE)
        time_str = time_match.group(0).upper() if time_match else None
        name = r["name"]
        ext_id = f"eb-{re.sub(r'[^a-z0-9]', '-', name.lower())[:50]}-{date_str or 'nd'}"
        events.append({
            "external_id": ext_id,
            "name":        name,
            "venue":       venue or city,
            "city":        city,
            "state":       "CA",
            "region":      "west",
            "lat":         lat,
            "lng":         lng,
            "type":        classify_type(name),
            "date":        date_str,
            "time":        time_str,
            "price":       parse_price(r.get("price", "")),
            "url":         r.get("href", ""),
            "source":      "eventbrite",
        })

    log.info("  Found %d events", len(events))
    return events


def upsert_events(events: list[dict]) -> None:
    if not events:
        log.info("Nothing to upsert.")
        return
    result = supabase.table("events").upsert(events, on_conflict="external_id").execute()
    log.info("Upserted %d events into Supabase", len(result.data))


def run():
    all_events = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = ctx.new_page()

        for city, url in SEARCH_URLS:
            events = scrape_city(page, city, url)
            all_events.extend(events)
            time.sleep(2)   # polite delay between cities

        browser.close()

    # Deduplicate within this batch
    seen = {e["external_id"]: e for e in all_events}
    unique = list(seen.values())
    log.info("Total unique events: %d", len(unique))

    upsert_events(unique)
    log.info("Done.")


if __name__ == "__main__":
    run()
