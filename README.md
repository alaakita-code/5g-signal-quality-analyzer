# 5G/4G 行動網路訊號品質分析儀

以模擬資料展示 4G/5G 基地台訊號品質(RSRP/RSRQ/SINR)、負載狀況的
統計分析、熱區偵測、瓶頸識別與最佳化建議,並提供互動式 Streamlit 儀表板
與一鍵 Markdown 報告輸出。

> 目前資料來源為模擬資料,尚未接上真實路測資料集。

## 專案簡介

- **輸入**:四種資料來源可選:①模擬資料產生器(可在儀表板側邊欄即時調整
  參數,不需重開)②案例演示情境(因無法取得真實電信商 OSS 資料,改用
  經過設計的具名情境重現特定實務場景)③模擬路測/群眾外包(模擬會移動的
  裝置,而非固定量測點)④上傳自己的 CSV(需符合欄位格式,見下方「上傳
  CSV 格式」說明);亦保留 OpenCelliD 真實基地台位置的匯入骨架(尚未實作
  API 串接)。
- **處理**:統計分析、地理熱區偵測(DBSCAN 聚類 / 門檻法)、
  瓶頸小區識別(負載 + SINR + RSRP 綜合評分)、規則式最佳化建議、
  離散品質分類(良好/普通/需關注)、簡易趨勢預測(線性迴歸)、
  頻寬/MIMO 對理論吞吐量的影響估算。
- **輸出**:Streamlit 互動式儀表板(含小區 ID 標籤、品質分類上色地圖)
  + 一鍵產生 Markdown/PDF 分析報告(PDF 含瓶頸分數長條圖)+ 不依賴
  Streamlit 的命令列報告工具(可排程自動執行)。

## 案例演示情境

因為沒有真實電信商 OSS 資料可用(涉及隱私與商業機密,無法取得真實
cell ID),`src/data_generator/scenarios.py` 提供四組具名情境,用經過
設計的模擬參數組合重現特定類型的實務場景,而非單純隨機模擬:

| 情境 | 說明 | 預期呈現 |
|---|---|---|
| 🏙️ 都會核心尖峰壅塞案例 | 市中心商業區,基地台密集但負載逼近滿載 | 負載偏高,訊號本身正常 |
| 🏞️ 偏鄉覆蓋不足案例 | 基地台稀疏、涵蓋半徑大,用戶量不高 | RSRP 明顯偏低,負載不是問題 |
| 📡 鄰區干擾異常案例 | PCI 規劃衝突/同頻干擾,RSRP、負載都正常 | SINR 明顯劣化,拖累整體品質分數 |
| 🎉 節慶活動瞬間湧入案例 | 大型活動現場,平時正常但尖峰時段暴衝 | 少數時段負載急遽升高(建議看時間序列分頁) |

在儀表板側邊欄選擇「案例演示情境」即可切換,每個情境都附有敘述文字
說明模擬邏輯背後對應的實務情境。**這仍然是模擬資料,不是真實案例**,
敘述文字只是幫助理解參數設計的用意。

## 模擬路測/群眾外包資料

跟「模擬資料」的差別在於產生方式:「模擬資料」是每個小區周圍固定散佈
一批靜止量測點,這裡則是模擬一批**會移動的裝置**(路測車、或群眾外包
App 使用者手機),隨時間沿隨機路徑移動,移動過程中自動連到最近的基地台
(模擬換手)。輸出欄位與模擬資料相同(多一個 device_id 欄位),可直接
沿用所有既有的分析邏輯,不需要另外改分析程式碼。

側邊欄可調整裝置數量與移動速度範圍;總覽分頁會額外顯示每個裝置的
換手次數統計。這仍然是模擬資料,不是真實路測/群眾外包資料集。

## 上傳 CSV 格式

在儀表板側邊欄選擇「上傳 CSV」,可用自己的量測資料取代模擬資料,
需包含以下欄位(可參考 `data/sample_upload_format.csv` 範例檔):

| 欄位 | 說明 |
|---|---|
| timestamp | 量測時間 |
| cell_id | 基地台(小區)編號 |
| site_lat / site_lon | 基地台經緯度 |
| sample_lat / sample_lon | 量測點經緯度 |
| distance_m | 量測點與基地台距離(公尺) |
| rsrp_dbm / rsrq_db / sinr_db | 訊號品質指標 |
| load_pct | 小區負載百分比 |
| num_users | 同時在線用戶數 |

## 安裝與執行

```bash
# 1. 安裝相依套件
pip install -r requirements.txt

# 2. (可選)手動產生模擬資料 CSV,存放於 data/raw/
python src/data_generator/simulate_cell_data.py \
    --config configs/default_config.yaml \
    --output data/raw/simulated_cell_data.csv

# 3. 啟動儀表板(儀表板本身也會即時產生模擬資料,不強制需要先跑步驟 2)
streamlit run src/dashboard/app.py
```

啟動後瀏覽器會開啟 `http://localhost:8501`。

## 部署

用 Streamlit Community Cloud 部署最簡單:

