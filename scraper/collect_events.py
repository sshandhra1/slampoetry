#!/usr/bin/env python3
"""
EverythingPoetry — Recurring Events Generator
Computes upcoming dates for recurring SF Bay Area poetry/spoken-word events.

Sources verified August 2026:
  avotcja.org/ongoing-poetry-readings/
  birdbeckett.com/events-upcoming/
  marinpoetrycenter.org/events/       → 1st Thursday at Mill Valley Public Library
  pegasusbookstore.com/upcoming-events → Lyrics & Dirges = last Wednesday
  nomadicpress.org                    → Oakland Slam confirmed Sep 6, 2026
  frankbettecenter.org                → AIP 1st Wed (currently Zoom)
  thestarryplough.com                 → Berkeley Slam every Wednesday
  dothebay.com                        → Sacred Grounds every Wednesday

Removed Aug 2026 (inactive / verified defunct):
  Gears Turning @ Adobe Books — last confirmed event January 2017 (user verified)
  Bird & Beckett Books — poetry is not on a fixed schedule; mixed into varied calendar of 20+ monthly events
  Poetry Express Berkeley — Himalayan Flavors closed April 2026; series on hiatus since 2022
  Café International — on hiatus per Instagram (SF City/County order)
  Holla Back! — last confirmed event April 2024, not on ESAA 2025-2026 calendar
  Poetry at the Bette (2nd Thu) — that slot is the AIP Workshop, a private writing workshop
  Alta Solano Lit Out Loud — no web presence found; user verified nothing there (August 2026)

No API keys or scraping needed — pure date math. Runs daily via GitHub Actions.
"""

import os
import re
import logging
from datetime import date, timedelta, datetime
import calendar
from zoneinfo import ZoneInfo

import requests
from icalendar import Calendar as ICalendar
from supabase import create_client, Client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

PACIFIC = ZoneInfo("America/Los_Angeles")

DRY_RUN = "--dry-run" in __import__("sys").argv

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if not DRY_RUN else None  # type: ignore

DAYS_AHEAD = 90

