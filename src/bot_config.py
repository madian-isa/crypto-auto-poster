import os

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
# AI / GROQ
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
# BINANCE
# =========================================================

BINANCE_FAPI_BASE = (
    "https://data-api.binance.vision"
)


# =========================================================
# SCREENER
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
# KLINE
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
# POST SETTINGS
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
# CHART
# =========================================================

CHART_OUTPUT_DIR = os.environ.get(
    "CHART_OUTPUT_DIR",
    "/tmp/trade_setup_charts",
)


# =========================================================
# DRY RUN
# =========================================================

DRY_RUN = (
    os.environ.get(
        "DRY_RUN",
        "true",
    ).lower()
    not in ("false", "0", "no")
)


# =========================================================
# STATE
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
# SCORING / SELECTION
# =========================================================

PICK_FROM_TOP_N = int(
    os.environ.get(
        "TRADE_PICK_FROM_TOP_N",
        "10",
    )
)


# =========================================================
# MARKET ANALYSIS
# =========================================================

ATR_MULTIPLIER = float(
    os.environ.get(
        "ATR_MULTIPLIER",
        "1.5",
    )
)

RISK_REWARD_CHOICES = [
    2,
    3,
]


# =========================================================
# 1H VOLATILITY FILTER
# =========================================================

MIN_1H_ATR_PERCENT = float(
    os.environ.get(
        "MIN_1H_ATR_PERCENT",
        "1.0",
    )
)


# =========================================================
# FINNHUB
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
# MARKET CONTEXT
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
# MAJOR COINS
# =========================================================

MAJOR_HIGH_VOLUME = {
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "SOLUSDT",
    "XRPUSDT",
}


# =========================================================
# MARKET BREADTH
# =========================================================

MARKET_BREADTH_LIMIT = int(
    os.environ.get(
        "MARKET_BREADTH_LIMIT",
        "100",
    )
)


# =========================================================
# MAJOR COIN SCORE BOOST
# =========================================================

MAJOR_COIN_SCORE_BOOST = float(
    os.environ.get(
        "MAJOR_COIN_SCORE_BOOST",
        "0.12",
    )
)
