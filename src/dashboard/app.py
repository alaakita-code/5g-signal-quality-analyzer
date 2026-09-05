"""
app.py — 5G/4G 訊號品質分析儀表板(Streamlit)
================================================

執行方式(於專案根目錄):
    streamlit run src/dashboard/app.py

分頁:
    1. 總覽:關鍵指標卡片 + 小區分佈地圖(離散品質分類上色 + 小區 ID 標籤)
    2. 時間序列:選定小區,觀察 RSRP/SINR/負載隨時間變化
    3. 熱區分析:訊號差/高負載熱區(表格 + 地圖)
    4. 瓶頸與建議:Top N 問題小區與對應建議
    5. 報告下載:一鍵產生 Markdown / PDF 報告(含長條圖)

資料來源(側邊欄選擇):
    - 模擬資料:可即時調整模擬參數(小區數量、路徑損耗指數、發射功率等),
      不需要修改設定檔或重新啟動
    - 案例演示情境:因為沒有真實電信商 OSS 資料可用,改用一組經過設計的
      具名情境(都會壅塞、偏鄉覆蓋不足、鄰區干擾、活動突波),重現特定
      類型的實務場景,而非單純隨機模擬(見 src/data_generator/scenarios.py)
    - 上傳 CSV:使用者可上傳符合欄位格式的真實量測資料,取代模擬資料

視覺風格採用明亮、簡潔配色,不使用暗色系介面。
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
import yaml

# 讓本檔案可以直接用 `streamlit run` 執行,並正確匯入 src/ 底下的模組
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from analysis import bottleneck_analysis, hotspot_detection, metrics, recommendations  # noqa: E402
from analysis.forecasting import forecast_series, trend_direction  # noqa: E402
from analysis.throughput import add_throughput_column, antenna_sensitivity, bandwidth_sensitivity  # noqa: E402
from data_generator.scenarios import SCENARIOS, apply_scenario, get_scenario  # noqa: E402
from data_generator.simulate_cell_data import generate  # noqa: E402
from data_generator.simulate_drive_test import count_handovers, generate_drive_test  # noqa: E402
from reports.report_generator import build_markdown_report, build_pdf_report  # noqa: E402

# 上傳 CSV 時,資料必須符合這個欄位格式(對應 simulate_cell_data.generate() 的輸出)
REQUIRED_UPLOAD_COLUMNS = {
    "timestamp", "cell_id", "site_lat", "site_lon", "sample_lat", "sample_lon",
    "distance_m", "rsrp_dbm", "rsrq_db", "sinr_db", "load_pct", "num_users",
}


# -----------------------------------------------------------------
# 頁面設定(明亮配色,避免暗色系)
# -----------------------------------------------------------------
st.set_page_config(
    page_title="5G/4G 訊號品質分析儀",
    page_icon="📶",
    layout="wide",
)

# 統一字級,避免各元件預設字級落差太大(例如指標數字過大、說明文字過小)
st.markdown(
    """
    <style>
    /* 統一字級,避免各元件預設字級落差太大(例如指標數字過大、說明文字過小) */
    [data-testid="stMetricValue"] { font-size: 1.7rem; }
    [data-testid="stMetricLabel"] { font-size: 0.95rem; }
    [data-testid="stCaptionContainer"] { font-size: 0.92rem; line-height: 1.6; }
    .stMarkdown p, .stMarkdown li { font-size: 1rem; line-height: 1.65; }
    h3 { font-size: 1.2rem !important; }

    /* 壓縮頁面最上方的預設留白(Streamlit wide layout 預設頂部留白偏大,
       導致標題上方看起來空一大塊),讓標題貼近瀏覽器上緣一點 */
    .block-container { padding-top: 2rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

PRIMARY_COLOR = "#2563eb"   # 沉穩藍
GOOD_COLOR = "#16a34a"      # 綠
WARN_COLOR = "#d97706"      # 橘
BAD_COLOR = "#dc2626"       # 紅

QUALITY_COLOR_MAP = {
    "良好": GOOD_COLOR,
    "普通": WARN_COLOR,
    "需關注": BAD_COLOR,
}


def _scatter_on_map(**kwargs):
    """相容層:依 style 決定畫圖方式。

    - "open-street-map" / "carto-positron" 等:走 Plotly 的地圖元件
      (px.scatter_map,新版;或 px.scatter_mapbox,舊版),需要瀏覽器能
      跑 WebGL 並且能動態載入 MapLibre GL 的 JS 模組,部分公司網路/資安
      政策會擋掉這種動態載入,導致地圖整個空白(連 white-bg 都不畫)。
    - "plain_scatter":完全不用地圖元件,把經緯度當一般 X/Y 座標畫成
      散佈圖(px.scatter)。沒有街道背景,但不依賴 WebGL、不需要動態載入
      任何外部模組,任何環境都能正常顯示,是最保險的備援方案。
    """
    style = kwargs.pop("style", "open-street-map")

    if style == "plain_scatter":
        return _plain_scatter(**kwargs)

    if hasattr(px, "scatter_map"):
        return px.scatter_map(map_style=style, **kwargs)
    else:
        fig = px.scatter_mapbox(**kwargs)
        fig.update_layout(mapbox_style=style)
        return fig


def _plain_scatter(**kwargs):
    """把 lat/lon 當一般平面座標畫散佈圖,不使用任何地圖元件。"""
    kwargs.pop("zoom", None)
    kwargs.pop("height", None)
    lat_col = kwargs.pop("lat")
    lon_col = kwargs.pop("lon")
    df_ = kwargs.pop("data_frame")

    fig = px.scatter(
        df_,
        x=lon_col,
        y=lat_col,
        labels={lon_col: "經度", lat_col: "緯度"},
        height=500,
        **kwargs,
    )
    # 注意:這裡刻意不鎖定 X/Y 軸的縱橫比例(scaleanchor)。原本想用
    # scaleanchor 依緯度校正經緯度的實際距離比例,但在手機直向的窄容器下,
    # Plotly 為了同時滿足「鎖定比例」與「塞進容器」兩個條件,會把可視範圍
    # 縮到只剩極小一塊(資料點全部被擠出畫面外,看起來像空白地圖)。純座標
    # 散佈圖本來就不是精確地圖,寧可犧牲一點縱橫比例的精確度,也要保證任何
    # 裝置、任何螢幕比例下都看得到完整資料。
    fig.update_traces(
        marker=dict(line=dict(width=0.5, color="white")),
        textposition="top center",
        textfont=dict(size=10),
    )
    return fig


@st.cache_data(show_spinner="正在載入設定檔...")
def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@st.cache_data(show_spinner="正在產生模擬資料...")
def load_data(config: dict) -> pd.DataFrame:
    return generate(config)


@st.cache_data(show_spinner="正在產生路測模擬資料...")
def load_drive_test_data(config: dict) -> pd.DataFrame:
    return generate_drive_test(config)


def _validate_upload(df: pd.DataFrame) -> list[str]:
    missing = REQUIRED_UPLOAD_COLUMNS - set(df.columns)
    return sorted(missing)


def main() -> None:
    st.title("📶 5G/4G 行動網路訊號品質分析儀")
    st.caption("以模擬資料展示:訊號統計、熱區偵測、瓶頸識別與最佳化建議")

    config_path = str(PROJECT_ROOT / "configs" / "default_config.yaml")
    base_config = load_config(config_path)

    df = None
    working_config = copy.deepcopy(base_config)
    active_scenario = None
    is_drive_test = False

    with st.sidebar:
        st.header("⚙️ 資料設定")
        data_source = st.radio(
            "資料來源",
            ["模擬資料(可調整參數)", "案例演示情境", "模擬路測/群眾外包", "上傳 CSV"],
            help=(
                "因無法取得真實電信商 OSS 資料(涉及隱私與商業機密),"
                "「案例演示情境」與「模擬路測/群眾外包」都是用經過設計的模擬方式"
                "重現特定類型的實務場景,並非真實資料;若你有自己的量測資料,"
                "可用「上傳 CSV」直接分析。"
            ),
        )

        if data_source == "案例演示情境":
            name_to_id = {f"{s['icon']} {s['name']}": s["id"] for s in SCENARIOS}
            selected_label = st.selectbox("選擇情境", list(name_to_id.keys()))
            scenario_id = name_to_id[selected_label]
            active_scenario = get_scenario(scenario_id)
            st.info(f"**{active_scenario['tag']}**\n\n{active_scenario['narrative']}")
            working_config = apply_scenario(base_config, scenario_id)
            df = load_data(working_config)

        elif data_source == "模擬路測/群眾外包":
            st.caption(
                "跟「模擬資料」的差別:這裡模擬的是**會移動的裝置**"
                "(路測車、或群眾外包 App 使用者手機),隨時間沿路徑移動、"
                "自動連到最近的基地台(模擬換手),而不是小區周圍固定的量測點。"
            )
            with st.expander("🚗 路測參數(展開調整,即時生效)", expanded=False):
                drive_cfg = working_config.setdefault(
                    "drive_test", {"num_devices": 15, "speed_kmh_range": [3, 40], "time_step_minutes": 1}
                )
                drive_cfg["num_devices"] = st.slider("裝置數量", 3, 40, drive_cfg["num_devices"])
                speed_range = st.slider(
                    "移動速度範圍(km/h,3 到 15 約為步行,15 到 40 約為市區行車)",
                    1, 60, tuple(drive_cfg["speed_kmh_range"])
                )
                drive_cfg["speed_kmh_range"] = list(speed_range)
            is_drive_test = True
            df = load_drive_test_data(working_config)

        elif data_source == "上傳 CSV":
            st.caption(
                "CSV 需包含欄位:timestamp, cell_id, site_lat, site_lon, "
                "sample_lat, sample_lon, distance_m, rsrp_dbm, rsrq_db, "
                "sinr_db, load_pct, num_users(可用「模擬資料」模式先下載一份"
                "範例格式參考)"
            )
            uploaded = st.file_uploader("上傳 CSV 檔案", type=["csv"])
            if uploaded is not None:
                try:
                    uploaded_df = pd.read_csv(uploaded)
                    missing_cols = _validate_upload(uploaded_df)
                    if missing_cols:
                        st.error(f"CSV 缺少必要欄位:{', '.join(missing_cols)}")
                    else:
                        uploaded_df["timestamp"] = pd.to_datetime(uploaded_df["timestamp"])
                        df = uploaded_df
                        st.success(f"已載入 {len(df)} 筆資料,共 {df['cell_id'].nunique()} 個小區。")
                except Exception as e:  # noqa: BLE001
                    st.error(f"讀取 CSV 失敗:{e}")

        else:  # 模擬資料(可調整參數)
            with st.expander("🔧 模擬參數(展開調整,即時生效)", expanded=False):
                sim = working_config["simulation"]
                sim["num_cells"] = st.slider("小區數量", 3, 30, sim["num_cells"])
                sim["samples_per_cell"] = st.slider("每小區樣本數", 5, 50, sim["samples_per_cell"])
                sim["path_loss_exponent"] = st.slider(
                    "路徑損耗指數(越大訊號衰減越快)", 2.0, 5.0, float(sim["path_loss_exponent"]), 0.1
                )
                sim["tx_power_dbm"] = st.slider(
                    "基地台發射功率(dBm)", 30.0, 50.0, float(sim["tx_power_dbm"]), 1.0
                )
            df = load_data(working_config)

        if df is None:
            st.warning("請先選擇資料來源(上傳 CSV 或切換到模擬資料/案例演示情境)。")
            st.stop()

        with st.expander("📏 判斷門檻(展開調整,即時生效)", expanded=False):
            base_th = working_config["thresholds"]
            thresholds = {
                "rsrp_poor_dbm": st.slider("RSRP 差門檻(dBm)", -140, -80, int(base_th["rsrp_poor_dbm"])),
                "rsrp_fair_dbm": base_th["rsrp_fair_dbm"],
                "sinr_poor_db": st.slider("SINR 差門檻(dB)", -5, 20, int(base_th["sinr_poor_db"])),
                "sinr_fair_db": base_th["sinr_fair_db"],
                "load_high_pct": st.slider("高負載門檻(%)", 50, 100, int(base_th["load_high_pct"])),
            }
        working_config["thresholds"] = thresholds

        with st.expander("📶 頻寬與 MIMO(展開調整,即時生效)", expanded=False):
            st.caption(
                "用簡化版公式估算理論吞吐量上限,示範調整頻寬/天線數對吞吐量的"
                "影響方向與量級,不是精確的鏈路預算計算。"
            )
            radio_cfg = working_config.setdefault("radio", {"bandwidth_mhz": 20, "num_antennas": 2})
            radio_cfg["bandwidth_mhz"] = st.slider(
                "頻寬(MHz)", 5, 100, int(radio_cfg["bandwidth_mhz"]), 5
            )
            radio_cfg["num_antennas"] = st.select_slider(
                "MIMO 天線數", options=[1, 2, 4, 8], value=radio_cfg["num_antennas"]
            )

        map_style = working_config.get("dashboard", {}).get("map_style", "plain_scatter")
        style_note = {
            "open-street-map": "含街道底圖,需要瀏覽器能跑地圖引擎(WebGL+動態載入 JS)並連到外部圖磚伺服器",
            "white-bg": "空白底圖但仍需要地圖引擎能動態載入,不需要連外部圖磚",
            "plain_scatter": "純座標散佈圖,不用地圖引擎,任何環境都能顯示,但沒有街道背景",
        }.get(map_style, "")
        st.caption(f"目前地圖底圖:`{map_style}`({style_note})")

    df = hotspot_detection.flag_poor_samples(
        df,
        rsrp_poor_dbm=thresholds["rsrp_poor_dbm"],
        sinr_poor_db=thresholds["sinr_poor_db"],
        load_high_pct=thresholds["load_high_pct"],
    )
    radio_cfg = working_config.get("radio", {"bandwidth_mhz": 20, "num_antennas": 2})
    df = add_throughput_column(df, radio_cfg["bandwidth_mhz"], radio_cfg["num_antennas"])
    per_cell = metrics.per_cell_summary(df)
    per_cell = metrics.classify_quality(per_cell, thresholds)
    per_cell["avg_throughput_mbps"] = (
        df.groupby("cell_id")["throughput_mbps"].mean().round(1).reindex(per_cell["cell_id"]).values
    )

    tab_overview, tab_timeseries, tab_hotspot, tab_bottleneck, tab_report = st.tabs(
        ["📊 總覽", "📈 時間序列", "🔥 熱區分析", "🧩 瓶頸與建議", "📄 報告下載"]
    )

    # ---------------- 總覽 ----------------
    with tab_overview:
        st.markdown(
            "這頁看的是**整個網路現在的整體狀況**:上面四張卡片是全部小區的平均值,"
            "下面的地圖告訴你「哪些小區在哪裡、目前狀況好不好」,"
            "表格則是每個小區各自的詳細數字,方便你逐一比對。"
        )

        if active_scenario:
            st.markdown(f"### {active_scenario['icon']} {active_scenario['name']}")

        summary = metrics.overall_summary(df)
        avg_throughput = round(df["throughput_mbps"].mean(), 1)
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("平均 RSRP", f"{summary['avg_rsrp_dbm']} dBm")
        c2.metric("平均 RSRQ", f"{summary['avg_rsrq_db']} dB")
        c3.metric("平均 SINR", f"{summary['avg_sinr_db']} dB")
        c4.metric("平均負載", f"{summary['avg_load_pct']} %")
        c5.metric("估計平均吞吐量", f"{avg_throughput} Mbps")
        st.caption(
            "RSRP 越接近 0 代表訊號越強(通常 -80 以上算不錯,-110 以下算偏弱);"
            "SINR 越高代表干擾越小、通話品質越好;負載是小區目前被用了多少百分比,"
            "太高代表快塞車了;估計吞吐量是依目前的 SINR、頻寬、MIMO 天線數"
            "(側邊欄可調整)概略估算的理論值,不是實際量測速度。"
        )

        with st.expander("📶 頻寬/MIMO 對吞吐量的影響(參數敏感度)"):
            st.caption(
                "固定目前的平均 SINR,分別看「只改頻寬」跟「只改天線數」時,"
                "理論吞吐量上限會怎麼變化——這只是示範參數之間的關係方向,"
                "不代表把頻寬/天線數調高就能無限提升實際速度。"
            )
            col_bw, col_ant = st.columns(2)
            with col_bw:
                bw_df = bandwidth_sensitivity(summary["avg_sinr_db"], radio_cfg["num_antennas"])
                fig_bw = px.bar(
                    bw_df, x="bandwidth_mhz", y="throughput_mbps",
                    title=f"頻寬影響(固定 {radio_cfg['num_antennas']} 天線)",
                    labels={"bandwidth_mhz": "頻寬(MHz)", "throughput_mbps": "估計吞吐量(Mbps)"},
                )
                st.plotly_chart(fig_bw, use_container_width=True, config={"displayModeBar": False})
            with col_ant:
                ant_df = antenna_sensitivity(summary["avg_sinr_db"], radio_cfg["bandwidth_mhz"])
                fig_ant = px.bar(
                    ant_df, x="num_antennas", y="throughput_mbps",
                    title=f"天線數影響(固定 {radio_cfg['bandwidth_mhz']}MHz)",
                    labels={"num_antennas": "MIMO 天線數", "throughput_mbps": "估計吞吐量(Mbps)"},
                )
                st.plotly_chart(fig_ant, use_container_width=True, config={"displayModeBar": False})

        st.subheader("小區地理分佈(依品質分類上色:良好/普通/需關注)")
        fig_map = _scatter_on_map(
            data_frame=per_cell,
            lat="site_lat",
            lon="site_lon",
            color="quality_status",
            color_discrete_map=QUALITY_COLOR_MAP,
            category_orders={"quality_status": ["良好", "普通", "需關注"]},
            size="sample_count",
            text="cell_id",
            hover_name="cell_id",
            hover_data=["avg_rsrp_dbm", "avg_sinr_db", "avg_load_pct"],
            zoom=11,
            height=500,
            style=map_style,
        )
        fig_map.update_layout(margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig_map, use_container_width=True, config={"displayModeBar": False})
        st.caption(
            "每個點是一個小區,顏色代表品質分類(綠=良好、橘=普通、紅=需關注),"
            "點越大代表這個小區收集到的樣本數越多。把滑鼠移到點上可以看到細節數字。"
        )

        st.subheader("各小區平均指標")
        st.dataframe(per_cell, use_container_width=True)
        st.caption(
            "這是上面地圖的原始數字版本,想確認某個小區的精確數值、"
            "或想自己排序比較時可以看這張表。"
        )

        st.download_button(
            "⬇️ 下載目前資料(CSV,可作為上傳格式參考)",
            data=df.to_csv(index=False).encode("utf-8-sig"),
            file_name="signal_quality_data.csv",
            mime="text/csv",
        )

        if is_drive_test:
            st.subheader("裝置換手統計")
            st.caption(
                "路測/群眾外包資料特有的統計:每個裝置在移動過程中,"
                "服務小區換了幾次(換手次數)。換手太頻繁通常代表裝置正好"
                "移動在多個小區交界處,訊號品質也容易跟著不穩定。"
            )
            handover_df = count_handovers(df)
            st.dataframe(handover_df.sort_values("handover_count", ascending=False), use_container_width=True)

    # ---------------- 時間序列 ----------------
    with tab_timeseries:
        st.markdown(
            "這頁看的是**單一小區隨時間的變化**:同一個小區在不同時段(例如上下班"
            "尖峰、深夜離峰)訊號跟負載會不一樣,選一個小區就能看出它一天下來的起伏,"
            "適合用來找「什麼時候特別容易出問題」。"
        )

        cell_ids = sorted(df["cell_id"].unique())
        selected_cell = st.selectbox("選擇小區", cell_ids)

        cell_ts = (
            df[df["cell_id"] == selected_cell]
            .groupby("timestamp")
            .agg(
                rsrp_dbm=("rsrp_dbm", "mean"),
                sinr_db=("sinr_db", "mean"),
                load_pct=("load_pct", "mean"),
            )
            .reset_index()
        )

        fig_rsrp = px.line(cell_ts, x="timestamp", y="rsrp_dbm", title=f"{selected_cell} — RSRP 隨時間變化")
        fig_sinr = px.line(cell_ts, x="timestamp", y="sinr_db", title=f"{selected_cell} — SINR 隨時間變化")
        fig_load = px.line(cell_ts, x="timestamp", y="load_pct", title=f"{selected_cell} — 負載隨時間變化")

        st.plotly_chart(fig_rsrp, use_container_width=True, config={"displayModeBar": False})
        st.caption("訊號強度是否隨時間忽高忽低。如果某個時段明顯下滑,可能跟當時的環境或距離有關。")

        st.plotly_chart(fig_sinr, use_container_width=True, config={"displayModeBar": False})
        st.caption("干擾程度是否隨時間變化。曲線越常往下掉,代表那個時段鄰近小區的干擾越明顯。")

        st.plotly_chart(fig_load, use_container_width=True, config={"displayModeBar": False})
        st.caption("忙碌程度隨時間的變化,通常會看到上下班時段有明顯的高峰。")

        st.subheader("簡易趨勢預測(線性迴歸)")
        st.caption(
            "用最簡單的線性迴歸模型,依這個小區的歷史資料外推未來幾個時間點的走勢。"
            "只是示範「拿到時間序列後可以怎麼接一個最基本的預測模型」,不是正式的"
            "容量規劃工具——資料只有一天份,線性外推的準確度有限,僅供參考。"
        )
        forecast_metric = st.selectbox(
            "要預測哪個指標", ["load_pct", "rsrp_dbm", "sinr_db"],
            format_func=lambda x: {"load_pct": "負載(%)", "rsrp_dbm": "RSRP(dBm)", "sinr_db": "SINR(dB)"}[x],
        )
        forecast_periods = st.slider("往未來預測幾個時間點", 3, 24, 12)

        try:
            direction = trend_direction(cell_ts, forecast_metric)
            # 從資料本身推算時間間隔,而不是寫死 5 分鐘——路測/群眾外包資料
            # 用的是更細的間隔(預設 1 分鐘),寫死會讓預測的時間軸跟實際不符
            ts_diffs = cell_ts["timestamp"].diff().dropna()
            inferred_step_minutes = (
                int(ts_diffs.median().total_seconds() / 60) if len(ts_diffs) > 0 else 5
            )
            forecast_df = forecast_series(
                cell_ts, forecast_metric, periods=forecast_periods,
                time_step_minutes=max(inferred_step_minutes, 1),
            )
            # px.line 用 color="is_forecast" 分兩條線畫,Plotly 不會自動把
            # 「歷史」跟「預測」兩條線接在一起,畫出來會有一段空隙看起來斷開。
            # 這裡把歷史資料的最後一筆,複製一份標成 is_forecast=True 插在
            # 預測資料最前面,讓兩條線在銜接點重疊,視覺上才會連成一條線。
            last_history_row = forecast_df[~forecast_df["is_forecast"]].iloc[[-1]].copy()
            last_history_row["is_forecast"] = True
            plot_df = pd.concat(
                [forecast_df[~forecast_df["is_forecast"]], last_history_row,
                 forecast_df[forecast_df["is_forecast"]]],
                ignore_index=True,
            )
            fig_forecast = px.line(
                plot_df, x="timestamp", y=forecast_metric, color="is_forecast",
                title=f"{selected_cell} — {forecast_metric} 趨勢預測(目前判斷:{direction})",
                color_discrete_map={False: PRIMARY_COLOR, True: WARN_COLOR},
            )
            st.plotly_chart(fig_forecast, use_container_width=True, config={"displayModeBar": False})
            st.caption("藍線是歷史資料,橘線是模型外推的預測值;判斷趨勢用的是同一個線性迴歸模型的斜率方向。")
        except ValueError as e:
            st.warning(f"目前資料不足以預測:{e}")

    # ---------------- 熱區分析 ----------------
    with tab_hotspot:
        st.markdown(
            "這頁在找**問題集中的地方**,用兩種不同的方法各自看一遍:第一種是把"
            "有問題的量測點在地圖上聚成一堆一堆(自然分群),第二種是直接看哪個"
            "小區的平均數字不好看(門檻判斷)。兩種方法互相參考,比只看一種更準。"
        )

        st.subheader("以聚類方式偵測地理熱區(DBSCAN)")
        st.caption(
            "把「訊號差或負載高」的量測點,依照彼此的地理距離自動分成一群一群,"
            "群集樣本數越多,代表這個區域的問題點越密集,越值得優先現場勘查。"
        )
        hotspot_cfg = working_config["hotspot"]
        clusters = hotspot_detection.detect_hotspots_dbscan(
            df,
            eps_km=hotspot_cfg["dbscan_eps_km"],
            min_samples=hotspot_cfg["dbscan_min_samples"],
        )
        if clusters.empty:
            st.info("目前資料中未偵測到明顯熱區群集。")
        else:
            st.dataframe(clusters, use_container_width=True)
            clusters_labeled = clusters.copy()
            clusters_labeled["cluster_label"] = "熱區 " + clusters_labeled["cluster_id"].astype(str)
            fig_hot = _scatter_on_map(
                data_frame=clusters_labeled,
                lat="center_lat",
                lon="center_lon",
                size="sample_count",
                color="sample_count",
                text="cluster_label",
                color_continuous_scale="Reds",
                zoom=11,
                height=450,
                style=map_style,
            )
            fig_hot.update_layout(margin=dict(l=0, r=0, t=0, b=0))
            st.plotly_chart(fig_hot, use_container_width=True, config={"displayModeBar": False})
            st.caption("顏色越深、點越大,代表這個熱區聚集的問題樣本越多,越優先處理。")

        st.subheader("以小區平均值判斷的問題小區(門檻法,快速版)")
        st.caption(
            "不看地理位置聚類,直接列出「平均數字超過門檻」的小區(門檻可在左側"
            "側邊欄調整),適合想快速抓出「哪幾個小區有問題」而不用管它們是不是"
            "彼此靠近。"
        )
        threshold_hot = hotspot_detection.detect_hotspots_threshold(
            per_cell,
            rsrp_poor_dbm=thresholds["rsrp_poor_dbm"],
            sinr_poor_db=thresholds["sinr_poor_db"],
            load_high_pct=thresholds["load_high_pct"],
        )
        st.dataframe(threshold_hot, use_container_width=True)

    # ---------------- 瓶頸與建議 ----------------
    with tab_bottleneck:
        st.markdown(
            "這頁幫你**排出優先順序**:把負載、訊號強度、干擾程度三個因素綜合"
            "算成一個 0 到 100 的分數,分數越高代表這個小區越需要優先處理,"
            "並附上針對性的建議動作。"
        )

        scored = bottleneck_analysis.score_bottleneck(per_cell)
        with_reco = recommendations.generate_recommendations(scored)

        top_n = st.slider("顯示前 N 名瓶頸小區", min_value=3, max_value=len(with_reco), value=min(5, len(with_reco)))
        top_bottlenecks = with_reco.head(top_n)

        st.subheader(f"Top {top_n} 瓶頸小區")
        st.caption(
            "分數計算方式:負載佔 40%、訊號干擾比(SINR)佔 35%、訊號強度(RSRP)佔 25%,"
            "點開下面每一筆可以看到詳細數字跟建議動作。"
        )
        for _, row in top_bottlenecks.iterrows():
            with st.expander(f"{row['cell_id']} — 瓶頸分數 {row['bottleneck_score']}"):
                st.write(
                    f"平均 RSRP: {row['avg_rsrp_dbm']} dBm ｜ "
                    f"平均 SINR: {row['avg_sinr_db']} dB ｜ "
                    f"平均負載: {row['avg_load_pct']} %"
                )
                st.markdown("**建議:**")
                for tip in row["recommendations"]:
                    st.markdown(f"- {tip}")

    # ---------------- 報告下載 ----------------
    with tab_report:
        st.markdown(
            "這頁把前面幾個分頁看到的東西,整理成一份**可以帶著走、給別人看**的"
            "報告檔案,不用截圖也不用一頁一頁點給人看。"
        )
        st.subheader("產生分析報告")
        st.write(
            "報告內容包含:資料範圍、整體統計、Top 瓶頸小區表格、瓶頸分數長條圖與建議清單,"
            "支援 Markdown 與 PDF 兩種格式。"
        )
        st.caption("Markdown 適合貼到筆記軟體或 GitHub;PDF 適合直接列印或寄給不會用 Markdown 的人。")

        col_md, col_pdf = st.columns(2)

        with col_md:
            if st.button("📄 產生 Markdown 報告"):
                st.session_state["report_text"] = build_markdown_report(df, per_cell, working_config)

            if "report_text" in st.session_state:
                st.download_button(
                    label="⬇️ 下載報告(Markdown)",
                    data=st.session_state["report_text"],
                    file_name="signal_quality_report.md",
                    mime="text/markdown",
                )

        with col_pdf:
            if st.button("📕 產生 PDF 報告"):
                st.session_state["report_pdf"] = build_pdf_report(df, per_cell, working_config)

            if "report_pdf" in st.session_state:
                st.download_button(
                    label="⬇️ 下載報告(PDF)",
                    data=st.session_state["report_pdf"],
                    file_name="signal_quality_report.pdf",
                    mime="application/pdf",
                )

        if "report_text" in st.session_state:
            with st.expander("預覽 Markdown 報告內容"):
                st.markdown(st.session_state["report_text"])


if __name__ == "__main__":
    main()
