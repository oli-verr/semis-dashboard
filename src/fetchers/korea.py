"""
Korea semiconductor exports via the Bank of Korea ECOS open API.
Register for a free API key at: https://ecos.bok.or.kr
Add to .env: ECOS_API_KEY=your_key

ECOS series used:
  Table code : 242Y001  (Merchandise Trade by Commodity)
  Item code  : 19       (Semiconductors — "반도체")
  Cycle      : MM       (monthly)

To verify the series codes in the ECOS web browser:
  https://ecos.bok.or.kr/#/SearchStat  → search "수출" or "export semiconductor"
If the item code is wrong, update _ITEM_CODE below and re-run `python -m src.refresh`.
"""
import os
import requests
import pandas as pd
from datetime import datetime

# Load .env without requiring python-dotenv as a dependency
def _load_env() -> None:
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())

_load_env()

_BASE = "https://ecos.bok.or.kr/api/StatisticSearch"
_TABLE_CODE = "242Y001"
_ITEM_CODE = "19"          # semiconductor item — verify in ECOS browser
_CYCLE = "MM"


def fetch_exports(lookback_years: int = 3) -> pd.DataFrame | None:
    """
    Pull monthly semiconductor export values (USD millions) from BOK ECOS.
    Returns a DataFrame or None if the API key is missing or the call fails.
    """
    api_key = os.getenv("ECOS_API_KEY", "")
    if not api_key:
        print("[korea] ECOS_API_KEY not set — add it to .env to enable live data")
        return None

    today = datetime.today()
    start = f"{today.year - lookback_years}01"
    end = f"{today.year}{today.month:02d}"

    url = (
        f"{_BASE}/{api_key}/json/en/1/500/"
        f"{_TABLE_CODE}/{_CYCLE}/{start}/{end}/{_ITEM_CODE}/"
    )

    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"[korea] ECOS API request failed: {e}")
        return None

    if "StatisticSearch" not in data:
        code = data.get("RESULT", {}).get("CODE", "?")
        msg = data.get("RESULT", {}).get("MESSAGE", str(data))
        print(f"[korea] ECOS API error {code}: {msg}")
        print("[korea] Verify _TABLE_CODE and _ITEM_CODE in src/fetchers/korea.py")
        return None

    rows = data["StatisticSearch"]["row"]
    records = []
    for row in rows:
        time_str = row.get("TIME", "")          # e.g. "202401"
        value_str = row.get("DATA_VALUE", "")
        if not time_str or not value_str:
            continue
        year, month = time_str[:4], time_str[4:6]
        try:
            # ECOS returns USD millions; convert to USD billions for display
            value_usd_bn = float(value_str) / 1000
        except ValueError:
            continue
        records.append({
            "date": f"{year}-{month}",
            "exports_usd": value_usd_bn,
            "source": "live",
        })

    if not records:
        return None

    df = pd.DataFrame(records).drop_duplicates("date").sort_values("date")
    return df
