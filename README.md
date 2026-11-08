# Lahore Air Quality + Weather: ETL + EDA Pipeline

Programming for AI, Project 1. Group: 2025-AI-254, 2025-AI-255, 2025-AI-260.

## Run it

```bash
pip install -r requirements.txt      # once
python run_all.py                    # all 5 stages, needs internet
```

`python run_all.py --skip-extract` reuses the JSON already in `raw/` (no internet needed).
If one stage fails, run just that file, e.g. `python transform.py`.

To see the website on your own computer, double-click `web/index.html` after the run.
To see the EDA as a notebook, open `eda_notebook.ipynb` in VS Code and click **Run All**.

## The pipeline

```
Open-Meteo APIs -> raw/*.json -> pandas tables -> Pydantic check -> SQLite -> EDA charts -> website
   extract.py                     transform.py      schema.py       load.py    eda.py     export_web_data.py
```

| File | Job |
|---|---|
| `config.py` | All settings: location, dates, URLs, variables, WHO limits |
| `extract.py` | Calls the two APIs (with retries), saves the raw JSON unchanged |
| `transform.py` | JSON to DataFrames, merge on time, remove duplicates, fill short gaps (up to 3 h), drop rows missing PM/weather |
| `schema.py` | Pydantic rules per row (e.g. humidity 0-100, PM2.5 >= 0) |
| `load.py` | Writes valid rows to `lahore_air_weather.db`, table `air_weather` |
| `eda.py` | Reads the DB back, makes charts/tables in `outputs/` and `findings.md` |
| `eda_notebook.ipynb` | Same EDA, step by step |
| `export_web_data.py` | Summarizes the DB into `web/data.js` for the website |
| `make_report.py` | Builds report.docx from the results (python make_report.py) |
| `web/` | The website: `index.html`, `style.css`, `app.js`, `data.js` (plain HTML/CSS/JS) |
| `tests/make_sample_data.py` | FAKE data for testing only |

## Outputs

- `raw/`: untouched API responses
- `processed/`: `clean_air_weather.csv`, `rejected_rows.csv` (rows Pydantic refused, with the reason), `transform_report.json`
- `outputs/`: 8 charts, `summary_stats.csv`, `missing_values.csv`, `daily_pm_vs_who.csv`, `findings.md`
- `web/data.js`: the numbers the website draws

## Automatic refresh

The date range is rolling: `END_DATE` is today minus 6 days (the weather archive lags about 5 days) and `START_DATE` is 364 days before that, so every run covers the latest 365 days. To pin dates, set the environment variables, e.g. in PowerShell `$env:START_DATE = "2025-11-01"; $env:END_DATE = "2026-10-31"`.

`.github/workflows/refresh.yml` is a GitHub Actions job that runs once a day at 02:30 UTC (or on demand from the **Actions** tab with **Run workflow**). It installs the packages, runs `python run_all.py`, and commits only `web/data.js` and `outputs/findings.md` if they changed. That push makes Vercel redeploy the site. If the `VERCEL_DEPLOY_HOOK` repository secret is set, the job also calls that hook to force a redeploy.

This is a scheduled batch job, not real-time: the website shows data up to about 6 days ago and changes at most once a day. If any stage fails, nothing is committed and the site keeps the last good data. The failed run shows up in red on the Actions tab.

## Design choices

- **Why two APIs?** Air quality and weather are separate Open-Meteo services; they share timestamps, so they merge on `time`.
- **Same timezone in both calls** (Asia/Karachi), otherwise the hours would not line up.
- **Short gaps (<= 3 h) are interpolated, long gaps are not.** Estimating a few hours is safe; inventing a day is not.
- **Pydantic validates every row.** Bad rows are saved to `rejected_rows.csv`, not silently lost.
- **WHO limits** (2021 daily guideline): PM2.5 = 15, PM10 = 45 ug/m3. A day counts only if it has 18+ hourly readings.
- **Correlation is not causation.** The findings say "association".
- **The air quality data is modeled (CAMS), not measured by sensors.** This is stated as a limitation on the website.
