# 部署紀錄:GitHub → GitHub Actions → Streamlit Community Cloud

這份文件記錄把這個專案從本機推上 GitHub、確認 CI 跑得動、再部署到
Streamlit Community Cloud 的完整流程,包含實際遇到的狀況與怎麼排除。
以後要重新部署,或想拿這套流程套用到別的專案,照著做就好。

**目前上線網址:** https://alaakita-5g-signal-quality-analyzer.streamlit.app/

---

## 第一階段:推上 GitHub

### 前置需求
- 本機已安裝 Git
- GitHub 上已建立好空的(或已有 README 的)repo

### 指令流程

```bash
# 1. 初始化 git(如果資料夾已經是 git repo,這行會顯示
#    "Reinitialized existing Git repository",不是錯誤,正常繼續)
git init

# 2. 確認 remote 有沒有設定過
git remote -v
# 如果沒有輸出,代表還沒設定,執行:
git remote add origin https://github.com/<你的帳號>/<repo名稱>.git
# 如果顯示 "error: remote origin already exists",代表已經設定過,
# 用下面這行確認網址對不對,不對再用 set-url 修正:
git remote set-url origin https://github.com/<你的帳號>/<repo名稱>.git

# 3. 分支名稱統一用 main(GitHub 現在預設也是 main,不是舊版的 master)
git branch -M main

# 4. 把所有檔案加入版控(這一步最容易漏做,一定要打)
git add .

# 5. 檢查真的有東西被加進去了,不要跳過這一步
git status
# 應該要看到「Changes to be committed」下面列出一大串 new file:
# .github/、src/、tests/、configs/ 等,不是空的

# 6. 提交
git commit -m "Add project files"

# 7. 推上 GitHub
git push -u origin main
```

### 這次實際遇到的狀況

| 狀況 | 原因 | 排除方式 |
|---|---|---|
| `git remote add origin` 報錯「already exists」 | 資料夾之前已經跟這個 repo 連過(可能 GitHub 建 repo 時勾了自動產生 README) | 用 `git remote -v` 確認網址對,對的話直接跳過這步 |
| `git push -u origin master` 報錯「src refspec master does not match any」 | 打錯分支名稱,前面已經用 `git branch -M main` 改名成 main,本地根本沒有 master 分支 | 改打 `git push -u origin main` |
| 第一次 `git push` 成功,但只有 3 個物件、6.36 KiB | `git add .` 那一步其實沒有真的執行到,只有 README.md 被追蹤 | 用 `git ls-files` 確認實際被追蹤的檔案清單,發現只有 README.md;重新確實執行 `git add .` → `git status` 確認清單不是空的 → 再 commit、push 一次,這次 43 個檔案、88.25 KiB 才是正確結果 |

### 驗證清單
- [ ] `git ls-files` 列出的檔案清單涵蓋 `src/`、`tests/`、`configs/`、`.github/` 等全部資料夾,不是只有 README.md
- [ ] `git push` 的輸出裡,物件數量(objects)與資料大小(KiB)跟專案實際大小相符,不是異常地小
- [ ] 到 GitHub 網頁上實際確認檔案結構,尤其是 `src/dashboard/app.py` 跟 `assets/fonts/*.ttf` 這兩個關鍵檔案存在

---

## 第二階段:確認 GitHub Actions 正常運作

專案裡有兩個 workflow:

| 檔案 | 觸發方式 | 用途 |
|---|---|---|
| `.github/workflows/tests.yml` | push / PR 到 main 分支時自動觸發 | 在 Python 3.11 / 3.12 上跑 pytest(51 項測試) |
| `.github/workflows/scheduled_report.yml` | 每日 UTC 00:00 排程,或手動觸發(workflow_dispatch) | 執行 `scripts/generate_report_cli.py`,產生報告並上傳成 Artifact |

### 確認步驟

1. 到 repo 的 **Actions** 分頁,push 完成後應該會自動出現一筆
   「自動化測試 (pytest)」的執行紀錄,等它跑完看是綠色勾勾(成功)
   還是紅色叉叉(失敗)
2. 想手動測試排程報告 workflow:左側選單點「排程自動產生分析報告」→
   右上角「Run workflow」下拉按鈕 → 情境 id 欄位留空 → 點綠色確認鈕
3. 等待執行完成(約 45 秒),點進該筆紀錄,確認:
   - Status 顯示 **Success**
   - 最下方 **Artifacts** 區塊有一個 `signal-quality-report-<數字>` 可下載
4. 下載 Artifact,解壓後應該有一份 `.md` 和一份 `.pdf`,實際打開確認
   內容(統計數字、瓶頸長條圖、中文顯示)都正常,不是只看檔案存在就算數

### 這次實際驗證結果
- `tests.yml`:Success,45 秒完成(這是這批測試第一次在真實 CI 環境
  被 `pytest` 指令實際執行,先前只在開發沙盒手動驗證過邏輯)
- `scheduled_report.yml` 手動觸發:Success,45 秒完成,產出
  `signal-quality-report-33961383720`(30.6 KB),下載後確認 PDF
  長條圖、中文字型、Markdown 內容格式都正常

> Actions 執行紀錄裡出現的「Node.js 20 is deprecated」是 GitHub 平台
> 自己的維護提示(底層 actions/checkout、actions/setup-python 等用的
> Node.js 版本要淘汰),跟這個專案的程式碼或 workflow 設定無關,可以
> 忽略,GitHub 之後會自動處理。

---

## 第三階段:部署到 Streamlit Community Cloud

### 步驟
1. 到 [share.streamlit.io](https://share.streamlit.io) 用 GitHub 帳號登入
2. 選擇這個 repo(`<你的帳號>/5g-signal-quality-analyzer`)
3. 主檔案路徑填 `src/dashboard/app.py`
4. 部署完成後會拿到一個 `*.streamlit.app` 的網址

專案裡已經準備好 Streamlit Cloud 需要的設定檔,不用額外處理:
- `requirements.txt` — 相依套件清單
- `runtime.txt` — 指定 Python 3.11
- `.streamlit/config.toml` — 鎖定明亮主題、限制上傳檔案大小 50MB

### 驗證清單
- [ ] 網址能正常開啟,標題「📶 5G/4G 行動網路訊號品質分析儀」正確顯示
- [ ] 側邊欄四種資料來源(模擬資料/案例演示情境/模擬路測群眾外包/上傳CSV)
      都能切換
- [ ] 地圖(plain_scatter 模式)能顯示資料點,不是空白
- [ ] PDF/Markdown 報告下載功能正常,PDF 中文字顯示正常
- [ ] 趨勢預測、頻寬與 MIMO 敏感度圖表能正常顯示

### 目前上線結果
**https://alaakita-5g-signal-quality-analyzer.streamlit.app/**

---

## 之後要更新程式碼時的流程

改完程式碼後,重複第一階段的 add → commit → push 三步就好:

```bash
git add .
git status   # 確認要進版控的檔案清單正確
git commit -m "說明這次改了什麼"
git push
```

push 之後:
- `tests.yml` 會自動重跑一次,去 Actions 分頁確認還是綠色
- Streamlit Community Cloud 通常會自動偵測到 GitHub 有新的 commit,
  幾分鐘內自動重新部署,不需要手動觸發
