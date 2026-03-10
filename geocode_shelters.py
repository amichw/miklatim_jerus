"""
Geocode shelter addresses via Nominatim and add geo_lat/geo_lon columns.

Usage:
    venv/bin/python geocode_shelters.py

Resumes automatically — already-geocoded records are skipped.
Results are written back to data/shelters.json after every 10 records.
Nominatim TOS: max 1 request/sec, valid User-Agent required.
"""

import json
import time
import urllib.request
import urllib.parse
from pathlib import Path

DATA_FILE = Path(__file__).parent / "data" / "shelters.json"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
HEADERS = {"User-Agent": "miklatim-jerusalem-geocoder/1.0 (amiweil2@gmail.com)"}
DELAY = 1.1  # seconds between requests (Nominatim limit: 1/s)


def geocode(address: str) -> tuple[float, float] | None:
    params = urllib.parse.urlencode({
        "q": address,
        "format": "json",
        "limit": "1",
        "countrycodes": "il",
        "accept-language": "he",
        "bounded": "1",
        "viewbox": "35.15,31.85,35.32,31.70",
    })
    req = urllib.request.Request(f"{NOMINATIM_URL}?{params}", headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            results = json.loads(resp.read())
        if results:
            return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception as e:
        print(f"  ERROR: {e}")
    return None


def main():
    shelters = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    total = len(shelters)
    already_done = sum(1 for s in shelters if s.get("geo_lat") is not None)
    pending = [i for i, s in enumerate(shelters) if s.get("geo_lat") is None]

    print(f"Total: {total}  |  Already geocoded: {already_done}  |  Pending: {len(pending)}")

    for count, idx in enumerate(pending, 1):
        s = shelters[idx]
        address = s.get("map_address") or s.get("address") or ""
        if not address:
            s["geo_lat"] = None
            s["geo_lon"] = None
            print(f"[{count}/{len(pending)}] #{idx} — no address, skipping")
            continue

        result = geocode(address)
        if result:
            s["geo_lat"], s["geo_lon"] = result
            print(f"[{count}/{len(pending)}] {address} → {result[0]:.6f}, {result[1]:.6f}")
        else:
            s["geo_lat"] = None
            s["geo_lon"] = None
            print(f"[{count}/{len(pending)}] {address} → NOT FOUND")

        # Save every 10 records
        if count % 10 == 0:
            DATA_FILE.write_text(json.dumps(shelters, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  ↳ saved ({count} processed this run)")

        time.sleep(DELAY)

    # Final save
    DATA_FILE.write_text(json.dumps(shelters, ensure_ascii=False, indent=2), encoding="utf-8")
    found = sum(1 for s in shelters if s.get("geo_lat") is not None)
    print(f"\nDone. {found}/{total} shelters have geocoded coordinates.")


if __name__ == "__main__":
    main()
