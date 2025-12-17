import pandas as pd
import numpy as np
import requests
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from data_fetcher import get_ohlc
from datetime import datetime, time as dt_time

# ================= CONFIG =================
RSI_PERIOD = 14
INTERVAL = 5
MAX_WORKERS = 16

# 🔧 PRICE FILTER (KEEP WIDE – PhysicsWallah ~130)
PRICE_MIN = 1
PRICE_MAX = 5000

TOP_PER_BUCKET = 10
# =========================================

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ================= UTIL =================

def calculate_rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    requests.post(url, json=payload)

# ================= CORE =================

def process_stock(row, symbol_col, secid_col):
    symbol = str(row[symbol_col])
    security_id = row[secid_col]

    df = get_ohlc(security_id, INTERVAL)
    if df.empty or len(df) < RSI_PERIOD + 5:
        return None

    df["rsi"] = calculate_rsi(df["close"])
    last = df.iloc[-1]

    if pd.isna(last["rsi"]):
        return None

    price = float(last["close"])
    rsi = round(float(last["rsi"]), 2)
    volume = int(last["volume"])

    if not (PRICE_MIN <= price <= PRICE_MAX):
        return None

    return {
        "symbol": symbol,
        "price": round(price, 2),
        "rsi": rsi,
        "volume": volume
    }

# ================= MAIN =================

def main():
    # ---- Market safety (optional but good) ----
    now = datetime.now().time()
    if now < dt_time(9, 20):
        send_telegram("⏳ RSI Scanner: Market data not ready (before 9:20)")
        return

    stocks = pd.read_csv("stocks.csv")

    # ---- Auto detect columns ----
    symbol_col = next(c for c in stocks.columns if "symbol" in c.lower())
    secid_col = next(c for c in stocks.columns if "security" in c.lower())

    results = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [
            executor.submit(process_stock, row, symbol_col, secid_col)
            for _, row in stocks.iterrows()
        ]
        for f in as_completed(futures):
            res = f.result()
            if res:
                results.append(res)

    if not results:
        send_telegram(
            "⚠️ <b>RSI & Volume Scanner (5m)</b>\n"
            "No stocks matched filters.\n"
            "Market may be sideways or low momentum."
        )
        return

    df = pd.DataFrame(results)

    # ================= RSI BUCKETS =================
    buckets = {
        "🔴 RSI > 80": df[df.rsi > 80],
        "🟠 RSI 70-80": df[(df.rsi >= 70) & (df.rsi < 80)],
        "🟡 RSI 60-70": df[(df.rsi >= 60) & (df.rsi < 70)],
        "🔵 RSI 20-30": df[(df.rsi >= 20) & (df.rsi < 30)],
        "🟢 RSI < 20 (EXTREME OVERSOLD)": df[df.rsi < 20],
    }


    msg = "<b>🔥 RSI & VOLUME SCANNER (5m)</b>\n"

    for title, bucket in buckets.items():
        if bucket.empty:
            continue

        bucket = bucket.sort_values("volume", ascending=False).head(TOP_PER_BUCKET)

        msg += f"\n<b>{title}</b>\n"
        for _, r in bucket.iterrows():
            msg += (
                f"• {r.symbol} | ₹{r.price} | "
                f"RSI: {r.rsi} | Vol: {r.volume:,}\n"
            )

    send_telegram(msg)

if __name__ == "__main__":
    main()
