import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import urllib.request
import re
import html
import json

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID", "")

BASE = "https://snkrdunk.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=1.0",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://snkrdunk.com/en/",
    "X-Forwarded-For": "111.255.26.144",  # 模擬台灣 IP，強制使用不含稅價格
    "CF-IPCountry": "TW",  # Cloudflare 地區標頭
}

class ScrapeRequest(BaseModel):
    url: str

class TelegramRequest(BaseModel):
    message: str


def _api_get(path: str):
    # 添加防快取標頭，確保獲取最新數據
    headers_with_cache = {
        **HEADERS,
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
    }
    req = urllib.request.Request(f"{BASE}{path}", headers=headers_with_cache)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(f"[API] {path} - 狀態碼: {resp.status}, 數據大小: {len(str(data))} bytes")
            return data
    except Exception as e:
        print(f"[API ERROR] {path}: {e}")
        return None


def _parse_html(url: str):
    data = {
        "title": "Unknown Card", "subtitle": "", "product_number": "",
        "thumbnail_url": "", "min_price_format": "N/A",
        "used_min_price": "N/A", "used_min_price_amount": 0,
        "used_listing_count": 0, "used_listing_count_text": "0",
        "listing_count": 0, "datalayer_price": 0, "released_at": "",
    }
    req = urllib.request.Request(url, headers={
        "User-Agent": HEADERS["User-Agent"], "Accept-Language": "en-US,en;q=0.9",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            page_html = resp.read().decode("utf-8")
    except Exception:
        return data

    title_m = re.search(r'<title>(.*?)</title>', page_html)
    if title_m:
        data["title"] = html.unescape(title_m.group(1)).replace(" | SNKRDUNK", "").strip()

    dl_m = re.search(r'dataLayer\.push\((\{.*?\})\)', page_html)
    if dl_m:
        try: data["datalayer_price"] = json.loads(dl_m.group(1)).get("price", 0)
        except Exception: pass

    sm_m = re.search(r':summary="(.*?)\n"', page_html, re.DOTALL)
    if sm_m:
        raw = html.unescape(sm_m.group(1).strip()).replace('\\"', '"')
        try:
            sm = json.loads(raw)
            data["used_min_price"] = sm.get("usedMinPrice", "N/A")
            data["used_min_price_amount"] = sm.get("usedMinPriceAmount", 0)
            data["used_listing_count"] = sm.get("usedListingCount", 0)
            data["used_listing_count_text"] = sm.get("usedListingCountText", "0")
            data["listing_count"] = sm.get("listingCount", 0)
            data["min_price_format"] = sm.get("minPrice", "N/A")
        except Exception: pass

    tc_m = re.search(r':trading-card="(.*?)\n"', page_html, re.DOTALL)
    if tc_m:
        tc_raw = html.unescape(tc_m.group(1).strip())
        pn = re.search(r'"productNumber"\s*:\s*"([^"]*)"', tc_raw)
        if pn: data["product_number"] = pn.group(1)
        th = re.search(r'"thumbnailUrl"\s*:\s*"([^"]*)"', tc_raw)
        if th: data["thumbnail_url"] = th.group(1)
        rel = re.search(r'"releasedAt"\s*:\s*"([^"]*)"', tc_raw)
        if rel: data["released_at"] = rel.group(1)
        name = re.search(r'"name"\s*:\s*"(.*?)(?:"|,\s*"minPrice)', tc_raw)
        if name: data["subtitle"] = name.group(1).replace("\\u0026", "&")

    return data


def _extract_card_id(url: str) -> str:
    m = re.search(r'/trading-cards/(\d+)', url)
    return m.group(1) if m else ""


@app.post("/api/scrape")
async def scrape_api(req: ScrapeRequest):
    from fastapi.responses import JSONResponse

    if not req.url.startswith("http"):
        raise HTTPException(status_code=400, detail="Invalid URL")
    card_id = _extract_card_id(req.url)
    if not card_id:
        raise HTTPException(status_code=400, detail="Could not extract card ID")

    info = _parse_html(req.url)
    condition_prices = _api_get(f"/en/v1/trading-cards/{card_id}/min-prices-by-conditions")

    all_histories = []
    for page in range(1, 51):  # 增加到 50 頁，最多 5000 筆記錄
        result = _api_get(f"/en/v1/streetwears/{card_id}/trading-histories?page={page}&perPage=100")
        if not result:
            print(f"[HISTORIES] Page {page}: API 返回 None，停止抓取")
            break
        histories = result.get("histories", [])
        if not histories:
            print(f"[HISTORIES] Page {page}: 無數據，停止抓取")
            break

        print(f"[HISTORIES] Page {page}: 獲取 {len(histories)} 筆記錄")
        all_histories.extend(histories)

        # 如果這一頁少於 100 筆，表示已經是最後一頁
        if len(histories) < 100:
            print(f"[HISTORIES] Page {page}: 數據不足 100 筆，判定為最後一頁")
            break

    print(f"[HISTORIES] 總共獲取 {len(all_histories)} 筆交易記錄")

    # 調試：記錄前3筆交易的完整原始數據
    if all_histories:
        print(f"[DEBUG] First 3 histories for card {card_id}:")
        for i, h in enumerate(all_histories[:3]):
            print(f"  [{i}] FULL DATA: {h}")

    # 🔧 價格標準化：移除地區稅費差異 (美國 IP 單卡價格比台灣高 $10)
    # 檢測是否為整盒商品 (Box 商品不需要調整價格)
    is_box_product = (not condition_prices or not condition_prices.get("conditionPrices")) and \
                     any(h.get("size", "").lower().find("box") != -1 for h in all_histories[:10])

    if is_box_product:
        print(f"[PRICE_FIX] 檢測到整盒商品 (Box)，跳過價格調整")
    else:
        # 只有單卡商品才套用 -10 USD 調整
        PRICE_ADJUSTMENT = -10
        print(f"[PRICE_FIX] 單卡商品，套用價格修正：{PRICE_ADJUSTMENT}")

        # 1. 修正歷史成交紀錄
        if all_histories:
            for h in all_histories:
                if "price" in h and h["price"] > 0:
                    h["price"] += PRICE_ADJUSTMENT
                    h["priceFormat"] = f"US ${h['price']}"

        # 2. 修正各狀態最低價 (PSA 10 等)
        if condition_prices and "conditionPrices" in condition_prices:
            for c in condition_prices["conditionPrices"]:
                if "minPrice" in c and c["minPrice"] > 0:
                    c["minPrice"] += PRICE_ADJUSTMENT
                    c["minPriceFormat"] = f"US ${c['minPrice']}"
                    
        # 3. 修正 Info 裡的 Used 最低價與 DataLayer 價格
        used_amount = int(info.get("used_min_price_amount", 0))
        if used_amount > 0:
            info["used_min_price_amount"] = used_amount + PRICE_ADJUSTMENT
            info["used_min_price"] = f"US ${info['used_min_price_amount']}"
            
        dl_price = int(info.get("datalayer_price", 0))
        if dl_price > 0:
            info["datalayer_price"] = dl_price + PRICE_ADJUSTMENT


    response_data = {
        "info": info,
        "condition_prices": condition_prices.get("conditionPrices", []) if condition_prices else [],
        "trading_histories": all_histories,
    }

    # Force no-cache to prevent stale data in Vercel edge network
    return JSONResponse(
        content=response_data,
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )


@app.get("/api/conditions")
def get_conditions():
    data = _api_get("/en/v1/streetwears/used-listings/conditions")
    return data if data else {"conditions": []}


@app.post("/api/telegram")
async def send_to_telegram(req: TelegramRequest):
    if not TELEGRAM_BOT_TOKEN:
        raise HTTPException(status_code=500, detail="Telegram token not configured")
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = json.dumps({"chat_id": TELEGRAM_CHANNEL_ID, "text": req.message, "parse_mode": "HTML"}).encode()
    r = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
