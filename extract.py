"""STAGE 1 - EXTRACT: download hourly data from the two Open-Meteo APIs and
save the raw JSON exactly as received (raw/air_quality.json, raw/weather.json)."""
import json
import sys
import time

import requests

import config


def fetch(url: str, params: dict, out_path, retries: int = 4) -> dict:
    """Call an API with retries. Saves the untouched JSON to out_path."""
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, params=params, timeout=60)
            if r.status_code == 429:  # too many requests -> wait and retry
                wait = 15 * attempt
                print(f"  rate limited, waiting {wait}s ...")
                time.sleep(wait)
                continue
            r.raise_for_status()  # error for any other bad status (404, 500 ...)
            data = r.json()
            break
        except requests.RequestException as e:
            print(f"  attempt {attempt}/{retries} failed: {e}")
            if attempt == retries:
                raise
            time.sleep(5 * attempt)
    else:
        raise RuntimeError("API kept rate-limiting us; try again in a few minutes")

    hourly = data.get("hourly") or {}
    if not hourly.get("time"):
        raise ValueError(f"API returned no hourly data: {str(data)[:300]}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(data, f)
    print(f"  saved {out_path.name}: {len(hourly['time'])} hourly rows")
    return data


def main():
    common = {
        "latitude": config.LAT,
        "longitude": config.LON,
        "start_date": config.START_DATE,
        "end_date": config.END_DATE,
        "timezone": config.TIMEZONE,
    }
    print("Extracting air quality ...")
    fetch(config.AIR_URL,
          {**common, "hourly": ",".join(config.AIR_VARS)},
          config.RAW_DIR / "air_quality.json")
    print("Extracting weather ...")
    fetch(config.WEATHER_URL,
          {**common, "hourly": ",".join(config.WEATHER_VARS)},
          config.RAW_DIR / "weather.json")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"EXTRACT FAILED: {e}")
        sys.exit(1)
