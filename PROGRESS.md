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

---

## Phase 3 — Automation & Polish (2026-07-03)

### What was built

1. **`data/live/` CSV snapshots** — the refresh command now exports `tsmc_revenue.csv` and `prices.csv` (and `korea_exports.csv` once ECOS key is set) to `data/live/` after every successful fetch. These files are committed to git so a fresh clone always has real data without needing to run a refresh.

2. **GitHub Actions cron** (`.github/workflows/refresh.yml`) — runs every Monday at 06:00 UTC. Fetches all sources, commits `data/live/*.csv` back to the repo. GitHub emails the repo owner automatically if the job fails. `ECOS_API_KEY` can be added as a repo secret to enable Korea data.

3. **`data/live/` fallback in `app.py`** — `_seed_data()` checks `data/live/` before `data/samples/`. Fresh clones load real data from the Actions snapshot instead of approximations.

4. **Stale-data banner for prices** (`_price_stale_banner`) — if the latest price close is more than 7 days old, the app shows a warning with the age and tells the user to run `python -m src`. TSMC and Korea don't get a stale flag (monthly data naturally lags 30+ days).

5. **"Last updated" captions** on every chart — TSMC and Korea show the latest month (`May 2026`); prices show the latest close date.

6. **Exit code cleanup in `src/__main__.py`** — Korea failure is now a "soft fail" (exits 0) since it's expected when ECOS_API_KEY isn't configured. TSMC or price failures exit 1 and alert via GitHub Actions.

7. **README.md** — public-facing documentation covering the investing thesis, quick start, architecture, and Korea data setup.

### What to review
1. **`.github/workflows/refresh.yml`** — read it top to bottom; it's 30 lines and shows the full automation flow. The `permissions: contents: write` line is what lets it push the data commit.
2. **`data/live/`** — these files are now in git. After the first Actions run on Monday, they'll contain real data. Until then they contain today's local refresh (TSMC + prices live; Korea samples).
3. **README "Screenshots" section** — placeholder. Take screenshots after opening the app in a browser and paste them in.

### Remaining for Phase 4
- Hyperscaler capex table (manual quarterly CSV)
- Memory spot price manual-entry form
- Streamlit Community Cloud deploy

---

## Phase 4 — Stretch Features (2026-07-03)

### What was built

**1. Hyperscaler Capex tab** (`data/capex.csv` + `_tab_capex()` in `app.py`)

A new "Capex" tab with two charts: a stacked bar showing each company's quarterly spend and a combined total line. The raw data table is under an expander. To update: add rows to `data/capex.csv` after each earnings season — the app reads it directly, no DB involved.

Companies: Amazon, Microsoft, Google, Meta. Data goes back to 2022-Q1 so the acceleration into AI capex is visible. Values are approximate from public earnings releases; treat as a directional guide, not exact accounting.

**2. Memory spot price form** (`store.memory_prices` + form in `_tab_memory()`)

Added a `memory_prices` table to SQLite and a Streamlit form at the bottom of the Memory tab. Enter DRAM (DDR5-4800 16GB module, USD) and NAND (128Gb TLC, ¢/GB) spot prices with an optional note. Once entries exist, a dual-axis line chart appears above the form. The form uses `st.rerun()` to refresh the chart immediately after saving.

Price series to track: DRAMeXchange weekly spot prices are a common source. Any web search for "DDR5 spot price" will surface current quotes.

**Persistence note:** on Streamlit Community Cloud, the SQLite DB is ephemeral (resets on restart). Manual spot prices entered through the form only persist in the local `data/semis.db`. For Cloud use, this is a limitation — a future improvement would export these to a committed CSV.

**3. Streamlit Community Cloud deploy**

- `.streamlit/config.toml`: dark theme, usage stats off
- README updated with Streamlit badge and deploy instructions
- Deploy URL: https://semis-dashboard-lkz9q9jt5gzq5szgkjqi6v.streamlit.app

The deploy flow relies on `data/live/*.csv` being committed — which they are after Phase 3. A fresh Streamlit Cloud instance loads data from those files without needing `python -m src` to run first.

### To deploy now
1. Go to [share.streamlit.io](https://share.streamlit.io)
2. New app → `oli-verr/semis-dashboard` → `main` → `app.py`
3. (Optional) add `ECOS_API_KEY` under Advanced secrets
4. Deploy
