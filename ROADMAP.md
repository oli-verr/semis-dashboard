# Roadmap

## Phase 1 — Skeleton ✅ (Session 1)
- Repo structure, venv, requirements
- `store.py`: SQLite schema and read/write helpers
- `market.py`: live yfinance fetcher for 9 tickers
- `transforms.py`: YoY, 3MMA, price indexing
- Streamlit app with Overview / Memory / Notes tabs
- Sample CSVs for TSMC and Korea (real fetchers in Phase 2)
- Tests for transforms
- Git initialized, first commit

## Phase 2 — Real Fetchers
- `tsmc.py`: scrape pr.tsmc.com monthly revenue releases; HTML fixture test
- `korea.py`: ECOS API (BOK) for semiconductor export series; needs ECOS_API_KEY in .env
- Wire both into SQLite; remove sample-data banners once live
- `python -m src.refresh` command to pull all sources

## Phase 3 — Automation & Polish
- GitHub Actions cron: weekly refresh, commit updated data
- README with screenshots (public portfolio artifact)
- Stale-data banners with last-updated timestamps
- Basic error alerting

## Phase 4 (Stretch)
- Hyperscaler capex table (manual quarterly CSV)
- Memory spot price manual-entry form
- Deploy on Streamlit Community Cloud
