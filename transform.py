"""STAGE 2 + 3 - TRANSFORM and VALIDATE.

raw JSON -> pandas tables -> merged on time -> cleaned -> checked row-by-row
with Pydantic -> processed/clean_air_weather.csv (+ rejected_rows.csv).
"""
import json
import sys

import pandas as pd
from pydantic import ValidationError

import config
from schema import AirWeatherRecord


def load_hourly(path) -> pd.DataFrame:
    """JSON {"hourly": {"time": [...], "pm2_5": [...]}} -> DataFrame."""
    with open(path) as f:
        data = json.load(f)
    hourly = data.get("hourly")
    if not hourly or "time" not in hourly:
        raise ValueError(f"{path} has no hourly/time data")
    df = pd.DataFrame(hourly)
    df["time"] = pd.to_datetime(df["time"], errors="coerce")
    return df


def fill_short_gaps(s: pd.Series, max_gap: int = 3) -> pd.Series:
    """Linearly fill runs of missing values that are at most max_gap hours long.
    Longer runs are left empty (we will not invent many hours of data)."""
    isna = s.isna()
    run_id = (isna != isna.shift()).cumsum()          # label each run of NaN / non-NaN
    run_len = isna.groupby(run_id).transform("sum")   # length of the NaN run each row is in
    filled = s.interpolate(limit_area="inside")
    return s.where(~(isna & (run_len <= max_gap)), filled)


def clean(air: pd.DataFrame, weather: pd.DataFrame):
    """Merge and clean. Returns (dataframe, report dict)."""
    report = {"air_rows_raw": len(air), "weather_rows_raw": len(weather)}

    # 1. Drop rows with a broken timestamp, and duplicate timestamps
    air = air.dropna(subset=["time"]).drop_duplicates("time")
    weather = weather.dropna(subset=["time"]).drop_duplicates("time")
    report["duplicates_removed"] = (report["air_rows_raw"] - len(air)
                                    + report["weather_rows_raw"] - len(weather))

    # 2. Merge the two tables on the timestamp (keep only hours present in both)
    df = air.merge(weather, on="time", how="inner").sort_values("time")
    df = df.reset_index(drop=True)
    report["rows_after_merge"] = len(df)

    # 3. Make sure every value column is a number (bad text -> NaN)
    for col in config.VALUE_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # 4. Missing values: fill gaps of up to 3 hours by interpolation
    #    (a short sensor gap is safe to estimate; a long one is not)
    missing_before = int(df[config.VALUE_COLS].isna().sum().sum())
    for col in config.VALUE_COLS:
        df[col] = fill_short_gaps(df[col], max_gap=3)
    report["missing_cells_before"] = missing_before
    report["missing_cells_after_interpolation"] = int(
        df[config.VALUE_COLS].isna().sum().sum())

    # 5. Rows still missing a REQUIRED value are dropped
    required = ["pm2_5", "pm10"] + config.WEATHER_VARS
    before = len(df)
    df = df.dropna(subset=required).reset_index(drop=True)
    report["rows_dropped_missing_required"] = before - len(df)
    return df, report


def validate(df: pd.DataFrame):
    """Run every row through the Pydantic model. Returns (valid_df, rejected_df)."""
    valid, rejected = [], []
    for rec in df.to_dict("records"):
        # NaN -> None so optional fields are accepted as "no value"
        row = {k: (None if pd.isna(v) else v) for k, v in rec.items()}
        try:
            valid.append(AirWeatherRecord(**row).model_dump())
        except ValidationError as e:
            reasons = "; ".join(f"{err['loc'][0]}: {err['msg']}" for err in e.errors())
            rejected.append({**row, "error": reasons})
    return pd.DataFrame(valid), pd.DataFrame(rejected)


def main():
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    air = load_hourly(config.RAW_DIR / "air_quality.json")
    weather = load_hourly(config.RAW_DIR / "weather.json")

    df, report = clean(air, weather)
    valid, rejected = validate(df)
    report["rows_valid"] = len(valid)
    report["rows_rejected"] = len(rejected)

    valid.to_csv(config.PROCESSED_DIR / "clean_air_weather.csv", index=False)
    rejected.to_csv(config.PROCESSED_DIR / "rejected_rows.csv", index=False)
    with open(config.PROCESSED_DIR / "transform_report.json", "w") as f:
        json.dump(report, f, indent=2)

    print("Transform report:")
    for k, v in report.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"TRANSFORM FAILED: {e}")
        sys.exit(1)
