"""
recommendations.py
=====================
依據簡單規則,為每個瓶頸小區產生初步的最佳化建議文字。

注意:這些建議是「規則式(rule-based)」的概念性提示,用於教學/展示,
實際網路優化仍須搭配路測資料、Moshell/MO dump、drive test 等現場資訊
交叉驗證,不能只靠模擬資料下結論。
"""

from __future__ import annotations

import pandas as pd


def _recommend_for_row(row: pd.Series) -> list[str]:
    tips: list[str] = []

    if row.get("avg_load_pct", 0) > 80:
        tips.append("負載偏高,建議評估新增載波(Carrier Aggregation)或分流鄰近小區")

    if row.get("avg_sinr_db", 99) < 5:
        tips.append("SINR 偏低,可能為鄰區干擾,建議檢查天線傾角(Tilt)與 PCI 規劃")

    if row.get("avg_rsrp_dbm", 0) < -105:
        tips.append("RSRP 偏弱,建議評估增加發射功率或新增小區/補強站")

    if row.get("max_load_pct", 0) > 95:
        tips.append("尖峰時段負載已接近滿載,建議優先排入擴容計畫")

    if not tips:
        tips.append("目前指標尚在正常範圍,建議持續觀察")

    return tips


def generate_recommendations(per_cell_df: pd.DataFrame) -> pd.DataFrame:
    """為每個小區產生建議清單,回傳附加 recommendations 欄位的資料表。"""
    out = per_cell_df.copy()
    out["recommendations"] = out.apply(_recommend_for_row, axis=1)
    out["recommendations_text"] = out["recommendations"].apply(
        lambda tips: " ; ".join(tips)
    )
    return out
