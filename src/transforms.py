"""Pure data transformations: YoY, 3-month moving average, price indexing."""
import pandas as pd


def calc_yoy(df: pd.DataFrame, value_col: str, date_col: str = "date") -> pd.DataFrame:
    """
    Add a yoy_pct column by shifting 12 rows.
    Assumes monthly data with no gaps — if there are gaps, results will be wrong.
    Phase 2 can tighten this with a date-based join if needed.
    """
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.sort_values(date_col).reset_index(drop=True)
    df["yoy_pct"] = df[value_col].pct_change(periods=12) * 100
    return df


def calc_3mma(df: pd.DataFrame, value_col: str) -> pd.DataFrame:
    """Add a 3-month centered trailing moving average column."""
    df = df.copy()
    df[f"{value_col}_3mma"] = df[value_col].rolling(3).mean()
    return df


def index_prices(prices_df: pd.DataFrame, base_date: str) -> pd.DataFrame:
    """
    Rebase each ticker to 100 at base_date.

    prices_df: long-format DataFrame with columns date (str), ticker, close.
    base_date: YYYY-MM-DD string. If no data on that exact date, uses the next
               available date (handles weekends / holidays).
    Returns a wide DataFrame indexed by datetime with one column per ticker.
    """
    pivoted = prices_df.pivot(index="date", columns="ticker", values="close")
    pivoted.index = pd.to_datetime(pivoted.index)
    pivoted = pivoted.sort_index()

    base_dt = pd.Timestamp(base_date)
    candidates = pivoted.index[pivoted.index >= base_dt]
    if candidates.empty:
        raise ValueError(f"No price data on or after {base_date}")
    actual_base = candidates[0]

    base_values = pivoted.loc[actual_base]
    # Division propagates NaN for tickers missing on base date — Plotly skips those gaps
    return pivoted.div(base_values) * 100
