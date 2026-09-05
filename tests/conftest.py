"""
conftest.py
=============
pytest 共用 fixture:提供縮小版設定檔與模擬資料,讓測試執行快速
(不使用 default_config.yaml 的完整規模,避免測試花太久時間)。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from data_generator.simulate_cell_data import generate  # noqa: E402


@pytest.fixture()
def small_config() -> dict:
    """縮小版設定:3 個小區、每小區 5 個樣本、12 個時間點,測試跑起來秒級完成。"""
    return {
        "simulation": {
            "num_cells": 3,
            "samples_per_cell": 5,
            "start_time": "2026-09-01 00:00:00",
            "end_time": "2026-09-01 00:55:00",
            "time_step_minutes": 5,
            "center_lat": 25.0478,
            "center_lon": 121.5319,
            "radius_km": 5.0,
            "cell_coverage_radius_km": 0.8,
            "random_seed": 1,
            "tx_power_dbm": 43.0,
            "path_loss_exponent": 3.5,
            "shadowing_std_db": 6.0,
            "fading_std_db": 2.0,
            "peak_hours": [8, 9, 12, 18, 19, 20, 21],
            "peak_load_range": [60, 100],
            "offpeak_load_range": [5, 40],
        },
        "thresholds": {
            "rsrp_poor_dbm": -110,
            "rsrp_fair_dbm": -95,
            "rsrq_poor_db": -15,
            "sinr_poor_db": 3,
            "sinr_fair_db": 10,
            "load_high_pct": 80,
        },
        "hotspot": {
            "method": "dbscan",
            "dbscan_eps_km": 0.5,
            "dbscan_min_samples": 3,
        },
    }


@pytest.fixture()
def small_df(small_config):
    return generate(small_config)
