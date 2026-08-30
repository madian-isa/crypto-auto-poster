"""
post_template.py

Builds the final post text from a news item, following the agreed rules:
- Honest hook, no fear/greed manipulation ("is your money safe", "golden opportunity")
- 3 short points with real facts
- One honest "my take" line, no guaranteed predictions
- 3 $cashtags relevant to the topic
- 5 #hashtags relevant to the topic (not fixed — generated per topic)
- Hard limit: 2000 characters
- Always ends with a DYOR / not-financial-advice line
"""

import re
from src import config

# Cashtag pools by rough topic keyword — expand over time
CASHTAG_MAP = {
    "fed": ["$BTC", "$ETH", "$BNB"],
    "rate": ["$BTC", "$ETH", "$BNB"],
    "inflation": ["$BTC", "$ETH", "$GOLD"],
    "cpi": ["$BTC", "$ETH", "$GOLD"],
    "gdp": ["$BTC", "$ETH", "$BNB"],
    "sec": ["$BTC", "$ETH", "$XRP"],
    "etf": ["$BTC", "$ETH", "$BNB"],
    "bitcoin": ["$BTC", "$ETH", "$BNB"],
    "btc": ["$BTC", "$ETH", "$BNB"],
    "ethereum": ["$ETH", "$BTC", "$BNB"],
    "regulation": ["$BTC", "$ETH", "$XRP"],
    "stablecoin": ["$USDT", "$USDC", "$BTC"],
}

DEFAULT_CASHTAGS = ["$BTC", "$ETH", "$BNB"]

HASHTAG_POOL_BY_TOPIC = {
    "fed": ["FedNews", "Macro", "RateDecision", "CryptoMarket", "DYOR"],
    "inflation": ["Inflation", "Macro", "CPI", "CryptoMarket", "DYOR"],
    "sec": ["SECNews", "CryptoRegulation", "BTC", "CryptoMarket", "DYOR"],
    "gdp": ["GDP", "Macro", "USEconomy", "CryptoMarket", "DYOR"],
    "bitcoin": ["Bitcoin", "BTC", "CryptoNews", "CryptoMarket", "DYOR"],
    "default": ["CryptoNews", "Macro", "CryptoMarket", "MarketUpdate", "DYOR"],
}


def _pick_by_keyword(text: str, mapping: dict, default_key="default"):
    text_lower = text.lower()
    for kw, value in mapping.items():
        if kw in text_lower:
            return value
    return mapping.get(default_key, list(mapping.values())[0])


def _clean_hashtag(tag: str) -> str:
    # Binance rejects punctuation in hashtags — keep alphanumeric only
    return re.sub(r"[^A-Za-z0-9]", "", tag)


def build_post_text(headline: str, points: list[str], my_take: str, source: str) -> str:
    """
    points: list of 2-3 short factual bullet strings (already written, real numbers only)
    my_take: one honest sentence, no guaranteed predictions
    source: e.g. "Finnhub / Reuters"
    """
    cashtags = _pick_by_keyword(headline, CASHTAG_MAP, default_key=None) or DEFAULT_CASHTAGS
    cashtags = cashtags[: config.NUM_CASHTAGS]

    hashtag_words = _pick_by_keyword(headline, HASHTAG_POOL_BY_TOPIC)
    hashtags = [f"#{_clean_hashtag(h)}" for h in hashtag_words[: config.NUM_HASHTAGS]]

    points_block = "\n".join(f"{i+1}. {p}" for i, p in enumerate(points))

    text = (
        f"{headline}\n\n"
        f"{points_block}\n\n"
        f"My take: {my_take}\n\n"
        f"{' '.join(cashtags)}\n"
        f"{' '.join(hashtags)}\n\n"
        f"Not financial advice. Source: {source}. DYOR."
    )

    if len(text) > config.CHAR_LIMIT:
        # Trim the points block first, keep header/footer intact
        overflow = len(text) - config.CHAR_LIMIT
        points_block_trimmed = points_block[: max(0, len(points_block) - overflow - 3)] + "..."
        text = (
            f"{headline}\n\n"
            f"{points_block_trimmed}\n\n"
            f"My take: {my_take}\n\n"
            f"{' '.join(cashtags)}\n"
            f"{' '.join(hashtags)}\n\n"
            f"Not financial advice. Source: {source}. DYOR."
        )

    return text[: config.CHAR_LIMIT]