# ── Recurring events ───────────────────────────────────────────────────────────
# recurrence types:
#   {"type": "every_week",   "weekday": N}           – every week
#   {"type": "nth_weekday",  "weekday": N, "n": K}   – Kth weekday of month (1-based)
#   {"type": "last_weekday", "weekday": N}            – last occurrence of weekday in month
# weekday: 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun
RECURRING_EVENTS = [

    # ── Wednesdays ───────────────────────────────────────────────────────────
    {
        # Verified: frankbettecenter.org shows AIP on 1st Wednesday.
        # NOTE: currently running on Zoom — contact cathydana@gmail.com for link.
        "name": "Alameda Island Poets",
        "venue": "Frank Bette Center for the Arts",
        "address": "1601 Paru Street",
        "city": "Alameda", "state": "CA",
        "lat": 37.7696, "lng": -122.2421,
        "time": "7:00 PM", "price": "Free",
        "type": "open_mic",
        "url": "https://www.frankbettecenter.org/poetry-at-the-bette",
        "recurrence": {"type": "nth_weekday", "weekday": 2, "n": 1},   # 1st Wednesday
    },
    {
        # Verified active Aug 2026. SF's longest-running open mic since 1972.
        "name": "Sacred Grounds Open Mic",
        "venue": "Sacred Ground Coffee House",
        "address": "2095 Hayes Street",
        "city": "San Francisco", "state": "CA",
        "lat": 37.7723, "lng": -122.4480,
        "time": "7:00 PM", "price": "Free",
        "type": "open_mic",
        "url": "https://dothebay.com/events/weekly/wed/poetry-open-mic",
        "recurrence": {"type": "every_week", "weekday": 2},            # every Wednesday
    },
    {
        # Verified active Aug 2026 (thestarryplough.com). West Coast's longest-running slam.
        # Competitive slam with prizes + open mic; free workshop beforehand.
        "name": "Berkeley Poetry Slam",
        "venue": "The Starry Plough",
        "address": "3101 Shattuck Avenue",
        "city": "Berkeley", "state": "CA",
        "lat": 37.8529, "lng": -122.2678,
        "time": "8:30 PM", "price": "$7",
        "type": "slam",
        "url": "https://thestarryplough.com/wednesday-berkeley-poetry-slam/",
        "recurrence": {"type": "every_week", "weekday": 2},            # every Wednesday
    },
    {
        # Verified active Aug 2026 (pegasusbookstore.com). 14th anniversary Aug 27, 2025.
        # July 2026 event was July 29 (last Wed). Runs on last Wednesday of each month.
        "name": "Lyrics & Dirges",
        "venue": "Pegasus Books Downtown",
        "address": "2349 Shattuck Avenue",
        "city": "Berkeley", "state": "CA",
        "lat": 37.8612, "lng": -122.2604,
        "time": "7:00 PM", "price": "Free",
        "type": "reading",
        "url": "https://pegasusbookstore.com/Lyrics-Dirges",
        "recurrence": {"type": "last_weekday", "weekday": 2},          # last Wednesday
    },

    # ── Thursdays ────────────────────────────────────────────────────────────
    {
        # Verified active (lib.berkeley.edu/visit/lunch-poems). Academic year only.
        "name": "Lunch Poems at UC Berkeley",
        "venue": "Morrison Library, Doe Library, UC Berkeley",
        "address": "UC Berkeley Campus",
        "city": "Berkeley", "state": "CA",
        "lat": 37.8724, "lng": -122.2596,
        "time": "12:10 PM", "price": "Free",
        "type": "reading",
        "url": "https://www.lib.berkeley.edu/visit/lunch-poems",
        "recurrence": {"type": "nth_weekday", "weekday": 3, "n": 1},   # 1st Thursday
    },
    {
        # Verified active Aug 2026 (nomadicpress.org). Chicanx/Latinx poetry + open mic.
        "name": "Speaking Axolotl Open Mic",
        "venue": "Nomadic Press",
        "address": "111 Fairmount Avenue",
        "city": "Oakland", "state": "CA",
        "lat": 37.8194, "lng": -122.2617,
        "time": "7:30 PM", "price": "Donation",
        "type": "open_mic",
        "url": "https://nomadicpress.org/events/",
        "recurrence": {"type": "nth_weekday", "weekday": 3, "n": 3},   # 3rd Thursday
    },
    {
        # Verified active Aug 2026. Regular reading series at Mill Valley Public Library.
        # NOTE: Falkirk Cultural Center is only used for one-off special events.
        # Sep 3 and Oct 1, 2026 events confirmed on marinpoetrycenter.org/events/
        "name": "Marin Poetry Center Reading Series",
        "venue": "Mill Valley Public Library",
        "address": "375 Throckmorton Avenue",
        "city": "Mill Valley", "state": "CA",
        "lat": 37.9076, "lng": -122.5468,
        "time": "7:30 PM", "price": "Free",
        "type": "reading",
        "url": "https://marinpoetrycenter.org/events/",
        "recurrence": {"type": "nth_weekday", "weekday": 3, "n": 1},   # 1st Thursday
    },

    # ── Fridays ──────────────────────────────────────────────────────────────
    {
        # Verified ongoing. Feature + open reading. At Nefeli Caffé.
        "name": "The Last Word Reading Series",
        "venue": "Nefeli Caffé",
        "address": "1854 Euclid Avenue",
        "city": "Berkeley", "state": "CA",
        "lat": 37.8765, "lng": -122.2558,
        "time": "7:00 PM", "price": "Free",
        "type": "open_mic",
        "url": "",
        "recurrence": {"type": "nth_weekday", "weekday": 4, "n": 2},   # 2nd Friday
    },

    # ── Mondays ──────────────────────────────────────────────────────────────
    {
        # Verified active Aug 2026. One of SF's longest-running open mics.
        # Mixed — musicians, poets, comedians. Free, 21+.
        "name": "Hotel Utah Open Mic",
        "venue": "Hotel Utah Saloon",
        "address": "500 4th Street",
        "city": "San Francisco", "state": "CA",
        "lat": 37.7785, "lng": -122.3968,
        "time": "7:30 PM", "price": "Free",
        "type": "open_mic",
        "url": "https://hotelutah.com/calendar/",
        "recurrence": {"type": "every_week", "weekday": 0},              # every Monday
    },

    # ── Saturdays ────────────────────────────────────────────────────────────
    {
        # Verified active Aug 2026 (poetryexpressberkeley.blogspot.com/p/bapc-listings.html).
        "name": "Bay Area Poets Coalition",
        "venue": "Strawberry Creek Lodge",
        "address": "1320 Addison Street",
        "city": "Berkeley", "state": "CA",
        "lat": 37.8743, "lng": -122.2919,
        "time": "3:00 PM", "price": "Free",
        "type": "reading",
        "url": "https://www.facebook.com/pages/Bay-Area-Poets-Coalition/231192550254579",
        "recurrence": {"type": "nth_weekday", "weekday": 5, "n": 1},   # 1st Saturday
    },
    {
        # Verified active: Sep 6, 2026 confirmed on nomadicpress.org. Competitive slam + open mic.
        # Moved from Awaken Cafe to Nomadic Bookshop (326 23rd St Unit C Oakland).
        "name": "Oakland Slam & Wide Open Mic",
        "venue": "Nomadic Bookshop",
        "address": "326 23rd Street Unit C",
        "city": "Oakland", "state": "CA",
        "lat": 37.8119, "lng": -122.2670,
        "time": "5:00 PM", "price": "$10",
        "type": "slam",
        "url": "https://nomadicpress.org/events/theoaklandslam/",
        "recurrence": {"type": "nth_weekday", "weekday": 5, "n": 1},   # 1st Saturday
    },
    {
        # Verified active (avotcja.org). Poetry, music, percussion welcome. Host: Avotcja.
        "name": "Music of the Word (La Palabra Musical)",
        "venue": "Cesar E. Chavez Branch Oakland Public Library",
        "address": "3301 East 12th Street",
        "city": "Oakland", "state": "CA",
        "lat": 37.7694, "lng": -122.2244,
        "time": "3:00 PM", "price": "Free",
        "type": "open_mic",
        "url": "http://www.avotcja.org",
        "recurrence": {"type": "nth_weekday", "weekday": 5, "n": 4},   # 4th Saturday
    },
]


