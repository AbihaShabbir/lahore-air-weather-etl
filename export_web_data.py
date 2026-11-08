"""STAGE 6 - EXPORT FOR THE WEBSITE.

Reads the finished data FROM THE DATABASE, summarises it, and writes web/data.js.
The website (web/index.html) loads that file and draws the charts in the browser.
No server or database is needed online - the website is just static files.
"""
import json
import sys
from datetime import datetime

import pandas as pd

import config
import eda

WEB_DIR = config.BASE / "web"
SCATTER_VARS = ["temperature_2m", "relative_humidity_2m",
                "wind_speed_10m", "surface_pressure"]
CORR_COLS = ["pm2_5", "pm10", "temperature_2m", "relative_humidity_2m",
             "wind_speed_10m", "surface_pressure", "precipitation"]


def r(x, n=1):
    """Round a number; turn NaN into None (null in JSON)."""
    return None if pd.isna(x) else round(float(x), n)


def build() -> dict:
    df = eda.load_data()
    if df.empty:
        raise ValueError("The database table is empty - run the pipeline first")
    daily = eda.daily_table(df)
    findings_text = eda.write_findings(df, daily)

    pm = df["pm2_5"]
    peak = df.loc[pm.idxmax()]
    month_mean = df.groupby("month")["pm2_5"].mean()
    winter = df["time"].dt.month.isin([11, 12, 1, 2])

    # monthly table: mean PM2.5 + how many days went over the WHO guideline
    by_month = daily.groupby("month").agg(days=("over_who_pm25", "size"),
                                          days_over=("over_who_pm25", "sum"))
    monthly = [{"month": m, "pm25": r(v),
                "days": int(by_month.loc[m, "days"]) if m in by_month.index else 0,
                "days_over": int(by_month.loc[m, "days_over"]) if m in by_month.index else 0}
               for m, v in month_mean.items()]

    hourly = [{"hour": int(h), "pm25": r(v)}
              for h, v in df.groupby("hour")["pm2_5"].mean().items()]

    daily_list = [{"d": str(row.date), "pm25": r(row.pm2_5_mean), "pm10": r(row.pm10_mean)}
                  for row in daily.itertuples()]

    # a random sample keeps the scatter plot fast in the browser
    sample = df.sample(n=min(1500, len(df)), random_state=0)
    scatter = {c: [[r(x), r(y)] for x, y in zip(sample[c], sample["pm2_5"])]
               for c in SCATTER_VARS}

    corr = df[CORR_COLS].corr()
    report_path = config.PROCESSED_DIR / "transform_report.json"
    pipeline = json.loads(report_path.read_text()) if report_path.exists() else {}
    pipeline["rows_in_database"] = len(df)

    return {
        "meta": {
            "location": "Lahore, Pakistan", "lat": config.LAT, "lon": config.LON,
            "start": f"{df['time'].min():%d %b %Y}", "end": f"{df['time'].max():%d %b %Y}",
            "hours": len(df), "generated": datetime.now().strftime("%d %b %Y"),
            "who_pm25": config.WHO_PM25_DAILY, "who_pm10": config.WHO_PM10_DAILY,
        },
        "kpis": {
            "mean": r(pm.mean()), "median": r(pm.median()), "max": r(pm.max()),
            "max_time": f"{peak['time']:%d %b %Y, %H:%M}",
            "days_measured": len(daily),
            "days_over_who": int(daily["over_who_pm25"].sum()),
            "days_over_who_pm10": int(daily["over_who_pm10"].sum()),
            "worst_month": {"month": month_mean.idxmax(), "mean": r(month_mean.max())},
            "best_month": {"month": month_mean.idxmin(), "mean": r(month_mean.min())},
            "winter_mean": r(pm[winter].mean()) if winter.any() else None,
            "other_mean": r(pm[~winter].mean()) if (~winter).any() else None,
        },
        "daily": daily_list,
        "monthly": monthly,
        "hourly": hourly,
        "scatter": scatter,
        "corr": {"cols": CORR_COLS,
                 "matrix": [[r(v, 2) for v in row] for row in corr.values]},
        "findings": [ln[2:] for ln in findings_text.splitlines() if ln.startswith("- ")],
        "pipeline": pipeline,
    }


def main():
    data = build()
    WEB_DIR.mkdir(parents=True, exist_ok=True)
    out = WEB_DIR / "data.js"
    out.write_text("window.DATA = " + json.dumps(data, ensure_ascii=False,
                                                 separators=(",", ":")) + ";\n",
                   encoding="utf-8")
    print(f"Website data written: {out} ({out.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"EXPORT FAILED: {e}")
        sys.exit(1)
