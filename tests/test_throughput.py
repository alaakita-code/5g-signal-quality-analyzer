"""測試 analysis.throughput 的吞吐量估算邏輯。"""

from __future__ import annotations

import pandas as pd

from analysis.throughput import (
    add_throughput_column,
    antenna_sensitivity,
    bandwidth_sensitivity,
    estimate_throughput_mbps,
)


def test_estimate_throughput_increases_with_sinr():
    low = estimate_throughput_mbps(0, 20, 2)
    high = estimate_throughput_mbps(20, 20, 2)
    assert high > low


def test_estimate_throughput_increases_with_bandwidth():
    narrow = estimate_throughput_mbps(10, 10, 2)
    wide = estimate_throughput_mbps(10, 40, 2)
    assert wide > narrow
    # 頻寬加倍,吞吐量應該也接近等比例增加(公式本身是線性關係)
    assert abs(wide / narrow - 4) < 0.01


def test_estimate_throughput_increases_with_antennas():
    single = estimate_throughput_mbps(10, 20, 1)
    quad = estimate_throughput_mbps(10, 20, 4)
    assert quad > single
    assert abs(quad / single - 4) < 0.01


def test_estimate_throughput_accepts_series(small_df):
    result = estimate_throughput_mbps(small_df["sinr_db"], 20, 2)
    assert isinstance(result, pd.Series)
    assert len(result) == len(small_df)
    assert (result >= 0).all()


def test_add_throughput_column(small_df):
    out = add_throughput_column(small_df, bandwidth_mhz=20, num_antennas=2)
    assert "throughput_mbps" in out.columns
    assert len(out) == len(small_df)
    assert (out["throughput_mbps"] >= 0).all()
    # 原始欄位不應被覆蓋或遺失
    assert "sinr_db" in out.columns


def test_bandwidth_sensitivity_returns_monotonic_increasing():
    result = bandwidth_sensitivity(avg_sinr_db=10, num_antennas=2)
    assert list(result["throughput_mbps"]) == sorted(result["throughput_mbps"])


def test_antenna_sensitivity_returns_monotonic_increasing():
    result = antenna_sensitivity(avg_sinr_db=10, bandwidth_mhz=20)
    assert list(result["throughput_mbps"]) == sorted(result["throughput_mbps"])
