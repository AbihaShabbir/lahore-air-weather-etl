"""STAGE 5 - EDA: read the data back FROM THE DATABASE, then explore it.

Run `python eda.py` to produce every chart + table in outputs/.
Each fig_* function also works on its own inside the notebook.

What is covered (the same list as the project description):
  summary statistics, missing-value check, pollutant distributions,
  hourly / daily / monthly patterns, weather-vs-pollutant correlations,
  days above the WHO guideline, and written findings.
"""
import sqlite3
import sys

import matplotlib

if "ipykernel" not in sys.modules:      # plain script -> draw to files only
    matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from matplotlib.colors import LinearSegmentedColormap

import config

# ---- look: one accent colour, quiet grid, no clutter ---------------------
INK, MUTED, GRID = "#1f2937", "#6b7280", "#e5e7eb"
ACCENT, WARN = "#2563eb", "#c2410c"
LIGHT = "#93b4f5"
DIVERGING = LinearSegmentedColormap.from_list(
    "div", ["#2563eb", "#f3f4f6", "#c2410c"])   # blue - neutral - orange

sns.set_theme(style="whitegrid", rc={
    "figure.figsize": (8, 4.5), "font.size": 10, "text.color": INK,
    "axes.edgecolor": MUTED, "axes.labelcolor": INK, "axes.titlesize": 12,
    "axes.titleweight": "bold", "axes.titlelocation": "left",
    "axes.spines.top": False, "axes.spines.right": False,
    "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
    "xtick.color": MUTED, "ytick.color": MUTED,
})

UG = "µg/m³"
LABELS = {"pm2_5": "PM2.5", "pm10": "PM10", "nitrogen_dioxide": "NO2",
          "ozone": "O3", "carbon_monoxide": "CO", "sulphur_dioxide": "SO2",
          "temperature_2m": "Temperature", "relative_humidity_2m": "Humidity",
          "wind_speed_10m": "Wind speed", "surface_pressure": "Pressure",
          "precipitation": "Rain"}


def _finish(fig, name):
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(config.OUTPUT_DIR / name, dpi=150)
    if "ipykernel" not in sys.modules:
        plt.close(fig)
    return fig


def _month_ticks(ax, months, rotate=45):
    """Label a categorical x axis with 'Nov 25' style month names."""
    ax.set_xticks(range(len(months)))
    ax.set_xticklabels([pd.Period(m).strftime("%b %y") for m in months],
                       rotation=rotate, ha="right" if rotate else "center")
    ax.set_xlabel("")
    ax.grid(axis="x", visible=False)


# ---- data -----------------------------------------------------------------
def load_data() -> pd.DataFrame:
    """Read the table back from the database (this is the 'L -> EDA' link)."""
    if not config.DB_PATH.exists():
        raise FileNotFoundError(f"{config.DB_PATH.name} not found - run load.py first")
    conn = sqlite3.connect(config.DB_PATH)
    try:
        df = pd.read_sql_query(f"SELECT * FROM {config.TABLE}", conn,
                               parse_dates=["time"])
    finally:
        conn.close()
    df["date"] = df["time"].dt.date
    df["hour"] = df["time"].dt.hour
    df["month"] = df["time"].dt.to_period("M").astype(str)
    return df


def daily_table(df: pd.DataFrame) -> pd.DataFrame:
    """One row per day. Days with fewer than 18 hourly readings are ignored."""
    g = df.groupby("date")
    daily = g.agg(hours=("pm2_5", "size"), pm2_5_mean=("pm2_5", "mean"),
                  pm10_mean=("pm10", "mean")).reset_index()
    daily = daily[daily["hours"] >= 18].copy()
    daily["month"] = pd.to_datetime(daily["date"]).dt.to_period("M").astype(str)
    daily["over_who_pm25"] = daily["pm2_5_mean"] > config.WHO_PM25_DAILY
    daily["over_who_pm10"] = daily["pm10_mean"] > config.WHO_PM10_DAILY
    return daily


