#!/usr/bin/env python3
"""
slim_shelters.py — run once (and after any geocode update) to regenerate
data/shelters.json with:
  - Baked coordinates: google_perfect → geo_lat/geo_lon, else muni lat/lon
  - Pre-computed type field `t` ∈ {'P','A','S','T'}
  - suspect bool: True if coord_source == 'muni_suspect'
  - Removed fields: geo_lat, geo_lon, geo_source, use_geo, coord_source, admin, district
  - Minified output (~200KB vs ~320KB)

Run score_coords.py first to generate coord_source in shelters.json.
"""

import json, os

INPUT  = os.path.join(os.path.dirname(__file__), 'data', 'shelters.json')
OUTPUT = INPUT  # overwrite in-place


def shelter_type(s):
    cat = (s.get('category') or '').lower()
    typ = (s.get('type') or '').lower()
    acc = (s.get('accessibility') or '').lower()
    if 'מחסה' in typ or 'מחסה' in cat:
        return 'P'
    if 'נגיש' in acc or 'נגיש' in cat or 'נגיש' in typ:
        return 'A'
    if 'בית ספר' in cat or 'בית-ספר' in cat:
        return 'S'
    return 'T'


DROP_FIELDS = {'geo_lat', 'geo_lon', 'geo_source', 'use_geo', 'coord_source', 'admin', 'district'}

ISRAEL_BBOX = dict(lat_min=29.0, lat_max=33.5, lon_min=34.0, lon_max=36.0)


def in_israel(s):
    lat, lon = s.get('lat'), s.get('lon')
    if lat is None or lon is None:
        return False
    return (ISRAEL_BBOX['lat_min'] <= lat <= ISRAEL_BBOX['lat_max'] and
            ISRAEL_BBOX['lon_min'] <= lon <= ISRAEL_BBOX['lon_max'])


def slim(s):
    # Bake coordinates: use Google only on a perfect match
    if s.get('coord_source') == 'google_perfect' and s.get('geo_lat') is not None:
        s['lat'] = s['geo_lat']
        s['lon'] = s['geo_lon']
    elif s.get('lat') is None and s.get('geo_lat') is not None:
        # No muni coords at all — use Google as last resort (still marked suspect)
        s['lat'] = s['geo_lat']
        s['lon'] = s['geo_lon']
    # else: keep muni lat/lon as-is
    # Add suspect flag
    s['suspect'] = s.get('coord_source') == 'muni_suspect'
    # Add pre-computed type
    s['t'] = shelter_type(s)
    # Drop unneeded fields
    return {k: v for k, v in s.items() if k not in DROP_FIELDS}


def main():
    with open(INPUT, encoding='utf-8') as f:
        data = json.load(f)

    slimmed = [slim(s) for s in data]

    valid = [s for s in slimmed if in_israel(s)]
    dropped = [s for s in slimmed if not in_israel(s)]
    for s in dropped:
        print(f"  DROPPED (outside Israel): {s.get('shelter_number')} lat={s.get('lat')} lon={s.get('lon')}")

    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(valid, f, ensure_ascii=False, separators=(',', ':'))

    size_kb = os.path.getsize(OUTPUT) / 1024
    print(f"Done. {len(valid)} records ({len(dropped)} dropped) → {OUTPUT} ({size_kb:.1f} KB)")
    # Verify all have lat/lon/t
    missing = [s.get('shelter_number') for s in valid
               if s.get('lat') is None or s.get('lon') is None or 't' not in s]
    if missing:
        print(f"WARNING: {len(missing)} records missing lat/lon/t: {missing[:5]}")
    else:
        print("All records have lat, lon, and t. ✓")


if __name__ == '__main__':
    main()
