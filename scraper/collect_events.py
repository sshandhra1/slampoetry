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
    """Scrape City Lights events page and return poetry-related events.

    City Lights uses a plain WordPress event template (NOT Tribe Events).
    Each event has an <h2> or <h3> containing a link to /events/<slug>/.
    The date string ("Wednesday, September 16, 2026, 7:00 pm PST") appears
    in the HTML immediately before the heading. We search backward from each
    heading to find the nearest date, then forward for the description.

    Poetry gate: POETRY_KW must appear in title OR description (case-insensitive).
    Past events are skipped via the "(Event Passed)" marker City Lights adds.
    """
    import html as _html
    from dateutil import parser as dateparser

    try:
        resp = requests.get("https://citylights.com/events/", timeout=30,
                            headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
    except Exception as e:
        log.error("City Lights fetch failed: %s", e)
        return []

    raw = resp.text
    today = date.today()
    end   = today + timedelta(days=DAYS_AHEAD)
    events = []
    seen_urls: set[str] = set()

    # Pattern: <h2> or <h3> containing a link to /events/<slug>/
    # Handles both absolute (https://citylights.com/events/slug/) and
    # relative (/events/slug/) hrefs — WordPress can produce either.
    heading_re = re.compile(
        r'<h[23][^>]*>\s*<a[^>]+href="((?:https://citylights\.com)?/events/[^"/]+/?)"[^>]*>'
        r'(.*?)</a>\s*</h[23]>',
        re.IGNORECASE | re.DOTALL,
    )

    # Full date string as City Lights writes it
    date_re = re.compile(
        r'(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+'
        r'(?:January|February|March|April|May|June|July|August|'
        r'September|October|November|December)\s+\d{1,2},\s+\d{4},'
        r'\s+\d{1,2}:\d{2}\s+(?:am|pm)\s+PST',
        re.IGNORECASE,
    )

    for m in heading_re.finditer(raw):
        raw_href = m.group(1)
        url = ("https://citylights.com" + raw_href if raw_href.startswith("/")
               else raw_href).rstrip("/") + "/"
        title = _html.unescape(re.sub(r'<[^>]+>', '', m.group(2))).strip()

        if not title or url in seen_urls:
            continue

        # Skip events City Lights has already marked as passed
        # 500-char window for date lookup (date paragraph precedes heading)
        pre_block  = raw[max(0, m.start() - 500): m.start()]
        # 150-char tight window for "Event Passed" — City Lights places it immediately
        # adjacent to its own heading; a wider window would bleed into the next event.
        tight_pre  = raw[max(0, m.start() - 150): m.start()]
        if "Event Passed" in tight_pre:
            continue

        # Find the nearest date string that appears before this heading
        date_matches = list(date_re.finditer(pre_block))
        if not date_matches:
            continue
        date_str = date_matches[-1].group()

        try:
            event_date = dateparser.parse(date_str).date()
        except Exception:
            continue

        if not (today <= event_date <= end):
            continue

        # Description: truncate at next <h2>/<h3> to prevent cross-event bleed
        post_raw = raw[m.end(): m.end() + 500]
        nh_m     = re.search(r'<h[23]', post_raw, re.IGNORECASE)
        post_raw = post_raw[:nh_m.start()] if nh_m else post_raw[:400]
        desc     = re.sub(r'<[^>]+>', ' ', post_raw).strip()[:250]

        # Poetry gate: keyword must appear in title OR description
        combined = (title + " " + desc).lower()
        if not any(kw in combined for kw in POETRY_KW):
            continue

        # Extract time from date string
        time_m = re.search(r'(\d{1,2}:\d{2}\s*(?:am|pm))', date_str, re.I)
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
    """Scrape Poetry Flash calendar and return upcoming reading events."""
    try:
        resp = requests.get("https://poetryflash.org/calendar/", timeout=30,
                            headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
    except Exception as e:
        log.error("Poetry Flash fetch failed: %s", e)
        return []

    # Poetry Flash events are all poetry — filter for Bay Area only
    bay_area_cities = ["san francisco", "berkeley", "oakland", "alameda",
                       "marin", "mill valley", "san rafael", "richmond",
                       "emeryville", "el cerrito", "albany"]
    text = resp.text
    text_lower = text.lower()

    if not any(city in text_lower for city in bay_area_cities):
        log.info("Poetry Flash: no Bay Area events found")
        return []

    # Basic extraction — Poetry Flash uses a simple table/list layout
    import re as _re
    today = date.today()
    end   = today + timedelta(days=DAYS_AHEAD)
    events = []

    # Match date patterns like "August 22" or "8/22"
    date_pattern = _re.compile(
        r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}',
        re.IGNORECASE
    )
    for match in date_pattern.finditer(text):
        try:
            from dateutil import parser as dateparser
            event_date = dateparser.parse(match.group()).date()
            # Assume current year; push to next year if past
            if event_date < today:
                event_date = event_date.replace(year=event_date.year + 1)
        except Exception:
            continue
        if not (today <= event_date <= end):
            continue
        # Grab surrounding context (200 chars)
        ctx_start = max(0, match.start() - 50)
        ctx_end   = min(len(text), match.end() + 200)
        ctx = text[ctx_start:ctx_end]
        # Only keep if Bay Area city mentioned nearby
        if not any(city in ctx.lower() for city in bay_area_cities):
            continue
        # Strip HTML tags for name
        name = _re.sub(r"<[^>]+>", " ", ctx).strip()[:80].split("\n")[0].strip()
        if not name:
            name = "Poetry Flash Reading"
        slug   = re.sub(r"[^a-z0-9]", "", name.lower())[:30]
        ext_id = f"poetryflash-{slug}-{event_date.strftime('%Y%m%d')}"
        if any(e["external_id"] == ext_id for e in events):
            continue
        events.append({
            "external_id": ext_id,
            "name":        name,
            "venue":       "Art House Gallery & Cultural Center",
            "city":        "Berkeley",
            "state":       "CA",
            "region":      "west",
            "lat":         37.8574,
            "lng":        -122.2596,
            "type":        "reading",
            "date":        event_date.strftime("%Y-%m-%d"),
            "time":        "3:00 PM",
            "price":       "Free",
            "url":         "https://poetryflash.org/calendar/",
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
