"""
Coord review tool — dev server on port 5001.

Endpoints:
  GET  /                   → serve review_coords.html
  GET  /data/shelters.json → read-only proxy of data/shelters.json
  POST /api/set-coords     → body: {shelter_number, use_geo}
                             updates matching entry, returns {ok: true}

Run: venv/bin/python review_coords.py
"""

import json
import os
from pathlib import Path
from flask import Flask, jsonify, request, send_file

BASE_DIR = Path(__file__).parent
DATA_FILE = BASE_DIR / 'data' / 'shelters.json'
HTML_FILE = BASE_DIR / 'review_coords.html'

app = Flask(__name__)


@app.get('/')
def index():
    return send_file(HTML_FILE)


@app.get('/data/shelters.json')
def shelters():
    return send_file(DATA_FILE, mimetype='application/json')


@app.post('/api/set-coords')
def set_coords():
    body = request.get_json(force=True)
    shelter_number = body.get('shelter_number')
    use_geo = body.get('use_geo')   # True, False, or None

    shelters = json.loads(DATA_FILE.read_text(encoding='utf-8'))
    updated = False
    for s in shelters:
        if str(s.get('shelter_number')) == str(shelter_number):
            if use_geo is None:
                s.pop('use_geo', None)
            else:
                s['use_geo'] = use_geo
            updated = True
            break

    if not updated:
        return jsonify({'ok': False, 'error': 'shelter not found'}), 404

    DATA_FILE.write_text(
        json.dumps(shelters, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    return jsonify({'ok': True})


if __name__ == '__main__':
    app.run(port=5001, debug=True)
