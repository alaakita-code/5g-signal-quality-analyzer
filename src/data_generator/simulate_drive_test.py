"""
simulate_drive_test.py
=========================
模擬「路測/群眾外包(crowdsourcing)」風格的量測資料。

跟 simulate_cell_data.py 的差異:
    - simulate_cell_data.py:每個小區周圍固定散佈一批「靜止量測點」,
      模擬的是「小區覆蓋範圍內的統計快照」。
    - simulate_drive_test.py(本檔案):模擬一批「會移動的裝置」(路測車、
      或群眾外包 App 使用者手機),每個裝置隨時間沿著隨機路徑移動,
      移動過程中依所在位置自動連到最近的基地台(模擬換手),
      量到的訊號會隨著裝置與服務小區的距離變化而起伏。

這仍然是模擬資料,不是真實路測/群眾外包資料集,只是換一種資料產生方式,
呈現「移動中量測」與「固定點量測」的不同型態。

輸出欄位與 simulate_cell_data.generate() 相同(多一個 device_id 欄位),
可直接套用既有的分析/儀表板/報告邏輯:
    timestamp, cell_id, site_lat, site_lon, sample_lat, sample_lon,
    distance_m, rsrp_dbm, rsrq_db, sinr_db, load_pct, num_users, device_id

使用方式:
    python simulate_drive_test.py --config ../../configs/default_config.yaml \
        --output ../../data/raw/simulated_drive_test.csv
"""

from __future__ import annotations

import argparse
import math
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from data_generator.simulate_cell_data import (
    _haversine_m,
    _is_peak_hour,
    _path_loss_db,
    _random_point_in_radius,
)


def _generate_sites(sim: dict, rng: np.random.Generator) -> list[dict]:
    """依設定產生基地台位置清單,邏輯與 simulate_cell_data.generate() 一致,
    確保兩種資料來源在同樣的設定檔下,看到的基地台佈局是一樣的。
    """
    sites = []
    for i in range(sim["num_cells"]):
        lat, lon = _random_point_in_radius(
            sim["center_lat"], sim["center_lon"], sim["radius_km"], rng
        )
        sites.append({"cell_id": f"CELL_{i+1:03d}", "site_lat": lat, "site_lon": lon})
    return sites


def _nearest_site(lat: float, lon: float, sites: list[dict]) -> tuple[dict, float]:
    """回傳離裝置目前位置最近的基地台,以及距離(公尺)。"""
    best_site = None
    best_dist = float("inf")
    for site in sites:
        d = _haversine_m(lat, lon, site["site_lat"], site["site_lon"])
        if d < best_dist:
            best_dist = d
            best_site = site
    return best_site, best_dist


