"""Test TSMC parser against the saved HTML fixture — no network calls."""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.fetchers.tsmc import _parse_page

_FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "tsmc_2024.html")


@pytest.fixture
def html_2024():
    with open(_FIXTURE, encoding="utf-8") as f:
        return f.read()


def test_parse_returns_rows(html_2024):
    rows = _parse_page(html_2024, 2024)
    assert len(rows) > 0


def test_parse_correct_month_count(html_2024):
    """2024 is a complete year, so all 12 months should be present."""
    rows = _parse_page(html_2024, 2024)
    assert len(rows) == 12


def test_parse_date_format(html_2024):
    rows = _parse_page(html_2024, 2024)
    for row in rows:
        assert row["date"].startswith("2024-"), f"Bad date: {row['date']}"
        month = row["date"].split("-")[1]
        assert month.isdigit() and 1 <= int(month) <= 12


def test_parse_revenue_positive(html_2024):
    rows = _parse_page(html_2024, 2024)
    for row in rows:
        assert row["revenue_ntd"] > 0, f"Non-positive revenue on {row['date']}"


def test_parse_source_is_live(html_2024):
    rows = _parse_page(html_2024, 2024)
    for row in rows:
        assert row["source"] == "live"


def test_parse_january_2024(html_2024):
    """Jan 2024 TSMC revenue: ~215,785 NT$ mn (from the live page fixture)."""
    rows = _parse_page(html_2024, 2024)
    jan = next(r for r in rows if r["date"] == "2024-01")
    assert jan["revenue_ntd"] > 200_000, f"Jan 2024 revenue looks low: {jan['revenue_ntd']}"
