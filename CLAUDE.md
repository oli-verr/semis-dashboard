# CLAUDE.md — Semis Data Dashboard

## What this project is
A personal dashboard tracking the AI/semiconductor trade through high-frequency public data. Owner: Oliver Ryan — product strategist and investor, competent-but-not-expert coder building this partly to learn. This is both a real investing tool and a public portfolio artifact (will be shared on GitHub and referenced in job applications).

## Working style — important
- Owner wants to UNDERSTAND this codebase, not just have it work. Prefer clear, boring, well-structured code over clever code. Add brief comments explaining *why*, not what.
- After each significant change, write a short summary in PROGRESS.md: what was built, key decisions, anything Oliver should read to understand it.
- Keep the architecture simple. No frameworks beyond what's listed. No premature abstraction.
- Never commit secrets. API keys live in .env (gitignored); provide .env.example.
- If a data source fails or is paywalled, degrade gracefully (cached/sample data + a visible "stale data" banner), log the issue in PROGRESS.md, and move on. Do not silently fabricate data.

## Stack (fixed — do not substitute)
- Python 3.11+, managed with a venv
- Data fetching: requests + beautifulsoup4 (scraping), yfinance (market data)
- Storage: SQLite via sqlite3 stdlib (single file: data/semis.db). Raw pulls also saved as CSV in data/raw/ for auditability.
- Dashboard: Streamlit + Plotly
- Scheduling (Phase 3): GitHub Actions cron
- Tests: pytest, minimal but real (fetch parsers tested against saved HTML fixtures)

## Repo structure
```
semis-dashboard/
  app.py                  # Streamlit entry point
  src/
    fetchers/
      tsmc.py             # TSMC monthly revenue
      korea.py            # Korea semiconductor exports
      market.py           # Tickers via yfinance
    store.py              # SQLite read/write helpers
    transforms.py         # YoY calcs, 3MMA, indexing
  data/                   # gitignored except samples
    samples/              # small sample CSVs so app runs on first clone
  tests/
  PROGRESS.md
  ROADMAP.md              # this plan, updated as phases complete
  .env.example
```

## Data sources (v1)
1. **TSMC monthly revenue** — published monthly on TSMC's investor relations site (pr.tsmc.com, English news listing, "Monthly Revenue" releases). Scrape the listing, parse NT$ revenue + YoY. This is the single best monthly proxy for leading-edge demand.
2. **Korea semiconductor exports** — Korea publishes trade data including semiconductor exports (monthly full data; 10-day preliminary reads). Primary route: Korea Customs Service / MOTIE monthly releases; if scraping is brittle, use the Bank of Korea ECOS open API (free key, owner will register at ecos.bok.or.kr) for the semiconductor export series. Best high-frequency proxy for memory pricing/volume.
3. **Market data via yfinance** — daily closes for: TSM, NVDA, MU, AMD, AVGO, ALAB, SOXX (index proxy), 000660.KS (SK Hynix), 005930.KS (Samsung). Compute indexed performance from a selectable start date.

## Dashboard views (v1)
- **Overview tab**: TSMC revenue YoY chart, Korea semi exports YoY chart, indexed ticker performance — the three-panel "state of the trade" view.
- **Memory tab**: Korea exports detail (level + YoY + 3-month moving average), MU/SK Hynix/Samsung price overlay.
- **Notes tab**: renders a local notes.md — owner's running commentary (this feeds his research memos).
- Every chart: clearly labeled source + last-updated timestamp. If showing sample/stale data, show a banner.

## Phases (work one phase per session; update ROADMAP.md as you go)
- **Phase 1 — Skeleton (first session):** repo structure, venv/requirements, store.py, market.py fetcher working end-to-end, minimal Streamlit app showing the indexed ticker chart from live yfinance data. Sample CSVs for the other two sources so all tabs render. Git initialized, first commit, PROGRESS.md written.
- **Phase 2 — Real fetchers:** TSMC scraper with HTML fixture test; Korea exports via ECOS API (read key from .env) or scraper; wire both into SQLite and the charts; add a `python -m src.refresh` command that updates everything.
- **Phase 3 — Automation & polish:** GitHub Actions cron (weekly refresh, commit updated data), README with screenshots written for a public audience (recruiters will see this), stale-data banners, basic error alerts.
- **Phase 4 (stretch):** hyperscaler capex table (manual quarterly CSV is fine), memory spot price manual-entry form, deploy on Streamlit Community Cloud.

## Definition of done for any session
Code runs (`streamlit run app.py` works from a fresh venv), tests pass, PROGRESS.md updated in plain English, changes committed with a clear message.
