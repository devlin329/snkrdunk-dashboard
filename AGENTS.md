# AGENTS.md — SNKRDUNK Intelligence Dashboard

> 給 AI Agent 或協作開發者的完整專案說明文件。
> 本文件描述專案的所有功能、架構、UI/UX 設計與開發規則。

---

## 專案概覽

**SNKRDUNK Intelligence** 是一款專為交易卡（Trading Card）投資者設計的市場分析平台。
目標用戶是台灣交易卡投資者，從 SNKRDUNK（日本卡牌交易平台）購買卡片作為投資標的。

- **GitHub**: 已上傳，使用 Git 版本控制
- **部署**: Vercel（Serverless Python）
- **備用部署設定**: Render（`render.yaml`）
- **版本**: v1.0.0
- **作者**: devcharles

---

## 技術架構

### 後端

| 檔案 | 說明 |
|------|------|
| `api/index.py` | Vercel Serverless Function 入口（FastAPI） |
| `main.py` | Render / 本機開發用 FastAPI 應用（功能與 api/index.py 相同） |
| `requirements.txt` | 依賴：`fastapi`、`uvicorn[standard]` |
| `vercel.json` | Vercel 路由設定，所有 `/api/*` 請求導向 `/api` |
| `render.yaml` | Render 部署設定（Python 3.12） |
| `Procfile` | 備用啟動指令（Render 用） |

**Framework**: FastAPI (Python)
**HTTP Client**: `urllib.request`（不依賴 `requests` 函式庫）

### 前端

| 檔案 | 說明 |
|------|------|
| `static/index.html` | 主要前端頁面（Single Page Application） |
| `index.html` | 根目錄複本（Vercel 靜態服務用） |
| `static/logo.png` | 品牌 Logo（PNG） |
| `static/logo.svg` | 品牌 Logo（SVG） |
| `static/favicon.svg` | 瀏覽器分頁圖示 |

**UI 技術棧**:
- 純 HTML + CSS + Vanilla JavaScript（無框架）
- `Chart.js` — 價格趨勢圖、成交量圖
- `chartjs-plugin-annotation` — 圖表高/低點標註線
- `html2canvas` — 截圖生成分享圖片
- `QRCode.js` — 分享圖片上的 QR Code
- Google Fonts: `DM Sans`

---

## 後端 API 端點

所有端點定義於 `api/index.py`，與 `main.py` 同步。

### `POST /api/scrape`

**功能**: 爬取指定 SNKRDUNK 卡片的完整市場數據

**Request Body**:
```json
{ "url": "https://snkrdunk.com/en/trading-cards/706813" }
```

**Response**:
```json
{
  "info": {
    "title": "卡片名稱",
    "subtitle": "系列/擴充包名稱",
    "product_number": "OP01-001",
    "thumbnail_url": "...",
    "used_min_price": "US $50",
    "used_min_price_amount": 50,
    "used_listing_count": 10,
    "released_at": "2023-01-01T00:00:00Z",
    "datalayer_price": 50
  },
  "condition_prices": [
    { "conditionName": "PSA 10", "minPrice": 100, "minPriceFormat": "US $100", "minPriceAmount": 100 }
  ],
  "trading_histories": [
    { "tradedAt": "2024-01-01T00:00:00Z", "price": 95, "priceFormat": "US $95", "condition": "PSA 10", "size": "", "iconUrl": "" }
  ]
}
```

**資料獲取策略（雙軌機制）**:
1. **主要**: 使用 `/en/v1/streetwears/{id}/sale-prices?range=all` API（需要 ENSID cookie）
2. **降級**: 若主要 API 失敗，使用 `/en/v1/streetwears/{id}/trading-histories?page={n}&perPage=100`，最多抓取 10 頁（1000 筆）

**價格修正邏輯**:
- 偵測到「單卡商品」（有 `conditionPrices`，或 `size` 不含 "box"）時，所有價格自動 **-$10 USD**
- 原因：SNKRDUNK 美國 IP 顯示的價格比台灣 IP 高 $10（含稅差異）
- 整盒商品（Box/Pack）跳過此修正

**Response Headers**: `Cache-Control: no-cache, no-store, must-revalidate`（防止 Vercel Edge Cache 快取舊數據）