# ── Date generation ────────────────────────────────────────────────────────────

def get_nth_weekday(year: int, month: int, weekday: int, n: int):
    """Return the date of the nth occurrence of weekday in (year, month).
    weekday: 0=Mon … 6=Sun. n: 1-based. Returns None if it falls outside the month."""
    first = date(year, month, 1)
    delta = (weekday - first.weekday()) % 7
    result = first + timedelta(days=delta + 7 * (n - 1))
    return result if result.month == month else None


def get_last_weekday(year: int, month: int, weekday: int) -> date:
    """Return the date of the last occurrence of weekday in (year, month).
    weekday: 0=Mon … 6=Sun."""
    last_day = date(year, month, calendar.monthrange(year, month)[1])
    delta = (last_day.weekday() - weekday) % 7
    return last_day - timedelta(days=delta)


def generate_dates(recurrence: dict, start: date, end: date) -> list[date]:
    r = recurrence
    dates = []

    if r["type"] == "every_week":
        wd = r["weekday"]
        delta = (wd - start.weekday()) % 7
        cur = start + timedelta(days=delta)
        while cur <= end:
            dates.append(cur)
            cur += timedelta(weeks=1)

    elif r["type"] == "nth_weekday":
        wd, n = r["weekday"], r["n"]
        cur_month = start.replace(day=1)
        while cur_month <= end:
            d = get_nth_weekday(cur_month.year, cur_month.month, wd, n)
            if d and start <= d <= end:
                dates.append(d)
            if cur_month.month == 12:
                cur_month = date(cur_month.year + 1, 1, 1)
            else:
                cur_month = date(cur_month.year, cur_month.month + 1, 1)

    elif r["type"] == "last_weekday":
        wd = r["weekday"]
        cur_month = start.replace(day=1)
        while cur_month <= end:
            d = get_last_weekday(cur_month.year, cur_month.month, wd)
            if start <= d <= end:
                dates.append(d)
            if cur_month.month == 12:
                cur_month = date(cur_month.year + 1, 1, 1)
            else:
                cur_month = date(cur_month.year, cur_month.month + 1, 1)

    return dates


# ── Build & upsert ─────────────────────────────────────────────────────────────

