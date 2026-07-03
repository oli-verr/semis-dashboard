"""
Streamlit entry point.
Run with: streamlit run app.py
"""
import os
import sys
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.dirname(__file__))

import src.store as store
import src.transforms as transforms
from src.fetchers.market import fetch_prices

_LIVE_DIR = os.path.join(os.path.dirname(__file__), "data", "live")
_SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "data", "samples")
_CAPEX_CSV = os.path.join(os.path.dirname(__file__), "data", "capex.csv")
_NVIDIA_CSV = os.path.join(os.path.dirname(__file__), "data", "nvidia_segments.csv")
_NOTES_PATH = os.path.join(os.path.dirname(__file__), "notes.md")

# Tickers grouped by theme for the multiselect default
_DEFAULT_TICKERS = ["TSM", "NVDA", "MU", "AMD", "AVGO", "SOXX"]

_PRICE_STALE_DAYS = 7

st.set_page_config(page_title="Semis Dashboard", layout="wide")


# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------

def _best_csv(csv_name: str) -> str:
    """Prefer data/live/ (committed by GitHub Actions) over data/samples/."""
    live = os.path.join(_LIVE_DIR, csv_name)
    return live if os.path.exists(live) else os.path.join(_SAMPLE_DIR, csv_name)


def _seed_data(table: str, csv_name: str, upsert_fn) -> None:
    if store.row_count(table) > 0:
        return
    df = pd.read_csv(_best_csv(csv_name))
    upsert_fn(df)


@st.cache_data(ttl=3600, show_spinner=False)
def _load_prices() -> pd.DataFrame:
    """Return prices from DB; load from live CSV or yfinance if DB is empty."""
    if store.row_count("prices") == 0:
        live_csv = os.path.join(_LIVE_DIR, "prices.csv")
        if os.path.exists(live_csv):
            store.upsert_prices(pd.read_csv(live_csv))
        else:
            with st.spinner("Fetching live market data from Yahoo Finance…"):
                try:
                    store.upsert_prices(fetch_prices())
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
    latest = _latest_date(prices)
    if latest and (date.today() - latest).days > _PRICE_STALE_DAYS:
        st.warning(
            f"Price data is {(date.today() - latest).days} days old (last close: {latest}). "
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
        xaxis_title="Month", yaxis_title="YoY %", yaxis_ticksuffix="%",
        margin=dict(l=0, r=0, t=40, b=0), legend=dict(orientation="h"),
    )
    return fig


