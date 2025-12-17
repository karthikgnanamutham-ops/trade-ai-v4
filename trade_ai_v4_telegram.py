import pandas as pd
import requests
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from data_fetcher import get_ohlc

# ================= CONFIG =================
RSI_PERIOD = 14
INTERVAL = 5
MAX_WORKERS = 16

PRICE_MIN = 1
PRICE_MAX = 5000

VOLUME_LOOKBACK = 6          # any spike in last 6 candles
RSI_SLOPE_LOOKBACK = 3
RANGE_LOOKBACK = 20

TOP_N = 5                   # top volume per RSI zone
# =========================================

load_dotenv()
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ================= INDICATORS =================
def calculate_rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def min_volume_required(price):
    if price < 50:
        return 300_000
    elif price < 100:
        return 200_000
    elif price < 200:
        return 150_000
    elif price < 500:
        return 100_000
    elif price < 1000:
        return 50_000
    else:
        return 20_000

def rsi_slope(df):
    return df["rsi"].iloc[-1] - df["rsi"].iloc[-RSI_SLOPE_LOOKBACK - 1]

def price_context(df):
    recent = df.tail(RANGE_LOOKBACK)
    low, high = recent["low"].min(), recent["high"].max()
    pos = (df["close"].iloc[-1] - low) / (high - low + 1e-6)
    if pos <= 0.3:
        return "Near Support"
    elif pos >= 0.7:
        return "Near Resistance"
    else:
        return "Mid Range"

def phase_label(rsi, slope):
    if rsi < 30:
        return "Reversal Attempt" if slope > 0 else "Falling Knife"
    elif rsi > 70:
        return "Momentum" if slope > 0 else "Exhaustion"
    elif 60 <= rsi <= 70:
        return "Bullish Strength"
    else:
        return "Neutral"

# ================= TELEGRAM =================
def send_telegram(msg):
    if not TG_TOKEN or not TG_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": msg,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    requests.post(url, json=payload, timeout=10)

# ================= CORE =================
def process_stock(row, symbol_col, secid_col):
    symbol = str(row[symbol_col])
    security_id = row[secid_col]

    df = get_ohlc(security_id, INTERVAL)
    if df.empty or len(df) < max(RSI_PERIOD + RSI_SLOPE_LOOKBACK, RANGE_LOOKBACK):
        return None

    df["rsi"] = calculate_rsi(df["close"])
    last = df.iloc[-1]
    if pd.isna(last["rsi"]):
        return None

    price = round(float(last["close"]), 2)
    rsi = round(float(last["rsi"]), 2)

    if not (PRICE_MIN <= price <= PRICE_MAX):
        return None

    min_vol = min_volume_required(price)
    vol_spike = int(df["volume"].tail(VOLUME_LOOKBACK).max())
    if vol_spike < min_vol:
        return None

    slope_val = rsi_slope(df)
    slope_icon = "↑" if slope_val > 0 else "↓"
    context = price_context(df)
    phase = phase_label(rsi, slope_val)

    return {
        "symbol": symbol,
        "price": price,
        "rsi": rsi,
        "slope": slope_icon,
        "context": context,
        "phase": phase,
        "volume": vol_spike
    }

# ================= MAIN =================
def main():
    stocks = pd.read_csv("stocks.csv")
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
        send_telegram("🤖 Trade AI V4\nNo valid setups right now.")
        return

    df = pd.DataFrame(results)

    buys = df[df.phase == "Reversal Attempt"]
    sells = df[df.phase == "Exhaustion"]

    msg = "<b>🤖 Trade AI V4 – Intraday Scanner (5m)</b>\n"

    # ===== BUY / WATCH =====
    if not buys.empty:
        msg += "\n<b>🟢 BUY / WATCH (Reversal)</b>\n"
        for _, r in buys.sort_values("volume", ascending=False).iterrows():
            msg += (
                f"\n<b>{r.symbol}</b>\n"
                f"{r.price} | {r.rsi} | {int(r.volume/1000)}K\n"
                f"{r.context}\n"
            )

    # ===== SELL / EXIT =====
    if not sells.empty:
        msg += "\n<b>🔴 SELL / EXIT (Exhaustion)</b>\n"
        for _, r in sells.sort_values("volume", ascending=False).iterrows():
            msg += (
                f"\n<b>{r.symbol}</b>\n"
                f"{r.price} | {r.rsi} | {int(r.volume/1000)}K\n"
                f"{r.context}\n"
            )

    # ===== TOP VOLUME BY RSI ZONE =====
    msg += "\n<b>📊 TOP VOLUME BY RSI ZONE</b>\n"

    zones = {
        "🔥 Extreme Overbought": df[df.rsi > 80],
        "⚠️ Overbought": df[(df.rsi >= 70) & (df.rsi < 80)],
        "💪 Bullish Strength": df[(df.rsi >= 60) & (df.rsi < 70)],
        "😬 Oversold": df[(df.rsi >= 20) & (df.rsi < 30)],
        "🧊 Extreme Oversold": df[df.rsi < 20],
    }

    for title, bucket in zones.items():
        if bucket.empty:
            continue

        msg += f"\n<b>{title}</b>\n"
        top = bucket.sort_values("volume", ascending=False).head(TOP_N)

        for _, r in top.iterrows():
            msg += (
                f"\n<b>{r.symbol}</b>\n"
                f"{r.price} | {r.rsi} | {int(r.volume/1000)}K\n"
            )

    send_telegram(msg)

if __name__ == "__main__":
    main()
