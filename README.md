# מקלטים – Jerusalem Emergency Shelters Map

Interactive map of 550+ public emergency shelters (מקלטים) in Jerusalem.

**Live site: https://amichw.github.io/miklatim_jerus/**

---

## Usage

### Map
- **Pan & zoom** – drag or pinch the map to explore
- **Tap a marker** – opens a details card with the shelter's address, type, capacity, and a **"🗺 נווט למקלט"** button that launches Google Maps walking directions
- **Tap the map** – collapses the sidebar on mobile

### Marker colors
| Color | Type |
|-------|------|
| 🔵 Blue | מקלט נגיש – accessible shelter |
| 🟢 Green | מקלט ציבורי – standard public shelter |
| ⚫ Gray | בית ספר – school shelter |

### GPS / Locate me
1. The map **automatically requests your location** on load
2. A **pulsing blue dot** marks your position and a **red dashed line** draws to the nearest shelter
3. Tap the **crosshair button** (bottom-left) at any time to re-center on your location
4. Tap **any marker** to see its distance from you
5. Tap the **blue dot** to refresh the nearest shelter

### Sidebar filters
Open the sidebar with the **☰** button (top-right on desktop, auto-hidden on mobile):

| Filter | What it does |
|--------|-------------|
| **חיפוש חופשי** | Free-text search by address, shelter number, or neighborhood |
| **סוג מקלט** | Toggle buttons to show/hide each shelter type |
| **שכונות** | Checkboxes to filter by neighborhood (select all / clear all) |

All filters work together (AND logic) and update the map live.

### Contact
A **WhatsApp button** is pinned at the bottom of the sidebar — click it to report errors or send suggestions directly to the developer.

---

## Deployment

### Local Development
```bash
git clone https://github.com/amichw/miklatim_jerus.git
cd miklatim_jerus
python3 -m http.server 8080
# → http://localhost:8080
```

## Stack
- **Leaflet.js** – interactive map
- **Bootstrap 5 RTL** – Hebrew-friendly UI
- **GitHub Pages** – static hosting (no server required)
- Data: `data/shelters.json` – 550 shelter records from the Jerusalem Municipality, geocoded via Google Maps with confidence scoring; out-of-Israel coordinates are excluded automatically
