"""
hotspot_detection.py
=======================
用閾值法或 DBSCAN 聚類,找出訊號差或高負載的熱區(問題區域)。
"""

from __future__ import annotations

import pandas as pd
from sklearn.cluster import DBSCAN


def flag_poor_samples(
    df: pd.DataFrame,
    rsrp_poor_dbm: float = -110,
    sinr_poor_db: float = 3,
    load_high_pct: float = 80,
) -> pd.DataFrame:
    """為每筆樣本標記是否為「訊號差」或「高負載」,回傳附加標記欄位的資料表。"""
    out = df.copy()
    out["flag_poor_signal"] = (out["rsrp_dbm"] < rsrp_poor_dbm) | (
        out["sinr_db"] < sinr_poor_db
    )
    out["flag_high_load"] = out["load_pct"] > load_high_pct
    out["flag_problem"] = out["flag_poor_signal"] | out["flag_high_load"]
    return out


def detect_hotspots_dbscan(
    df: pd.DataFrame,
    eps_km: float = 0.5,
    min_samples: int = 5,
) -> pd.DataFrame:
    """對「有問題的樣本點」(flag_problem = True)做地理聚類,找出熱區中心。

    需先呼叫 flag_poor_samples() 產生 flag_problem 欄位。
    回傳每個熱區群集的中心座標與涵蓋樣本數。
    """
    problem_df = df[df.get("flag_problem", False) == True].copy()  # noqa: E712
    if problem_df.empty:
        return pd.DataFrame(
            columns=["cluster_id", "center_lat", "center_lon", "sample_count"]
        )

    coords = problem_df[["sample_lat", "sample_lon"]].to_numpy()
    # 概略換算:1 度緯度約 111 公里,DBSCAN 的 eps 用度數表示
    eps_deg = eps_km / 111.0

    db = DBSCAN(eps=eps_deg, min_samples=min_samples).fit(coords)
    problem_df["cluster_id"] = db.labels_

    clusters = problem_df[problem_df["cluster_id"] != -1]
    if clusters.empty:
        return pd.DataFrame(
            columns=["cluster_id", "center_lat", "center_lon", "sample_count"]
        )

    summary = (
        clusters.groupby("cluster_id")
        .agg(
            center_lat=("sample_lat", "mean"),
            center_lon=("sample_lon", "mean"),
            sample_count=("sample_lat", "count"),
        )
        .reset_index()
        .round(5)
    )
    return summary.sort_values("sample_count", ascending=False).reset_index(drop=True)


def detect_hotspots_threshold(
    per_cell_df: pd.DataFrame,
    rsrp_poor_dbm: float = -105,
    sinr_poor_db: float = 5,
    load_high_pct: float = 80,
) -> pd.DataFrame:
    """簡化版:直接以「小區平均值」超過門檻來判斷熱區,不做地理聚類。

    適合資料量小、或不需要精細地理聚類時的快速判斷。
    """
    hot = per_cell_df[
        (per_cell_df["avg_rsrp_dbm"] < rsrp_poor_dbm)
        | (per_cell_df["avg_sinr_db"] < sinr_poor_db)
        | (per_cell_df["avg_load_pct"] > load_high_pct)
    ].copy()
    return hot.sort_values("avg_load_pct", ascending=False).reset_index(drop=True)
