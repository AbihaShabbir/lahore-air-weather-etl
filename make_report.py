"""Builds the short project report (report.docx) from your REAL results.

Every number comes from the database, processed/transform_report.json and the
charts in outputs/, so run the pipeline first:

    python run_all.py
    pip install python-docx          # once
    python make_report.py --web-url https://YOUR-PROJECT.vercel.app

Open report.docx in Word, check it, edit anything you like, and submit it.
(--web-url is optional; --github defaults to the project repository.)
"""
import argparse
import json
import sys
from datetime import date

import pandas as pd
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

import config
import eda
from schema import AirWeatherRecord

GROUP = ["2025-AI-254", "2025-AI-255", "2025-AI-260"]
WORK = [
    ("2025-AI-254", "Data extraction and raw data storage"),
    ("2025-AI-255", "Data transformation and Pydantic validation"),
    ("2025-AI-260", "Database loading and EDA"),
]
UNITS = {"pm2_5": "µg/m³", "pm10": "µg/m³", "nitrogen_dioxide": "µg/m³",
         "ozone": "µg/m³", "carbon_monoxide": "µg/m³", "sulphur_dioxide": "µg/m³",
         "temperature_2m": "°C", "relative_humidity_2m": "%",
         "wind_speed_10m": "km/h", "surface_pressure": "hPa", "precipitation": "mm"}
FIGURES = [
    ("01_pm25_distribution.png", "Distribution of hourly PM2.5, with the WHO 24-hour guideline.", 5.2),
    ("02_pollutant_distributions.png", "Distribution of each of the six pollutants.", 6.2),
    ("03_pm25_by_hour.png", "Average PM2.5 by hour of day (band = 95% confidence interval).", 5.2),
    ("04_pm25_daily.png", "Daily average PM2.5 through the period, with a 7-day average.", 6.2),
    ("05_pm25_monthly_boxplot.png", "PM2.5 by month (box = middle 50% of hours, line = median).", 5.4),
    ("06_correlation_heatmap.png", "Correlation of each pollutant with each weather variable.", 4.8),
    ("07_pm25_vs_weather.png", "PM2.5 against four weather variables (dark line = median per slice).", 5.4),
    ("08_days_over_who.png", "Number of days per month above the WHO PM2.5 guideline.", 5.2),
]


# ---------------------------------------------------------------- helpers
def strength(r):
    a = abs(r)
    return "a strong" if a >= 0.5 else "a moderate" if a >= 0.3 else "a weak" if a >= 0.1 else "almost no"


def month_long(m):
    return pd.Period(m).strftime("%B %Y")


def set_cell(cell, text, bold=False, align=None):
    cell.text = ""
    run = cell.paragraphs[0].add_run(str(text))
    run.font.size = Pt(10)
    run.bold = bold
    if align:
        cell.paragraphs[0].alignment = align


def table(doc, header, rows, widths=None, right_from=None):
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Light Grid Accent 1"
    for i, h in enumerate(header):
        set_cell(t.rows[0].cells[i], h, bold=True)
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            right = right_from is not None and i >= right_from
            set_cell(cells[i], v, align=WD_ALIGN_PARAGRAPH.RIGHT if right else None)
    if widths:
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Inches(w)
    doc.add_paragraph()
    return t


def bullets(doc, items):
    for it in items:
        doc.add_paragraph(it, style="List Bullet")


def add_page_number(paragraph):
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run()
    for kind, text in (("begin", None), (None, "PAGE"), ("end", None)):
        if kind:
            el = OxmlElement("w:fldChar")
            el.set(qn("w:fldCharType"), kind)
        else:
            el = OxmlElement("w:instrText")
            el.set(qn("xml:space"), "preserve")
            el.text = text
        run._r.append(el)
    run.font.size = Pt(9)


