# Progress Log

## Phase 1 — Skeleton (2026-07-03)

### What was built
A working Streamlit dashboard with three tabs (Overview, Memory, Notes), backed by SQLite. Live market data loads from Yahoo Finance on first run; TSMC and Korea data show sample values with visible warning banners until Phase 2 wires up the real fetchers.

### File-by-file

| File | Purpose |
|------|---------|
| `src/store.py` | All SQLite interaction: schema creation, upserts, reads. Single `init_db()` called at app start. |
| `src/transforms.py` | Pure functions: `calc_yoy` (row-shift by 12, assumes no gaps), `calc_3mma` (rolling average), `index_prices` (rebase to 100 at chosen date). |
| `src/fetchers/market.py` | Downloads 9 tickers via yfinance, melts to long format, saves raw CSV to `data/raw/`. |
| `src/fetchers/tsmc.py` | Stub — returns `None`. Scraper goes here in Phase 2. |
| `src/fetchers/korea.py` | Stub — returns `None`. ECOS API client goes here in Phase 2. |
| `app.py` | Streamlit entry point. Seeds DB from sample CSVs if empty, caches price loads for 1 hour. |
| `data/samples/` | Approximate historical values (2023–2025) clearly marked `source=sample`. |
| `tests/test_transforms.py` | 10 unit tests covering YoY math, 3MMA, and price indexing. All pass. |

### Key decisions

**Why row-shift for YoY instead of date-based join?** The monthly data has no gaps (TSMC and Korea both publish every month), so `pct_change(12)` is correct and simpler. If gaps appear in Phase 2 real data, replace with a date-aware merge.

**Why SQLite instead of just reading CSVs?** Phase 2 will append live scraped data incrementally. A DB makes upserts trivial and keeps the app code simple (one `store.get_tsmc()` call regardless of data source).

**Why `@st.cache_data(ttl=3600)` on price loading?** Streamlit reruns the whole script on every user interaction. Without caching, yfinance would be called on every click. 1-hour TTL is a reasonable balance between freshness and performance.

**Why sample CSVs in `data/samples/` instead of hardcoded data in the app?** The sample CSVs let the app work on a fresh clone without a network call or API key. They're also easy to inspect and diff.

### What to review / understand
1. **`src/transforms.py`** — the three functions are the core logic. Read them top to bottom; they're short and have no side effects.
2. **`app.py`** — the `main()` function at the bottom is the entry point. It calls `store.init_db()`, seeds sample data, then hands off to three `_tab_*` renderers.
3. **Sample data disclaimer** — the TSMC NT$ figures and Korea USD export figures in `data/samples/` are approximate (drawn from public reports in my training data). They will be replaced by real scraped values in Phase 2. The "SAMPLE DATA" banners in the app make this visible.
4. **`calc_yoy` limitation** — assumes complete monthly data with no gaps. This is noted in the docstring. Phase 2 should verify and tighten if needed.

### Not done (Phase 2+)
- Real TSMC scraper (pr.tsmc.com HTML parsing)
- Real Korea exports via ECOS API (`ECOS_API_KEY` in `.env`)
- `python -m src.refresh` CLI command
- GitHub Actions cron