---

### `GET /api/conditions`

**功能**: 獲取所有可用的卡片等級清單（PSA 10, PSA 9, Raw 等）

**Response**:
```json
{ "conditions": [...] }
```

---

### `POST /api/browse`

**功能**: 瀏覽特定品牌與類別的卡片列表

**Request Body**:
```json
{
  "brand": "onepiece",
  "category_id": 14,
  "page": 1,
  "per_page": 30,
  "sort": "featured"
}
```

**brand 可選值**: `"onepiece"` 或 `"pokemon"`
**sort 可選值**: `"featured"` (popular)、`"price_asc"`、`"price_desc"`
**category_id**: `14` = Box & Pack，`25` = Single Card

**Response**: SNKRDUNK API 的 `tradingCards` 列表

---

### `POST /api/telegram`

**功能**: 推播卡片分析摘要至 Telegram 頻道

**Request Body**:
```json
{ "message": "<b>卡片名稱</b>\n..." }
```

**環境變數**（Vercel / Render 需設定）:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHANNEL_ID`

---

## 前端功能詳解

### 1. 卡片分析（Analyze 視圖）

主要功能入口。使用者貼入 SNKRDUNK 卡片 URL，點擊「Analyze」觸發 `fetchAll()`。

**分析流程**:
1. 呼叫 `/api/scrape` 取得完整市場數據
2. 解析 `rawData`，更新 `allHistories`（全域交易歷史）
3. 渲染以下元件：Hero 卡片資訊、Condition 最低價網格、交易歷史表格、價格趨勢圖、匯率、成本試算器

**卡片資訊 Hero**:
- 顯示卡片圖片、名稱、副標題（系列名）、品番（product_number）、發售日期

**各等級最低價格網格**:
- 單卡：列出所有 condition（PSA 10、PSA 9、Raw 等），PSA 10 高亮顯示
- 整盒商品：顯示 Box 最低成交價

---

### 2. 成交歷史表格（Trading History）

- 條件篩選 Tabs（All / PSA 10 / PSA 9 / Raw...）
- 整盒商品：按 size 分類（1 box / 6 boxes 等）
- 最多顯示 100 筆，依時間倒序排列
- 欄位：交易日期、等級/規格、成交價格

---

### 3. 價格趨勢圖（Price Chart）

**時間範圍**: 1W / 1M / 3M（預設）/ All

**圖表組成**（上下兩個 Chart.js canvas）:
- **上方**（`priceChart`）: 移動中位數趨勢線（MA line）
  - 線條顏色：上漲為綠（`#7a9177`），下跌為橘紅（`#b85c3a`）
  - 上漲/下跌對應不同漸層背景填色
  - 標註線：趨勢高點（綠色虛線）、趨勢低點（紅色虛線）
  - Hover tooltip 同時顯示趨勢價 + 原始成交價
- **下方**（`volChart`）: 每日成交量長條圖（按日聚合）

**圖表統計數據**（圖表下方）:
- Trend High / Trend Low / Latest / Change % / 成交筆數
- 原始成交範圍（含離群值）

**捆綁交易偵測演算法** (`cleanForTrend`):
> 核心功能：自動過濾多張卡合賣導致的異常高價

- **Step 1**: IQR 離群值檢測，計算全域上界 `Q3 + 1.5 × IQR`
- **Step 2**: 對超過上界的價格，收集半徑 15 筆的局部鄰近價格
- **Step 3**: 嘗試 2x～20x 所有整數倍除法，找出修正後最接近局部與全域中位數的倍數
- 修正標準：修正後價格與中位數距離需在 40% 以內
- 權重：局部中位數 60%、全域中位數 40%

**移動中位數（MA）計算** (`calcMA`):
- 視窗大小 = max(3, min(15, floor(數據量 / 8)))
- 中位數而非平均值，抵抗離群值干擾

---

### 4. 即時匯率顯示

- 資料來源: `https://api.exchangerate-api.com/v4/latest/USD`（免費 API）
- 顯示：USD/TWD、JPY/TWD、1 TWD = ? JPY
- 失敗時使用預設值（USD/TWD = 32）
- 匯率用於成本試算器的台幣換算

---

### 5. 購入成本試算器

