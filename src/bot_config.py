import os


# =========================================================
# Base config
# =========================================================

try:
    from src import config as base_config

    BINANCE_SQUARE_OPENAPI_KEY = (
        base_config.BINANCE_SQUARE_OPENAPI_KEY
    )

    CHAR_LIMIT = base_config.CHAR_LIMIT

except ImportError:
    BINANCE_SQUARE_OPENAPI_KEY = os.environ.get(
        "BINANCE_SQUARE_OPENAPI_KEY",
        "",
    )

    CHAR_LIMIT = 2000


# =========================================================
# Groq
# =========================================================

GROQ_API_KEY = os.environ.get(
    "GROQ_API_KEY",
    "",
)

GROQ_MODEL = os.environ.get(
    "GROQ_MODEL",
    "openai/gpt-oss-120b",
)


# =========================================================
# Binance data
# =========================================================

BINANCE_FAPI_BASE = (
    "https://data-api.binance.vision"
)


# =========================================================
# CoinGlass
# =========================================================

COINGLASS_API_KEY = os.environ.get(
    "COINGLASS_API_KEY",
    "",
)

COINGLASS_BASE_URL = os.environ.get(
    "COINGLASS_BASE_URL",
    "https://open-api-v4.coinglass.com",
)

COINGLASS_TIMEOUT = float(
    os.environ.get(
        "COINGLASS_TIMEOUT",
        "6",
    )
)

COINGLASS_WORKERS = int(
    os.environ.get(
        "COINGLASS_WORKERS",
        "6",
    )
)


# =========================================================
# Screener
# =========================================================

SCREENER_SHORTLIST_SIZE = int(
    os.environ.get(
        "SCREENER_SHORTLIST_SIZE",
        "100",
    )
)

EXCLUDE_SYMBOLS = {
    "USDCUSDT",
    "FDUSDUSDT",
    "TUSDUSDT",
    "BUSDUSDT",
}


# =========================================================
# Futures perpetual whitelist
# =========================================================

FUTURES_PERPETUAL_WHITELIST = set(
    os.environ.get(
        "FUTURES_PERPETUAL_WHITELIST",
        "",
    ).split(",")
)

FUTURES_PERPETUAL_WHITELIST = {
    symbol.strip().upper()
    for symbol in FUTURES_PERPETUAL_WHITELIST
    if symbol.strip()
}


# =========================================================
# Kline settings
# =========================================================

KLINE_INTERVAL = os.environ.get(
    "KLINE_INTERVAL",
    "1h",
)

KLINE_LIMIT = int(
    os.environ.get(
        "KLINE_LIMIT",
        "100",
    )
)


# =========================================================
# Posting
# =========================================================

POSTS_PER_CYCLE = int(
    os.environ.get(
        "TRADE_POSTS_PER_CYCLE",
        "3",
    )
)

MINUTES_BETWEEN_POSTS = int(
    os.environ.get(
        "TRADE_MINUTES_BETWEEN_POSTS",
        "20",
    )
)


# =========================================================
# Chart
# =========================================================

CHART_OUTPUT_DIR = os.environ.get(
    "CHART_OUTPUT_DIR",
    "/tmp/trade_setup_charts",
)


# =========================================================
# Runtime
# =========================================================

DRY_RUN = (
    os.environ.get(
        "DRY_RUN",
        "true",
    ).lower()
    not in ("false", "0", "no")
)


# =========================================================
# State
# =========================================================

STATE_FILE = os.environ.get(
    "TRADE_BOT_STATE_FILE",
    "trade_bot_state.json",
)

MAX_POSTS_PER_DAY = int(
    os.environ.get(
        "TRADE_MAX_POSTS_PER_DAY",
        "70",
    )
)


# =========================================================
# Candidate selection
# =========================================================

PICK_FROM_TOP_N = int(
    os.environ.get(
        "TRADE_PICK_FROM_TOP_N",
        "10",
    )
)


# =========================================================
# Risk / reward
# =========================================================

RISK_REWARD_CHOICES = [
    2,
    3,
]


# =========================================================
# Finnhub
# =========================================================

try:
    FINNHUB_API_KEY = (
        base_config.FINNHUB_API_KEY
    )

except (NameError, AttributeError):
    FINNHUB_API_KEY = os.environ.get(
        "FINNHUB_API_KEY",
        "",
    )


# =========================================================
# Market context
# =========================================================

MARKET_CONTEXT_ENABLED = (
    os.environ.get(
        "MARKET_CONTEXT_ENABLED",
        "true",
    ).lower()
    not in ("false", "0", "no")
)


BTC_SYMBOL = "BTCUSDT"


# =========================================================
# Major coins
# =========================================================

MAJOR_HIGH_VOLUME = {
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "SOLUSDT",
    "XRPUSDT",
}


# =========================================================
# Market breadth
# =========================================================

MARKET_BREADTH_LIMIT = int(
    os.environ.get(
        "MARKET_BREADTH_LIMIT",
        "100",
    )
)


# =========================================================
# Major coin score boost
# =========================================================

MAJOR_COIN_SCORE_BOOST = float(
    os.environ.get(
        "MAJOR_COIN_SCORE_BOOST",
        "0.12",
    )
)
