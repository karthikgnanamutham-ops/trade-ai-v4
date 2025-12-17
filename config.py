# ===== DATA / EXECUTION =====
INTERVAL = 5
LOOKBACK_DAYS = 7
MIN_CANDLES = 30
MAX_WORKERS = 16

PRICE_MIN = 100
PRICE_MAX = 500

# ===== RISK =====
RR_RATIO = 2.0

# ===== CONFIDENCE =====
BASE_CONFIDENCE = 50
MAX_CONFIDENCE = 100

# ===== MODE =====
MODE = "EXPLORATION"   # STRICT / EXPLORATION

# ===== NOISE REDUCTION =====
SHOW_GRADES = ["A", "B"]

TIER_1_SETUPS = [
    "Breakout BUY",
    "Strong Breakout BUY",
    "Failed Breakout SELL",
    "Failed Breakdown BUY"
]

TIER_2_SETUPS = [
    "Trend Continuation BUY",
    "Trend Breakdown SELL",
    "Pullback BUY",
    "Pullback SELL",
    "VWAP Reclaim BUY",
    "VWAP Rejection SELL"
]

# ===== OUTPUT =====
MAX_ALERTS = 20

# ==================================
# VOLUME FILTER CONFIG (TUNABLE)
# ==================================

# Absolute liquidity (sum of last N candles)
VOLUME_LIQUIDITY_WINDOW = 5        # candles
VOLUME_LIQUIDITY_MIN = 200_000     # change to 100_000 / 300_000 anytime

# Baseline window
VOLUME_BASELINE_WINDOW = 20        # candles

# Recent spike logic (ANY of last N candles)
VOLUME_RECENT_SPIKE_WINDOW = 5     # candles
VOLUME_RECENT_SPIKE_MULT = 1.5     # 1.3 / 1.5 / 2.0

# Current candle spike
VOLUME_CURRENT_SPIKE_MULT = 1.2    # 1.1 / 1.2 / 1.3

# Enable OR logic between recent & current spike
VOLUME_SPIKE_LOGIC = "OR"          # "OR" or "AND"


