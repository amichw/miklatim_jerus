#!/usr/bin/env python3
"""score_coords.py — smart coordinate selection with confidence scoring.

For each shelter:
  1. Load muni CSV coordinates
  2. Geocode via Google Maps (with persistent cache)
  3. Check if Google result is a "perfect match" (ROOFTOP, Jerusalem, street match)
  4. Check if muni coords are suspect (outside bbox or neighborhood outlier)
  5. Select final coordinates and record decision

Outputs:
  data/geocode_cache.json  — full Google responses, keyed by shelter_number
  data/coord_decisions.csv — audit trail
  data/shelters.json       — updated with coord_source field (for slim_shelters.py)

Usage:
  venv/bin/python score_coords.py
  venv/bin/python score_coords.py --force   # re-geocode all (ignore cache)
"""

import csv
import json
import math
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from statistics import median, stdev

GOOGLE_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
CSV_FILE = DATA_DIR / "miklatim.csv"
CACHE_FILE = DATA_DIR / "geocode_cache.json"
DECISIONS_FILE = DATA_DIR / "coord_decisions.csv"
SHELTERS_FILE = DATA_DIR / "shelters.json"

# Hebrew → internal column mapping (utf-8-sig strips BOM from first col)
COL_MAP = {
    "שם השכונה": "neighborhood",
    "מספר מקלט": "shelter_number",
    "כתובת": "address",
    "שטח": "area",
    "סוג": "type",
    "נגישות": "accessibility",
    "מס' נפשות": "capacity",
    "שייכות": "affiliation",
    "קואורדינטות ציר x": "lat",
    "קורדינטות ציר y": "lon",
    "כתובות למפה": "map_address",
    "מינהל": "admin",
    "שכונה": "district",
    "קטגוריה": "category",
}

# Jerusalem bounding box for muni coordinate validation
BBOX = {
    "lat_min": 31.70, "lat_max": 31.90,
    "lon_min": 35.10, "lon_max": 35.35,
}

GEOCODE_DELAY_S = 0.1  # 100ms between Google API calls
SAVE_EVERY = 10        # Save cache every N records


