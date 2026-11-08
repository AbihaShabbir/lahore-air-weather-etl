"""Central settings. Change things here, not inside the other files."""
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Everything (raw/, processed/, outputs/, the database) lives next to this file.
# ETL_BASE lets you point the pipeline somewhere else (used for testing).
BASE = Path(os.environ.get("ETL_BASE", Path(__file__).resolve().parent))
RAW_DIR = BASE / "raw"
PROCESSED_DIR = BASE / "processed"
OUTPUT_DIR = BASE / "outputs"
DB_PATH = BASE / "lahore_air_weather.db"
TABLE = "air_weather"

# Location: Lahore
LAT, LON = 31.5497, 74.3436
TIMEZONE = "Asia/Karachi"  # same timezone in BOTH calls so timestamps line up

# Date range: a rolling 365 days, so we see Lahore's winter smog AND the cleaner months.
# END_DATE is 6 days ago because the weather archive API lags about 5 days.
# Set the START_DATE / END_DATE environment variables (YYYY-MM-DD) to pin dates.
_end = datetime.now(timezone.utc).date() - timedelta(days=6)
END_DATE = os.environ.get("END_DATE") or _end.isoformat()
START_DATE = os.environ.get("START_DATE") or (
    datetime.strptime(END_DATE, "%Y-%m-%d").date() - timedelta(days=364)).isoformat()

AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
WEATHER_URL = "https://archive-api.open-meteo.com/v1/archive"

AIR_VARS = ["pm2_5", "pm10", "nitrogen_dioxide", "ozone",
            "carbon_monoxide", "sulphur_dioxide"]
WEATHER_VARS = ["temperature_2m", "relative_humidity_2m", "wind_speed_10m",
                "surface_pressure", "precipitation"]
VALUE_COLS = AIR_VARS + WEATHER_VARS

# WHO 2021 24-hour air quality guideline levels (ug/m3)
WHO_PM25_DAILY = 15
WHO_PM10_DAILY = 45