1. 推上 GitHub(私有 repo 即可)
2. 到 [share.streamlit.io](https://share.streamlit.io) 用 GitHub 帳號登入
3. 選擇這個 repo,主檔案路徑填 `src/dashboard/app.py`

`runtime.txt` 與 `.streamlit/config.toml` 已配置好給 Streamlit Cloud 使用。

也可以用容器部署(本機 Docker、或 Render / Railway 等平台),
`docker/Dockerfile` 已提供。

> 注意:Streamlit 需要長駐的 Python 進程,無法部署在 Cloudflare
> Pages/Workers 這類無狀態的 edge function 平台上。

## 模擬資料說明

模擬資料基於簡化版對數距離路徑損耗模型:

- 基地台位置:隨機散佈於設定檔指定的地理中心與半徑範圍內
- RSRP:依距離、路徑損耗指數、陰影衰落與小尺度衰落雜訊計算
- RSRQ / SINR:依 RSRP 概略推導並加入隨機雜訊(僅供模擬示範,
  非精確通訊理論公式)
- 負載:依尖峰/離峰時段設定不同的隨機範圍

所有參數皆可於 `configs/default_config.yaml` 調整。

## 儀表板功能

| 分頁 | 內容 |
|---|---|
| 📊 總覽 | 關鍵指標卡片(含估計吞吐量)+ 小區地理分佈地圖(品質分類離散上色 + 小區 ID 標籤)+ 頻寬/MIMO 敏感度圖表 + 資料下載 |
| 📈 時間序列 | 選定小區,觀察 RSRP/SINR/負載隨時間變化 + 簡易線性迴歸趨勢預測 |
| 🔥 熱區分析 | DBSCAN 地理聚類熱區(含群集標籤)+ 門檻法問題小區列表 |
| 🧩 瓶頸與建議 | Top N 瓶頸小區與對應規則式建議 |
| 📄 報告下載 | 一鍵產生並下載 Markdown / PDF 分析報告(PDF 含瓶頸分數長條圖) |

側邊欄可即時調整:資料來源(模擬資料/案例演示情境/模擬路測群眾外包/
上傳 CSV)、模擬參數(小區數量、路徑損耗指數、發射功率等,僅模擬資料
模式)、判斷門檻(RSRP/SINR/負載門檻)、頻寬與 MIMO 天線數,調整後
立即套用到所有分頁,不需重開。

## 趨勢預測

時間序列分頁提供一個簡易的線性迴歸預測(`src/analysis/forecasting.py`):
依選定小區的歷史資料,外推未來幾個時間點的走勢,並判斷大致是上升、
下降還是持平。這是教學/展示用的簡化模型,只用時間索引當特徵,沒有
考慮日期型態、節慶等真實世界因素,不是正式的容量規劃工具。

## 頻寬與 MIMO 影響估算

`src/analysis/throughput.py` 用簡化版 Shannon 容量公式,依 SINR、頻寬、
MIMO 天線數估算理論吞吐量上限,並提供「只改頻寬」「只改天線數」的
敏感度比較圖表(總覽分頁的「頻寬/MIMO 對吞吐量的影響」區塊)。這不是
精確的 3GPP 鏈路預算計算,沒有考慮實際調變編碼機制、通道相關性等因素,
只用來示範參數調整對理論吞吐量的影響方向與量級。

## 命令列報告工具與排程自動化

`scripts/generate_report_cli.py` 提供不依賴 Streamlit 的命令列報告產生
方式,適合本機排程(cron)或 CI 環境使用:

```bash
python scripts/generate_report_cli.py \
    --config configs/default_config.yaml \
    --output-dir reports_output \
    --format both

# 也可以指定套用某個案例演示情境
python scripts/generate_report_cli.py --scenario urban_congestion
```

`.github/workflows/scheduled_report.yml` 設定了每日排程(UTC 00:00),
自動執行上述腳本並把報告上傳為 GitHub Actions Artifact(保留 30 天);
也可以在 Actions 頁面手動觸發(workflow_dispatch),並選擇要套用的
案例演示情境。

## 執行自動化測試

```bash
pip install -r requirements.txt
pytest -v
```

測試涵蓋:模擬資料產生器(欄位、數量、數值範圍、可重現性)、統計指標、
品質分類、熱區偵測(標記邏輯 + DBSCAN 聚類)、瓶頸評分與建議產生、
案例演示情境套用邏輯、路測/群眾外包資料產生與換手統計、趨勢預測、
吞吐量估算、Markdown/PDF 報告產生(含 PDF 檔頭簽章驗證)。
共 51 項測試。

`.github/workflows/tests.yml` 設定了 GitHub Actions,push 或發 PR 到
main/master 分支時會自動在 Python 3.11 / 3.12 上跑一次 pytest。

## 分析報告範例

報告內容包含:資料時間範圍、整體統計、Top 瓶頸小區表格、
逐一小區的建議清單。支援兩種輸出格式:

- **Markdown**(`build_markdown_report`):輕量,適合嵌入 GitHub README
- **PDF**(`build_pdf_report`,使用 reportlab):明亮簡潔版面,適合正式交付,
  內嵌 `assets/fonts/WenQuanYiZenHei-Subset.ttf` 繁體中文子集字型(見該資料夾
  `LICENSE-fonts.txt`),確保任何 PDF 檢視器都能正確顯示中文,不會變成空心方塊;
  另外用 reportlab 內建繪圖元件畫出瓶頸分數長條圖,不依賴 matplotlib 或任何
  外部圖片產生流程

## 專案結構

```
5g-signal-quality-analyzer/
  README.md
  requirements.txt
  pytest.ini
  .github/workflows/
    tests.yml               # CI:push/PR 自動跑 pytest
    scheduled_report.yml    # 排程:每日自動產生報告並上傳 Artifact
  assets/fonts/                 # PDF 報告用的繁體中文子集字型
  scripts/
    generate_report_cli.py  # 不依賴 Streamlit 的命令列報告產生工具
  data/
    raw/                        # 原始資料(模擬產生或匯入)
    processed/                  # 處理後資料(目前骨架階段尚未使用)
    sample_upload_format.csv    # CSV 上傳格式範例
  src/
    data_generator/
      simulate_cell_data.py     # 模擬資料產生(固定量測點)
      simulate_drive_test.py    # 模擬路測/群眾外包資料產生(移動裝置)
      load_opencellid.py        # OpenCelliD 真實資料匯入骨架
      scenarios.py               # 案例演示情境庫
    analysis/
      metrics.py, hotspot_detection.py, bottleneck_analysis.py,
      recommendations.py        # 統計、品質分類、熱區、瓶頸、建議邏輯
      forecasting.py             # 簡易線性迴歸趨勢預測
      throughput.py               # 頻寬/MIMO 吞吐量估算
    dashboard/                   # Streamlit 前端(資料來源切換、互動參數)
    reports/                     # 報告產生(Markdown + PDF)
  tests/
    conftest.py                 # 共用 fixture(縮小版模擬資料)
    test_*.py                   # 各模組單元測試(51 項)
  notebooks/
    explore_data.ipynb
  configs/
    default_config.yaml
  docker/
    Dockerfile
```

## 已知限制

- RSRQ/SINR 由 RSRP 概略推導,非嚴謹通訊理論公式,僅供展示用途
- 掉話率為 SINR-based proxy 指標,非真實 RRC/Call trace 掉話率
- OpenCelliD 真實資料匯入模組(`load_opencellid.py`)尚未串接下載 API,
  僅提供清洗邏輯骨架
- 案例演示情境是經過設計的模擬參數組合,不是真實電信商資料,
  敘述文字僅供理解參數設計邏輯用途
- 側邊欄互動參數調整僅涵蓋部分模擬參數(小區數量、路徑損耗指數、
  發射功率、判斷門檻),尚未涵蓋全部 `configs/default_config.yaml` 的欄位
  (如陰影衰落標準差、尖峰時段設定等仍需改設定檔)

## 疑難排解

**PDF 報告中文字顯示成空心方塊**
reportlab 內建的 CID 字型不會真正嵌入 PDF,多數 PDF 檢視器因此無法顯示。
本專案改用內嵌的 `assets/fonts/WenQuanYiZenHei-Subset.ttf` 字型子集,
任何 PDF 檢視器都能正確顯示。若修改 `recommendations.py` 或報告樣板時
加入了字型子集裡沒有的中文字,該字仍會顯示不出來,需要重新執行字型
子集抽取(參考 `assets/fonts/LICENSE-fonts.txt` 說明)。

**總覽/熱區分析頁的地圖只顯示底色、看不到街道,或完全空白**
Plotly 6.x 的地圖元件(`scatter_map`)底層是 MapLibre GL,需要瀏覽器能跑
WebGL、並且能動態載入對應的 JS 模組,還要連到外部圖磚伺服器下載底圖。
部分公司網路/資安政策會擋掉動態載入的 JS 模組,這種情況下連 `white-bg`
(不需要圖磚,但仍需要地圖引擎本身)也會是空白——代表問題不是「圖磚
下載被擋」,而是連地圖引擎的 JS 模組載入都被擋了。

排除方式:把 `configs/default_config.yaml` 的 `dashboard.map_style`
依序試過三種:
1. `open-street-map`(完整街道底圖)
2. `white-bg`(空白底圖,仍用同一套地圖引擎)
3. `plain_scatter`(完全不用地圖元件,把經緯度當一般座標畫散佈圖)

如果 1、2 都空白但 3 正常顯示,代表該環境擋掉了地圖引擎的動態載入,
建議固定使用 `plain_scatter`(目前預設值);沒有街道背景,但不依賴
任何外部資源,任何環境都能顯示。

## 可延伸方向

- 接入真實路測 / crowdsourcing 資料集(目前只有模擬版本)
- 精確的 3GPP 鏈路預算與 MCS 對應表(目前吞吐量估算是簡化版 Shannon 公式)
- 更完整的時間序列預測模型(目前是最基本的線性迴歸,可換成
  ARIMA、Prophet 等真正的時間序列模型)
- OpenCelliD 真實基地台位置串接下載 API(目前只有清洗邏輯骨架)
# 5g-signal-quality-analyzer
