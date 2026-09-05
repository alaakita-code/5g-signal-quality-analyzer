"""
throughput.py
================
用簡化版 Shannon 容量公式,估算頻寬(bandwidth)與 MIMO 天線數對
理論吞吐量(throughput)的影響。

重要:這是教學/展示用的簡化模型,不是精確的 3GPP 鏈路預算計算:
    - 用單一有效 SINR 直接套 Shannon 公式,沒有考慮實際調變編碼機制
      (MCS table)、通道品質回報粒度、重傳(HARQ)等真實系統的損耗
    - MIMO 增益用一個固定的「空間串流效率」係數概略打折,不是精確的
      通道容量矩陣運算(需要天線相關性、通道矩陣秩等更多資訊才能精算)
    - 目的是示範「調整頻寬或天線數,對理論吞吐量上限的影響方向與量級」,
      不是拿來做真正的無線網路容量規劃
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

# MIMO 空間串流效率係數:代表實際天線數增加時,吞吐量不會是線性倍增
# (受限於通道相關性、干擾等因素),這裡用一個概念性的遞減係數概略表示。
_MIMO_EFFICIENCY = 0.75


def estimate_throughput_mbps(sinr_db, bandwidth_mhz: float, num_antennas: int):
    """依 SINR、頻寬、天線數估算理論吞吐量(Mbps)。

    sinr_db 可以是單一數值,也可以是 pandas Series(會逐筆計算)。
    """
    if isinstance(sinr_db, pd.Series):
        sinr_linear = 10 ** (sinr_db / 10.0)
        capacity_per_stream = bandwidth_mhz * np.log2(1 + sinr_linear)
    else:
        sinr_linear = 10 ** (sinr_db / 10.0)
        capacity_per_stream = bandwidth_mhz * math.log2(1 + sinr_linear)

    return capacity_per_stream * num_antennas * _MIMO_EFFICIENCY


def add_throughput_column(
    df: pd.DataFrame, bandwidth_mhz: float, num_antennas: int
) -> pd.DataFrame:
    """在資料表加上 throughput_mbps 欄位(依 sinr_db 逐筆估算)。"""
    out = df.copy()
    out["throughput_mbps"] = estimate_throughput_mbps(
        out["sinr_db"], bandwidth_mhz, num_antennas
    ).round(1)
    return out


def bandwidth_sensitivity(
    avg_sinr_db: float,
    num_antennas: int,
    bandwidths_mhz: list[float] | None = None,
) -> pd.DataFrame:
    """固定 SINR 與天線數,計算不同頻寬下的理論吞吐量,用來畫出敏感度曲線。"""
    if bandwidths_mhz is None:
        bandwidths_mhz = [5, 10, 20, 40, 60, 80, 100]

    rows = [
        {
            "bandwidth_mhz": bw,
            "throughput_mbps": round(estimate_throughput_mbps(avg_sinr_db, bw, num_antennas), 1),
        }
        for bw in bandwidths_mhz
    ]
    return pd.DataFrame(rows)


def antenna_sensitivity(
    avg_sinr_db: float,
    bandwidth_mhz: float,
    antenna_options: list[int] | None = None,
) -> pd.DataFrame:
    """固定 SINR 與頻寬,計算不同 MIMO 天線數下的理論吞吐量。"""
    if antenna_options is None:
        antenna_options = [1, 2, 4, 8]

    rows = [
        {
            "num_antennas": n,
            "throughput_mbps": round(estimate_throughput_mbps(avg_sinr_db, bandwidth_mhz, n), 1),
        }
        for n in antenna_options
    ]
    return pd.DataFrame(rows)
