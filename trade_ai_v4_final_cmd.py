import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from data_fetcher import get_ohlc

# ================= CONFIG =================
RSI_PERIOD = 14
INTERVAL = 5
MAX_WORKERS = 16

PRICE_MIN = 100
PRICE_MAX = 2000

VOLUME_LOOKBACK = 6          # last 6 candles (~30 min)
RSI_SLOPE_LOOKBACK = 3
RANGE_LOOKBACK = 20

TOP_N = 5
# =========================================


# ================= RSI =================
def calculate_rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


# ================= VOLUME RULE =================
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


# ================= CONTEXT =================
def rsi_slope(df):
    return df["rsi"].iloc[-1] - df["rsi"].iloc[-RSI_SLOPE_LOOKBACK - 1]


def price_context(df):
    recent = df.tail(RANGE_LOOKBACK)
    low = recent["low"].min()
    high = recent["high"].max()
    price = df["close"].iloc[-1]

    pos = (price - low) / (high - low + 1e-6)

    if pos <= 0.3:
        return "Near Support"
    elif pos >= 0.7:
        return "Near Resistance"
    else:
        return "Mid Range"


def phase_label(rsi, slope):
    if rsi < 30:
        return "🔄 Reversal Attempt" if slope > 0 else "🗡️ Falling Knife"
    elif rsi > 70:
        return "🚀 Momentum Continuation" if slope > 0 else "⚠️ Exhaustion Risk"
    elif 60 <= rsi <= 70:
        return "💪 Bullish Strength"
    else:
        return "➖ Neutral"


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

    price = float(last["close"])
    rsi = round(float(last["rsi"]), 2)

    if not (PRICE_MIN <= price <= PRICE_MAX):
        return None

    min_vol = min_volume_required(price)
    recent_vol = int(df["volume"].tail(VOLUME_LOOKBACK).max())

    if recent_vol < min_vol:
        return None

    slope_val = rsi_slope(df)
    slope = "Rising" if slope_val > 0 else "Falling"
    context = price_context(df)
    phase = phase_label(rsi, slope_val)

    return {
        "symbol": symbol,
        "price": round(price, 2),
        "rsi": rsi,
        "slope": slope,
        "context": context,
        "phase": phase,
        "volume": recent_vol
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
        print("\n⚠️ No stocks passed RSI + Volume filters\n")
        return

    df = pd.DataFrame(results)

    # ================= SECTION 1: PHASE VIEW =================
    print("\n========= TRADE AI V4 – PHASE VIEW (5m) =========\n")

    for phase in df.phase.unique():
        bucket = df[df.phase == phase].sort_values("volume", ascending=False)

        print(phase)
        print("-" * len(phase))

        for _, r in bucket.iterrows():
            print(
                f"{r.symbol:<18} "
                f"Price: {r.price:<7} "
                f"RSI: {r.rsi:<6} "
                f"{r.slope:<7} "
                f"{r.context:<15} "
                f"Vol: {r.volume:,}"
            )
        print()

    # ================= SECTION 2: TOP-5 BY VOLUME =================
    print("\n========= TOP 5 BY VOLUME (DECISION SUPPORT) =========\n")

    zones = {
        "🔥 Extreme Overbought (RSI > 80)": df[df.rsi > 80],
        "⚠️ Overbought (RSI 70–80)": df[(df.rsi >= 70) & (df.rsi < 80)],
        "💪 Bullish Strength (RSI 60–70)": df[(df.rsi >= 60) & (df.rsi < 70)],
        "😬 Oversold (RSI 20–30)": df[(df.rsi >= 20) & (df.rsi < 30)],
        "🧊 Extreme Oversold (RSI < 20)": df[df.rsi < 20],
    }

    for title, bucket in zones.items():
        if bucket.empty:
            continue

        bucket = bucket.sort_values("volume", ascending=False).head(TOP_N)

        print(title)
        print("-" * len(title))

        for _, r in bucket.iterrows():
            print(
                f"{r.symbol:<18} "
                f"Price: {r.price:<7} "
                f"RSI: {r.rsi:<6} "
                f"Vol: {r.volume:,}"
            )
        print()


if __name__ == "__main__":
    main()
