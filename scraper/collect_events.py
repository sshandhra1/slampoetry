#!/usr/bin/env python3
import os, logging, requests
from datetime import datetime
from supabase import create_client, Client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
TM_KEY       = os.environ["TICKETMASTER_KEY"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

CITIES = [
    ("San Francisco", "CA"), ("Oakland", "CA"),
    ("Berkeley", "CA"), ("San Jose", "CA"), ("San Rafael", "CA"),
]
SEARCH_TERMS = ["poetry", "slam poetry", "spoken word", "open mic poetry"]
CITY_COORDS = {
    "San Francisco": (37.7749, -122.4194), "Oakland": (37.8044, -122.2712),
    "Berkeley": (37.8716, -122.2727), "San Jose": (37.3382, -121.8863),
    "San Rafael": (37.9735, -122.5311),
}
TYPE_KEYWORDS = {
    "slam": ["slam", "slam poetry"],
    "open_mic": ["open mic", "open-mic", "open mike", "spoken word"],
    "workshop": ["workshop", "class", "writing"],
    "festival": ["festival", "gala", "fundraiser"],
}

def classify_type(name):
    nl = name.lower()
    for t, kws in TYPE_KEYWORDS.items():
        if any(k in nl for k in kws):
            return t
    return "reading"

def parse_price(ev):
    ranges = ev.get("priceRanges")
    if not ranges:
        return "Free"
    lo = ranges[0].get("min")
    hi = ranges[0].get("max")
    if lo and hi and lo != hi:
        return "$%.0f-$%.0f" % (lo, hi)
    elif lo:
        return "$%.0f" % lo
    return "TBD"

def fetch_events(city, state, term):
    url = "https://app.ticketmaster.com/discovery/v2/events.json"
    params = {
        "apikey": TM_KEY, "keyword": term, "city": city,
        "stateCode": state, "countryCode": "US",
        "radius": 30, "unit": "miles", "size": 50,
        "startDateTime": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        log.error("API error %s / %s: %s", city, term, e)
        return []
    raw_events = data.get("_embedded", {}).get("events", [])
    log.info("  %s / '%s' -> %d raw", city, term, len(raw_events))
    events = []
    for ev in raw_events:
        name = ev.get("name", "").strip()
        if not name:
            continue
        dates = ev.get("dates", {}).get("start", {})
        date_str = dates.get("localDate")
        time_str = dates.get("localTime")
        if time_str:
            try:
                t = datetime.strptime(time_str, "%H:%M:%S")
                time_str = t.strftime("%-I:%M %p")
            except Exception:
                pass
        venues = ev.get("_embedded", {}).get("venues", [{}])
        venue = venues[0] if venues else {}
        venue_name = venue.get("name", city)
        ev_city = venue.get("city", {}).get("name", city)
        loc = venue.get("location", {})
        try:
            lat = float(loc.get("latitude", 0)) or None
            lng = float(loc.get("longitude", 0)) or None
        except Exception:
            lat = lng = None
        if not lat or not lng:
            lat, lng = CITY_COORDS.get(city, (37.7749, -122.4194))
        ext_id = "tm-" + str(ev.get("id", ""))
        events.append({
            "external_id": ext_id, "name": name, "venue": venue_name,
            "city": ev_city, "state": "CA", "region": "west",
            "lat": lat, "lng": lng, "type": classify_type(name),
            "date": date_str, "time": time_str, "price": parse_price(ev),
            "url": ev.get("url", ""), "source": "ticketmaster",
        })
    return events

def upsert_events(events):
    if not events:
        log.info("Nothing to upsert.")
        return
    result = supabase.table("events").upsert(events, on_conflict="external_id").execute()
    log.info("Upserted %d events into Supabase", len(result.data))

def run():
    all_events = []
    for city, state in CITIES:
        for term in SEARCH_TERMS:
            all_events.extend(fetch_events(city, state, term))
    seen = {e["external_id"]: e for e in all_events}
    unique = list(seen.values())
    log.info("Total unique events: %d", len(unique))
    upsert_events(unique)
    log.info("Done.")

if __name__ == "__main__":
    run()