# ---- tables ---------------------------------------------------------------
def save_tables(df, daily):
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stats = df[config.VALUE_COLS].describe().T.round(2)
    stats.to_csv(config.OUTPUT_DIR / "summary_stats.csv")
    miss = df[config.VALUE_COLS].isna().sum().to_frame("missing")
    miss["percent"] = (miss["missing"] / len(df) * 100).round(2)
    miss.to_csv(config.OUTPUT_DIR / "missing_values.csv")
    daily.to_csv(config.OUTPUT_DIR / "daily_pm_vs_who.csv", index=False)
    return stats, miss


# ---- figures (seaborn on top of matplotlib) ---------------------------------
def fig_distribution(df):
    """01 - how are hourly PM2.5 values spread?"""
    fig, ax = plt.subplots()
    sns.histplot(df["pm2_5"], bins=50, color=ACCENT, edgecolor="white",
                 linewidth=0.5, ax=ax)
    ax.axvline(config.WHO_PM25_DAILY, color=WARN, ls="--", lw=1.5)
    ax.text(config.WHO_PM25_DAILY, 0.96, f"  WHO 24-h guideline: {config.WHO_PM25_DAILY}",
            transform=ax.get_xaxis_transform(), color=WARN, va="top")
    ax.set(title="Distribution of hourly PM2.5 in Lahore",
           xlabel=f"PM2.5 ({UG})", ylabel="Number of hours")
    return _finish(fig, "01_pm25_distribution.png")


def fig_pollutants(df):
    """02 - the distribution of every pollutant (x axis cut at the 99.5th percentile)."""
    fig, axes = plt.subplots(2, 3, figsize=(12, 6.5))
    for i, (ax, col) in enumerate(zip(axes.ravel(), config.AIR_VARS)):
        s = df[col].dropna()
        s = s[s <= s.quantile(0.995)]
        sns.histplot(s, bins=40, kde=s.nunique() > 5, color=ACCENT,
                     edgecolor="white", linewidth=0.4, ax=ax)
        ax.set(title=LABELS[col], xlabel=UG, ylabel="Hours" if i % 3 == 0 else "")
    fig.suptitle("Distribution of each pollutant (hourly values)", x=0.01,
                 ha="left", fontweight="bold")
    return _finish(fig, "02_pollutant_distributions.png")


def fig_hourly(df):
    """03 - hour-of-day pattern: line = mean, band = 95% confidence interval."""
    fig, ax = plt.subplots()
    sns.lineplot(data=df, x="hour", y="pm2_5", estimator="mean",
                 errorbar=("ci", 95), n_boot=200, seed=0, color=ACCENT,
                 linewidth=2, marker="o", markeredgecolor="white", ax=ax)
    ax.set(title="Average PM2.5 by hour of day (band = 95% confidence interval)",
           xlabel="Hour of day (Pakistan time)", ylabel=f"Mean PM2.5 ({UG})",
           xticks=range(0, 24, 3))
    return _finish(fig, "03_pm25_by_hour.png")


def fig_daily(daily):
    """04 - daily mean PM2.5 through the whole period, with the WHO limit."""
    d = daily.copy()
    d["date"] = pd.to_datetime(d["date"])
    d = d.sort_values("date")
    fig, ax = plt.subplots(figsize=(10, 4.5))
    sns.lineplot(data=d, x="date", y="pm2_5_mean", color=ACCENT, linewidth=1.2,
                 label="Daily mean", ax=ax)
    roll = d.set_index("date")["pm2_5_mean"].rolling(7, center=True, min_periods=4).mean()
    ax.plot(roll.index, roll.values, color=INK, lw=2.2, label="7-day average")
    ax.axhline(config.WHO_PM25_DAILY, color=WARN, ls="--", lw=1.5,
               label=f"WHO 24-h guideline ({config.WHO_PM25_DAILY})")
    ax.legend(loc="upper right", frameon=False)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
    ax.set(title="Daily average PM2.5", xlabel="", ylabel=f"PM2.5 ({UG})")
    return _finish(fig, "04_pm25_daily.png")


