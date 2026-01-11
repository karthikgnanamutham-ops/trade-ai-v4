import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from data_fetcher import get_ohlc

# ================= CONFIG =================
RSI_PERIOD = 14
INTERVAL = 5
MAX_WORKERS = 16

PRICE_MIN = 100
PRICE_MAX = 2000

VOLUME_LOOKBACK = 6      # last 6 candles (~30 min)
RSI_SLOPE_LOOKBACK = 3
RANGE_LOOKBACK = 20

TOP_PER_BUCKET = 10
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


# ================= VOLUME FILTER =================
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


# ================= CONTEXT HELPERS =================
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


def classify_trade(rsi, slope, context):
    if rsi > 70:
        if slope > 0:
            return "🚀 Momentum Continuation"
        else:
            return "⚠️ Exhaustion Risk"
    elif rsi < 30:
        if slope > 0:
            return "🔄 Reversal Attempt"
        else:
            return "🗡️ Falling Knife"
    else:
        return "➖ Neutral / Trend"


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
    recent_volumes = df["volume"].tail(VOLUME_LOOKBACK)
    max_recent_vol = int(recent_volumes.max())

    if max_recent_vol < min_vol:
        return None

    slope = rsi_slope(df)
    slope_dir = "Rising" if slope > 0 else "Falling"

    context = price_context(df)
    trade_type = classify_trade(rsi, slope, context)

    return {
        "symbol": symbol,
        "price": round(price, 2),
        "rsi": rsi,
        "slope": slope_dir,
        "context": context,
        "trade_type": trade_type,
        "volume": max_recent_vol,
        "min_vol": min_vol
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
        print("\n⚠️ No stocks passed all filters\n")
        return

    df = pd.DataFrame(results)

    print("\n========= V4 RSI + VOLUME + CONTEXT SCANNER (5m) =========\n")

    for trade in df.trade_type.unique():
        bucket = df[df.trade_type == trade].sort_values("volume", ascending=False)

        print(trade)
        print("-" * len(trade))

        for _, r in bucket.iterrows():
            print(
                f"{r.symbol:<18} "
                f"Price: {r.price:<7} "
                f"RSI: {r.rsi:<6} "
                f"{r.slope:<7} "
                f"{r.context:<16} "
                f"Vol: {r.volume:,}"
            )
        print()


if __name__ == "__main__":
    main()
