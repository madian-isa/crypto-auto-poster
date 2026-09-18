"""
Config — reads all secrets from environment variables ONLY.
Never hard-code keys here. Set these in Render's "Environment" tab:

  BINANCE_SQUARE_OPENAPI_KEY   -> your Binance Square OpenAPI key
  FINNHUB_API_KEY              -> free key from finnhub.io (no card needed)
  POLL_INTERVAL_MINUTES        -> how often to check for news (default 10)
"""

import os

BINANCE_SQUARE_OPENAPI_KEY = os.environ.get("BINANCE_SQUARE_OPENAPI_KEY", "")
FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")  # optional but recommended
POLL_INTERVAL_MINUTES = int(os.environ.get("POLL_INTERVAL_MINUTES", "10"))

# Kept deliberately conservative: real human creators rarely post more than
# a handful of times a day. Posting too often (even under Binance's 100/day
# hard cap) can itself look bot-like to the recommendation algorithm.
MAX_POSTS_PER_DAY = int(os.environ.get("MAX_POSTS_PER_DAY", "60"))

# Randomized delay range (minutes) added on top of POLL_INTERVAL_MINUTES,
# so posts don't land on a suspiciously exact, machine-like schedule.
MIN_JITTER_MINUTES = int(os.environ.get("MIN_JITTER_MINUTES", "3"))
MAX_JITTER_MINUTES = int(os.environ.get("MAX_JITTER_MINUTES", "18"))

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# How long (minutes) to wait for an Approve/Reject before giving up on a draft
APPROVAL_TIMEOUT_MINUTES = int(os.environ.get("APPROVAL_TIMEOUT_MINUTES", "60"))

CHAR_LIMIT = 2000
NUM_HASHTAGS = 5
NUM_CASHTAGS = 3

SEEN_EVENTS_FILE = "seen_events.json"  # tracks what's already been posted


def validate():
    missing = []
    if not BINANCE_SQUARE_OPENAPI_KEY:
        missing.append("BINANCE_SQUARE_OPENAPI_KEY")
    if not FINNHUB_API_KEY:
        missing.append("FINNHUB_API_KEY")
    if not TELEGRAM_BOT_TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not TELEGRAM_CHAT_ID:
        missing.append("TELEGRAM_CHAT_ID")
    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}. "
            "Set these in Render's Environment tab — never in code."
        )
