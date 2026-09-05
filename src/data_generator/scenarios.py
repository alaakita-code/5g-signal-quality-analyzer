"""
scenarios.py
==============
案例演示情境庫。

因為沒有真實電信商 OSS 資料可用(涉及隱私與商業機密,無法取得真實 cell ID),
這裡改用「具名情境」取代單純的隨機模擬:每個情境用一組經過設計的模擬參數
組合,重現特定類型的實務場景(都會壅塞、偏鄉覆蓋不足、鄰區干擾等),
讓展示內容更貼近實際案例分析,而不是無意義的隨機數字。

每個情境是 configs/default_config.yaml 的參數覆寫(override),疊加在
base_config 之上,搭配一段情境敘述文字(narrative)說明這個案例在講什麼、
預期會看到什麼樣的分析結果。

注意:這仍然是模擬資料,不是真實案例;`narrative` 只是幫助理解模擬參數
背後對應的實務情境,不代表任何特定電信商或特定地點的真實數據。
"""

from __future__ import annotations

import copy

SCENARIOS = [
    {
        "id": "default",
        "icon": "🎛️",
        "name": "一般模擬(無特定情境)",
        "tag": "使用設定檔預設參數",
        "narrative": "純粹依照 configs/default_config.yaml 的參數模擬,不套用任何情境覆寫。",
        "overrides": {},
    },
    {
        "id": "urban_congestion",
        "icon": "🏙️",
        "name": "都會核心尖峰壅塞案例",
        "tag": "高負載 + 中等訊號品質",
        "narrative": (
            "情境設定:市中心商業區,白天上班時段與晚間尖峰人流密集,"
            "多個小區同時逼近滿載,但訊號覆蓋本身沒有問題(基地台密度高、"
            "距離近)。預期看到:平均負載偏高、瓶頸小區以「負載」為主因,"
            "RSRP/SINR 相對正常。"
        ),
        "overrides": {
            "num_cells": 10,
            "radius_km": 2.0,
            "cell_coverage_radius_km": 0.4,
            "peak_hours": [8, 9, 10, 11, 12, 13, 17, 18, 19, 20, 21, 22],
            "peak_load_range": [75, 100],
            "offpeak_load_range": [30, 60],
            "path_loss_exponent": 3.0,
        },
    },
    {
        "id": "rural_coverage_gap",
        "icon": "🏞️",
        "name": "偏鄉覆蓋不足案例",
        "tag": "訊號弱 + 負載低",
        "narrative": (
            "情境設定:郊區/山區,基地台稀疏、涵蓋半徑大,用戶量本身不多,"
            "負載並不高,但訊號強度普遍偏弱。預期看到:平均 RSRP 明顯偏低、"
            "瓶頸小區以「訊號弱」為主因,負載反而不是問題。"
        ),
        "overrides": {
            "num_cells": 6,
            "radius_km": 15.0,
            "cell_coverage_radius_km": 2.0,
            "peak_load_range": [30, 55],
            "offpeak_load_range": [5, 20],
            "path_loss_exponent": 3.6,
            "tx_power_dbm": 40.0,
        },
    },
    {
        "id": "interference_anomaly",
        "icon": "📡",
        "name": "鄰區干擾異常案例",
        "tag": "SINR 明顯劣化",
        "narrative": (
            "情境設定:PCI 規劃衝突或鄰區同頻干擾,基地台涵蓋距離、負載都"
            "正常,但訊號干擾雜訊比(SINR)明顯偏低。預期看到:RSRP 正常、"
            "負載正常,但 SINR 拖累整體品質分數,建議清單會指向「檢查天線"
            "傾角與 PCI 規劃」。"
        ),
        "overrides": {
            "num_cells": 8,
            "radius_km": 4.0,
            "cell_coverage_radius_km": 0.8,
            "peak_load_range": [40, 65],
            "offpeak_load_range": [15, 35],
            "path_loss_exponent": 3.2,
            "interference_penalty_db": 8.0,
        },
    },
    {
        "id": "event_surge",
        "icon": "🎉",
        "name": "節慶活動瞬間湧入案例",
        "tag": "短時間負載暴衝",
        "narrative": (
            "情境設定:演唱會、跨年晚會等大型活動現場,平時負載正常,"
            "但特定時段(活動進行中)人流瞬間暴增,單一/少數小區負載逼近"
            "滿載。預期看到:多數時段正常,少數尖峰時段(如晚間活動時段)"
            "負載急遽升高,適合在時間序列分頁觀察這種「突波」型態。"
        ),
        "overrides": {
            "num_cells": 5,
            "radius_km": 1.0,
            "cell_coverage_radius_km": 0.3,
            "peak_hours": [19, 20, 21],
            "peak_load_range": [90, 100],
            "offpeak_load_range": [10, 25],
            "path_loss_exponent": 2.8,
        },
    },
]


def get_scenario(scenario_id: str) -> dict:
    for s in SCENARIOS:
        if s["id"] == scenario_id:
            return s
    raise KeyError(f"找不到情境:{scenario_id}")


def apply_scenario(base_config: dict, scenario_id: str) -> dict:
    """回傳套用情境覆寫參數後的新設定(不修改原本的 base_config)。"""
    scenario = get_scenario(scenario_id)
    config = copy.deepcopy(base_config)
    config["simulation"].update(scenario["overrides"])
    config["_scenario"] = {
        "id": scenario["id"],
        "name": scenario["name"],
        "tag": scenario["tag"],
        "narrative": scenario["narrative"],
    }
    return config
