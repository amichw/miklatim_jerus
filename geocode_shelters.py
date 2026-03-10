"""
Geocode shelter addresses → geo_lat/geo_lon columns in data/shelters.json.

Strategy (in order):
  1. Nominatim  (1 req/sec limit)
  2. Photon     (fallback, no hard rate limit but be polite)

Run:
    venv/bin/python geocode_shelters.py          # skips already-geocoded
    venv/bin/python geocode_shelters.py --retry  # re-tries nulls too
"""

import json
import sys
import time
import urllib.request
import urllib.parse
from pathlib import Path

DATA_FILE = Path(__file__).parent / "data" / "shelters.json"
HEADERS = {"User-Agent": "miklatim-jerusalem-geocoder/1.0 (amiweil2@gmail.com)"}


def _fetch(url: str) -> list | dict:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def nominatim(address: str) -> tuple[float, float] | None:
    params = urllib.parse.urlencode({
        "q": address,
        "format": "json",
        "limit": "1",
        "countrycodes": "il",
        "accept-language": "he",
        "bounded": "1",
        "viewbox": "35.15,31.85,35.32,31.70",
    })
    try:
        results = _fetch(f"https://nominatim.openstreetmap.org/search?{params}")
        if results:
            return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception as e:
        print(f"    Nominatim error: {e}")
    return None


def photon(address: str) -> tuple[float, float] | None:
    q = urllib.parse.quote(address)
    try:
        data = _fetch(
            f"https://photon.komoot.io/api/?q={q}&lang=default&limit=1"
            f"&bbox=35.15,31.70,35.32,31.85"
        )
        feats = data.get("features", [])
        if feats:
            lon, lat = feats[0]["geometry"]["coordinates"]
            return float(lat), float(lon)
    except Exception as e:
        print(f"    Photon error: {e}")
    return None


def geocode(address: str) -> tuple[tuple[float, float] | None, str]:
    """Returns (result, source) where source is 'nominatim', 'photon', or 'none'."""
    result = nominatim(address)
    time.sleep(1.1)  # Nominatim rate limit
    if result:
        return result, "nominatim"

    result = photon(address)
    time.sleep(0.5)
    if result:
        return result, "photon"

    return None, "none"


def main():
    retry_nulls = "--retry" in sys.argv

    shelters = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    total = len(shelters)

    if retry_nulls:
        pending = [i for i, s in enumerate(shelters) if s.get("geo_lat") is None]
        print(f"Retry mode — re-geocoding {len(pending)} nulls")
    else:
        pending = [i for i, s in enumerate(shelters)
                   if "geo_lat" not in s or (s.get("geo_lat") is None and not s.get("geo_source"))]
        already = total - len(pending)
        print(f"Total: {total}  |  Already done: {already}  |  Pending: {len(pending)}")

    for count, idx in enumerate(pending, 1):
        s = shelters[idx]
        address = s.get("map_address") or s.get("address") or ""
        if not address:
            s["geo_lat"] = s["geo_lon"] = None
            s["geo_source"] = "none"
            print(f"[{count}/{len(pending)}] #{idx} — no address")
            continue

        result, source = geocode(address)
        if result:
            s["geo_lat"], s["geo_lon"] = result
            s["geo_source"] = source
            print(f"[{count}/{len(pending)}] [{source}] {address} → {result[0]:.6f}, {result[1]:.6f}")
        else:
            s["geo_lat"] = s["geo_lon"] = None
            s["geo_source"] = "none"
            print(f"[{count}/{len(pending)}] NOT FOUND  {address}")

        if count % 10 == 0:
            DATA_FILE.write_text(json.dumps(shelters, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  ↳ saved ({count} processed this run)")

    DATA_FILE.write_text(json.dumps(shelters, ensure_ascii=False, indent=2), encoding="utf-8")
    found = sum(1 for s in shelters if s.get("geo_lat") is not None)
    print(f"\nDone. {found}/{total} shelters have geocoded coordinates.\a")


if __name__ == "__main__":
    main()