def fig_monthly(df):
    """05 - monthly distribution: box = middle 50% of hours, line = median."""
    months = sorted(df["month"].unique())
    fig, ax = plt.subplots()
    sns.boxplot(data=df, x="month", y="pm2_5", order=months, color=LIGHT,
                linecolor=INK, linewidth=1, showfliers=False, ax=ax)
    ax.axhline(config.WHO_PM25_DAILY, color=WARN, ls="--", lw=1.5,
               label=f"WHO 24-h guideline ({config.WHO_PM25_DAILY})")
    ax.legend(loc="upper right", frameon=False)
    ax.set(title="PM2.5 by month (outliers hidden)", ylabel=f"PM2.5 ({UG})")
    _month_ticks(ax, months)
    return _finish(fig, "05_pm25_monthly_boxplot.png")


def fig_corr(df):
    """06 - correlation of every pollutant with every weather variable."""
    rows, cols = config.AIR_VARS, config.WEATHER_VARS
    c = df[rows + cols].corr().loc[rows, cols]
    fig, ax = plt.subplots(figsize=(7.5, 5))
    sns.heatmap(c, annot=True, fmt=".2f", cmap=DIVERGING, vmin=-1, vmax=1,
                center=0, linewidths=2, linecolor="white", ax=ax,
                cbar_kws={"label": "Correlation (-1 to +1)", "shrink": 0.85})
    ax.set_xticklabels([LABELS[x] for x in cols], rotation=30, ha="right")
    ax.set_yticklabels([LABELS[x] for x in rows], rotation=0)
    ax.set(title="Correlation: pollutants vs weather", xlabel="", ylabel="")
    ax.grid(False)
    return _finish(fig, "06_correlation_heatmap.png")


def fig_scatter(df):
    """07 - PM2.5 against each weather variable (dark line = median per slice)."""
    pairs = [("temperature_2m", "Temperature (°C)"),
             ("relative_humidity_2m", "Humidity (%)"),
             ("wind_speed_10m", "Wind speed (km/h)"),
             ("surface_pressure", "Pressure (hPa)")]
    fig, axes = plt.subplots(2, 2, figsize=(10, 7.5), sharey=True)
    for ax, (col, label) in zip(axes.ravel(), pairs):
        sns.scatterplot(data=df, x=col, y="pm2_5", s=8, alpha=0.15,
                        color=ACCENT, linewidth=0, ax=ax)
        bins = pd.cut(df[col], 15)
        med = df.groupby(bins, observed=True).agg(x=(col, "mean"), y=("pm2_5", "median"))
        ax.plot(med["x"], med["y"], color=INK, lw=2.2)
        ax.set(xlabel=label, ylabel=f"PM2.5 ({UG})")
    fig.suptitle("PM2.5 vs weather (dark line = median per slice)",
                 x=0.01, ha="left", fontweight="bold")
    return _finish(fig, "07_pm25_vs_weather.png")


def fig_who(daily):
    """08 - how many days per month went above the WHO PM2.5 guideline."""
    g = (daily.groupby("month")
              .agg(over=("over_who_pm25", "sum"), days=("over_who_pm25", "size"))
              .reset_index())
    fig, ax = plt.subplots()
    sns.barplot(data=g, x="month", y="over", color=ACCENT, errorbar=None, ax=ax)
    for i, row in enumerate(g.itertuples()):
        ax.text(i, row.over, f"{row.over}/{row.days}", ha="center", va="bottom",
                color=MUTED, fontsize=8)
    ax.set(title=f"Days above the WHO PM2.5 guideline ({config.WHO_PM25_DAILY} {UG})",
           ylabel="Days (label = days over / days measured)")
    _month_ticks(ax, list(g["month"]))
    return _finish(fig, "08_days_over_who.png")


