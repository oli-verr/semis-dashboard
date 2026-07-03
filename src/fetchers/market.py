"""Fetch daily closes for semiconductor/AI tickers via yfinance."""
import os
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

TICKERS = ["TSM", "NVDA", "MU", "AMD", "AVGO", "ALAB", "SOXX", "000660.KS", "005930.KS"]

_RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw")


def fetch_prices(start_date: str | None = None) -> pd.DataFrame:
    """
    Download adjusted daily closes for all TICKERS from start_date.
    Defaults to 2 years back so indexed charts have enough history.
    Returns long-format DataFrame: date (YYYY-MM-DD str), ticker, close.
    Also saves a raw CSV to data/raw/ for auditability.
    """
    if start_date is None:
        start_date = (datetime.today() - timedelta(days=730)).strftime("%Y-%m-%d")

    raw = yf.download(TICKERS, start=start_date, auto_adjust=True, progress=False)

    # yfinance returns MultiIndex columns when >1 ticker; 'Close' is the price level
    closes: pd.DataFrame = raw["Close"]

    # Long format: one row per (date, ticker)
    closes.index = closes.index.strftime("%Y-%m-%d")
    long = (
        closes.reset_index()
        .rename(columns={"Date": "date", "Datetime": "date", "Price": "date"})
        .melt(id_vars=closes.index.name or "Date", var_name="ticker", value_name="close")
    )
    # Normalise the date column name regardless of yfinance version quirks
    long.columns = ["date", "ticker", "close"]
    long = long.dropna(subset=["close"]).reset_index(drop=True)

    os.makedirs(_RAW_DIR, exist_ok=True)
    ts = datetime.today().strftime("%Y%m%d")
    long.to_csv(os.path.join(_RAW_DIR, f"prices_{ts}.csv"), index=False)

    return long