def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def load_csv():
    records = []
    with open(CSV_FILE, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            r = {}
            for heb, eng in COL_MAP.items():
                val = row.get(heb, "").strip() or None
                r[eng] = val
            # Parse coords to float
            for coord in ("lat", "lon"):
                try:
                    r[coord] = float(r[coord]) if r[coord] else None
                except (ValueError, TypeError):
                    r[coord] = None
            records.append(r)
    return records


def load_cache():
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    return {}


def save_cache(cache):
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def google_geocode(address):
    """Call Google Maps Geocoding API and return parsed result dict or None."""
    if not GOOGLE_KEY:
        return None
    params = urllib.parse.urlencode({
        "address": address,
        "key": GOOGLE_KEY,
        "language": "he",
        "region": "il",
        "bounds": "31.70,35.15|31.85,35.32",
    })
    try:
        url = f"https://maps.googleapis.com/maps/api/geocode/json?{params}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        if data.get("status") == "OK" and data["results"]:
            result = data["results"][0]
            loc = result["geometry"]["location"]
            return {
                "geo_lat": float(loc["lat"]),
                "geo_lon": float(loc["lng"]),
                "location_type": result["geometry"].get("location_type"),
                "formatted_address": result.get("formatted_address"),
                "address_components": result.get("address_components", []),
                "viewport": result["geometry"].get("viewport"),
                "place_id": result.get("place_id"),
                "types": result.get("types", []),
            }
        elif data.get("status") in ("ZERO_RESULTS", "OK"):
            return {
                "geo_lat": None, "geo_lon": None, "location_type": None,
                "formatted_address": None, "address_components": [],
                "viewport": None, "place_id": None, "types": [],
            }
    except Exception as e:
        print(f"    Google error: {e}")
    return None


def extract_street(address):
    """Extract base street name from address, stripping trailing house numbers.

    e.g. 'מלל 3' → 'מלל', 'ישא ברכה 23' → 'ישא ברכה'
    """
    if not address:
        return ""
    parts = address.strip().split()
    # Remove trailing numeric tokens (house numbers, apartment numbers)
    while parts and re.match(r'^\d', parts[-1]):
        parts.pop()
    return " ".join(parts).strip()


# Street-type prefixes to ignore when comparing words
_STREET_PREFIXES = {"רחוב", "דרך", "שד'", "שדרות", "סמטת", "מבוא", "כיכר", "גן"}

# Quote characters to strip before word comparison (handles מל"ל ↔ מלל mismatches)
_QUOTES = str.maketrans('', '', '"\'״׳')


def _normalize(word):
    return word.translate(_QUOTES)


def _street_words(text):
    """Return set of significant words from a street name, ignoring prefixes."""
    return {_normalize(w) for w in text.split() if w not in _STREET_PREFIXES and len(w) > 1}


def is_perfect_match(record, cached):
    """Return True if Google result is a confident, Jerusalem-confirmed match.

    Accepts ROOFTOP and RANGE_INTERPOLATED (house-number interpolation is still
    reliable). Uses word-set matching so reversed Hebrew names still match.
    Also tries the shelter name (shelter_number) as a fallback for institutions
    that have no plain street address.
    """
    if not cached or cached.get("geo_lat") is None:
        return False
    loc_type = cached.get("location_type")
    if loc_type not in ("ROOFTOP", "RANGE_INTERPOLATED"):
        return False
    fmt = cached.get("formatted_address") or ""
    if "ירושלים" not in fmt:
        return False

    # Build word sets for comparison (normalize quotes for מל"ל ↔ מלל matching)
    fmt_words = {_normalize(w) for w in fmt.split()}

    # Try address-based match (word-set, order-independent)
    street = extract_street(record.get("address") or "")
    if street:
        sw = _street_words(street)
        if sw and sw.issubset(fmt_words):
            return True

    # Fallback: match key words from the shelter name (for schools, parking, etc.)
    name = record.get("shelter_number") or ""
    # Strip generic prefix "מקלט ציבורי מספר ..." to avoid false matches
    name = re.sub(r"מקלט\s+ציבורי\s+מספר.*", "", name).strip()
    if name:
        nw = _street_words(name)
        # Require at least 2 significant words to match (guards against short names)
        matches = nw & fmt_words
        if len(matches) >= 2:
            return True

    return False


def check_muni_bbox(record):
    """Return True if muni coords are within Jerusalem bounding box."""
    lat, lon = record.get("lat"), record.get("lon")
    if lat is None or lon is None:
        return False
    return (BBOX["lat_min"] <= lat <= BBOX["lat_max"] and
            BBOX["lon_min"] <= lon <= BBOX["lon_max"])


def compute_neighborhood_stats(records):
    """For each neighborhood (from category prefix), compute median lat/lon and stdev.

    Returns dict: neighborhood → {median_lat, median_lon, std_dev, count}
    """
    groups = {}
    for r in records:
        cat = r.get("category") or ""
        nb = cat.split(",")[0].strip() if cat else (r.get("neighborhood") or "")
        if not nb:
            continue
        lat, lon = r.get("lat"), r.get("lon")
        if lat is None or lon is None:
            continue
        groups.setdefault(nb, []).append((lat, lon))

    stats = {}
    for nb, pts in groups.items():
        if len(pts) < 4:
            continue
        lats = [p[0] for p in pts]
        lons = [p[1] for p in pts]
        med_lat = median(lats)
        med_lon = median(lons)
        dists = [haversine(p[0], p[1], med_lat, med_lon) for p in pts]
        std_dev = stdev(dists) if len(dists) > 1 else 0
        stats[nb] = {
            "median_lat": med_lat,
            "median_lon": med_lon,
            "std_dev": std_dev,
            "count": len(pts),
        }
    return stats


def is_muni_outlier(record, nb_stats):
    """Return (is_outlier, median_lat, median_lon, distance_m) tuple."""
    cat = record.get("category") or ""
    nb = cat.split(",")[0].strip() if cat else (record.get("neighborhood") or "")
    lat, lon = record.get("lat"), record.get("lon")
    if not nb or nb not in nb_stats or lat is None or lon is None:
        return False, None, None, None

    st = nb_stats[nb]
    med_lat = st["median_lat"]
    med_lon = st["median_lon"]
    dist = haversine(lat, lon, med_lat, med_lon)
    std_dev = st["std_dev"]
    # 3σ rule only applies at ≥800m — avoids flagging edges of large neighborhoods
    is_outlier = dist > 2000 or (dist >= 800 and std_dev > 0 and dist > 3 * std_dev)
    return is_outlier, med_lat, med_lon, dist


def main():
    force_all = "--force" in sys.argv

    if not GOOGLE_KEY:
        print("WARNING: GOOGLE_MAPS_API_KEY not set. Will skip geocoding for uncached shelters.")

    print("Loading CSV...")
    records = load_csv()
    print(f"  {len(records)} records loaded.")

    print("Loading cache...")
    cache = load_cache()
    print(f"  {len(cache)} entries in cache.")

    # Determine what needs geocoding
    to_geocode = []
    for r in records:
        key = r.get("shelter_number")
        if not key:
            continue
        if force_all or key not in cache:
            to_geocode.append(r)

    if to_geocode:
        print(f"Geocoding {len(to_geocode)} shelters...")
        for i, r in enumerate(to_geocode, 1):
            key = r["shelter_number"]
            address = r.get("map_address") or r.get("address") or ""
            print(f"  [{i}/{len(to_geocode)}] {key}: {address}")
            if not address:
                cache[key] = {
                    "geo_lat": None, "geo_lon": None, "location_type": None,
                    "formatted_address": None, "address_components": [],
                    "viewport": None, "place_id": None, "types": [],
                }
            else:
                result = google_geocode(address)
                if result is not None:
                    cache[key] = result
                    glat = result.get("geo_lat")
                    glon = result.get("geo_lon")
                    loc_type = result.get("location_type")
                    coords = f"{glat:.6f}, {glon:.6f}" if glat is not None else "None"
                    print(f"    → {coords} [{loc_type}]")
                else:
                    print(f"    → geocode failed (no API key or network error)")
                time.sleep(GEOCODE_DELAY_S)

            if i % SAVE_EVERY == 0:
                save_cache(cache)
                print(f"    [cache saved at {i}]")

        save_cache(cache)
        print("Geocoding complete.")
    else:
        print("All shelters already cached.")

    # Compute neighborhood stats from muni coords
    print("Computing neighborhood outlier stats...")
    nb_stats = compute_neighborhood_stats(records)
    print(f"  {len(nb_stats)} neighborhoods with ≥4 records.")

    # Make decisions
    print("Making coordinate decisions...")
    decisions = []
    output_shelters = []

    for r in records:
        key = r.get("shelter_number")
        cached = cache.get(key, {}) if key else {}
        muni_lat = r.get("lat")
        muni_lon = r.get("lon")
        geo_lat = cached.get("geo_lat")
        geo_lon = cached.get("geo_lon")
        location_type = cached.get("location_type")
        fmt_addr = cached.get("formatted_address")

        # Perfect match check
        perfect = is_perfect_match(r, cached)
        street = extract_street(r.get("address") or "")
        street_match = bool(street and fmt_addr and street in fmt_addr)
        city_match = bool(fmt_addr and "ירושלים" in fmt_addr)

        # Muni checks
        muni_in_bbox = check_muni_bbox(r)
        outlier, med_lat, med_lon, dist_from_median = is_muni_outlier(r, nb_stats)
        muni_suspect = not muni_in_bbox or outlier

        # Geo distance from muni (for audit)
        geo_dist = None
        if muni_lat and muni_lon and geo_lat and geo_lon:
            geo_dist = haversine(muni_lat, muni_lon, geo_lat, geo_lon)

        # Decision
        if perfect:
            final_source = "google_perfect"
        elif muni_suspect:
            final_source = "muni_suspect"
        else:
            final_source = "muni"

        decisions.append({
            "shelter_number": key,
            "address": r.get("address"),
            "category": r.get("category"),
            "muni_lat": muni_lat,
            "muni_lon": muni_lon,
            "geo_lat": geo_lat,
            "geo_lon": geo_lon,
            "location_type": location_type,
            "geo_formatted_address": fmt_addr,
            "street_match": street_match,
            "city_match": city_match,
            "perfect_match": perfect,
            "muni_in_bbox": muni_in_bbox,
            "muni_outlier": outlier,
            "cluster_median_lat": med_lat,
            "cluster_median_lon": med_lon,
            "distance_from_median_m": round(dist_from_median, 1) if dist_from_median is not None else None,
            "geo_distance_m": round(geo_dist, 1) if geo_dist is not None else None,
            "final_source": final_source,
        })

        # Build output shelter record (pre-slim format, with coord_source)
        s = dict(r)
        s["geo_lat"] = geo_lat
        s["geo_lon"] = geo_lon
        s["coord_source"] = final_source
        output_shelters.append(s)

    # Write coord_decisions.csv
    if decisions:
        fieldnames = list(decisions[0].keys())
        with open(DECISIONS_FILE, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(decisions)
        print(f"Wrote {len(decisions)} rows → {DECISIONS_FILE}")

    # Write shelters.json (pre-slim, with coord_source)
    SHELTERS_FILE.write_text(
        json.dumps(output_shelters, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {len(output_shelters)} records → {SHELTERS_FILE}")

    # Summary
    counts = {}
    for d in decisions:
        src = d["final_source"]
        counts[src] = counts.get(src, 0) + 1
    print("\nDecision summary:")
    for src, count in sorted(counts.items()):
        print(f"  {src}: {count}")


if __name__ == "__main__":
    main()
