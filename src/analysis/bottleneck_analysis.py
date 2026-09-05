"""
bottleneck_analysis.py
=========================
識別「高負載 + 低訊號品質」的小區,並依嚴重程度排序,列出 Top N 瓶頸小區。
"""

from __future__ import annotations

import pandas as pd


def score_bottleneck(per_cell_df: pd.DataFrame) -> pd.DataFrame:
    """為每個小區計算一個簡易「瓶頸分數」(0~100,越高代表問題越嚴重)。

    分數採簡單加權合成,僅供排序與展示用途,非正式網路優化評分標準:
        - 負載權重 40%
        - SINR 劣化權重 35%(SINR 越低分數越高)
        - RSRP 劣化權重 25%(RSRP 越低分數越高)
    """
    df = per_cell_df.copy()

    load_score = df["avg_load_pct"].clip(0, 100)
    # SINR 由 -5~35 dB 映射到 0~100(越差分數越高)
    sinr_score = (35 - df["avg_sinr_db"]).clip(0, 40) / 40 * 100
    # RSRP 由 -140~-40 dBm 映射到 0~100(越差分數越高)
    rsrp_score = (df["avg_rsrp_dbm"] * -1 - 40).clip(0, 100)

    df["bottleneck_score"] = (
        load_score * 0.40 + sinr_score * 0.35 + rsrp_score * 0.25
    ).round(1)

    return df.sort_values("bottleneck_score", ascending=False).reset_index(drop=True)


def top_n_bottlenecks(per_cell_df: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    """回傳瓶頸分數最高的前 N 個小區。"""
    scored = score_bottleneck(per_cell_df)
    return scored.head(n)
