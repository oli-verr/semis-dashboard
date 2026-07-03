"""SQLite read/write helpers. All tables are created here; no SQL lives in other modules."""
import os
import sqlite3
import pandas as pd

# data/ is gitignored (except data/samples/); DB is created on first run
_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "semis.db")


def _conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(os.path.abspath(_DB_PATH)), exist_ok=True)
    return sqlite3.connect(_DB_PATH)


def init_db() -> None:
    """Create tables if they don't exist. Safe to call on every startup."""
    with _conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS tsmc_revenue (
                date        TEXT PRIMARY KEY,
                revenue_ntd REAL,
                source      TEXT DEFAULT 'sample'
            );
            CREATE TABLE IF NOT EXISTS korea_exports (
                date        TEXT PRIMARY KEY,
                exports_usd REAL,
                source      TEXT DEFAULT 'sample'
            );
            CREATE TABLE IF NOT EXISTS prices (
                date   TEXT,
                ticker TEXT,
                close  REAL,
                PRIMARY KEY (date, ticker)
            );
        """)


def upsert_tsmc(df: pd.DataFrame) -> None:
    with _conn() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO tsmc_revenue (date, revenue_ntd, source) VALUES (?, ?, ?)",
            df[["date", "revenue_ntd", "source"]].values.tolist(),
        )


def upsert_korea(df: pd.DataFrame) -> None:
    with _conn() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO korea_exports (date, exports_usd, source) VALUES (?, ?, ?)",
            df[["date", "exports_usd", "source"]].values.tolist(),
        )


def upsert_prices(df: pd.DataFrame) -> None:
    """df must have columns: date (YYYY-MM-DD str), ticker, close."""
    with _conn() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO prices (date, ticker, close) VALUES (?, ?, ?)",
            df[["date", "ticker", "close"]].values.tolist(),
        )


def get_tsmc() -> pd.DataFrame:
    with _conn() as conn:
        return pd.read_sql("SELECT * FROM tsmc_revenue ORDER BY date", conn)


def get_korea() -> pd.DataFrame:
    with _conn() as conn:
        return pd.read_sql("SELECT * FROM korea_exports ORDER BY date", conn)


def get_prices() -> pd.DataFrame:
    with _conn() as conn:
        return pd.read_sql("SELECT * FROM prices ORDER BY date", conn)


def row_count(table: str) -> int:
    with _conn() as conn:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
