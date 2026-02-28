import os
import pandas as pd
from flask import Flask, Response, render_template

app = Flask(__name__)

CSV_PATH = os.path.join(os.path.dirname(__file__), "Records.csv")

STRIP_CHARS = "\u200b\u200f\u200e\xa0"

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


def load_shelters():
    df = pd.read_csv(CSV_PATH, encoding="utf-8-sig", dtype=str)

    # Strip BOM/invisible chars from column names
    df.columns = [c.strip(STRIP_CHARS) for c in df.columns]

    # Strip invisible chars from all string cells
    for col in df.columns:
        df[col] = df[col].apply(
            lambda v: v.strip(STRIP_CHARS) if isinstance(v, str) else v
        )

    df.rename(columns=COL_MAP, inplace=True)

    # Convert coordinates to float
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")

    # Drop rows with missing coordinates
    df.dropna(subset=["lat", "lon"], inplace=True)

    return df


SHELTERS_DF = load_shelters()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/shelters")
def shelters():
    cols = [
        "neighborhood", "shelter_number", "address", "area", "type",
        "accessibility", "capacity", "affiliation", "lat", "lon",
        "map_address", "admin", "district", "category",
    ]
    # Only include columns that exist in the dataframe
    existing = [c for c in cols if c in SHELTERS_DF.columns]
    # to_json() correctly serializes NaN → null (unlike jsonify + to_dict)
    json_str = SHELTERS_DF[existing].to_json(orient="records", force_ascii=False)
    return Response(json_str, mimetype="application/json")


if __name__ == "__main__":
    app.run(debug=True)
