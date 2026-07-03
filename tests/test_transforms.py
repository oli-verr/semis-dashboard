"""Unit tests for src/transforms.py — no network calls, no DB."""
import pytest
import pandas as pd
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.transforms import calc_yoy, calc_3mma, index_prices


def _monthly_df(n: int = 24, start_value: float = 100.0, step: float = 5.0) -> pd.DataFrame:
    dates = pd.date_range("2023-01-01", periods=n, freq="MS").strftime("%Y-%m-%d")
    return pd.DataFrame({"date": dates, "value": [start_value + i * step for i in range(n)]})


# --- calc_yoy ---

def test_calc_yoy_adds_column():
    result = calc_yoy(_monthly_df(24), "value")
    assert "yoy_pct" in result.columns


def test_calc_yoy_first_12_are_nan():
    result = calc_yoy(_monthly_df(24), "value")
    assert result.iloc[:12]["yoy_pct"].isna().all()


def test_calc_yoy_after_12_are_not_nan():
    result = calc_yoy(_monthly_df(24), "value")
    assert result.iloc[12:]["yoy_pct"].notna().all()


def test_calc_yoy_math():
    """First 12 months at 100, 13th month at 125 → 25% YoY."""
    df = pd.DataFrame({
        "date": pd.date_range("2023-01-01", periods=13, freq="MS").strftime("%Y-%m-%d"),
        "value": [100.0] * 12 + [125.0],
    })
    result = calc_yoy(df, "value")
    assert result.iloc[-1]["yoy_pct"] == pytest.approx(25.0, abs=0.01)


# --- calc_3mma ---

def test_calc_3mma_adds_column():
    result = calc_3mma(_monthly_df(12), "value")
    assert "value_3mma" in result.columns


def test_calc_3mma_first_two_nan():
    result = calc_3mma(_monthly_df(12), "value")
    assert pd.isna(result.iloc[0]["value_3mma"])
    assert pd.isna(result.iloc[1]["value_3mma"])


def test_calc_3mma_third_is_average():
    df = _monthly_df(12)
    result = calc_3mma(df, "value")
    expected = (df.iloc[0]["value"] + df.iloc[1]["value"] + df.iloc[2]["value"]) / 3
    assert result.iloc[2]["value_3mma"] == pytest.approx(expected, abs=0.001)


# --- index_prices ---

def _price_df():
    dates = pd.date_range("2024-01-02", periods=5, freq="B").strftime("%Y-%m-%d")
    return pd.DataFrame({
        "date": list(dates) * 2,
        "ticker": ["A"] * 5 + ["B"] * 5,
        "close": [100.0, 110.0, 120.0, 130.0, 140.0, 50.0, 55.0, 60.0, 65.0, 70.0],
    })


def test_index_prices_base_is_100():
    df = _price_df()
    base = df["date"].min()
    result = index_prices(df, base)
    assert result.loc[pd.Timestamp(base), "A"] == pytest.approx(100.0)
    assert result.loc[pd.Timestamp(base), "B"] == pytest.approx(100.0)


def test_index_prices_second_row():
    df = _price_df()
    base = df["date"].min()
    result = index_prices(df, base)
    # A: 110/100*100 = 110; B: 55/50*100 = 110
    assert result.iloc[1]["A"] == pytest.approx(110.0)
    assert result.iloc[1]["B"] == pytest.approx(110.0)


def test_index_prices_no_data_after_base_raises():
    df = _price_df()
    with pytest.raises(ValueError):
        index_prices(df, "2099-01-01")
