"""
bot_config.py

Settings specific to the trade-setup bot. Reuses the SAME environment-variable
pattern as your existing config.py (BINANCE_SQUARE_OPENAPI_KEY etc.) — drop
this file into the same `src/` package as your news bot and it will pick up
the same key automatically.
"""

import os

# --- reuse your existing keys/config ---
try:
    from src import config as base_config  # your existing config.py
    BINANCE_SQUARE_OPENAPI_KEY = base_config.BINANCE_SQUARE_OPENAPI_KEY
    CHAR_LIMIT = base_config.CHAR_LIMIT
except ImportError:
    # Fallback so this file can also run standalone / outside your repo.
    BINANCE_SQUARE_OPENAPI_KEY = os.environ.get("BINANCE_SQUARE_OPENAPI_KEY", "")
    CHAR_LIMIT = 2000

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

BINANCE_FAPI_BASE = "https://fapi.binance.com"

# Screener
SCREENER_SHORTLIST_SIZE = int(os.environ.get("SCREENER_SHORTLIST_SIZE", "15"))
EXCLUDE_SYMBOLS = {"USDCUSDT", "FDUSDUSDT", "TUSDUSDT", "BUSDUSDT"}

# Indicators
KLINE_INTERVAL = os.environ.get("KLINE_INTERVAL", "1h")
KLINE_LIMIT = int(os.environ.get("KLINE_LIMIT", "100"))

# Posting cadence
POSTS_PER_CYCLE = int(os.environ.get("TRADE_POSTS_PER_CYCLE", "3"))
MINUTES_BETWEEN_POSTS = int(os.environ.get("TRADE_MINUTES_BETWEEN_POSTS", "20"))

# Chart image
CHART_OUTPUT_DIR = os.environ.get("CHART_OUTPUT_DIR", "/tmp/trade_setup_charts")

# Safety switch: when true (the default), nothing is uploaded or posted to
# Binance Square — the bot builds everything (indicators, AI setup, chart)
# and just PRINTS what it would have posted. Set DRY_RUN=false to go live.
DRY_RUN = os.environ.get("DRY_RUN", "true").lower() not in ("false", "0", "no")