def generate_drive_test(config: dict) -> pd.DataFrame:
    sim = config["simulation"]
    drive_cfg = config.get("drive_test", {})
    rng = np.random.default_rng(sim["random_seed"])

    sites = _generate_sites(sim, rng)

    start = datetime.fromisoformat(sim["start_time"])
    end = datetime.fromisoformat(sim["end_time"])
    # 路測資料用比小區資料更細的時間間隔(預設 1 分鐘),移動軌跡才會平滑;
    # 沿用小區資料的 5 分鐘間隔的話,車速快一點一步就能跨過整個模擬區域,
    # 看起來會像瞬移而不是移動。
    step_minutes = drive_cfg.get("time_step_minutes", 1)
    step = timedelta(minutes=step_minutes)

    timestamps = []
    t = start
    while t <= end:
        timestamps.append(t)
        t += step

    num_devices = drive_cfg.get("num_devices", 15)
    speed_lo, speed_hi = drive_cfg.get("speed_kmh_range", [3, 40])
    radius_km = sim["radius_km"]
    center_lat, center_lon = sim["center_lat"], sim["center_lon"]

    rows = []
    for device_idx in range(num_devices):
        speed_kmh = rng.uniform(speed_lo, speed_hi)
        step_km = speed_kmh * (step_minutes / 60.0)

        lat, lon = _random_point_in_radius(center_lat, center_lon, radius_km, rng)
        heading_rad = rng.uniform(0, 2 * math.pi)

        for ts in timestamps:
            heading_rad += rng.normal(0, 0.4)

            step_deg = step_km / 111.0
            new_lat = lat + step_deg * math.cos(heading_rad)
            new_lon = lon + step_deg * math.sin(heading_rad) / max(
                math.cos(math.radians(lat)), 0.1
            )

            dist_from_center_km = (
                _haversine_m(new_lat, new_lon, center_lat, center_lon) / 1000.0
            )
            if dist_from_center_km > radius_km:
                heading_rad += math.pi
                new_lat = lat + step_deg * math.cos(heading_rad)
                new_lon = lon + step_deg * math.sin(heading_rad) / max(
                    math.cos(math.radians(lat)), 0.1
                )

            lat, lon = new_lat, new_lon

            serving_site, dist_m = _nearest_site(lat, lon, sites)

            pl_db = _path_loss_db(dist_m, sim["path_loss_exponent"])
            shadowing = rng.normal(0, sim["shadowing_std_db"])
            fading = rng.normal(0, sim["fading_std_db"])

            rsrp = sim["tx_power_dbm"] - pl_db + shadowing + fading
            rsrp = float(np.clip(rsrp, -140, -40))

            rsrq = float(np.clip(-3 - (110 + rsrp) * 0.15 + rng.normal(0, 1.5), -20, -3))
            interference_penalty = sim.get("interference_penalty_db", 0.0)
            sinr = float(
                np.clip(
                    (rsrp + 110) * 0.35 - interference_penalty + rng.normal(0, 3),
                    -5,
                    35,
                )
            )

            hour = ts.hour
            peak = _is_peak_hour(hour, sim["peak_hours"])
            load_lo, load_hi = (
                sim["peak_load_range"] if peak else sim["offpeak_load_range"]
            )
            load_pct = float(np.clip(rng.uniform(load_lo, load_hi), 0, 100))
            num_users = int(load_pct / 100 * rng.integers(50, 200))

            rows.append(
                {
                    "timestamp": ts,
                    "cell_id": serving_site["cell_id"],
                    "site_lat": serving_site["site_lat"],
                    "site_lon": serving_site["site_lon"],
                    "sample_lat": lat,
                    "sample_lon": lon,
                    "distance_m": round(dist_m, 1),
                    "rsrp_dbm": round(rsrp, 1),
                    "rsrq_db": round(rsrq, 1),
                    "sinr_db": round(sinr, 1),
                    "load_pct": round(load_pct, 1),
                    "num_users": num_users,
                    "device_id": f"DEVICE_{device_idx+1:03d}",
                }
            )

    return pd.DataFrame(rows)


def count_handovers(df: pd.DataFrame) -> pd.DataFrame:
    """統計每個裝置沿路徑經歷了幾次換手(serving cell 改變的次數)。"""
    out = []
    for device_id, group in df.sort_values("timestamp").groupby("device_id"):
        cell_changes = (group["cell_id"] != group["cell_id"].shift()).sum() - 1
        out.append({"device_id": device_id, "handover_count": max(cell_changes, 0)})
    return pd.DataFrame(out)


def main():
    parser = argparse.ArgumentParser(description="產生模擬路測/群眾外包資料")
    parser.add_argument("--config", type=str, default="configs/default_config.yaml")
    parser.add_argument("--output", type=str, default="data/raw/simulated_drive_test.csv")
    args = parser.parse_args()

    with open(args.config, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    df = generate_drive_test(config)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")

    print(f"已產生 {len(df)} 筆路測模擬資料,共 {df['device_id'].nunique()} 個裝置。")
    print(f"輸出至:{output_path.resolve()}")


if __name__ == "__main__":
    main()
