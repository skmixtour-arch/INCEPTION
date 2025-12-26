# TRADING BOT CONFIGURATION
# ==========================

# --- EXCHANGE SETTINGS ---
EXCHANGE = "MEXC"
API_KEY = "YOUR_MEXC_API_KEY"
API_SECRET = "YOUR_MEXC_API_SECRET"

# --- TRADING SETTINGS ---
SYMBOL = "BTCUSDT"
TIMEFRAME = "15m"       # 1m, 5m, 15m, 1h, 4h, 1d
LEVERAGE = 10
POSITION_SIZE_PCT = 0.025  # 2.5% of balance per trade

# --- RISK MANAGEMENT ---
STOP_LOSS_PCT = 0.008      # 0.8%
TAKE_PROFIT_1_PCT = 0.008  # 1:1 RR (0.8%) - Close 50%
TAKE_PROFIT_2_PCT = 0.016  # 2:1 RR (1.6%) - Close remaining 50%
MAX_OPEN_TRADES = 1

# --- TRADING MODE ---
# 'PAPER' = Simulated (no real money)
# 'LIVE' = Real trading (requires valid API keys)
TRADING_MODE = "PAPER"

# --- BRINKS BOX SETTINGS ---
# Brinks Session Time (Server Time, typically UTC)
BRINKS_START_HOUR = 14  # 14:00 UTC
BRINKS_END_HOUR = 15    # 15:00 UTC

# --- ASIAN SESSION (for liquidity sweep detection) ---
ASIAN_START_HOUR = 0   # 00:00 UTC
ASIAN_END_HOUR = 8     # 08:00 UTC

# --- VECTOR CANDLE SETTINGS ---
VECTOR_GREEN_RED_THRESHOLD = 2.0  # 200% of average volume
VECTOR_BLUE_PINK_THRESHOLD = 1.5  # 150% of average volume
VOLUME_AVG_PERIOD = 10            # Candles to average
