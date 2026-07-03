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

---

## Phase 2 — Real Fetchers (2026-07-03)

### What was built
TSMC scraper is live. `python -m src` now refreshes all data sources. Korea is wired but blocked on API key registration.

### TSMC scraper (`src/fetchers/tsmc.py`)
Scrapes `https://investor.tsmc.com/english/monthly-revenue/{year}` per year. The page is server-rendered so plain requests + BeautifulSoup works. Fetches the last 3 calendar years by default (currently 2024, 2025, 2026). Parses the `basicTable` class, converts month abbreviations to YYYY-MM dates, skips future months (empty cells).

The DB now has 29 rows of live TSMC data from 2024-01 through 2026-05. The "SAMPLE DATA" banner will disappear in the app.

6 HTML fixture tests all pass (fixture saved in `tests/fixtures/tsmc_2024.html`).

### Korea exports (`src/fetchers/korea.py`)
Written to call the Bank of Korea ECOS API. Reads `ECOS_API_KEY` from `.env`. Returns None gracefully when key is absent — the app stays on sample data with a banner.

**Pending**: Verify the ECOS series code. The fetcher is configured with:
- Table: `242Y001` (Merchandise Trade by Commodity)
- Item: `19` (Semiconductors)

Until you register at ecos.bok.or.kr and add your key to `.env`, Korea data stays on sample. Once you have the key, run `python -m src` and check if data comes back. If the item code `19` is wrong (ECOS error code INFO-200 or similar), browse `https://ecos.bok.or.kr/#/SearchStat` for the correct semiconductor export series and update `_ITEM_CODE` in `src/fetchers/korea.py`.

### `python -m src` refresh command (`src/__main__.py`)
Runs all three fetchers in sequence, prints status, exits 1 if any source fails (useful for CI alerting in Phase 3). Currently outputs:
```
TSMC   ✓  29 rows
Korea  ✗  no key
Prices ✓  4477 rows
```

### Bug fixed in `market.py`
yfinance's `reset_index()` column name varies by version. Fixed by taking `reset.columns[0]` instead of hardcoding "Date".

### What to review
1. **TSMC banner gone** — Overview tab should now show real data without the warning.
2. **Korea banner stays** — will clear after adding `ECOS_API_KEY` to `.env` and re-running refresh.
3. **`src/__main__.py`** — tiny script; read it to understand the refresh flow before Phase 3 automation.

### Known ECOS series code uncertainty
The item code `19` for semiconductors within table `242Y001` is a best-effort guess — the ECOS sample API key does not have sufficient permissions to browse item lists. Needs verification with a real key.
