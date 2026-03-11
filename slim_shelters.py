#!/usr/bin/env python3
"""
slim_shelters.py — run once (and after any geocode update) to regenerate
data/shelters.json with:
  - Baked coordinates: geo_lat/geo_lon → lat/lon (respects use_geo flag)
  - Pre-computed type field `t` ∈ {'P','A','S','T'}
  - Removed fields: geo_lat, geo_lon, geo_source, use_geo, admin, district
  - Minified output (~200KB vs ~320KB)
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


DROP_FIELDS = {'geo_lat', 'geo_lon', 'geo_source', 'use_geo', 'admin', 'district'}


def slim(s):
    # Bake coordinates
    if s.get('geo_lat') is not None and s.get('use_geo') is not False:
        s['lat'] = s['geo_lat']
        s['lon'] = s['geo_lon']
    # Add pre-computed type
    s['t'] = shelter_type(s)
    # Drop unneeded fields
    return {k: v for k, v in s.items() if k not in DROP_FIELDS}


def main():
    with open(INPUT, encoding='utf-8') as f:
        data = json.load(f)

    slimmed = [slim(s) for s in data]

    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(slimmed, f, ensure_ascii=False, separators=(',', ':'))

    size_kb = os.path.getsize(OUTPUT) / 1024
    print(f"Done. {len(slimmed)} records → {OUTPUT} ({size_kb:.1f} KB)")
    # Verify all have lat/lon/t
    missing = [s.get('shelter_number') for s in slimmed
               if s.get('lat') is None or s.get('lon') is None or 't' not in s]
    if missing:
        print(f"WARNING: {len(missing)} records missing lat/lon/t: {missing[:5]}")
    else:
        print("All records have lat, lon, and t. ✓")


if __name__ == '__main__':
    main()
