# מקלטים – Jerusalem Emergency Shelters Map

Interactive map of 550+ public emergency shelters (מקלטים) in Jerusalem.

**Live site: https://miklatim-jerus.onrender.com/**

---

## Usage

### Map
- **Pan & zoom** – drag or pinch the map to explore
- **Tap a marker** – opens a details card with the shelter's address, type, capacity, and a **"🗺 נווט למקלט"** button that launches Google Maps walking directions

### Marker colors
| Color | Type |
|-------|------|
| 🔴 Red | מחסה – most protected shelter |
| 🔵 Blue | מקלט נגיש – accessible shelter |
| 🟢 Green | מקלט ציבורי – standard public shelter |
| ⚫ Gray | בית ספר – school shelter |

### GPS / Locate me
1. Tap **⊕** (bottom-right corner) to find your current location
2. The map zooms to you and a **pulsing blue dot** marks your position
3. A **red dashed line** automatically draws to the nearest shelter and its popup opens
4. Tap **any marker** to see its distance from you
5. Tap the **blue dot** again at any time to refresh the nearest shelter

### Sidebar filters
Open the sidebar with the **☰** button (top-right on desktop, auto-hidden on mobile):

| Filter | What it does |
|--------|-------------|
| **חיפוש חופשי** | Free-text search by address, shelter number, or neighborhood |
| **סוג מקלט** | Toggle buttons to show/hide each shelter type |
| **שכונות** | Checkboxes to filter by neighborhood (select all / clear all) |

All filters work together (AND logic) and update the map live.

---

## Local development

```bash
git clone https://github.com/amichw/miklatim_jerus.git
cd miklatim
python -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/python app.py
# → http://localhost:5000
```

## Stack
- **Flask** – Python web server
- **pandas** – CSV loading and cleaning
- **Leaflet.js** – interactive map
- **Bootstrap 5 RTL** – Hebrew-friendly UI
- Data: `Records.csv` – 557 shelter records from the Jerusalem Municipality
