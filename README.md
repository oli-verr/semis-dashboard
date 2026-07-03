# AI / Semiconductor Trade Dashboard

A personal dashboard for tracking the AI/semiconductor investment thesis through high-frequency public data. Built as both a real investing tool and a portfolio artifact.

The core insight: leading-edge semiconductor demand is highly concentrated — TSMC alone makes ~90% of the world's most advanced chips. Three data series tell most of the story: TSMC's monthly revenue (demand for AI/HPC compute), Korea's semiconductor exports (memory pricing and volume), and relative price performance of the major players.

---

## What it tracks

| Series | Why it matters | Update cadence |
|--------|---------------|----------------|
| TSMC monthly revenue (NT$) | Best single proxy for leading-edge demand — NVDA, AMD, Apple, all run through TSMC | Monthly (~10th of following month) |
| Korea semiconductor exports (USD) | Best proxy for memory cycle — DRAM and NAND pricing signal shows up here first | Monthly |
| 9 equity tickers | TSM, NVDA, MU, AMD, AVGO, ALAB, SOXX, SK Hynix (KRX), Samsung (KRX) | Daily |

---

## Screenshots

*(Add screenshots here after first run — `streamlit run app.py`, then screenshot each tab)*

**Overview tab** — TSMC YoY, Korea exports YoY, indexed equity performance

**Memory tab** — Korea export level + 3-month MA, memory chip stock comparison

**Notes tab** — personal research log rendered from `notes.md`

---

## Quick start

```bash
git clone https://github.com/your-username/semis-dashboard
cd semis-dashboard

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Populate the database with live data
python -m src

# Launch the dashboard
streamlit run app.py
```

On first run without `python -m src`, the app loads from `data/live/` (last GitHub Actions snapshot) for TSMC and prices, and falls back to `data/samples/` for Korea (until you add an ECOS key). Sample data banners indicate which sources are approximate.

---

## Korea data setup (optional)

The Korea semiconductor export series requires a free API key from the Bank of Korea:

1. Register at [ecos.bok.or.kr](https://ecos.bok.or.kr) (free, instant)
2. Copy your key into `.env`:
   ```
   ECOS_API_KEY=your_key_here
   ```
3. Run `python -m src` — Korea data loads and the sample banner disappears

For GitHub Actions automation, add `ECOS_API_KEY` as a repository secret (Settings → Secrets → Actions).

---

## Refreshing data manually

```bash
python -m src
```

This fetches TSMC revenue, Korea exports (if key set), and all market prices — then updates SQLite and exports CSVs to `data/live/` for audit.

---

## Automation (GitHub Actions)

A weekly cron workflow (`.github/workflows/refresh.yml`) runs every Monday at 06:00 UTC:
- Fetches all sources
- Commits updated `data/live/*.csv` back to the repo
- Job fails (GitHub sends an email notification) if TSMC or prices fail

No server required. The `data/live/` CSVs in the repo mean a fresh clone always has real data.

---

## Architecture

```
app.py                  Streamlit entry point; tabs → chart builders → store
src/
  store.py              All SQLite I/O. One DB file (data/semis.db, gitignored).
  transforms.py         Pure functions: calc_yoy, calc_3mma, index_prices
  fetchers/
    tsmc.py             Scrapes investor.tsmc.com/english/monthly-revenue/{year}
    korea.py            BOK ECOS API — semiconductor export series
    market.py           yfinance download for 9 tickers
  __main__.py           python -m src refresh command
data/
  live/                 Last refresh snapshot (committed; updated by Actions)
  samples/              Approximate historical data for offline/first-clone use
  semis.db              SQLite database (gitignored — rebuilt from live/ on refresh)
tests/
  test_transforms.py    Unit tests for all transform functions
  test_tsmc.py          Parser tests against saved HTML fixture
  fixtures/             Saved HTML pages for offline testing
```

**Stack:** Python 3.11+, Streamlit, Plotly, yfinance, requests + BeautifulSoup, SQLite, GitHub Actions

---

## Adding your own notes

Edit `notes.md` at the repo root. Markdown renders in the Notes tab. This feeds research memos — the intent is to keep analysis alongside the data.

---

## Roadmap

- **Phase 4 (stretch):** Hyperscaler capex table, memory spot price form, Streamlit Community Cloud deploy
