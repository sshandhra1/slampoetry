#!/usr/bin/env python3
import os, logging, requests
from datetime import datetime
from supabase import create_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
TOKEN = os.environ["EVENTBRITE_TOKEN"]
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

SEARCHES = [
    ("San Francisco", "San Francisco, CA"),
    ("Oakland", "Oakland, CA"),
    ("Berkeley", "Berkeley, CA"),
    ("San Jose", "San Jose, CA"),
    ("San Rafael", "San Rafael, CA"),
]
TERMS = ["poetry", "slam poetry", "open mic poetry", "spoken word"]
CITY_COORDS = {
    "San Francisco": (37.7749, -122.4194),
    "Oakland": (37.8044, -122.2712),
    "Berkeley": (37.8716, -122.2727),
    "San Jose": (37.3382, -121.8863),
    "San Rafael": (37.9735, -122.5311),
}
TYPE_KW = {
    "slam": ["slam"],
    "open_mic": ["open mic", "open-mic", "spoken word"],
    "workshop": ["workshop", "class", "writing"],
    "festival": ["festival", "gala"],
}

def classify(name):
    nl = name.lower()
    for t, kws in TYPE_KW.items():
        if any(k in nl for k in kws):
            return t
    return "reading"

def price(ev):
    if ev.get("is_free"): return "Free"
    for tc in ev.get("ticket_classes", []):
        c = tc.get("cost")
        if c: return c.get("display", "TBD")
    return "TBD"

def fetch(city, loc, term):
    try:
        r = requests.get("https://www.eventbriteapi.com/v3/events/search/",
            params={"q": term, "location.address": loc, "location.within": "30mi",
                    "expand": "venue,ticket_classes", "page_size": 50},
            headers=HEADERS, timeout=15)
        r.raise_for_status()
        evs = r.json().get("events", [])
    except Exception as e:
        log.error("%s/%s: %s", city, term, e); return []
    today = datetime.now().strftime("%Y-%m-%d")
    out = []
    for ev in evs:
        name = ev.get("name", {}).get("text", "").strip()
        if not name: continue
        sl = ev.get("start", {}).get("local", "")
        ds = sl[:10] if sl else None
        if ds and ds < today: continue
        ts = None
        if sl and "T" in sl:
            ts = datetime.fromisoformat(sl).strftime("%-I:%M %p")
        vo = ev.get("venue") or {}
        ad = vo.get("address", {})
        lat = vo.get("latitude"); lng = vo.get("longitude")
        if lat and lng: lat, lng = float(lat), float(lng)
        else: lat, lng = CITY_COORDS.get(city, (37.7749, -122.4194))
        out.append({"external_id": f"eb-{ev.get("id","")}",
            "name": name, "venue": vo.get("name", city),
            "city": ad.get("city", city), "state": "CA", "region": "west",
            "lat": lat, "lng": lng, "type": classify(name),
            "date": ds, "time": ts, "price": price(ev),
            "url": ev.get("url", ""), "source": "eventbrite"})
    log.info("%s/%s -> %d", city, term, len(out))
    return out

def run():
    all_ev = []
    for city, loc in SEARCHES:
        for term in TERMS:
            all_ev.extend(fetch(city, loc, term))
    unique = list({e["external_id"]: e for e in all_ev}.values())
    log.info("Total unique: %d", len(unique))
    if unique:
        sb.table("events").upsert(unique, on_conflict="external_id").execute()
    log.info("Done.")

if __name__ == "__main__":
    