**自動填入**: 分析後自動填入 PSA 10 最低價（或 Box 最低價）

**計算公式**（以 USD 計）:
```
手續費 = 商品價格 × 3.5%
運費   = 整盒 $26 / 單卡 $19
小計   = 商品價格 + 手續費 + 運費
關稅   = 若商品價格 × USD/TWD 匯率 > 2000 TWD，則 商品價格 × 5%
總計   = 小計 + 關稅
```

顯示每項費用的 USD 與 TWD 雙幣別金額。

---

### 6. 關注清單（Watchlist）

**儲存**: `localStorage`，key = `snkrdunk_watchlist`

**資料結構**（每筆）:
```json
{
  "cardId": "706813",
  "url": "https://snkrdunk.com/en/trading-cards/706813",
  "title": "卡片名稱",
  "thumbnail": "...",
  "usedMinPrice": "US $50",
  "psa10Price": "US $100",
  "addedAt": "2024-01-01T00:00:00.000Z"
}
```

**功能**:
- 加入：分析後點「📌 關注」按鈕
- 移除：滑鼠懸停顯示「✕」按鈕
- 點擊關注項目：自動填入 URL 並重新分析

---

### 7. 投資組合（Portfolio）

**儲存**: `localStorage`，key = `snkrdunk_portfolio`，以 `{cardId}_{condition}` 為 key 的物件

**資料結構**（每筆）:
```json
{
  "card_id": "706813",
  "card_name": "卡片名稱",
  "card_image": "...",
  "condition": "PSA 10",
  "buy_price": 100.00,
  "is_box": false,
  "added_at": "2024-01-01T00:00:00.000Z",
  "include_fee": true,
  "include_shipping": true,
  "include_tariff": true,
  "shipping_amount": 19
}
```

**加入投資組合 Modal**:
- 選擇條件/規格（自動從歷史數據提取可選項）
- 輸入購入價格（USD）
- 費用選項：手續費 3.5%（可勾選）、運費（可自訂金額，可勾選）、關稅 5%（可勾選）
- 實時預覽購入總成本
- 本地購買/面交提示：可取消不需要的費用

**投資組合側邊欄**:
- 總覽：總投資金額、當前估值、總報酬（金額 + 百分比 + 方向圖示）
- 個別卡片：買入價 → 現價、ROI（盈虧金額 + 百分比）
- 顏色：獲利綠色左邊框，虧損紅色左邊框

**市價估算邏輯**:
1. 優先使用 5 分鐘內的快取（`portfolioPriceCache`）
2. 若是當前分析的卡片，使用即時 `allHistories` 數據
3. 其他卡片：背景呼叫 `/api/scrape` 更新（最多同時 3 個並行請求）
4. 市價計算：對應條件的最近 30 筆 → 清洗捆綁交易 → 取前 10 筆中位數

**ROI 分析區**（分析頁底部）:
- 持倉資訊（購入價格、等級）
- 成本明細（逐項顯示各費用）
- 當前估值（市價 + 賣出可得，扣除賣出手續費 3.5%）
- 損益結果（獲利/虧損金額 + ROI %）
- 工具提示：回本需漲到多少錢、獲利 10% 目標價
- 編輯/移除按鈕

---

### 8. 瀏覽系列（Browse 視圖）

**入口**: 頂部導覽 Tab「🗂️ 瀏覽系列」

**品牌**:
- ONE PIECE（🏴‍☠️）
- Pokémon（⚡）

**類別**:
- Box & Pack（category_id = 14）
- Single Card（category_id = 25）

**排序**:
- Featured（熱門，`order=popular`）
- Price: Low to High
- Price: High to Low

**卡片列表格式**:
- 卡片圖片（220px 高）
- 品番、卡片名稱（最多 2 行截斷）、最低價格

**互動**:
- 點擊任意卡片 → 自動切換至「分析卡片」視圖並分析

---

### 9. 分享功能（Share Image）

觸發 `generateShareImage()`，以 `html2canvas` 截取隱藏的 `#shareCard` 模板元素。

