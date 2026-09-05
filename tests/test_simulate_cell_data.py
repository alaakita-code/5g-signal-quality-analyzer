"""測試 simulate_cell_data.generate() 的輸出結構與數值範圍是否合理。"""

from __future__ import annotations

import pandas as pd


def test_output_is_dataframe_with_expected_columns(small_df):
    expected_cols = {
        "timestamp",
        "cell_id",
        "site_lat",
        "site_lon",
        "sample_lat",
        "sample_lon",
        "distance_m",
        "rsrp_dbm",
        "rsrq_db",
        "sinr_db",
        "load_pct",
        "num_users",
    }
    assert isinstance(small_df, pd.DataFrame)
    assert expected_cols.issubset(set(small_df.columns))


def test_row_count_matches_expected(small_df, small_config):
    sim = small_config["simulation"]
    # 12 個時間點(00:00 ~ 00:55,每 5 分鐘一筆)x 3 小區 x 5 樣本
    expected_rows = 12 * sim["num_cells"] * sim["samples_per_cell"]
    assert len(small_df) == expected_rows


def test_cell_count_matches_config(small_df, small_config):
    assert small_df["cell_id"].nunique() == small_config["simulation"]["num_cells"]


def test_value_ranges_are_physically_plausible(small_df):
    assert small_df["rsrp_dbm"].between(-140, -40).all()
    assert small_df["rsrq_db"].between(-20, -3).all()
    assert small_df["sinr_db"].between(-5, 35).all()
    assert small_df["load_pct"].between(0, 100).all()
    assert (small_df["distance_m"] >= 0).all()
    assert (small_df["num_users"] >= 0).all()


def test_deterministic_with_fixed_seed(small_config):
    from data_generator.simulate_cell_data import generate

    df1 = generate(small_config)
    df2 = generate(small_config)
    pd.testing.assert_frame_equal(df1, df2)
