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
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")

BINANCE_FAPI_BASE = "https://data-api.binance.vision"

# Screener
SCREENER_SHORTLIST_SIZE = int(os.environ.get("SCREENER_SHORTLIST_SIZE", "25"))
EXCLUDE_SYMBOLS = {"USDCUSDT", "FDUSDUSDT", "TUSDUSDT", "BUSDUSDT"}

# Market data comes from Binance's SPOT mirror (data-api.binance.vision) to
# avoid the US geo-block on fapi.binance.com — but posts are framed as
# perpetual futures setups (entry/SL/TP, leverage-style), so the screener
# must only pick symbols that actually exist as a USDT-M perpetual on
# Binance Futures. This is a curated list of major, liquid perpetuals —
# update it if Binance adds/removes contracts you want covered.
FUTURES_PERPETUAL_WHITELIST = {
    # Blue-chip / long-established majors
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT",
    "DOGEUSDT", "TRXUSDT", "TONUSDT", "LINKUSDT", "AVAXUSDT", "DOTUSDT",
    "LTCUSDT", "BCHUSDT", "ATOMUSDT", "XLMUSDT", "ETCUSDT", "NEARUSDT",
    "FILUSDT", "EOSUSDT", "ALGOUSDT", "EGLDUSDT", "THETAUSDT", "XTZUSDT",
    "KAVAUSDT", "VETUSDT", "ICPUSDT", "HBARUSDT", "RUNEUSDT", "IOTAUSDT",
    "NEOUSDT", "WAVESUSDT", "DASHUSDT", "ZECUSDT", "QTUMUSDT", "ONTUSDT",
    "ZRXUSDT", "BATUSDT", "OMGUSDT", "KSMUSDT", "RVNUSDT",
    "HOTUSDT", "IOSTUSDT", "ZILUSDT", "ONEUSDT",
    # DeFi
    "AAVEUSDT", "UNIUSDT", "MKRUSDT", "LDOUSDT", "SNXUSDT", "CRVUSDT",
    "COMPUSDT", "SUSHIUSDT", "YFIUSDT", "1INCHUSDT", "DYDXUSDT", "GMXUSDT",
    "PENDLEUSDT", "WOOUSDT", "CVXUSDT",
    # Layer-1 / Layer-2 growth names
    "APTUSDT", "ARBUSDT", "OPUSDT", "SUIUSDT", "INJUSDT", "STXUSDT",
    "IMXUSDT", "MANTAUSDT", "STRKUSDT", "SEIUSDT", "TIAUSDT", "ARUSDT",
    "KASUSDT", "ROSEUSDT", "CFXUSDT", "CELOUSDT", "FLOWUSDT",
    # Gaming / metaverse / NFT-adjacent
    "SANDUSDT", "MANAUSDT", "GALAUSDT", "AXSUSDT", "ENJUSDT", "CHZUSDT",
    "APEUSDT", "GMTUSDT", "MAGICUSDT", "PEOPLEUSDT",
    # AI / data
    "FETUSDT", "AGIXUSDT", "OCEANUSDT", "RNDRUSDT", "GRTUSDT", "ARKMUSDT",
    "WLDUSDT",
    # Meme / high-volume trending
    "PEPEUSDT", "WIFUSDT", "BONKUSDT", "FLOKIUSDT", "1000SHIBUSDT",
    "ORDIUSDT", "JUPUSDT", "NOTUSDT",
    # Other established liquid pairs
    "BANDUSDT", "SKLUSDT", "ANKRUSDT", "CTSIUSDT",
    "MASKUSDT", "BLURUSDT", "LPTUSDT", "HIGHUSDT", "PYTHUSDT", "JTOUSDT",
    "TAOUSDT", "ENAUSDT", "ONDOUSDT",
}

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

# --- single-run mode (for GitHub Actions / any external scheduler) ---
# Each invocation of `python main.py` posts ONE setup, then exits — no
# internal sleep loop. A scheduler (GitHub Actions cron, etc.) re-runs it
# every N minutes. This file tracks how many posts have gone out today so
# we don't blow past a daily cap even if the scheduler runs often.
STATE_FILE = os.environ.get("TRADE_BOT_STATE_FILE", "trade_bot_state.json")
MAX_POSTS_PER_DAY = int(os.environ.get("TRADE_MAX_POSTS_PER_DAY", 20"))

# When picking a symbol each run, choose randomly among the top N of the
# screener shortlist (instead of always the #1) so consecutive runs aren't
# always the same coin.
PICK_FROM_TOP_N = int(os.environ.get("TRADE_PICK_FROM_TOP_N", "10"))

# Risk sizing: SL is placed at ATR_MULTIPLIER x ATR(14) away from entry —
# proportionate to the coin's actual recent volatility, instead of a
# freeform AI guess (which tended to produce unrealistically wide stops).
ATR_MULTIPLIER = float(os.environ.get("ATR_MULTIPLIER", "1.5"))
# Reward is this multiple of the risk distance — randomly 2x or 3x each
# post, so posts don't all look identical.
RISK_REWARD_CHOICES = [2, 3]

# News (reuses your existing FINNHUB_API_KEY from config.py if present)
try:
    FINNHUB_API_KEY = base_config.FINNHUB_API_KEY
except (NameError, AttributeError):
    FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY", "")
