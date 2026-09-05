"""測試 analysis.metrics 的統計計算邏輯。"""

from __future__ import annotations

from analysis import metrics


def test_overall_summary_keys(small_df):
    summary = metrics.overall_summary(small_df)
    expected_keys = {
        "avg_rsrp_dbm",
        "avg_rsrq_db",
        "avg_sinr_db",
        "avg_load_pct",
        "total_samples",
        "total_cells",
        "time_range",
    }
    assert expected_keys.issubset(summary.keys())
    assert summary["total_samples"] == len(small_df)
    assert summary["total_cells"] == small_df["cell_id"].nunique()


def test_per_cell_summary_row_count(small_df):
    per_cell = metrics.per_cell_summary(small_df)
    assert len(per_cell) == small_df["cell_id"].nunique()
    assert "avg_rsrp_dbm" in per_cell.columns
    assert "sample_count" in per_cell.columns
    assert per_cell["sample_count"].sum() == len(small_df)


def test_per_cell_summary_keeps_site_coordinates_distinct(small_df):
    """回歸測試:per_cell_summary 曾經把 site_lat/site_lon 一起四捨五入到
    小數點後 1 位(約 11 公里精度),導致同一份模擬區域(半徑通常只有幾公里)
    裡好幾個實際位置不同的小區,座標被壓成完全一樣,在地圖上疊成同一個點。
    這裡驗證小區座標至少維持小數點後 3 位以上精度,不會被過度四捨五入。
    """
    per_cell = metrics.per_cell_summary(small_df)
    # 檢查小數位數:轉成字串看小數點後有幾位數字
    for col in ["site_lat", "site_lon"]:
        decimals = per_cell[col].apply(
            lambda v: len(str(v).split(".")[1]) if "." in str(v) else 0
        )
        assert (decimals >= 3).any(), f"{col} 精度看起來被過度四捨五入"


def test_dropped_call_proxy_range(small_df):
    proxy = metrics.dropped_call_proxy(small_df, sinr_threshold_db=0.0)
    assert "dropped_call_proxy_pct" in proxy.columns
    assert proxy["dropped_call_proxy_pct"].between(0, 100).all()
    assert len(proxy) == small_df["cell_id"].nunique()


def test_classify_quality_adds_column_with_valid_categories(small_df):
    thresholds = {
        "rsrp_poor_dbm": -110, "rsrp_fair_dbm": -95,
        "sinr_poor_db": 3, "sinr_fair_db": 10, "load_high_pct": 80,
    }
    per_cell = metrics.per_cell_summary(small_df)
    classified = metrics.classify_quality(per_cell, thresholds)
    assert "quality_status" in classified.columns
    assert set(classified["quality_status"].unique()).issubset({"良好", "普通", "需關注"})


def test_classify_quality_flags_high_load_as_needs_attention():
    import pandas as pd

    thresholds = {
        "rsrp_poor_dbm": -110, "rsrp_fair_dbm": -95,
        "sinr_poor_db": 3, "sinr_fair_db": 10, "load_high_pct": 80,
    }
    per_cell = pd.DataFrame(
        [{"cell_id": "X", "avg_rsrp_dbm": -80, "avg_sinr_db": 20, "avg_load_pct": 95}]
    )
    classified = metrics.classify_quality(per_cell, thresholds)
    assert classified.loc[0, "quality_status"] == "需關注"


def test_classify_quality_flags_good_cell_correctly():
    import pandas as pd

    thresholds = {
        "rsrp_poor_dbm": -110, "rsrp_fair_dbm": -95,
        "sinr_poor_db": 3, "sinr_fair_db": 10, "load_high_pct": 80,
    }
    per_cell = pd.DataFrame(
        [{"cell_id": "Y", "avg_rsrp_dbm": -70, "avg_sinr_db": 25, "avg_load_pct": 30}]
    )
    classified = metrics.classify_quality(per_cell, thresholds)
    assert classified.loc[0, "quality_status"] == "良好"
