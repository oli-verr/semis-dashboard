"""
CLI entry point: python -m src

Pulls all live data sources, updates SQLite, then exports CSVs to data/live/
so GitHub Actions can commit a human-readable snapshot of the latest data.

Exit codes:
  0 — TSMC and market prices both succeeded (Korea is optional; needs ECOS key)
  1 — TSMC or market prices failed (needs investigation)
"""
import os
import sys

import pandas as pd

import src.store as store
from src.fetchers.korea import fetch_exports
from src.fetchers.market import fetch_prices
from src.fetchers.runpod import fetch_gpu_prices
from src.fetchers.tsmc import fetch_revenue

_LIVE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "live")


def _export_csv(df: pd.DataFrame, filename: str) -> None:
    """Write df to data/live/{filename} so GitHub Actions can commit it."""
    os.makedirs(_LIVE_DIR, exist_ok=True)
    df.to_csv(os.path.join(_LIVE_DIR, filename), index=False)


def _export_gpu_csv(new_df: pd.DataFrame) -> None:
    """Append today's GPU rows to the accumulated history CSV.
    Unlike other sources (which are point-in-time snapshots), GPU spot prices
    are a time series we build ourselves — each weekly run appends a new row
    so the trend chart fills in over time."""
    path = os.path.join(_LIVE_DIR, "gpu_spot_prices.csv")
    os.makedirs(_LIVE_DIR, exist_ok=True)
    if os.path.exists(path):
        existing = pd.read_csv(path)
        combined = (
            pd.concat([existing, new_df])
            .drop_duplicates(subset=["fetch_date", "gpu_id"], keep="last")
            .sort_values(["fetch_date", "gpu_name"])
            .reset_index(drop=True)
        )
    else:
        combined = new_df
    combined.to_csv(path, index=False)
    print(f"  ✓ {len(combined)} total rows  →  data/live/gpu_spot_prices.csv")


def refresh() -> None:
    store.init_db()
    hard_fail = []   # TSMC + prices — exit 1 if either fails
    soft_fail = []   # Korea — optional, needs ECOS key

    # --- TSMC ---
    print("Fetching TSMC monthly revenue...")
    tsmc_df = fetch_revenue()
    if tsmc_df is not None and not tsmc_df.empty:
        store.upsert_tsmc(tsmc_df)
        _export_csv(tsmc_df, "tsmc_revenue.csv")
        print(f"  ✓ {len(tsmc_df)} rows  →  data/live/tsmc_revenue.csv")
    else:
        print("  ✗ TSMC fetch failed — keeping existing data")
        hard_fail.append("TSMC")

    # --- Korea exports ---
    print("Fetching Korea semiconductor exports...")
    korea_df = fetch_exports()
    if korea_df is not None and not korea_df.empty:
        store.upsert_korea(korea_df)
        _export_csv(korea_df, "korea_exports.csv")
        print(f"  ✓ {len(korea_df)} rows  →  data/live/korea_exports.csv")
    else:
        print("  ✗ Korea fetch failed (set ECOS_API_KEY in .env to enable)")
        soft_fail.append("Korea")

    # --- Market prices ---
    print("Fetching market prices...")
    prices_df = fetch_prices()
    if prices_df is not None and not prices_df.empty:
        store.upsert_prices(prices_df)
        _export_csv(prices_df, "prices.csv")
        print(f"  ✓ {len(prices_df)} rows  →  data/live/prices.csv")
    else:
        print("  ✗ Price fetch failed")
        hard_fail.append("Prices")

    # --- GPU spot prices ---
    print("Fetching GPU spot prices from RunPod...")
    gpu_df = fetch_gpu_prices()
    if gpu_df is not None and not gpu_df.empty:
        store.upsert_gpu_prices(gpu_df)
        _export_gpu_csv(gpu_df)   # append-only — builds history week by week
    else:
        print("  ✗ GPU price fetch failed")
        soft_fail.append("GPU")

    ok = [s for s in ["TSMC", "Korea", "Prices", "GPU"]
          if s not in hard_fail and s not in soft_fail]
    print(f"\nDone.  OK: {ok or '—'}  |  Soft fail: {soft_fail or '—'}  |  Hard fail: {hard_fail or '—'}")

    if hard_fail:
        sys.exit(1)


if __name__ == "__main__":
    refresh()
