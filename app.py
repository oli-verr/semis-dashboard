"""
Streamlit entry point.
Run with: streamlit run app.py
"""
import os
import sys
from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.dirname(__file__))

import src.store as store
import src.transforms as transforms
from src.fetchers.market import fetch_prices

_LIVE_DIR = os.path.join(os.path.dirname(__file__), "data", "live")
_SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "data", "samples")
_NOTES_PATH = os.path.join(os.path.dirname(__file__), "notes.md")

# Market prices are stale if the latest close is more than this many days old.
# 7 days covers a week of missed refreshes without false-positives on weekends.
_PRICE_STALE_DAYS = 7

st.set_page_config(page_title="Semis Dashboard", layout="wide")


# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------

def _best_csv(csv_name: str) -> str:
    """Return path to data/live/{name} if it exists, else data/samples/{name}.
    GitHub Actions commits live/ after each weekly refresh; samples/ is the
    fallback for a fresh clone before any refresh has run."""
    live = os.path.join(_LIVE_DIR, csv_name)
    return live if os.path.exists(live) else os.path.join(_SAMPLE_DIR, csv_name)


def _seed_data(table: str, csv_name: str, upsert_fn) -> bool:
    """Seed the DB from the best available CSV if the table is empty.
    Returns True if seeded from live data, False if from samples."""
    if store.row_count(table) > 0:
        return None  # already populated
    path = _best_csv(csv_name)
    df = pd.read_csv(path)
    upsert_fn(df)
    return "live" in path


@st.cache_data(ttl=3600, show_spinner=False)
def _load_prices() -> pd.DataFrame:
    """Return prices from the DB, fetching from yfinance first if empty.
    TTL=3600 means at most one yfinance call per hour."""
    if store.row_count("prices") == 0:
        # Try the live CSV first (faster than yfinance on first load)
        live_csv = os.path.join(_LIVE_DIR, "prices.csv")
        if os.path.exists(live_csv):
            df = pd.read_csv(live_csv)
            store.upsert_prices(df)
        else:
            with st.spinner("Fetching live market data from Yahoo Finance…"):
                try:
                    fresh = fetch_prices()
                    store.upsert_prices(fresh)
                except Exception as e:
                    st.error(f"Could not fetch market data: {e}")
                    return pd.DataFrame()
    return store.get_prices()


def _is_sample(df: pd.DataFrame) -> bool:
    return "source" in df.columns and (df["source"] == "sample").all()


def _latest_date(df: pd.DataFrame, date_col: str = "date") -> date | None:
    if df.empty:
        return None
    return pd.to_datetime(df[date_col].max()).date()


def _price_stale_banner(prices: pd.DataFrame) -> None:
    """Warn if the latest price close is older than _PRICE_STALE_DAYS."""
    latest = _latest_date(prices)
    if latest is None:
        return
    age = (date.today() - latest).days
    # Subtract expected non-trading days (rough: 2 weekend days per 7)
    if age > _PRICE_STALE_DAYS:
        st.warning(
            f"Price data is {age} days old (last close: {latest}). "
            "Run `python -m src` to refresh.",
            icon="⚠️",
        )


# ---------------------------------------------------------------------------
# Chart builders
# ---------------------------------------------------------------------------

def _yoy_bar(df: pd.DataFrame, value_col: str, title: str) -> go.Figure:
    df = transforms.calc_yoy(df, value_col)
    df = df.dropna(subset=["yoy_pct"])
    fig = go.Figure()
    fig.add_bar(x=df["date"], y=df["yoy_pct"], name="YoY %")
    fig.update_layout(
        title=title,
        xaxis_title="Month",
        yaxis_title="YoY %",
        yaxis_ticksuffix="%",
        margin=dict(l=0, r=0, t=40, b=0),
        legend=dict(orientation="h"),
    )
    return fig


def _indexed_line(
    prices_df: pd.DataFrame,
    base_date: str,
    tickers: list[str] | None = None,
) -> go.Figure:
    if tickers:
        prices_df = prices_df[prices_df["ticker"].isin(tickers)]
    indexed = transforms.index_prices(prices_df, base_date)
    fig = go.Figure()
    for ticker in indexed.columns:
        fig.add_scatter(x=indexed.index, y=indexed[ticker], name=ticker, mode="lines")
    fig.add_hline(y=100, line_dash="dot", line_color="gray", opacity=0.5)
    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="Indexed (100 = start date)",
        hovermode="x unified",
        legend=dict(orientation="h"),
        margin=dict(l=0, r=0, t=0, b=0),
    )
    return fig


# ---------------------------------------------------------------------------
# Tab renderers
# ---------------------------------------------------------------------------

