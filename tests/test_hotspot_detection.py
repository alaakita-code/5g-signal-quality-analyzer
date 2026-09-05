"""測試 analysis.hotspot_detection 的標記與聚類邏輯。"""

from __future__ import annotations

import pandas as pd

from analysis import hotspot_detection, metrics


def test_flag_poor_samples_adds_expected_columns(small_df):
    flagged = hotspot_detection.flag_poor_samples(small_df)
    assert {"flag_poor_signal", "flag_high_load", "flag_problem"}.issubset(
        flagged.columns
    )
    assert flagged["flag_problem"].dtype == bool


def test_flag_poor_samples_logic_is_consistent(small_df):
    flagged = hotspot_detection.flag_poor_samples(
        small_df, rsrp_poor_dbm=-110, sinr_poor_db=3, load_high_pct=80
    )
    # flag_problem 必須恰為 flag_poor_signal 或 flag_high_load 的邏輯或
    expected = flagged["flag_poor_signal"] | flagged["flag_high_load"]
    assert (flagged["flag_problem"] == expected).all()


def test_detect_hotspots_dbscan_returns_expected_columns(small_df):
    flagged = hotspot_detection.flag_poor_samples(
        small_df, rsrp_poor_dbm=-40, sinr_poor_db=100, load_high_pct=-1
    )  # 門檻拉到極端,確保全部樣本都被標記為問題,測試聚類流程本身
    clusters = hotspot_detection.detect_hotspots_dbscan(
        flagged, eps_km=1.0, min_samples=2
    )
    assert set(clusters.columns) == {
        "cluster_id",
        "center_lat",
        "center_lon",
        "sample_count",
    }


def test_detect_hotspots_dbscan_empty_when_no_problem_samples(small_df):
    flagged = hotspot_detection.flag_poor_samples(
        small_df, rsrp_poor_dbm=-999, sinr_poor_db=-999, load_high_pct=999
    )  # 門檻設到不可能觸發,確保沒有任何問題樣本
    clusters = hotspot_detection.detect_hotspots_dbscan(flagged)
    assert clusters.empty


def test_detect_hotspots_threshold_returns_dataframe(small_df):
    per_cell = metrics.per_cell_summary(small_df)
    hot = hotspot_detection.detect_hotspots_threshold(per_cell, load_high_pct=80)
    assert isinstance(hot, pd.DataFrame)
    # 回傳的欄位應該是 per_cell 的子集
    assert set(hot.columns) == set(per_cell.columns)


def test_detect_hotspots_threshold_respects_custom_rsrp_and_sinr_thresholds(small_df):
    """回歸測試:detect_hotspots_threshold 曾經把 RSRP/SINR 門檻寫死成 -105/5,
    完全忽略呼叫端傳入的自訂門檻,導致儀表板側邊欄的門檻滑桿對這張表毫無作用。
    這裡故意把門檻設到極端寬鬆/極端嚴格,驗證回傳結果真的會隨參數變化。
    """
    per_cell = metrics.per_cell_summary(small_df)

    # 門檻設到不可能觸發,應該完全沒有小區被抓出來
    none_hot = hotspot_detection.detect_hotspots_threshold(
        per_cell, rsrp_poor_dbm=-999, sinr_poor_db=-999, load_high_pct=999
    )
    assert none_hot.empty

    # 門檻設到極寬鬆(幾乎任何小區都會被判定為問題),應該抓到全部小區
    all_hot = hotspot_detection.detect_hotspots_threshold(
        per_cell, rsrp_poor_dbm=-40, sinr_poor_db=100, load_high_pct=-1
    )
    assert len(all_hot) == len(per_cell)
