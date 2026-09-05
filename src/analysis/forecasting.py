"""
forecasting.py
=================
用簡單的機器學習模型(線性迴歸),依單一小區的歷史時間序列,
預測未來幾個時間點的負載或訊號走勢。

這是教學/展示用的簡化模型,不是正式的網路容量規劃工具:
    - 只用時間索引(第幾個時間點)當特徵,沒有考慮日期型態、節慶、
      天氣等真實世界會影響負載的因素
    - 只用歷史資料本身的線性趨勢外推,資料量小、趨勢不明顯時
      預測準確度有限
    - 適合用來示範「拿到時間序列資料後,可以怎麼串一個最基本的
      預測模型」,不是拿來做真正的容量規劃決策
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression


def forecast_series(
    ts_df: pd.DataFrame,
    value_col: str,
    periods: int = 12,
    time_step_minutes: int = 5,
) -> pd.DataFrame:
    """對單一小區的時間序列做線性迴歸外推,預測未來 periods 個時間點。

    Parameters
    ----------
    ts_df : 至少要有 "timestamp" 與 value_col 兩欄,依時間排序的資料表
    value_col : 要預測的欄位名稱(例如 "load_pct"、"rsrp_dbm")
    periods : 要往未來預測幾個時間點
    time_step_minutes : 每個時間點間隔幾分鐘(用來推算未來時間戳記)

    Returns
    -------
    DataFrame,欄位為 timestamp、value_col、is_forecast(True/False),
    把歷史資料與預測資料接在一起回傳,方便直接畫成同一張折線圖。
    """
    history = ts_df[["timestamp", value_col]].dropna().sort_values("timestamp").reset_index(drop=True)
    if len(history) < 2:
        raise ValueError("歷史資料點數太少(少於 2 筆),無法做線性迴歸預測")

    x = np.arange(len(history)).reshape(-1, 1)
    y = history[value_col].to_numpy()

    model = LinearRegression()
    model.fit(x, y)

    future_x = np.arange(len(history), len(history) + periods).reshape(-1, 1)
    future_y = model.predict(future_x)

    last_ts = history["timestamp"].iloc[-1]
    future_ts = [
        last_ts + pd.Timedelta(minutes=time_step_minutes * (i + 1)) for i in range(periods)
    ]

    history_out = history.copy()
    history_out["is_forecast"] = False

    forecast_out = pd.DataFrame({"timestamp": future_ts, value_col: future_y})
    forecast_out["is_forecast"] = True

    return pd.concat([history_out, forecast_out], ignore_index=True)


def trend_direction(ts_df: pd.DataFrame, value_col: str) -> str:
    """回傳簡短的趨勢描述文字(上升/下降/大致持平),依線性迴歸的斜率判斷。"""
    history = ts_df[["timestamp", value_col]].dropna().sort_values("timestamp")
    if len(history) < 2:
        return "資料點數太少,無法判斷趨勢"

    x = np.arange(len(history)).reshape(-1, 1)
    y = history[value_col].to_numpy()
    model = LinearRegression()
    model.fit(x, y)
    slope = model.coef_[0]

    # 用整體數值範圍的 1% 當作「有感變化」的門檻,避免雜訊被誤判為趨勢
    value_range = y.max() - y.min()
    noise_threshold = max(value_range * 0.01, 1e-6)

    if slope > noise_threshold:
        return "上升"
    elif slope < -noise_threshold:
        return "下降"
    return "大致持平"
