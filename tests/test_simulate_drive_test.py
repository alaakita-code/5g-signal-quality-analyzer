"""測試 simulate_drive_test.generate_drive_test() 與 count_handovers()。"""

from __future__ import annotations

import pandas as pd

from data_generator.simulate_drive_test import count_handovers, generate_drive_test


def _drive_config(small_config):
    import copy

    cfg = copy.deepcopy(small_config)
    cfg["drive_test"] = {"num_devices": 4, "speed_kmh_range": [3, 30], "time_step_minutes": 5}
    return cfg


def test_output_columns_and_device_count(small_config):
    cfg = _drive_config(small_config)
    df = generate_drive_test(cfg)

    expected_cols = {
        "timestamp", "cell_id", "site_lat", "site_lon", "sample_lat", "sample_lon",
        "distance_m", "rsrp_dbm", "rsrq_db", "sinr_db", "load_pct", "num_users", "device_id",
    }
    assert expected_cols.issubset(set(df.columns))
    assert df["device_id"].nunique() == cfg["drive_test"]["num_devices"]


def test_value_ranges_are_physically_plausible(small_config):
    cfg = _drive_config(small_config)
    df = generate_drive_test(cfg)

    assert df["rsrp_dbm"].between(-140, -40).all()
    assert df["rsrq_db"].between(-20, -3).all()
    assert df["sinr_db"].between(-5, 35).all()
    assert df["load_pct"].between(0, 100).all()
    assert (df["distance_m"] >= 0).all()


def test_cell_id_references_valid_generated_sites(small_config):
    cfg = _drive_config(small_config)
    df = generate_drive_test(cfg)
    expected_ids = {f"CELL_{i+1:03d}" for i in range(cfg["simulation"]["num_cells"])}
    assert set(df["cell_id"].unique()).issubset(expected_ids)


def test_deterministic_with_fixed_seed(small_config):
    cfg = _drive_config(small_config)
    df1 = generate_drive_test(cfg)
    df2 = generate_drive_test(cfg)
    pd.testing.assert_frame_equal(df1, df2)


def test_count_handovers_returns_nonnegative_counts(small_config):
    cfg = _drive_config(small_config)
    df = generate_drive_test(cfg)
    handovers = count_handovers(df)

    assert set(handovers.columns) == {"device_id", "handover_count"}
    assert len(handovers) == df["device_id"].nunique()
    assert (handovers["handover_count"] >= 0).all()


def test_device_movement_is_continuous_not_teleporting(small_config):
    """移動軌跡相鄰兩個時間點之間的距離,應該遠小於整個模擬區域的直徑,
    確認裝置是連續移動而不是每個時間點隨機瞬移到任意位置。
    """
    cfg = _drive_config(small_config)
    df = generate_drive_test(cfg)

    one_device = df[df["device_id"] == "DEVICE_001"].sort_values("timestamp").reset_index(drop=True)
    lat_diff = one_device["sample_lat"].diff().abs().dropna()
    lon_diff = one_device["sample_lon"].diff().abs().dropna()

    # 模擬區域半徑用度數概略表示,相鄰時間點的位移不應超過半徑的一半
    radius_deg = cfg["simulation"]["radius_km"] / 111.0
    assert (lat_diff < radius_deg * 0.5).all()
    assert (lon_diff < radius_deg * 0.5).all()
