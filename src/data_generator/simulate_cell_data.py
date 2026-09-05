"""
simulate_cell_data.py
=======================
模擬多基地台、多時間點的 4G/5G 訊號與負載資料。

產生的欄位:
    timestamp   量測時間
    cell_id     基地台(小區)編號
    site_lat    基地台緯度
    site_lon    基地台經度
    sample_lat  量測點緯度
    sample_lon  量測點經度
    distance_m  量測點與基地台的距離(公尺)
    rsrp_dbm    參考訊號接收功率
    rsrq_db     參考訊號接收品質
    sinr_db     訊號干擾雜訊比
    load_pct    小區負載百分比(0~100)
    num_users   小區同時在線用戶數(估算值)

使用方式:
    python simulate_cell_data.py --config ../../configs/default_config.yaml \
        --output ../../data/raw/simulated_cell_data.csv
"""

from __future__ import annotations

import argparse
import math
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


# ---------------------------------------------------------------
# 地理座標輔助函式
# ---------------------------------------------------------------
def _random_point_in_radius(
    center_lat: float, center_lon: float, radius_km: float, rng: np.random.Generator
) -> tuple[float, float]:
    """在指定中心點的圓形範圍內,隨機產生一個 (lat, lon) 座標。"""
    radius_deg = radius_km / 111.0  # 粗略換算:1 度緯度約 111 公里
    r = radius_deg * math.sqrt(rng.random())
    theta = rng.random() * 2 * math.pi
    lat = center_lat + r * math.cos(theta)
    lon = center_lon + r * math.sin(theta) / math.cos(math.radians(center_lat))
    return lat, lon


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """計算兩點之間的距離(公尺),使用 Haversine 公式。"""
    r_earth = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * r_earth * math.asin(math.sqrt(a))


# ---------------------------------------------------------------
# 訊號模型
# ---------------------------------------------------------------
def _path_loss_db(distance_m: float, exponent: float) -> float:
    """簡化版對數距離路徑損耗模型。距離低於 1 公尺時鎖定為 1 公尺,避免 log(0)。"""
    d = max(distance_m, 1.0)
    # 參考距離 1 公尺、參考損耗 40 dB(概念性設定,非特定廠牌校準值)
    return 40.0 + 10.0 * exponent * math.log10(d)


def _is_peak_hour(hour: int, peak_hours: list[int]) -> bool:
    return hour in peak_hours


def generate(config: dict) -> pd.DataFrame:
    sim = config["simulation"]
    rng = np.random.default_rng(sim["random_seed"])

    start = datetime.fromisoformat(sim["start_time"])
    end = datetime.fromisoformat(sim["end_time"])
    step = timedelta(minutes=sim["time_step_minutes"])

    # 產生基地台位置
    cells = []
    for i in range(sim["num_cells"]):
        lat, lon = _random_point_in_radius(
            sim["center_lat"], sim["center_lon"], sim["radius_km"], rng
        )
        cells.append({"cell_id": f"CELL_{i+1:03d}", "site_lat": lat, "site_lon": lon})

    coverage_radius_km = sim.get("cell_coverage_radius_km", sim["radius_km"] / 2)

    rows = []
    timestamps = []
    t = start
    while t <= end:
        timestamps.append(t)
        t += step

    for cell in cells:
        for ts in timestamps:
            hour = ts.hour
            peak = _is_peak_hour(hour, sim["peak_hours"])
            load_lo, load_hi = (
                sim["peak_load_range"] if peak else sim["offpeak_load_range"]
            )

            for _ in range(sim["samples_per_cell"]):
                s_lat, s_lon = _random_point_in_radius(
                    cell["site_lat"], cell["site_lon"], coverage_radius_km, rng
                )
                dist_m = _haversine_m(
                    cell["site_lat"], cell["site_lon"], s_lat, s_lon
                )

                pl_db = _path_loss_db(dist_m, sim["path_loss_exponent"])
                shadowing = rng.normal(0, sim["shadowing_std_db"])
                fading = rng.normal(0, sim["fading_std_db"])

                rsrp = sim["tx_power_dbm"] - pl_db + shadowing + fading
                rsrp = float(np.clip(rsrp, -140, -40))

                # RSRQ 與 SINR 依 RSRP 概略推導,並加入隨機雜訊(僅供模擬示範用)
                rsrq = float(np.clip(-3 - (110 + rsrp) * 0.15 + rng.normal(0, 1.5), -20, -3))
                interference_penalty = sim.get("interference_penalty_db", 0.0)
                sinr = float(
                    np.clip(
                        (rsrp + 110) * 0.35 - interference_penalty + rng.normal(0, 3),
                        -5,
                        35,
                    )
                )

                load_pct = float(np.clip(rng.uniform(load_lo, load_hi), 0, 100))
                num_users = int(load_pct / 100 * rng.integers(50, 200))

                rows.append(
                    {
                        "timestamp": ts,
                        "cell_id": cell["cell_id"],
                        "site_lat": cell["site_lat"],
                        "site_lon": cell["site_lon"],
                        "sample_lat": s_lat,
                        "sample_lon": s_lon,
                        "distance_m": round(dist_m, 1),
                        "rsrp_dbm": round(rsrp, 1),
                        "rsrq_db": round(rsrq, 1),
                        "sinr_db": round(sinr, 1),
                        "load_pct": round(load_pct, 1),
                        "num_users": num_users,
                    }
                )

    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser(description="產生模擬 4G/5G 基地台訊號資料")
    parser.add_argument(
        "--config",
        type=str,
        default="configs/default_config.yaml",
        help="設定檔路徑",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/raw/simulated_cell_data.csv",
        help="輸出 CSV 路徑",
    )
    args = parser.parse_args()

    with open(args.config, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    df = generate(config)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")

    print(f"已產生 {len(df)} 筆模擬資料,共 {df['cell_id'].nunique()} 個小區。")
    print(f"輸出至:{output_path.resolve()}")


if __name__ == "__main__":
    main()
