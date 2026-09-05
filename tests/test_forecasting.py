"""測試 analysis.forecasting 的線性迴歸預測與趨勢判斷邏輯。"""

from __future__ import annotations

import pandas as pd
import pytest

from analysis.forecasting import forecast_series, trend_direction


def _make_series(values):
    timestamps = pd.date_range("2026-09-01 00:00:00", periods=len(values), freq="5min")
    return pd.DataFrame({"timestamp": timestamps, "value": values})


def test_forecast_series_returns_history_plus_forecast():
    df = _make_series([10, 12, 14, 16, 18])
    result = forecast_series(df, "value", periods=3, time_step_minutes=5)

    assert len(result) == len(df) + 3
    assert result["is_forecast"].sum() == 3
    assert (~result["is_forecast"]).sum() == len(df)


def test_forecast_series_extrapolates_upward_trend():
    """資料明顯是線性上升(每步 +2),預測值應該延續這個趨勢往上。"""
    df = _make_series([10, 12, 14, 16, 18])
    result = forecast_series(df, "value", periods=2, time_step_minutes=5)
    forecast_rows = result[result["is_forecast"]]

    assert forecast_rows["value"].iloc[0] > 18
    assert forecast_rows["value"].iloc[1] > forecast_rows["value"].iloc[0]


def test_forecast_series_raises_on_insufficient_data():
    df = _make_series([10])
    with pytest.raises(ValueError):
        forecast_series(df, "value")


def test_forecast_series_timestamps_are_sequential():
    df = _make_series([10, 20, 30])
    result = forecast_series(df, "value", periods=4, time_step_minutes=5)
    forecast_rows = result[result["is_forecast"]].reset_index(drop=True)

    diffs = forecast_rows["timestamp"].diff().dropna()
    assert (diffs == pd.Timedelta(minutes=5)).all()


def test_trend_direction_detects_upward():
    df = _make_series([10, 20, 30, 40, 50])
    assert trend_direction(df, "value") == "上升"


def test_trend_direction_detects_downward():
    df = _make_series([50, 40, 30, 20, 10])
    assert trend_direction(df, "value") == "下降"


def test_trend_direction_detects_flat():
    df = _make_series([40, 50, 45, 50, 40])
    assert trend_direction(df, "value") == "大致持平"


def test_trend_direction_insufficient_data_message():
    df = _make_series([30])
    result = trend_direction(df, "value")
    assert "資料點數太少" in result