def _tab_overview(prices: pd.DataFrame) -> None:
    st.header("Overview — State of the Trade")

    col1, col2 = st.columns(2)

    with col1:
        tsmc = store.get_tsmc()
        if _is_sample(tsmc):
            st.warning("SAMPLE DATA — TSMC scraper not yet run. Run `python -m src`.", icon="⚠️")
        st.plotly_chart(
            _yoy_bar(tsmc, "revenue_ntd", "TSMC Monthly Revenue — YoY %"),
            use_container_width=True,
        )
        latest_tsmc = _latest_date(tsmc)
        st.caption(
            f"Source: TSMC Investor Relations (investor.tsmc.com) | NT$ millions"
            + (f" | Last data: {latest_tsmc.strftime('%b %Y')}" if latest_tsmc else "")
        )

    with col2:
        korea = store.get_korea()
        if _is_sample(korea):
            st.warning(
                "SAMPLE DATA — add ECOS_API_KEY to .env and run `python -m src`.", icon="⚠️"
            )
        st.plotly_chart(
            _yoy_bar(korea, "exports_usd", "Korea Semiconductor Exports — YoY %"),
            use_container_width=True,
        )
        latest_korea = _latest_date(korea)
        st.caption(
            f"Source: Bank of Korea ECOS / Korea Customs Service | USD billions"
            + (f" | Last data: {latest_korea.strftime('%b %Y')}" if latest_korea else "")
        )

    st.subheader("Indexed Ticker Performance")

    if prices.empty:
        st.error("No price data available — check your internet connection.")
        return

    _price_stale_banner(prices)

    min_date = pd.to_datetime(prices["date"].min()).date()
    max_date = pd.to_datetime(prices["date"].max()).date()
    default_start = max(min_date, (pd.Timestamp.today() - pd.DateOffset(years=1)).date())

    base_date = st.date_input(
        "Index to 100 on:",
        value=default_start,
        min_value=min_date,
        max_value=max_date,
        key="overview_base",
    )
    prices_from_base = prices[prices["date"] >= str(base_date)]

    try:
        st.plotly_chart(_indexed_line(prices_from_base, str(base_date)), use_container_width=True)
    except ValueError as e:
        st.error(str(e))

    st.caption(f"Source: Yahoo Finance via yfinance | Last close: {max_date}")


def _tab_memory(prices: pd.DataFrame) -> None:
    st.header("Memory — Korea Exports + Chip Stocks")

    korea = store.get_korea()
    if _is_sample(korea):
        st.warning(
            "SAMPLE DATA — add ECOS_API_KEY to .env and run `python -m src`.", icon="⚠️"
        )

    korea = korea.copy()
    korea["date"] = pd.to_datetime(korea["date"])
    korea = korea.sort_values("date")
    korea = transforms.calc_3mma(korea, "exports_usd")

    fig_level = go.Figure()
    fig_level.add_bar(x=korea["date"], y=korea["exports_usd"], name="Exports", opacity=0.55)
    fig_level.add_scatter(
        x=korea["date"], y=korea["exports_usd_3mma"],
        name="3-month MA", mode="lines", line=dict(width=3),
    )
    fig_level.update_layout(
        title="Korea Semiconductor Exports — Level (USD bn)",
        xaxis_title="Month", yaxis_title="USD billions",
        legend=dict(orientation="h"), margin=dict(l=0, r=0, t=40, b=0),
    )
    st.plotly_chart(fig_level, use_container_width=True)

    st.plotly_chart(
        _yoy_bar(
            korea.assign(date=korea["date"].dt.strftime("%Y-%m-%d")),
            "exports_usd",
            "Korea Semiconductor Exports — YoY %",
        ),
        use_container_width=True,
    )

    latest_korea = _latest_date(korea, "date")
    st.caption(
        "Source: Bank of Korea ECOS / Korea Customs Service | USD billions"
        + (f" | Last data: {latest_korea.strftime('%b %Y')}" if latest_korea else "")
    )

    st.subheader("Memory Chip Stocks")
    MEMORY_TICKERS = ["MU", "000660.KS", "005930.KS"]

    if prices.empty:
        st.error("No price data available.")
        return

    _price_stale_banner(prices)

    mem_prices = prices[prices["ticker"].isin(MEMORY_TICKERS)]
    if mem_prices.empty:
        st.warning("No memory ticker data found.")
        return

    min_date = pd.to_datetime(mem_prices["date"].min()).date()
    max_date = pd.to_datetime(mem_prices["date"].max()).date()
    default_start = max(min_date, (pd.Timestamp.today() - pd.DateOffset(years=1)).date())

    base_date = st.date_input(
        "Index to 100 on:",
        value=default_start,
        min_value=min_date,
        max_value=max_date,
        key="memory_base",
    )
    mem_from_base = mem_prices[mem_prices["date"] >= str(base_date)]

    try:
        st.plotly_chart(
            _indexed_line(mem_from_base, str(base_date), MEMORY_TICKERS),
            use_container_width=True,
        )
    except ValueError as e:
        st.error(str(e))

    st.caption(f"Source: Yahoo Finance via yfinance | Last close: {max_date}")


def _tab_notes() -> None:
    st.header("Notes")
    if not os.path.exists(_NOTES_PATH):
        st.info("Create notes.md at the project root to add research notes here.")
        return
    with open(_NOTES_PATH) as f:
        st.markdown(f.read())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    store.init_db()
    _seed_data("tsmc_revenue", "tsmc_revenue.csv", store.upsert_tsmc)
    _seed_data("korea_exports", "korea_exports.csv", store.upsert_korea)

    prices = _load_prices()

    st.title("AI / Semiconductor Trade Dashboard")
    tab_ov, tab_mem, tab_notes = st.tabs(["Overview", "Memory", "Notes"])

    with tab_ov:
        _tab_overview(prices)
    with tab_mem:
        _tab_memory(prices)
    with tab_notes:
        _tab_notes()


main()
