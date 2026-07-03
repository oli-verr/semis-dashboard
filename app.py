"""
Streamlit entry point.
Run with: streamlit run app.py
"""
import os
import sys

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Ensure src/ is importable when the script is run from the project root
sys.path.insert(0, os.path.dirname(__file__))

import src.store as store
import src.transforms as transforms
from src.fetchers.market import fetch_prices

_SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "data", "samples")
_NOTES_PATH = os.path.join(os.path.dirname(__file__), "notes.md")

st.set_page_config(page_title="Semis Dashboard", layout="wide")


# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------

def _seed_sample(table: str, csv_name: str, upsert_fn) -> None:
    """Load a sample CSV into the DB if the table is empty."""
    if store.row_count(table) == 0:
        df = pd.read_csv(os.path.join(_SAMPLE_DIR, csv_name))
        upsert_fn(df)


@st.cache_data(ttl=3600, show_spinner=False)
def _load_prices() -> pd.DataFrame:
    """
    Return prices from the DB, fetching from yfinance first if the table is empty.
    TTL=3600 means Streamlit re-fetches at most once per hour.
    """
    if store.row_count("prices") == 0:
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


def _indexed_line(prices_df: pd.DataFrame, base_date: str, tickers: list[str] | None = None) -> go.Figure:
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
            st.warning("SAMPLE DATA — TSMC scraper not yet wired (Phase 2)", icon="⚠️")
        st.plotly_chart(
            _yoy_bar(tsmc, "revenue_ntd", "TSMC Monthly Revenue — YoY %"),
            use_container_width=True,
        )
        st.caption("Source: TSMC Investor Relations (pr.tsmc.com) | NT$ millions")

    with col2:
        korea = store.get_korea()
        if _is_sample(korea):
            st.warning("SAMPLE DATA — Korea exports fetcher not yet wired (Phase 2)", icon="⚠️")
        st.plotly_chart(
            _yoy_bar(korea, "exports_usd", "Korea Semiconductor Exports — YoY %"),
            use_container_width=True,
        )
        st.caption("Source: Korea Customs Service | USD billions")

    st.subheader("Indexed Ticker Performance")

    if prices.empty:
        st.error("No price data available — check your internet connection.")
        return

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
        fig = _indexed_line(prices_from_base, str(base_date))
        st.plotly_chart(fig, use_container_width=True)
    except ValueError as e:
        st.error(str(e))

    st.caption(f"Source: Yahoo Finance via yfinance | Last updated: {max_date}")


def _tab_memory(prices: pd.DataFrame) -> None:
    st.header("Memory — Korea Exports + Chip Stocks")

    korea = store.get_korea()
    if _is_sample(korea):
        st.warning("SAMPLE DATA — Korea exports fetcher not yet wired (Phase 2)", icon="⚠️")

    # Level + 3MMA
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

    # YoY
    st.plotly_chart(
        _yoy_bar(korea.assign(date=korea["date"].dt.strftime("%Y-%m-%d")), "exports_usd",
                 "Korea Semiconductor Exports — YoY %"),
        use_container_width=True,
    )

    st.caption("Source: Korea Customs Service (sample) | USD billions")

    # Memory chip stocks
    st.subheader("Memory Chip Stocks")
    MEMORY_TICKERS = ["MU", "000660.KS", "005930.KS"]

    if prices.empty:
        st.error("No price data available.")
        return

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
        fig = _indexed_line(mem_from_base, str(base_date), MEMORY_TICKERS)
        st.plotly_chart(fig, use_container_width=True)
    except ValueError as e:
        st.error(str(e))

    st.caption(f"Source: Yahoo Finance via yfinance | Last updated: {max_date}")


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
    _seed_sample("tsmc_revenue", "tsmc_revenue.csv", store.upsert_tsmc)
    _seed_sample("korea_exports", "korea_exports.csv", store.upsert_korea)

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