**生成的 1080px 寬分享圖包含**:
- 卡片圖片 + 名稱/系列/品番
- PSA 10 中位數價格 + Raw 最低價格網格
- 7 天價格走勢折線圖
- 購入成本試算明細（商品價格、手續費、運費、關稅、總計）
- AI 生成的投資建議文字（依 7 天波動率自動產生）
- 品牌水印 + 時間戳 + 連結 QR Code

**投資建議邏輯** (`generateInvestmentAdvice`):
- 波動率 < 10%：「走勢穩定，建議長期持有」
- 波動率 10~25%：「適度波動，建議分批低買高賣」
- 波動率 > 25%：「波動較大，謹慎評估風險」

**下載檔名**: `SNKRDUNK_{品番}_analysis.png`

---

### 10. Telegram 推播

點擊「🍃 Push to Telegram」，推播卡片摘要至設定的 Telegram 頻道。

**推播內容**:
- 卡片名稱（加粗）
- PSA 10 最低價
- Used 最低價 + 上架數量
- 最近成交紀錄
- 卡片連結

---

## UI/UX 設計系統

### 設計風格

暖色系、仿古典交易卡收藏感。

### CSS 設計 Token（CSS Variables）

```css
--bg: #faf6f1;           /* 主背景（米白） */
--bg-warm: #f5efe7;      /* 暖色輔助背景 */
--card: rgba(255,255,255,0.88); /* 卡片背景 */
--primary: #c0784c;      /* 主色（赭紅） */
--primary-light: #d4956a;
--accent: #8b6f4e;       /* 強調色（棕） */
--rust: #b85c3a;         /* 虧損/警告色 */
--sage: #7a9177;         /* 獲利/成功色（鼠尾草綠） */
--sage-light: #a3bfa0;
--gold: #c9a84c;         /* 金色 */
--plum: #8b5e7b;         /* 紫色 */
--text: #3d3229;         /* 主文字色 */
--text-sec: #7a6b5d;     /* 次要文字 */
--muted: #b0a396;        /* 灰色提示文字 */
--border: rgba(139,111,78,0.12);
--shadow: rgba(139,111,78,0.08);
```

### 佈局結構

```
┌─────────────────────────────────────────────────────────┐
│  左側 Sidebar (240px 固定)   │  主內容區 (flex: 1)         │
│  ┌─────────────────────────┐ │  ┌─────────────────────┐    │
│  │  📌 關注清單             │ │  │  Header + 導覽 Tab  │    │
│  │  ─────────────────────  │ │  │  ─────────────────  │    │
│  │  💼 投資組合             │ │  │  [分析視圖]          │    │
│  │  總覽摘要               │ │  │  URL 輸入框          │    │
│  │  各卡片 ROI             │ │  │  → 數據儀表板        │    │
│  └─────────────────────────┘ │  │  [瀏覽視圖]          │    │
│                               │  │  品牌/類別/排序      │    │
│                               │  │  → 卡片格狀列表      │    │
│                               │  └─────────────────────┘    │
└─────────────────────────────────────────────────────────┘
Footer: v1.0.0 | Created by devcharles
```

### 響應式設計（RWD）

斷點：`max-width: 768px`

Mobile 主要調整：
- Sidebar 從左側固定改為頂部水平排列（`max-height: 400px`）
- 主內容減少 padding
- 輸入列變垂直排列（按鈕在上方，URL 輸入框在下方）
- 卡片網格改為 2 欄
- Modal 寬度 95%

### 互動狀態反饋

| 互動 | 反饋 |
|------|------|
| 按鈕懸停 | `transform: translateY(-1px)` + hover 顏色 |
| 卡片懸停 | `-1px` 上移 + 更深陰影 |
| 分析中 | 轉圈動畫 Spinner（`spin` keyframe） |
| 操作成功 | 底部彈出 Toast 通知（2.5s 後隱藏） |
| 輸入框 focus | 3px 主色外發光 |
| 當前關注項目 | `.wl-item.active` 背景高亮 |

---

## 核心演算法說明

### 捆綁交易偵測 (`cleanForTrend`)

SNKRDUNK 允許賣家一次賣多張卡（如 10 張 PSA 10），導致成交記錄出現 10 倍高價。此演算法自動偵測並修正這類數據，確保圖表和 ROI 計算不被污染。