def build_events() -> list[dict]:
    today = date.today()
    end   = today + timedelta(days=DAYS_AHEAD)
    events = []

    for ev in RECURRING_EVENTS:
        for d in generate_dates(ev["recurrence"], today, end):
            slug   = re.sub(r"[^a-z0-9]", "", ev["name"].lower())[:30]
            ext_id = f"recurring-{slug}-{d.strftime('%Y%m%d')}"
            events.append({
                "external_id": ext_id,
                "name":        ev["name"],
                "venue":       ev["venue"],
                "city":        ev["city"],
                "state":       ev["state"],
                "region":      "west",
                "lat":         ev["lat"],
                "lng":         ev["lng"],
                "type":        ev["type"],
                "date":        d.strftime("%Y-%m-%d"),
                "time":        ev["time"],
                "price":       ev["price"],
                "url":         ev["url"],
                "source":      "recurring",
            })

    log.info("Generated %d upcoming events across %d series", len(events), len(RECURRING_EVENTS))
    return events


def upsert_events(events: list[dict]) -> None:
    if not events:
        log.info("Nothing to upsert.")
        return
    chunk = 500
    for i in range(0, len(events), chunk):
        batch  = events[i : i + chunk]
        result = supabase.table("events").upsert(batch, on_conflict="external_id").execute()
        log.info("Upserted %d events (batch %d)", len(result.data), i // chunk + 1)


def cleanup_past_events() -> None:
    """Delete events whose date is before today.

    Runs after upsert so that any same-day events are inserted first, then
    only truly past events are removed.  This also handles cancelled events:
    if a venue removes a future event we won't re-upsert it, and it will be
    purged automatically once its expected date passes.
    """
    today_str = date.today().isoformat()
    result = supabase.table("events").delete().lt("date", today_str).execute()
    deleted = len(result.data) if result.data else 0
    log.info("Cleaned up %d past events (date < %s)", deleted, today_str)


BIRDBECKETT_ICS = (
    "https://calendar.google.com/calendar/ical/"
    "r5o3loovr013c5rftpv75lji18%40group.calendar.google.com/public/basic.ics"
)

# Keywords used to decide whether an event is poetry-related.
# Applied to: title + description (case-insensitive).
# Used across Bird & Beckett, City Lights, and library scrapers.
POETRY_KW = [
    "poet", "poetry", "poem", "poems",
    "spoken word", "open mic", "slam",
    "verse", "haiku", "lyric", "laureate",
    "reading series", "literary reading",
]


def fetch_birdbeckett_events() -> list[dict]:
    """Fetch Bird & Beckett's Google Calendar ICS feed and return poetry events."""
    try:
        resp = requests.get(BIRDBECKETT_ICS, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        log.error("Bird & Beckett ICS fetch failed: %s", e)
        return []

    cal = ICalendar.from_ical(resp.content)
    today = date.today()
    end   = today + timedelta(days=DAYS_AHEAD)
    events = []

    for component in cal.walk():
        if component.name != "VEVENT":
            continue

        summary     = str(component.get("SUMMARY", ""))
        description = str(component.get("DESCRIPTION", ""))

        # Only keep poetry events — check title + description against shared keyword list
        text = (summary + " " + description).lower()
        if not any(kw in text for kw in POETRY_KW):
            continue

        dtstart = component.get("DTSTART")
        if dtstart is None:
            continue

        dt = dtstart.dt
        if isinstance(dt, datetime):
            if dt.tzinfo:
                dt = dt.astimezone(PACIFIC)
            event_date = dt.date()
            event_time = dt.strftime("%I:%M %p").lstrip("0")
        else:
            event_date = dt
            event_time = "TBD"

        if not (today <= event_date <= end):
            continue

        slug   = re.sub(r"[^a-z0-9]", "", summary.lower())[:30]
        ext_id = f"birdbeckett-{slug}-{event_date.strftime('%Y%m%d')}"

        events.append({
            "external_id": ext_id,
            "name":        summary,
            "venue":       "Bird & Beckett Books",
            "city":        "San Francisco",
            "state":       "CA",
            "region":      "west",
            "lat":         37.7310,
            "lng":        -122.4352,
            "type":        "reading",
            "date":        event_date.strftime("%Y-%m-%d"),
            "time":        event_time,
            "price":       "Free",
            "url":         "https://birdbeckett.com/events-upcoming/",
            "source":      "birdbeckett",
        })

    log.info("Found %d Bird & Beckett poetry events", len(events))
    return events


def fetch_citylights_events() -> list[dict]:
    """Scrape City Lights events using Playwright (headless Chromium).

    Plain requests.get() is blocked by Cloudflare on GitHub Actions IPs.
    Playwright runs a real Chromium browser, executes the JS challenge, and
    lets us use the same JS extraction snippet that works in Chrome DevTools.

    HTML structure (confirmed via DevTools Aug 2026):
      <div class="list-item-block">
        <div class="content-block">
          <p class="shortcode-date" data-test2="1787797800">  ← Unix epoch
            Wednesday, August 26, 2026, 6:00 pm PST
          </p>
          <h3 class="shortcode-title list-heading">
            <a href="https://citylights.com/events/slug/">Title</a>
          </h3>
          <p>Description text...</p>
        </div>
      </div>

    Key: data-test2 is the Unix epoch of event start.
    "Event Passed" is JS-injected — we compare timestamps instead.
    """
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        log.error("playwright not installed — skipping City Lights (pip install playwright)")
        return []

    now_ts = datetime.now(tz=PACIFIC).timestamp()
    end_ts = now_ts + DAYS_AHEAD * 86400
    events: list[dict] = []
    time_re = re.compile(r'(\d{1,2}:\d{2}\s*(?:am|pm))', re.IGNORECASE)

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox"],
            )
            page = browser.new_page(user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ))
            page.goto("https://citylights.com/events/", timeout=45_000,
                      wait_until="domcontentloaded")
            try:
                page.wait_for_selector(".list-item-block", timeout=15_000)
            except PWTimeout:
                log.error("City Lights: timed out waiting for .list-item-block")
                browser.close()
                return []

            raw_items = page.evaluate("""
                () => Array.from(document.querySelectorAll('.list-item-block')).map(el => {
                    const titleEl = el.querySelector('.list-heading a');
                    const dateEl  = el.querySelector('.shortcode-date');
                    // Description is in .list-content (confirmed Aug 2026 DevTools)
                    const contentEl = el.querySelector('.list-content');
                    let desc = '';
                    if (contentEl) {
                        const fullText = contentEl.innerText.trim();
                        const titleText = titleEl ? titleEl.innerText.trim() : '';
                        const dateText  = dateEl  ? dateEl.innerText.trim().split('\\n')[0] : '';
                        desc = fullText.replace(dateText, '').replace(titleText, '').trim().slice(0, 500);
                    }
                    return {
                        title:    titleEl ? titleEl.innerText.trim() : '',
                        link:     titleEl ? titleEl.href : '',
                        ts:       dateEl  ? parseInt(dateEl.dataset.test2 || '0', 10) : 0,
                        dateText: dateEl  ? dateEl.innerText.trim() : '',
                        desc:     desc,
                    };
                })
            """)
            browser.close()
    except Exception as e:
        log.error("City Lights Playwright error: %s", e)
        return []

    log.info("City Lights: got %d raw items from browser", len(raw_items))

    import time as _time

    def _detail_page_matches(detail_url: str) -> bool:
        """Fetch a City Lights event detail page and check for poetry keywords.

        Individual event pages are NOT Cloudflare-blocked — plain requests works.
        Returns True if any POETRY_KW found in the page body text.
        """
        try:
            r = requests.get(detail_url, timeout=15, headers={"User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            )})
            r.raise_for_status()
        except Exception as e:
            log.warning("City Lights detail fetch failed for %s: %s", detail_url, e)
            return False
        body = r.text.lower()
        return any(kw in body for kw in POETRY_KW)

    seen_urls: set[str] = set()
    for item in raw_items:
        event_ts = item.get("ts", 0)
        if not event_ts or not (now_ts <= event_ts <= end_ts):
            continue

        title = item.get("title", "").strip()
        url   = item.get("link", "").rstrip("/") + "/"
        if not title or not url or url in seen_urls:
            continue

        desc = item.get("desc", "")
        combined = (title + " " + desc).lower()
        if not any(kw in combined for kw in POETRY_KW):
            # Listing page text didn't match — check the full detail page.
            # Individual event pages are accessible without Cloudflare blocking.
            _time.sleep(0.5)   # be polite
            if not _detail_page_matches(url):
                continue
            log.info("City Lights: detail-page match for '%s'", title)

        event_date = datetime.fromtimestamp(event_ts, tz=PACIFIC).date()
        date_text  = item.get("dateText", "")
        time_m = time_re.search(date_text)
        evt_time = time_m.group(1).strip().upper() if time_m else "7:00 PM"

        seen_urls.add(url)
        slug   = re.sub(r"[^a-z0-9]", "", title.lower())[:30]
        ext_id = f"citylights-{slug}-{event_date.strftime('%Y%m%d')}"

        events.append({
            "external_id": ext_id,
            "name":        title,
            "venue":       "City Lights Bookstore",
            "city":        "San Francisco",
            "state":       "CA",
            "region":      "west",
            "lat":         37.7976,
            "lng":        -122.4064,
            "type":        "reading",
            "date":        event_date.strftime("%Y-%m-%d"),
            "time":        evt_time,
            "price":       "Free",
            "url":         url,
            "source":      "citylights",
        })

    log.info("Found %d City Lights poetry events", len(events))
    return events


def fetch_poetryflash_events() -> list[dict]:
    """Scrape Poetry Flash calendar for Bay Area poetry events.

    Page structure (confirmed Aug 2026):
      - Date headers: <p> tags matching "DD MONTH YYYY — weekday"
      - Events: subsequent <p>/<li> tags, ending with an "EVENT PAGE" link
      - All date headers and events share a common parent container

    Fetches current month + follows "next month >" link to cover 90-day window.
    """
    from bs4 import BeautifulSoup
    from dateutil import parser as dateparser

    BAY_AREA_CITIES = [
        "san francisco", "berkeley", "oakland", "alameda",
        "mill valley", "san rafael", "richmond", "emeryville",
        "el cerrito", "albany", "palo alto", "petaluma",
        "sausalito", "tiburon", "fairfax", "san anselmo", "novato",
    ]

    today = date.today()
    end   = today + timedelta(days=DAYS_AHEAD)

    date_re = re.compile(r'^(\d{1,2})\s+([A-Z]+)\s+(\d{4})', re.IGNORECASE)
    time_re = re.compile(r'(\d{1,2}:\d{2}\s*(?:am|pm))', re.IGNORECASE)

    events:    list[dict] = []
    seen_ids:  set[str]   = set()
    fetched:   set[str]   = set()
    queue = ["https://poetryflash.org/calendar/"]
    months_fetched = 0

    while queue and months_fetched < 4:
        url = queue.pop(0)
        if url in fetched:
            continue
        fetched.add(url)
        months_fetched += 1

        try:
            resp = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
        except Exception as e:
            log.error("Poetry Flash fetch failed for %s: %s", url, e)
            continue

        soup = BeautifulSoup(resp.text, "html.parser")

        # Queue the next month's page if within our window
        next_link = soup.find("a", string=re.compile(r"next month", re.IGNORECASE))
        if next_link and next_link.get("href"):
            next_url = next_link["href"]
            if not next_url.startswith("http"):
                next_url = "https://poetryflash.org" + next_url
            if next_url not in fetched:
                queue.append(next_url)

        # Walk all <p> and <li> elements in document order
        current_date = None
        for el in soup.find_all(["p", "li"]):
            text = el.get_text(" ", strip=True)
            if not text:
                continue

            # Date header?
            dm = date_re.match(text)
            if dm:
                try:
                    current_date = dateparser.parse(
                        f"{dm.group(1)} {dm.group(2).capitalize()} {dm.group(3)}"
                    ).date()
                except Exception:
                    current_date = None
                continue

            if current_date is None or not (today <= current_date <= end):
                continue

            text_lower = text.lower()

            # Bay Area filter
            if not any(city in text_lower for city in BAY_AREA_CITIES):
                continue

            # Poetry keyword filter
            if not any(kw in text_lower for kw in POETRY_KW):
                continue

            # Event URL — prefer the EVENT PAGE anchor
            event_url = "https://poetryflash.org/calendar/"
            ep_link = el.find("a", string=re.compile(r"EVENT PAGE", re.IGNORECASE))
            if ep_link and ep_link.get("href"):
                event_url = ep_link["href"]

            # Time
            time_m = time_re.search(text)
            evt_time = time_m.group(1).strip().upper() if time_m else "7:00 PM"

            # Name — strip "EVENT PAGE" suffix, trim to 100 chars
            name = re.sub(r"\s+", " ", text.split("EVENT PAGE")[0]).strip()[:100]
            if not name:
                name = "Poetry Flash Event"

            # City
            event_city = "San Francisco"
            for city in BAY_AREA_CITIES:
                if city in text_lower:
                    event_city = city.title()
                    break

            slug   = re.sub(r"[^a-z0-9]", "", name.lower())[:30]
            ext_id = f"poetryflash-{slug}-{current_date.strftime('%Y%m%d')}"
            if ext_id in seen_ids:
                continue
            seen_ids.add(ext_id)

            events.append({
                "external_id": ext_id,
                "name":        name,
                "venue":       "Various Venues",
                "city":        event_city,
                "state":       "CA",
                "region":      "west",
                "lat":         37.7749,
                "lng":        -122.4194,
                "type":        "reading",
                "date":        current_date.strftime("%Y-%m-%d"),
                "time":        evt_time,
                "price":       "Free",
                "url":         event_url,
                "source":      "poetryflash",
            })

    log.info("Found %d Poetry Flash Bay Area events", len(events))
    return events


def fetch_youthspeaks_events() -> list[dict]:
    """Scrape Youth Speaks events page for their annual slam season (semifinals + finals).
    Not a fixed recurring schedule — scrape their site to catch exact dates each year.
    Listed as type='festival' since these are season-culminating competitions, not open mics.
    """
    try:
        resp = requests.get("https://youthspeaks.org/events/", timeout=30,
                            headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
    except Exception as e:
        log.error("Youth Speaks fetch failed: %s", e)
        return []

    text      = resp.text
    text_low  = text.lower()
    slam_kws  = ["slam", "semifinal", "final", "spoken word", "poetry"]
    if not any(kw in text_low for kw in slam_kws):
        log.info("Youth Speaks: no slam events found")
        return []

    import re as _re
    from dateutil import parser as dateparser

    today = date.today()
    end   = today + timedelta(days=DAYS_AHEAD)
    events = []

    date_pattern = _re.compile(
        r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}',
        re.IGNORECASE
    )
    seen = set()
    for match in date_pattern.finditer(text):
        try:
            event_date = dateparser.parse(match.group()).date()
            if event_date < today:
                event_date = event_date.replace(year=event_date.year + 1)
        except Exception:
            continue
        if not (today <= event_date <= end) or event_date in seen:
            continue
        # Check surrounding context for slam keywords
        ctx = text[max(0, match.start()-50) : min(len(text), match.end()+300)]
        ctx_low = ctx.lower()
        if not any(kw in ctx_low for kw in slam_kws):
            continue
        seen.add(event_date)
        name = _re.sub(r"<[^>]+>", " ", ctx).strip()[:80].split("\n")[0].strip()
        if not name:
            name = "Youth Speaks Teen Poetry Slam"
        slug   = re.sub(r"[^a-z0-9]", "", name.lower())[:30]
        ext_id = f"youthspeaks-{slug}-{event_date.strftime('%Y%m%d')}"
        events.append({
            "external_id": ext_id,
            "name":        name,
            "venue":       "Various Venues",
            "city":        "San Francisco",
            "state":       "CA",
            "region":      "west",
            "lat":         37.7749,
            "lng":        -122.4194,
            "type":        "festival",
            "date":        event_date.strftime("%Y-%m-%d"),
            "time":        "TBD",
            "price":       "Free",
            "url":         "https://youthspeaks.org/events/",
            "source":      "youthspeaks",
        })

    log.info("Found %d Youth Speaks events", len(events))
    return events


def run():
    events = build_events()
    events += fetch_birdbeckett_events()
    events += fetch_citylights_events()
    events += fetch_poetryflash_events()
    events += fetch_youthspeaks_events()

    if DRY_RUN:
        # Print a readable table — no DB writes
        events_sorted = sorted(events, key=lambda e: e.get("date", ""))
        print(f"\n{'─'*100}")
        print(f"  DRY RUN — {len(events_sorted)} events collected  (no DB writes)")
        print(f"{'─'*100}")
        print(f"  {'DATE':<12} {'SOURCE':<16} {'VENUE':<30} {'NAME'}")
        print(f"{'─'*100}")
        for e in events_sorted:
            print(f"  {e.get('date','?'):<12} {e.get('source','?'):<16} {e.get('venue','?'):<30} {e.get('name','?')}")
        print(f"{'─'*100}\n")
    else:
        upsert_events(events)
        cleanup_past_events()
    log.info("Done.")


if __name__ == "__main__":
    run()