# ---- written findings (numbers computed from the data) ---------------------
def write_findings(df, daily):
    pm = df["pm2_5"]
    peak = df.loc[pm.idxmax()]
    month_mean = df.groupby("month")["pm2_5"].mean()
    hour_mean = df.groupby("hour")["pm2_5"].mean()
    corr = df[["pm2_5"] + config.WEATHER_VARS].corr()["pm2_5"].drop("pm2_5")
    strongest = corr.abs().idxmax()
    n_days, n_over = len(daily), int(daily["over_who_pm25"].sum())
    n_over10 = int(daily["over_who_pm10"].sum())

    lines = [
        "# EDA findings (auto-generated from the database)", "",
        f"- Period: {df['time'].min():%d %b %Y} to {df['time'].max():%d %b %Y}, "
        f"{len(df):,} hourly records.",
        f"- PM2.5: mean {pm.mean():.1f}, median {pm.median():.1f}, "
        f"max {pm.max():.1f} {UG} (on {peak['time']:%d %b %Y, %H:%M}).",
        f"- {n_over} of {n_days} measured days ({n_over / n_days:.0%}) had a daily mean "
        f"PM2.5 above the WHO guideline of {config.WHO_PM25_DAILY} {UG}; "
        f"{n_over10} days exceeded the PM10 guideline of {config.WHO_PM10_DAILY}.",
        f"- Worst month: {month_mean.idxmax()} (mean {month_mean.max():.1f}). "
        f"Cleanest month: {month_mean.idxmin()} (mean {month_mean.min():.1f}).",
        f"- Daily pattern: highest average at {hour_mean.idxmax()}:00 "
        f"({hour_mean.max():.1f}), lowest at {hour_mean.idxmin()}:00 ({hour_mean.min():.1f}).",
    ]
    winter = df["time"].dt.month.isin([11, 12, 1, 2])
    if winter.any() and (~winter).any():
        lines.append(f"- Winter (Nov-Feb) mean PM2.5 {pm[winter].mean():.1f} vs "
                     f"{pm[~winter].mean():.1f} in the other months.")
    lines.append("- Correlation of PM2.5 with weather: " + ", ".join(
        f"{LABELS[k]} {v:+.2f}" for k, v in corr.items()) +
        f". Strongest: {LABELS[strongest]}.")

    # strongest weather link for every pollutant (not only PM2.5)
    cm = df[config.AIR_VARS + config.WEATHER_VARS].corr().loc[config.AIR_VARS, config.WEATHER_VARS]
    parts = []
    for p in config.AIR_VARS:
        row = cm.loc[p].dropna()
        if not row.empty:
            w = row.abs().idxmax()
            parts.append(f"{LABELS[p]}: {LABELS[w]} ({row[w]:+.2f})")
    if parts:
        lines.append("- Strongest weather correlation per pollutant: " + "; ".join(parts) + ".")

    rain = df["precipitation"] > 0
    if rain.any() and (~rain).any():
        lines.append(f"- Mean PM2.5 in hours with rain: {pm[rain].mean():.1f} vs "
                     f"{pm[~rain].mean():.1f} in dry hours.")
    lines += ["", "Note: correlation shows association, not proof that one thing causes another."]
    text = "\n".join(lines)
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (config.OUTPUT_DIR / "findings.md").write_text(text, encoding="utf-8")
    return text


def main():
    df = load_data()
    if df.empty:
        raise ValueError("The database table is empty - nothing to analyse")
    daily = daily_table(df)
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # remove charts from older versions so outputs/ never holds stale pictures
    for old in config.OUTPUT_DIR.glob("[0-9][0-9]_*.png"):
        old.unlink()
    save_tables(df, daily)
    for fn, arg in [(fig_distribution, df), (fig_pollutants, df), (fig_hourly, df),
                    (fig_daily, daily), (fig_monthly, df), (fig_corr, df),
                    (fig_scatter, df), (fig_who, daily)]:
        fn(arg)
    print(write_findings(df, daily))
    print(f"\nCharts and tables saved in {config.OUTPUT_DIR}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"EDA FAILED: {e}")
        sys.exit(1)
