"""
load_opencellid.py
=====================
(選用模組)匯入 OpenCelliD 公開資料集,取得真實基地台地理位置作為模擬基礎。

OpenCelliD (https://opencellid.org/) 提供全球基地台位置的社群資料庫,
下載需要免費註冊 API Key。本模組僅示範資料清洗流程,實際下載邏輯
需依 OpenCelliD API 文件另行串接,此處保留為骨架,尚未實作 API 呼叫。

預期輸入欄位(OpenCelliD CSV 匯出格式,節錄):
    radio, mcc, mnc, lac, cid, lon, lat, range, samples, ...

輸出欄位(統一後供本專案其餘模組使用):
    cell_id, site_lat, site_lon, radio_type
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_and_clean(raw_csv_path: str) -> pd.DataFrame:
    """讀取 OpenCelliD 匯出的原始 CSV,並轉換為本專案的統一欄位格式。

    注意:此函式假設檔案已經是使用者自行從 OpenCelliD 下載的匯出檔,
    本專案不含自動下載邏輯(需要 API Key,且涉及外部服務條款)。
    """
    path = Path(raw_csv_path)
    if not path.exists():
        raise FileNotFoundError(
            f"找不到 OpenCelliD 匯出檔:{path}。"
            "請先至 https://opencellid.org/ 下載對應區域的資料。"
        )

    df = pd.read_csv(path)

    required_cols = {"radio", "lon", "lat", "cid"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"OpenCelliD 檔案缺少必要欄位:{missing}")

    cleaned = pd.DataFrame(
        {
            "cell_id": df["cid"].astype(str),
            "site_lat": df["lat"],
            "site_lon": df["lon"],
            "radio_type": df["radio"],
        }
    )

    # 過濾明顯異常座標(0,0 通常代表資料缺失)
    cleaned = cleaned[(cleaned["site_lat"] != 0) | (cleaned["site_lon"] != 0)]

    return cleaned.reset_index(drop=True)


if __name__ == "__main__":
    print(
        "此模組為骨架,尚未接上 OpenCelliD 下載 API。"
        "請先手動下載 CSV,再呼叫 load_and_clean() 進行清洗。"
    )