def field_rules():
    """Read the Pydantic model so the report always matches schema.py."""
    rows = []
    for name, info in AirWeatherRecord.model_fields.items():
        if name == "time":
            rows.append(("time", "yes", "valid date and time"))
            continue
        lo = next((m.ge for m in info.metadata if hasattr(m, "ge")), None)
        hi = next((m.le for m in info.metadata if hasattr(m, "le")), None)
        unit = UNITS.get(name, "")
        rows.append((f"{name} ({unit})", "yes" if info.is_required() else "no (may be empty)",
                     f"{lo} to {hi}"))
    return rows


# ---------------------------------------------------------------- build
def build(args):
    df = eda.load_data()
    daily = eda.daily_table(df)
    pm = df["pm2_5"]
    rep_path = config.PROCESSED_DIR / "transform_report.json"
    rep = json.loads(rep_path.read_text()) if rep_path.exists() else {}
    g = lambda k: f"{rep[k]:,}" if k in rep else "n/a"   # noqa: E731

    month_mean = df.groupby("month")["pm2_5"].mean()
    hour_mean = df.groupby("hour")["pm2_5"].mean()
    corr = df[["pm2_5"] + config.WEATHER_VARS].corr()["pm2_5"].drop("pm2_5")
    n_days, n_over = len(daily), int(daily["over_who_pm25"].sum())
    winter = df["time"].dt.month.isin([11, 12, 1, 2])
    start, end = df["time"].min(), df["time"].max()
    n_missing = int(df[config.VALUE_COLS].isna().sum().sum())

    doc = Document()
    sec = doc.sections[0]
    sec.left_margin = sec.right_margin = Inches(1)
    sec.top_margin = sec.bottom_margin = Inches(0.9)
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)
    for lvl in ("Title", "Heading 1", "Heading 2"):
        doc.styles[lvl].font.color.rgb = RGBColor(0x1F, 0x29, 0x37)
        doc.styles[lvl].font.name = "Calibri"
    add_page_number(sec.footer.paragraphs[0])

    # ---- title block
    doc.add_heading("Lahore Air Quality and Weather: an ETL + EDA Pipeline", level=0)
    p = doc.add_paragraph()
    p.add_run("Programming for AI (Fall 2026) · Project 1").bold = True
    doc.add_paragraph("Group members (roll numbers): " + ", ".join(GROUP))
    doc.add_paragraph(f"Report date: {date.today():%d %B %Y}")

    # ---- 1
    doc.add_heading("1. Introduction", level=1)
    doc.add_paragraph(
        "Lahore regularly has some of the highest air pollution levels in the world. "
        "This project builds an ETL (Extract, Transform, Load) pipeline that collects hourly "
        "air quality and weather data for Lahore from public APIs, validates and stores it in a "
        "database, and then carries out a structured exploratory data analysis (EDA) to study how "
        "weather conditions relate to pollution levels.")

    # ---- 2
    doc.add_heading("2. Dataset and why we chose it", level=1)
    table(doc, ["Item", "Details"], [
        ("Source", "Open-Meteo Air Quality API and Open-Meteo Historical Weather API (free, no API key)"),
        ("Location", f"Lahore, Pakistan (latitude {config.LAT}, longitude {config.LON})"),
        ("Period", f"{start:%d %b %Y} to {end:%d %b %Y}, hourly (timezone {config.TIMEZONE})"),
        ("Records", f"{len(df):,} hourly records in the database"),
        ("Pollutants", "PM2.5, PM10, nitrogen dioxide (NO2), ozone (O3), carbon monoxide (CO), sulphur dioxide (SO2)"),
        ("Weather", "temperature, relative humidity, wind speed, surface pressure, precipitation"),
    ], widths=[1.3, 5.2])
    doc.add_paragraph(
        "We chose this dataset because both APIs are free and give hourly data with shared "
        "timestamps, so they can be merged exactly. The topic is also local and relevant: "
        "Lahore's winter smog is a real public-health problem, and weather is one of the main "
        "factors that influence it.")

    # ---- 3
    doc.add_heading("3. Method: the ETL pipeline", level=1)
    doc.add_heading("3.1 Extract", level=2)
    doc.add_paragraph(
        "extract.py calls the two APIs with the Python requests library. It retries failed calls "
        "(up to 4 attempts), waits when the API rate-limits, and saves the raw JSON responses "
        "unchanged in the raw/ folder, so the pipeline can be re-run without calling the API again. "
        f"The air quality API returned {g('air_rows_raw')} hourly rows and the weather API "
        f"{g('weather_rows_raw')} rows.")
    doc.add_heading("3.2 Transform (pandas)", level=2)
    bullets(doc, [
        "The JSON is converted to pandas DataFrames and the two tables are merged on the timestamp.",
        f"Duplicate timestamps are removed ({g('duplicates_removed')} found); {g('rows_after_merge')} rows remain after the merge.",
        "All value columns are converted to numbers.",
        "Missing values: gaps of up to 3 hours are filled by linear interpolation (a short sensor gap is "
        "safe to estimate, a long one is not). "
        f"Missing cells before filling: {g('missing_cells_before')}, after: {g('missing_cells_after_interpolation')}.",
        f"Rows still missing PM2.5, PM10 or any weather value are dropped ({g('rows_dropped_missing_required')} rows).",
    ])
    doc.add_heading("3.3 Validate (Pydantic)", level=2)
    doc.add_paragraph(
        "Every row is checked against a Pydantic model (schema.py). A row that breaks any rule is "
        "rejected and saved to processed/rejected_rows.csv together with the reason, instead of "
        f"silently entering the database. Result: {g('rows_valid')} rows valid, {g('rows_rejected')} rejected.")
    table(doc, ["Field", "Required", "Valid range"], field_rules(), widths=[2.6, 1.6, 2.3])
    doc.add_heading("3.4 Load (database)", level=2)
    doc.add_paragraph(
        f"The validated rows are written with SQLAlchemy into a SQLite database ({config.DB_PATH.name}), "
        f"table '{config.TABLE}', which now holds {len(df):,} rows. SQLite is a real SQL database stored in a "
        "single file, so no server is needed. The EDA reads the data back from this database, which "
        "confirms that the Load step worked.")

    # ---- 4
    doc.add_heading("4. Exploratory data analysis", level=1)
    doc.add_heading("4.1 Summary statistics and missing values", level=2)
    rows = []
    for c in config.VALUE_COLS:
        s = df[c]
        rows.append((eda.LABELS[c], UNITS[c], f"{s.mean():.1f}", f"{s.median():.1f}",
                     f"{s.min():.1f}", f"{s.max():.1f}"))
    table(doc, ["Variable", "Unit", "Mean", "Median", "Min", "Max"], rows,
          widths=[1.7, 0.9, 0.9, 0.9, 0.9, 0.9], right_from=2)
    doc.add_paragraph(
        "The database contains no missing values after cleaning." if n_missing == 0 else
        f"The database contains {n_missing} missing cells in total "
        f"({n_missing / df[config.VALUE_COLS].size:.2%} of all values); they are in optional pollutant columns.")

    doc.add_heading("4.2 Charts", level=2)
    for i, (fname, caption, width) in enumerate(FIGURES, 1):
        path = config.OUTPUT_DIR / fname
        if not path.exists():
            continue
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.keep_with_next = True
        p.add_run().add_picture(str(path), width=Inches(width))
        cap = doc.add_paragraph()
        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = cap.add_run(f"Figure {i}. {caption}")
        r.italic = True
        r.font.size = Pt(9)

    doc.add_heading("4.3 Findings", level=2)
    items = [
        f"PM2.5 averaged {pm.mean():.1f} µg/m³ (median {pm.median():.1f}) and peaked at "
        f"{pm.max():.1f} µg/m³ on {df.loc[pm.idxmax(), 'time']:%d %B %Y at %H:%M}.",
        f"{n_over} of {n_days} measured days ({n_over / n_days:.0%}) had a daily mean PM2.5 above the WHO "
        f"guideline of {config.WHO_PM25_DAILY} µg/m³, and {int(daily['over_who_pm10'].sum())} days "
        f"were above the PM10 guideline of {config.WHO_PM10_DAILY} µg/m³.",
        f"The worst month was {month_long(month_mean.idxmax())} (mean {month_mean.max():.1f} µg/m³) and the "
        f"cleanest was {month_long(month_mean.idxmin())} (mean {month_mean.min():.1f} µg/m³).",
    ]
    if winter.any() and (~winter).any():
        w, o = pm[winter].mean(), pm[~winter].mean()
        items.append(f"Mean PM2.5 in November-February was {w:.1f} µg/m³ compared with {o:.1f} µg/m³ in the other "
                     f"months ({w / o:.1f} times as high).")
    items.append(f"Over the day, PM2.5 was highest around {hour_mean.idxmax()}:00 ({hour_mean.max():.1f} µg/m³) and "
                 f"lowest around {hour_mean.idxmin()}:00 ({hour_mean.min():.1f} µg/m³).")
    items.append("Relationship of PM2.5 with weather: " + "; ".join(
        f"{eda.LABELS[k].lower()} shows {strength(v)} {'positive' if v > 0 else 'negative'} "
        f"relationship (r = {v:+.2f})" if abs(v) >= 0.1 else
        f"{eda.LABELS[k].lower()} shows almost no linear relationship (r = {v:+.2f})"
        for k, v in corr.items()) + ".")
    rain = df["precipitation"] > 0
    if rain.any() and (~rain).any():
        items.append(f"Mean PM2.5 was {pm[rain].mean():.1f} µg/m³ in hours with rain and "
                     f"{pm[~rain].mean():.1f} µg/m³ in dry hours.")
    bullets(doc, items)

    # ---- 5
    doc.add_heading("5. Limitations", level=1)
    bullets(doc, [
        "The air quality values come from an atmospheric computer model (CAMS, accessed through Open-Meteo), "
        "not from monitors on the ground in Lahore, so real readings can differ.",
        "One grid point is used to represent the whole city.",
        "The analysis covers about one year, so seasonal patterns come from a single winter.",
        "Correlation shows association only. It does not prove that weather causes the changes in pollution.",
        "Gaps of up to 3 hours were filled by interpolation, which is an estimate rather than a measurement.",
    ])

    # ---- 6
    doc.add_heading("6. Conclusion", level=1)
    concl = (f"Between {start:%B %Y} and {end:%B %Y}, PM2.5 in Lahore was above the WHO daily guideline on "
             f"{n_over / n_days:.0%} of measured days. ")
    if winter.any() and (~winter).any():
        concl += (f"Pollution was {'higher' if pm[winter].mean() > pm[~winter].mean() else 'lower'} in "
                  "November-February than in the rest of the year. ")
    top = corr.abs().idxmax()
    concl += (f"Among the weather variables, {eda.LABELS[top].lower()} had the strongest linear association with "
              f"PM2.5 (r = {corr[top]:+.2f}). These are associations measured on modelled data; they do not by "
              "themselves show cause and effect. The pipeline is fully automated, so it can be re-run to refresh "
              "the data and the analysis.")
    doc.add_paragraph(concl)

    # ---- 7
    doc.add_heading("7. Project links and how to run", level=1)
    bullets(doc, [f"GitHub repository: {args.github}"] +
            ([f"Web dashboard: {args.web_url}"] if args.web_url else []))
    doc.add_paragraph("To run the whole pipeline: pip install -r requirements.txt, then python run_all.py.")
    doc.add_heading("Work division", level=2)
    table(doc, ["Roll number", "Responsibility"], WORK, widths=[1.5, 5.0])

    out = args.out
    doc.save(out)
    return out


def main():
    ap = argparse.ArgumentParser(description="Build report.docx from the pipeline results")
    ap.add_argument("--github", default="https://github.com/AbihaShabbir/lahore-air-weather-etl")
    ap.add_argument("--web-url", default=None, help="your .vercel.app link (optional)")
    ap.add_argument("--out", default=str(config.BASE / "report.docx"))
    args = ap.parse_args()
    print("Report written:", build(args))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"REPORT FAILED: {e}")
        sys.exit(1)
