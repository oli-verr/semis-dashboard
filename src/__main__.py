"""
CLI entry point: python -m src.refresh (or python -m src)

Pulls all live data sources and updates SQLite. Designed to be run manually
or triggered by a cron job (Phase 3 will wire this into GitHub Actions).
"""
import sys
import src.store as store
from src.fetchers.tsmc import fetch_revenue
from src.fetchers.korea import fetch_exports
from src.fetchers.market import fetch_prices


def refresh() -> None:
    store.init_db()
    ok, fail = [], []

    # --- TSMC ---
    print("Fetching TSMC monthly revenue...")
    tsmc_df = fetch_revenue()
    if tsmc_df is not None and not tsmc_df.empty:
        store.upsert_tsmc(tsmc_df)
        print(f"  ✓ {len(tsmc_df)} TSMC rows upserted")
        ok.append("TSMC")
    else:
        print("  ✗ TSMC fetch failed — keeping existing data")
        fail.append("TSMC")

    # --- Korea exports ---
    print("Fetching Korea semiconductor exports...")
    korea_df = fetch_exports()
    if korea_df is not None and not korea_df.empty:
        store.upsert_korea(korea_df)
        print(f"  ✓ {len(korea_df)} Korea rows upserted")
        ok.append("Korea")
    else:
        print("  ✗ Korea fetch failed — keeping existing data")
        fail.append("Korea")

    # --- Market prices ---
    print("Fetching market prices...")
    prices_df = fetch_prices()
    if prices_df is not None and not prices_df.empty:
        store.upsert_prices(prices_df)
        print(f"  ✓ {len(prices_df)} price rows upserted")
        ok.append("Prices")
    else:
        print("  ✗ Price fetch failed — keeping existing data")
        fail.append("Prices")

    print(f"\nDone. OK: {ok or 'none'} | Failed: {fail or 'none'}")
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    refresh()
