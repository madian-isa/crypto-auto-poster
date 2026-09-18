"""
news.py

Pulls recent crypto news from Finnhub (reusing your existing
FINNHUB_API_KEY) and looks for a headline that actually mentions the coin.
Returns None when nothing relevant is found — the bot must NEVER invent
news, so callers should just omit the news line in that case.
"""

import time
import requests
from src import bot_config as cfg

_CACHE_TTL_SECONDS = 15 * 60
_cache = {"fetched_at": 0, "articles": []}


def get_relevant_news(symbol: str) -> dict | None:
    if not cfg.FINNHUB_API_KEY:
        return None

    base = symbol.replace("USDT", "").replace("1000", "")
    articles = _fetch_crypto_news()

    for article in articles:
        headline = (article.get("headline") or "")
        summary = (article.get("summary") or "")
        haystack = f"{headline} {summary}".upper()
        if base.upper() in haystack:
            return {
                "headline": headline.strip(),
                "url": article.get("url"),
            }

    return None


def _fetch_crypto_news() -> list:
    now = time.time()
    if now - _cache["fetched_at"] < _CACHE_TTL_SECONDS and _cache["articles"]:
        return _cache["articles"]

    try:
        res = requests.get(
            "https://finnhub.io/api/v1/news",
            params={"category": "crypto", "token": cfg.FINNHUB_API_KEY},
            timeout=10,
        )
        res.raise_for_status()
        articles = res.json() or []
    except requests.RequestException:
        articles = []

    _cache["fetched_at"] = now
    _cache["articles"] = articles
    return articles
