#!/usr/bin/env python3
import os, json, re, logging, requests
from bs4 import BeautifulSoup
from datetime import datetime
from supabase import create_client, Client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
SCRAPER_KEY  = os.environ["SCRAPER_API_KEY"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

SEARCHES = [
    ("san-francisco", "San Francisco"),
    ("oakland", "Oakland"),
    ("berkeley", "Berkeley"),
    ("san-jose", "San Jose"),
]
TERMS = ["poetry", "spoken-word", "open-mic"]
CITY_COORDS = {
    "San Francisco": (37.7749, -122.4194),
    "Oakland": (37.8044, -122.2712),
    "Berkeley": (37.8716, -122.2727),
    "San Jose": (37.3382, -121.8863),
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

def scrape_eventbrite(city_slug, city_name, term):
    target = "https://www.eventbrite.com/d/ca--" + city_slug + "/" + term + "/"
    api_url = "http://api.scraperapi.com?api_key=" + SCRAPER_KEY + "&url=" + target + "&render=true"
    try:
        resp = requests.get(api_url, timeout=60)
        resp.raise_for_status()
    except Exception as e:
        log.error("ScraperAPI error %s/%s: %s", city_name, term, e)
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    events = []

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            items = data if isinstance(data, list) else [data]
            for item in items:
                if item.get("@type") != "Event":
                    continue
                name = item.get("name", "").strip()
                if not name:
                    continue
                url = item.get("url", "")
                start = item.get("startDate", "")
                date_str = start[:10] if start else None
                time_str = None
                if start and "T" in start:
                    try:
                        t = datetime.fromisoformat(start.replace("Z", "+00:00"))
                        time_str = t.strftime("%-I:%M %p")
                    except Exception:
                        pass
                loc = item.get("location", {})
                venue_name = loc.get("name", city_name)
                addr = loc.get("address", {})
                ev_city = addr.get("addressLocality", city_name) if isinstance(addr, dict) else city_name
                offers = item.get("offers", {})
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}
                price_val = offers.get("price", "")
                price = "Free" if str(price_val) == "0" else (str(price_val) if price_val else "TBD")
                lat, lng = CITY_COORDS.get(city_name, (37.7749, -122.4194))
                ext_id = "eb-" + re.sub(r"[^a-z0-9]", "", url.lower())[-40:]
                events.append({
                    "external_id": ext_id, "name": name, "venue": venue_name,
                    "city": ev_city or city_name, "state": "CA", "region": "west",
                    "lat": lat, "lng": lng, "type": classify_type(name),
                    "date": date_str, "time": time_str, "price": price,
                    "url": url, "source": "eventbrite",
                })
        except Exception as e:
            log.debug("parse error: %s", e)

    log.info("  %s / %s -> %d events", city_name, term, len(events))
    return events

def upsert_events(events):
    if not events:
        log.info("Nothing to upsert.")
        return
    result = supabase.table("events").upsert(events, on_conflict="external_id").execute()
    log.info("Upserted %d events", len(result.data))

def run():
    all_events = []
    for city_slug, city_name in SEARCHES:
        for term in TERMS:
            all_events.extend(scrape_eventbrite(city_slug, city_name, term))
    seen = {e["external_id"]: e for e in all_events}
    unique = list(seen.values())
    log.info("Total unique: %d", len(unique))
    upsert_events(unique)
    log.info("Done.")

if __name__ == "__main__":
    run()