```
輸入: prices[] (原始成交價陣列), histories[] (原始記錄), conditionBaseline (最低掛牌價)
輸出: cleanedPrices[] (清洗後的價格陣列)

步驟:
1. 若資料少於 5 筆，不做處理直接返回
2. IQR 分析: 計算 Q1, Q3, IQR，上界 = Q3 + 1.5 * IQR
3. 對每個價格:
   a. 若 <= 上界：保留原價
   b. 若 > 上界：
      - 收集前後 15 筆的局部鄰近值
      - 嘗試除以 2~20 所有整數
      - 評分公式: globalDist * 0.4 + localDist * 0.6
      - 選取分數最低且兩個距離都 < 40% 的修正倍數
      - 若找到合適倍數，使用修正後的值
```

### 投資組合市價計算

```
1. 取對應條件的交易記錄（最近 30 筆）
2. 通過 cleanForTrend() 清洗
3. 取清洗後前 10 筆
4. 排序後取中位數（index = floor(length/2)）
→ 此為當前市場估值
```

---

## 環境變數（Vercel 需設定）

| 變數名 | 說明 | 必填 |
|--------|------|------|
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token | 否（Telegram 功能才需要） |
| `TELEGRAM_CHANNEL_ID` | Telegram 頻道 ID（如 `@mychannel`） | 否 |

---

## 本機開發

```bash
# 安裝依賴
pip install -r requirements.txt

# 啟動（根目錄）
uvicorn main:app --reload --port 8000

# 瀏覽
open http://localhost:8000
```

---

## 部署架構

### Vercel 部署（主要）

```
vercel.json 路由規則:
  /api/* → /api (api/index.py)
  其他   → 靜態檔案服務 (index.html)
```

注意：Vercel Edge Network 有快取機制，API 回應已加入 `no-cache` 標頭防止快取。

### Render 部署（備用）

```yaml
# render.yaml
startCommand: uvicorn main:app --host 0.0.0.0 --port $PORT
Python: 3.12
```

---

## 重要實作細節（給 AI Agent 的注意事項）

1. **IP 偽裝**: 後端使用台灣 IP Header (`X-Forwarded-For: 111.255.26.144`, `CF-IPCountry: TW`) 強制取得不含消費稅的台灣定價

2. **價格修正**: 所有單卡商品的成交價和掛牌價都經過 `-$10 USD` 修正。整盒（Box）商品不做此修正。修改此邏輯需同時更新 `api/index.py` 和 `main.py` 兩個檔案

3. **前後端同步**: `api/index.py`（Vercel）和 `main.py`（Render/本機）的業務邏輯應保持一致，新功能需同時更新兩個檔案

4. **localStorage 儲存**: 所有用戶數據（關注清單、投資組合）儲存在瀏覽器 localStorage，無後端資料庫，清除瀏覽器儲存即遺失數據

5. **跨域設定**: `api/index.py` 有 CORS Middleware（允許所有來源），`main.py` 沒有（因為靜態檔案同源提供）

6. **Chart 實例管理**: 重新渲染圖表前必須呼叫 `chart.destroy()` 和 `volChart.destroy()`，否則會記憶體洩漏

7. **整盒商品偵測**: 透過判斷 `condition_prices` 是否為空 && `trading_histories` 中的 `size` 包含 "box" 字串來判斷是否為整盒商品

8. **SNKRDUNK API 路徑差異**: 
   - 成交歷史: `/en/v1/streetwears/{id}/trading-histories`（注意是 `streetwears` 非 `trading-cards`）
   - 各等級最低價: `/en/v1/trading-cards/{id}/min-prices-by-conditions`
   - 完整歷史圖表: `/en/v1/streetwears/{id}/sale-prices?range=all`（需要 Cookie）

---

## 已知限制與未來改進方向

- `sale-prices` API 需要 SNKRDUNK 的 ENSID Session Cookie，若 Cookie 獲取失敗會降級使用 `trading-histories`（最多 1000 筆）
- 價格 `-$10` 修正是硬編碼，若 SNKRDUNK 調整定價策略需手動更新
- 投資組合無後端儲存，換瀏覽器或清除瀏覽器儲存會遺失
- 目前只支援 ONE PIECE 和 Pokémon 兩個品牌
- 分享圖片使用 `html2canvas`，跨域圖片載入可能失敗
