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
            CREATE TABLE IF NOT EXISTS memory_prices (
                date         TEXT PRIMARY KEY,
                dram_ddr5    REAL,   -- DDR5-4800 16GB module spot, USD
                nand_tlc     REAL,   -- 128Gb TLC NAND, USD cents/GB
                notes        TEXT
            );
            CREATE TABLE IF NOT EXISTS gpu_spot_prices (
                fetch_date TEXT,
                gpu_id     TEXT,
                gpu_name   TEXT,
                mem_gb     INTEGER,
                spot_price REAL,    -- cheapest spot (community > secure)
                on_demand  REAL,    -- cheapest on-demand
                PRIMARY KEY (fetch_date, gpu_id)
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


def upsert_memory_price(date: str, dram: float | None, nand: float | None, notes: str = "") -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO memory_prices (date, dram_ddr5, nand_tlc, notes) VALUES (?, ?, ?, ?)",
            (date, dram, nand, notes),
        )


def upsert_gpu_prices(df: pd.DataFrame) -> None:
    with _conn() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO gpu_spot_prices "
            "(fetch_date, gpu_id, gpu_name, mem_gb, spot_price, on_demand) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            df[["fetch_date", "gpu_id", "gpu_name", "mem_gb", "spot_price", "on_demand"]].values.tolist(),
        )


def get_gpu_prices() -> pd.DataFrame:
    with _conn() as conn:
        return pd.read_sql("SELECT * FROM gpu_spot_prices ORDER BY fetch_date, gpu_name", conn)


def get_memory_prices() -> pd.DataFrame:
    with _conn() as conn:
        return pd.read_sql("SELECT * FROM memory_prices ORDER BY date", conn)


def row_count(table: str) -> int:
    with _conn() as conn:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
