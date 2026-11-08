"""STAGE 4 - LOAD: put the validated data into a SQLite database.

Uses SQLAlchemy if it is installed, otherwise Python's built-in sqlite3.
Both write the same database file with the same table.
"""
import sys

import pandas as pd

import config


def get_connection():
    """Return (connection_or_engine, name_of_library_used)."""
    try:
        from sqlalchemy import create_engine
        return create_engine(f"sqlite:///{config.DB_PATH}"), "SQLAlchemy"
    except ImportError:
        import sqlite3
        return sqlite3.connect(config.DB_PATH), "sqlite3"


def main():
    df = pd.read_csv(config.PROCESSED_DIR / "clean_air_weather.csv",
                     parse_dates=["time"])
    # store time as plain text so any database/tool can read it
    df["time"] = df["time"].dt.strftime("%Y-%m-%d %H:%M:%S")

    conn, lib = get_connection()
    try:
        df.to_sql(config.TABLE, conn, if_exists="replace", index=False)
        n = pd.read_sql_query(f"SELECT COUNT(*) AS n FROM {config.TABLE}", conn)["n"][0]
    finally:
        # engine -> dispose(), sqlite3 connection -> close()
        (conn.dispose if lib == "SQLAlchemy" else conn.close)()

    print(f"Loaded {n} rows into table '{config.TABLE}' in {config.DB_PATH.name} (using {lib})")
    if n != len(df):
        raise RuntimeError(f"Row count mismatch: wrote {len(df)}, database has {n}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"LOAD FAILED: {e}")
        sys.exit(1)