def _indexed_line(
    prices_df: pd.DataFrame, base_date: str, tickers: list[str] | None = None,
) -> go.Figure:
    if tickers:
        prices_df = prices_df[prices_df["ticker"].isin(tickers)]
    indexed = transforms.index_prices(prices_df, base_date)
    fig = go.Figure()
    for ticker in indexed.columns:
        fig.add_scatter(x=indexed.index, y=indexed[ticker], name=ticker, mode="lines")
    fig.add_hline(y=100, line_dash="dot", line_color="gray", opacity=0.5)
    fig.update_layout(
        xaxis_title="Date", yaxis_title="Indexed (100 = start date)",
        hovermode="x unified", legend=dict(orientation="h"),
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
            st.warning("SAMPLE DATA — run `python -m src` to load live data.", icon="⚠️")
        st.plotly_chart(_yoy_bar(tsmc, "revenue_ntd", "TSMC Monthly Revenue — YoY %"),
                        use_container_width=True, key="ov_tsmc_yoy")
        latest = _latest_date(tsmc)
        st.caption(
            "Source: TSMC Investor Relations (investor.tsmc.com) | NT$ millions"
            + (f" | Last data: {latest.strftime('%b %Y')}" if latest else "")
        )

    with col2:
        korea = store.get_korea()
        if _is_sample(korea):
            st.warning("SAMPLE DATA — add ECOS_API_KEY and run `python -m src`.", icon="⚠️")
        st.plotly_chart(_yoy_bar(korea, "exports_usd", "Korea Semiconductor Exports — YoY %"),
                        use_container_width=True, key="ov_korea_yoy")
        latest = _latest_date(korea)
        st.caption(
            "Source: Bank of Korea ECOS / Korea Customs Service | USD billions"
            + (f" | Last data: {latest.strftime('%b %Y')}" if latest else "")
        )

    st.subheader("Indexed Ticker Performance")

    if prices.empty:
        st.error("No price data available — check your internet connection.")
        return

    _price_stale_banner(prices)

    all_tickers = sorted(prices["ticker"].unique().tolist())
    selected = st.multiselect(
        "Tickers", options=all_tickers,
        default=[t for t in _DEFAULT_TICKERS if t in all_tickers],
        key="ov_tickers",
    )

    min_date = pd.to_datetime(prices["date"].min()).date()
    max_date = pd.to_datetime(prices["date"].max()).date()
    default_start = max(min_date, (pd.Timestamp.today() - pd.DateOffset(years=1)).date())

    base_date = st.date_input(
        "Index to 100 on:", value=default_start,
        min_value=min_date, max_value=max_date, key="overview_base",
    )
    if selected:
        try:
            st.plotly_chart(
                _indexed_line(prices[prices["date"] >= str(base_date)], str(base_date), selected),
                use_container_width=True, key="ov_indexed",
            )
        except ValueError as e:
            st.error(str(e))

    st.caption(f"Source: Yahoo Finance via yfinance | Last close: {max_date}")


def _tab_memory(prices: pd.DataFrame) -> None:
    st.header("Memory — Korea Exports + Chip Stocks")

    korea = store.get_korea()
    if _is_sample(korea):
        st.warning("SAMPLE DATA — add ECOS_API_KEY and run `python -m src`.", icon="⚠️")

    korea = korea.copy()
    korea["date"] = pd.to_datetime(korea["date"])
    korea = korea.sort_values("date")
    korea = transforms.calc_3mma(korea, "exports_usd")

    fig_level = go.Figure()
    fig_level.add_bar(x=korea["date"], y=korea["exports_usd"], name="Exports", opacity=0.55)
    fig_level.add_scatter(x=korea["date"], y=korea["exports_usd_3mma"],
                          name="3-month MA", mode="lines", line=dict(width=3))
    fig_level.update_layout(
        title="Korea Semiconductor Exports — Level (USD bn)",
        xaxis_title="Month", yaxis_title="USD billions",
        legend=dict(orientation="h"), margin=dict(l=0, r=0, t=40, b=0),
    )
    st.plotly_chart(fig_level, use_container_width=True, key="mem_korea_level")

    st.plotly_chart(
        _yoy_bar(korea.assign(date=korea["date"].dt.strftime("%Y-%m-%d")),
                 "exports_usd", "Korea Semiconductor Exports — YoY %"),
        use_container_width=True, key="mem_korea_yoy",
    )

    latest = _latest_date(korea, "date")
    st.caption(
        "Source: Bank of Korea ECOS / Korea Customs Service | USD billions"
        + (f" | Last data: {latest.strftime('%b %Y')}" if latest else "")
    )

    # --- Memory chip stocks ---
    st.subheader("Memory Chip Stocks")
    MEMORY_TICKERS = ["MU", "000660.KS", "005930.KS"]

    if not prices.empty:
        _price_stale_banner(prices)
        mem = prices[prices["ticker"].isin(MEMORY_TICKERS)]
        if not mem.empty:
            min_d = pd.to_datetime(mem["date"].min()).date()
            max_d = pd.to_datetime(mem["date"].max()).date()
            default = max(min_d, (pd.Timestamp.today() - pd.DateOffset(years=1)).date())
            base = st.date_input("Index to 100 on:", value=default,
                                 min_value=min_d, max_value=max_d, key="memory_base")
            try:
                st.plotly_chart(
                    _indexed_line(mem[mem["date"] >= str(base)], str(base), MEMORY_TICKERS),
                    use_container_width=True, key="mem_stocks",
                )
            except ValueError as e:
                st.error(str(e))
            st.caption(f"Source: Yahoo Finance via yfinance | Last close: {max_d}")

    # --- Memory spot price form ---
    st.subheader("Memory Spot Prices")
    mem_prices = store.get_memory_prices()

    if not mem_prices.empty:
        fig_spot = go.Figure()
        mem_prices["date"] = pd.to_datetime(mem_prices["date"])
        if mem_prices["dram_ddr5"].notna().any():
            fig_spot.add_scatter(x=mem_prices["date"], y=mem_prices["dram_ddr5"],
                                 name="DRAM DDR5-4800 16GB (USD)", mode="lines+markers")
        if mem_prices["nand_tlc"].notna().any():
            fig_spot.add_scatter(x=mem_prices["date"], y=mem_prices["nand_tlc"],
                                 name="NAND TLC 128Gb (¢/GB)", mode="lines+markers",
                                 yaxis="y2")
        fig_spot.update_layout(
            title="Memory Spot Prices (manual entry)",
            xaxis_title="Date",
            yaxis=dict(title="DRAM (USD)"),
            yaxis2=dict(title="NAND (¢/GB)", overlaying="y", side="right"),
            legend=dict(orientation="h"), margin=dict(l=0, r=0, t=40, b=0),
            hovermode="x unified",
        )
        st.plotly_chart(fig_spot, use_container_width=True, key="mem_spot")
        st.caption("Source: manual entry | DRAM = DDR5-4800 16GB module | NAND = 128Gb TLC spot")

    with st.expander("Add memory spot price entry"):
        with st.form("mem_price_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                entry_date = st.date_input("Date", value=date.today())
            with col2:
                dram = st.number_input("DRAM DDR5-4800 16GB (USD)", min_value=0.0,
                                       step=0.5, value=None, placeholder="e.g. 85.0")
            with col3:
                nand = st.number_input("NAND TLC 128Gb (¢/GB)", min_value=0.0,
                                       step=0.1, value=None, placeholder="e.g. 3.5")
            notes = st.text_input("Notes", placeholder="e.g. from DRAMeXchange wk27")
            if st.form_submit_button("Save"):
                store.upsert_memory_price(str(entry_date), dram, nand, notes)
                st.success(f"Saved entry for {entry_date}.")
                st.rerun()


def _tab_capex() -> None:
    st.header("Hyperscaler Capex")

    if not os.path.exists(_CAPEX_CSV):
        st.error(f"Missing {_CAPEX_CSV} — add it manually (see PROGRESS.md).")
        return

    # Skip comment lines in the CSV
    df = pd.read_csv(_CAPEX_CSV, comment="#")
    df["quarter"] = df["quarter"].str.strip()

    companies = ["Amazon", "Microsoft", "Google", "Meta"]
    colors = {"Amazon": "#FF9900", "Microsoft": "#00A4EF", "Google": "#4285F4", "Meta": "#0866FF"}

    # --- Stacked bar chart ---
    fig = go.Figure()
    for company in companies:
        sub = df[df["company"] == company].sort_values("quarter")
        fig.add_bar(x=sub["quarter"], y=sub["capex_bn_usd"],
                    name=company, marker_color=colors.get(company))
    fig.update_layout(
        barmode="stack",
        title="Hyperscaler Quarterly Capex (USD bn)",
        xaxis_title="Quarter", yaxis_title="USD billions",
        legend=dict(orientation="h"), margin=dict(l=0, r=0, t=40, b=0),
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True, key="cap_stacked")

    # --- Total per quarter line ---
    totals = df.groupby("quarter")["capex_bn_usd"].sum().reset_index()
    totals = totals.sort_values("quarter")
    fig2 = go.Figure()
    fig2.add_scatter(x=totals["quarter"], y=totals["capex_bn_usd"],
                     mode="lines+markers", name="Combined Total", line=dict(width=3))
    fig2.update_layout(
        title="Combined Hyperscaler Capex — Total",
        xaxis_title="Quarter", yaxis_title="USD billions",
        margin=dict(l=0, r=0, t=40, b=0),
    )
    st.plotly_chart(fig2, use_container_width=True, key="cap_total")

    st.caption(
        "Sources: Amazon/Microsoft/Google/Meta quarterly earnings releases | "
        "Approximate — edit `data/capex.csv` each quarter to keep current."
    )

    with st.expander("Raw data table"):
        pivot = df.pivot(index="quarter", columns="company", values="capex_bn_usd")
        pivot["Total"] = pivot.sum(axis=1)
        st.dataframe(pivot.sort_index(ascending=False).style.format("{:.1f}"),
                     use_container_width=True)


def _tab_gpu() -> None:
    st.header("GPU Market")

    # --- Spot price snapshot ---
    st.subheader("Cloud GPU Spot Prices (RunPod)")
    gpu_df = store.get_gpu_prices()

    if gpu_df.empty:
        st.info("No GPU price data yet — run `python -m src` to fetch from RunPod.")
    else:
        latest_date = gpu_df["fetch_date"].max()
        current = (
            gpu_df[gpu_df["fetch_date"] == latest_date]
            .dropna(subset=["spot_price"])
            .sort_values("spot_price", ascending=True)
        )

        fig_bar = go.Figure()
        fig_bar.add_bar(
            x=current["spot_price"], y=current["gpu_name"],
            orientation="h",
            text=current["spot_price"].map(lambda p: f"${p:.2f}/hr"),
            textposition="outside",
            marker_color="#00D4FF",
        )
        fig_bar.update_layout(
            title=f"GPU Spot Price Snapshot — {latest_date}",
            xaxis_title="USD / hr", yaxis_title="",
            margin=dict(l=0, r=80, t=40, b=0),
            height=380,
        )
        st.plotly_chart(fig_bar, use_container_width=True, key="gpu_snapshot")

        # Bloomberg-style price history — always shown; accumulates week by week via cron
        st.subheader("GPU Spot Price History")
        dates = sorted(gpu_df["fetch_date"].unique())

        gpus_with_spot = (
            gpu_df.dropna(subset=["spot_price"])
            .groupby("gpu_id")["gpu_name"]
            .first()
            .reset_index()
        )
        _HIST_DEFAULTS = [
            "NVIDIA H100 80GB HBM3", "NVIDIA H200",
            "NVIDIA A100-SXM4-80GB", "NVIDIA GeForce RTX 4090",
        ]
        default_sel = [g for g in _HIST_DEFAULTS if g in gpus_with_spot["gpu_id"].values]
        name_map = gpus_with_spot.set_index("gpu_id")["gpu_name"].to_dict()

        selected_ids = st.multiselect(
            "GPUs to chart",
            options=gpus_with_spot["gpu_id"].tolist(),
            format_func=lambda gid: name_map.get(gid, gid),
            default=default_sel or gpus_with_spot["gpu_id"].tolist()[:3],
            key="gpu_hist_select",
        )

        fig_hist = go.Figure()
        for gpu_id in selected_ids:
            rows = (
                gpu_df[gpu_df["gpu_id"] == gpu_id]
                .sort_values("fetch_date")
                .dropna(subset=["spot_price"])
            )
            if not rows.empty:
                fig_hist.add_scatter(
                    x=rows["fetch_date"], y=rows["spot_price"],
                    mode="lines+markers" if len(rows) > 1 else "markers",
                    name=rows["gpu_name"].iloc[0], line=dict(width=2),
                )
        fig_hist.update_layout(
            xaxis_title="Date", yaxis_title="USD / hr",
            hovermode="x unified", legend=dict(orientation="h"),
            margin=dict(l=0, r=0, t=0, b=0),
        )
        st.plotly_chart(fig_hist, use_container_width=True, key="gpu_h100_hist")
        if len(dates) == 1:
            st.caption(
                f"One data point so far ({dates[0]}) — "
                "trend lines fill in week by week via the refresh cron."
            )

        st.caption(
            f"Source: RunPod public GraphQL API (api.runpod.io/graphql) | "
            f"Spot = cheapest available (community > secure). "
            f"Refreshed weekly via `python -m src`. Last fetch: {latest_date}"
        )

        with st.expander("All GPU prices table"):
            display = current[["gpu_name", "mem_gb", "spot_price", "on_demand"]].copy()
            display.columns = ["GPU", "VRAM (GB)", "Spot ($/hr)", "On-demand ($/hr)"]
            st.dataframe(display.set_index("GPU").style.format("{:.2f}"),
                         use_container_width=True)

    st.divider()

    # --- NVIDIA segment revenue ---
    st.subheader("NVIDIA Revenue by Segment")

    if not os.path.exists(_NVIDIA_CSV):
        st.error(f"Missing {_NVIDIA_CSV}")
        return

    nv = pd.read_csv(_NVIDIA_CSV, comment="#")
    segments = ["Data Center", "Gaming", "Pro Visualization", "Automotive"]
    seg_colors = {
        "Data Center": "#76B900",
        "Gaming": "#00D4FF",
        "Pro Visualization": "#FF6B35",
        "Automotive": "#FFD700",
    }

    fig_nv = go.Figure()
    for seg in segments:
        sub = nv[nv["segment"] == seg].sort_values("quarter")
        fig_nv.add_bar(
            x=sub["quarter"], y=sub["revenue_bn_usd"],
            name=seg, marker_color=seg_colors.get(seg),
        )
    fig_nv.update_layout(
        barmode="stack",
        title="NVIDIA Quarterly Revenue by Segment (USD bn)",
        xaxis_title="Quarter", yaxis_title="USD billions",
        legend=dict(orientation="h"), margin=dict(l=0, r=0, t=40, b=0),
        hovermode="x unified",
    )
    st.plotly_chart(fig_nv, use_container_width=True, key="nv_segments")

    # Data Center as % of total — shows the AI concentration story
    totals = nv.groupby("quarter")["revenue_bn_usd"].sum().rename("total")
    dc = nv[nv["segment"] == "Data Center"].set_index("quarter")["revenue_bn_usd"]
    pct = (dc / totals * 100).reset_index()
    pct.columns = ["quarter", "dc_pct"]
    pct = pct.sort_values("quarter")

    fig_pct = go.Figure()
    fig_pct.add_scatter(
        x=pct["quarter"], y=pct["dc_pct"],
        mode="lines+markers", name="Data Center % of revenue",
        line=dict(width=2, color="#76B900"),
    )
    fig_pct.update_layout(
        title="Data Center as % of NVIDIA Total Revenue",
        xaxis_title="Quarter", yaxis_title="%", yaxis_ticksuffix="%",
        margin=dict(l=0, r=0, t=40, b=0),
    )
    st.plotly_chart(fig_pct, use_container_width=True, key="nv_dc_pct")

    st.caption(
        "Source: NVIDIA quarterly earnings releases (investor.nvidia.com) | "
        "Approximate — NVDA fiscal year ends Jan; mapped to calendar quarters. "
        "Update `data/nvidia_segments.csv` each quarter."
    )


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

    # Seed GPU prices from the committed live snapshot (no sample fallback needed)
    live_gpu = os.path.join(_LIVE_DIR, "gpu_spot_prices.csv")
    if store.row_count("gpu_spot_prices") == 0 and os.path.exists(live_gpu):
        store.upsert_gpu_prices(pd.read_csv(live_gpu))

    prices = _load_prices()

    st.title("AI / Semiconductor Trade Dashboard")
    tab_ov, tab_mem, tab_cap, tab_gpu, tab_notes = st.tabs(
        ["Overview", "Memory", "Capex", "GPU", "Notes"]
    )

    with tab_ov:
        _tab_overview(prices)
    with tab_mem:
        _tab_memory(prices)
    with tab_cap:
        _tab_capex()
    with tab_gpu:
        _tab_gpu()
    with tab_notes:
        _tab_notes()


main()
