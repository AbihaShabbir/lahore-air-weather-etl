"""Creates FAKE JSON in the same shape as the Open-Meteo responses, so the
pipeline can be tested without internet. It includes deliberately bad data
(nulls, a duplicate hour, impossible humidity) to prove cleaning/validation work.

DO NOT use this data for your real report.   Usage: python tests/make_sample_data.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402

rng = np.random.default_rng(42)
times = pd.date_range(config.START_DATE, config.END_DATE + " 23:00", freq="h")
n = len(times)
doy = times.dayofyear.to_numpy()
hour = times.hour.to_numpy()

winter = np.cos((times.month.to_numpy() - 12) / 12 * 2 * np.pi) * 0.5 + 0.5   # 1 in Dec
wind = np.clip(rng.gamma(2.0, 4.0, n), 0, 60)
humidity = np.clip(55 + 25 * winter + rng.normal(0, 12, n), 5, 100)
temp = 25 + 10 * (1 - winter) + 6 * np.sin((hour - 9) / 24 * 2 * np.pi) + rng.normal(0, 1.5, n)
rain = np.where(rng.random(n) < 0.06, rng.gamma(1.5, 1.5, n), 0.0)
pressure = 1000 + 12 * winter + rng.normal(0, 3, n)
pm25 = np.clip(40 + 150 * winter + 25 * np.cos((hour - 7) / 24 * 2 * np.pi)
               - 3 * wind - 20 * (rain > 0) + rng.normal(0, 20, n), 2, None)
pm10 = np.clip(pm25 * 1.8 + rng.normal(0, 10, n), 1, None)


def hourly(d):
    return {"hourly": {"time": [t.strftime("%Y-%m-%dT%H:%M") for t in times],
                       **{k: [None if np.isnan(x) else round(float(x), 2) for x in v]
                          for k, v in d.items()}}}


air = {"pm2_5": pm25.copy(), "pm10": pm10.copy(),
       "nitrogen_dioxide": 20 + rng.normal(0, 5, n).clip(-15) + 0 * pm25,
       "ozone": 60 + rng.normal(0, 15, n), "carbon_monoxide": 500 + 4 * pm25,
       "sulphur_dioxide": 10 + rng.normal(0, 2, n).clip(-8)}
weather = {"temperature_2m": temp, "relative_humidity_2m": humidity,
           "wind_speed_10m": wind, "surface_pressure": pressure, "precipitation": rain}

# --- inject problems on purpose ---
air["pm2_5"][100:102] = np.nan          # short gap (should be interpolated)
air["pm2_5"][500:520] = np.nan          # long gap (rows should be dropped)
air["ozone"][300:310] = np.nan          # optional column, allowed to stay missing
weather["relative_humidity_2m"][700] = 140   # impossible -> Pydantic must reject
weather["temperature_2m"][900] = 90          # impossible -> Pydantic must reject

air_json, weather_json = hourly(air), hourly(weather)
air_json["hourly"]["time"].append(air_json["hourly"]["time"][5])   # duplicate hour
for k in config.AIR_VARS:
    air_json["hourly"][k].append(air_json["hourly"][k][5])

config.RAW_DIR.mkdir(parents=True, exist_ok=True)
(config.RAW_DIR / "air_quality.json").write_text(json.dumps(air_json))
(config.RAW_DIR / "weather.json").write_text(json.dumps(weather_json))
print(f"Fake data written to {config.RAW_DIR} ({n} hours)")
