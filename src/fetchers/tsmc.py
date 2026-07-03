"""
Scrape TSMC monthly revenue from investor.tsmc.com.
URL pattern: https://investor.tsmc.com/english/monthly-revenue/{year}
The page renders server-side, so plain requests + BeautifulSoup is enough.
"""
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime

_BASE_URL = "https://investor.tsmc.com/english/monthly-revenue"
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; semis-dashboard/1.0)"}

# Map month abbreviations as TSMC prints them → zero-padded month number
_MONTH_MAP = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "may": "05", "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "sept": "09", "oct": "10", "nov": "11", "dec": "12",
}


def _parse_page(html: str, year: int) -> list[dict]:
    """
    Parse one year's revenue page. Returns list of dicts with keys:
    date (YYYY-MM), revenue_ntd (float, NT$ millions), source.
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", class_=lambda c: c and "basicTable" in c)
    if not table:
        return []

    rows = []
    for tr in table.find_all("tr"):
        cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        if len(cells) < 2:
            continue
        month_raw = cells[0].lower().rstrip(".")
        if month_raw not in _MONTH_MAP:
            continue  # header, total, or empty row
        revenue_str = cells[1].replace(",", "").strip()
        if not revenue_str:
            continue  # future month not yet published
        rows.append({
            "date": f"{year}-{_MONTH_MAP[month_raw]}",
            "revenue_ntd": float(revenue_str),
            "source": "live",
        })
    return rows


def fetch_revenue(years: int = 3) -> pd.DataFrame | None:
    """
    Fetch TSMC monthly revenue for the last `years` calendar years plus the
    current year. Returns a DataFrame or None on failure.
    """
    current_year = datetime.today().year
    target_years = list(range(current_year - years + 1, current_year + 1))

    all_rows = []
    for year in target_years:
        try:
            r = requests.get(f"{_BASE_URL}/{year}", headers=_HEADERS, timeout=15)
            r.raise_for_status()
            all_rows.extend(_parse_page(r.text, year))
        except Exception as e:
            # Log but keep going — partial data is better than none
            print(f"[tsmc] failed to fetch {year}: {e}")

    if not all_rows:
        return None

    df = pd.DataFrame(all_rows).drop_duplicates("date").sort_values("date")
    return df
