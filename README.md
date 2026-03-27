# SNKRDUNK Intelligence Dashboard

TCG（Trading Card Game）市場分析平台，專為從 [SNKRDUNK](https://snkrdunk.com/) 購買卡片的投資者設計。輸入卡片網址即可取得即時價格、歷史走勢、成本試算與投資建議。

## 核心功能

### 卡片分析

貼入任一 SNKRDUNK 卡片 URL，系統自動爬取並呈現：

- **各等級最低價** — PSA 10 / PSA 9 / Raw 等，一目了然
- **歷史成交紀錄** — 依等級篩選，最多顯示 1000 筆交易
- **價格趨勢圖** — 自動清洗捆綁交易離群值，以移動中位數（Moving Median）繪製平滑趨勢線
- **成交量圖** — 每日交易量長條圖，觀察市場熱度
- **購入成本試算** — 自動帶入卡片價格，計算手續費（3.5%）、國際運費、關稅，換算 TWD 總成本
- **即時匯率** — USD/TWD、JPY/TWD 匯率自動抓取

### 瀏覽系列

不知道要分析哪張卡？直接瀏覽熱門系列：

| 分類 | 模式 | 說明 |
|------|------|------|
| ONE PIECE | 品牌瀏覽 | Box & Pack / Single Card 分類 |
| Pokemon | 品牌瀏覽 | Box & Pack / Single Card 分類 |
| Luffy SEC | 關鍵字搜尋 | 搜尋所有 Monkey.D.Luffy SEC 卡片 |

支援 Featured / Price Low-High / Price High-Low 排序，點擊任一卡片直接跳轉分析。

### 分享圖片

一鍵生成精美的分析摘要圖片（使用 html2canvas 截圖），包含：

- 卡片圖片與基本資訊
- PSA 10 / Raw 最低價
- 7 天價格趨勢圖（經清洗 + MA 平滑，與主圖表一致）
- 購入成本試算明細
- AI 投資建議
- QR Code 連結原始頁面

### Telegram 推播

將分析摘要推送至 Telegram 頻道，方便團隊或社群共享資訊。

## 技術架構

```
前端 (SPA)                    後端 (FastAPI)                SNKRDUNK
index.html ──POST──> /api/scrape ────> snkrdunk.com/en/v1/*
                     /api/browse ───>  (brandId 瀏覽)
                     /api/search ───>  (keyword 搜尋)
                     /api/image-proxy  (圖片代理，解決 CORS)
```

| 層級 | 技術 |
|------|------|
| 前端 | 純 HTML/CSS/JS、Chart.js、html2canvas、QRCode.js |
| 後端 | Python FastAPI、urllib.request（無 requests 依賴） |
| 部署 | Vercel Serverless（主要）、Render（備用） |

### 關鍵演算法

**捆綁交易偵測**（`cleanForTrend`）— SNKRDUNK 上常見一次成交多張卡片（如 10 張一起賣），導致成交價是單張的 N 倍。系統使用 IQR 離群值偵測 + 局部視窗雙重驗證，自動嘗試 2x-20x 倍數修正，還原真實單張價格。

**移動中位數**（`calcMA`）— 以滑動窗口取中位數（而非平均值），對離群值有更強的抗干擾能力，產出平滑的價格趨勢線。

**價格修正** — 自動偵測單卡 vs 整盒商品，對單卡價格套用 -$10 USD 修正（補償美國 IP 與台灣 IP 的含稅差異）。

## 本機開發

```bash
# 安裝依賴
pip install -r requirements.txt

# 啟動開發伺服器
uvicorn main:app --reload --port 8000

# 開啟瀏覽器
open http://localhost:8000
```

## 部署

### Vercel（主要）

專案已透過 GitHub 連接 Vercel，push 到 main 即自動部署。

環境變數需在 Vercel Dashboard 設定：
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHANNEL_ID`

### Render（備用）

使用 `render.yaml` 和 `Procfile` 設定，Python 3.12 運行。

## 專案結構

```
snkrdunk_app/
  index.html          # 前端 SPA（Vercel 靜態服務）
  static/index.html   # 前端 SPA（main.py 本機服務）
  api/index.py        # Vercel Serverless FastAPI
  main.py             # 本機/Render FastAPI
  requirements.txt
  vercel.json
  render.yaml
  Procfile
  AGENTS.md           # AI Agent 詳細技術文件
```
