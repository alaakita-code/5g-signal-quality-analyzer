"""
metrics.py
============
計算基本統計指標:整體平均值、各小區平均值、簡易掉話率 proxy 等。
"""

from __future__ import annotations

import pandas as pd


def overall_summary(df: pd.DataFrame) -> dict:
    """回傳整份資料的整體統計摘要(字典格式,方便直接餵給儀表板卡片)。"""
    return {
        "avg_rsrp_dbm": round(df["rsrp_dbm"].mean(), 1),
        "avg_rsrq_db": round(df["rsrq_db"].mean(), 1),
        "avg_sinr_db": round(df["sinr_db"].mean(), 1),
        "avg_load_pct": round(df["load_pct"].mean(), 1),
        "total_samples": int(len(df)),
        "total_cells": int(df["cell_id"].nunique()),
        "time_range": (
            str(df["timestamp"].min()),
            str(df["timestamp"].max()),
        ),
    }


def per_cell_summary(df: pd.DataFrame) -> pd.DataFrame:
    """依小區彙整平均指標,並附上樣本數。"""
    grouped = (
        df.groupby("cell_id")
        .agg(
            avg_rsrp_dbm=("rsrp_dbm", "mean"),
            avg_rsrq_db=("rsrq_db", "mean"),
            avg_sinr_db=("sinr_db", "mean"),
            avg_load_pct=("load_pct", "mean"),
            max_load_pct=("load_pct", "max"),
            sample_count=("rsrp_dbm", "count"),
            site_lat=("site_lat", "first"),
            site_lon=("site_lon", "first"),
        )
        .reset_index()
    )
    return grouped.round(1)


def classify_quality(per_cell_df: pd.DataFrame, thresholds: dict) -> pd.DataFrame:
    """依門檻值把每個小區分類為「良好」/「普通」/「需關注」三個離散等級。

    比起連續色階(數值差異不明顯時很難一眼看出好壞),離散分類更適合
    快速掃描哪些小區需要優先處理。判斷邏輯(符合任一項即降級):
        - 需關注:RSRP 低於 rsrp_poor_dbm 或 SINR 低於 sinr_poor_db
                  或負載高於 load_high_pct
        - 普通:RSRP 低於 rsrp_fair_dbm 或 SINR 低於 sinr_fair_db
        - 良好:以上皆非
    """
    def _classify(row: pd.Series) -> str:
        if (
            row["avg_rsrp_dbm"] < thresholds["rsrp_poor_dbm"]
            or row["avg_sinr_db"] < thresholds["sinr_poor_db"]
            or row["avg_load_pct"] > thresholds["load_high_pct"]
        ):
            return "需關注"
        if (
            row["avg_rsrp_dbm"] < thresholds["rsrp_fair_dbm"]
            or row["avg_sinr_db"] < thresholds["sinr_fair_db"]
        ):
            return "普通"
        return "良好"

    out = per_cell_df.copy()
    out["quality_status"] = out.apply(_classify, axis=1)
    return out


def dropped_call_proxy(df: pd.DataFrame, sinr_threshold_db: float = 0.0) -> pd.DataFrame:
    """簡易掉話率 proxy:以 SINR 低於門檻的樣本比例,推估各小區的通話品質風險。

    這不是真實掉話率(需要實際 call trace/RRC release cause 資料才能精確計算),
    僅作為訊號劣化程度的代理指標,供教學/展示用途。
    """
    def _ratio(group: pd.DataFrame) -> float:
        return float((group["sinr_db"] < sinr_threshold_db).mean() * 100)

    proxy = (
        df.groupby("cell_id")
        .apply(_ratio, include_groups=False)
        .reset_index(name="dropped_call_proxy_pct")
    )
    return proxy.round(2)
