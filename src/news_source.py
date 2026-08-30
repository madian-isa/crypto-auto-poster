"""
news_source.py

Pulls fresh news from Finnhub's free tier (crypto + general market categories).
Only returns items that look genuinely market-moving, to avoid low-value spam posts.
"""

import requests
from src import config

FINNHUB_NEWS_URL = "https://finnhub.io/api/v1/news"

# Keywords that suggest a headline is actually relevant to crypto/macro trading,
# used to filter out irrelevant "general" news noise.
RELEVANT_KEYWORDS = [
    "fed", "rate", "inflation", "cpi", "pce", "gdp", "jobs", "payroll",
    "bitcoin", "btc", "ethereum", "eth", "crypto", "sec", "etf",
    "interest rate", "powell", "warsh", "hammack", "treasury", "dollar",
    "regulation", "binance", "coinbase", "stablecoin",
]


def fetch_latest_news(category="crypto", limit=15):
    """Fetch latest news items from Finnhub for a given category."""
    if not config.FINNHUB_API_KEY:
        raise RuntimeError("FINNHUB_API_KEY not set.")

    params = {"category": category, "token": config.FINNHUB_API_KEY}
    resp = requests.get(FINNHUB_NEWS_URL, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    if not isinstance(data, list):
        return []

    return data[:limit]


def is_relevant(headline: str, summary: str = "") -> bool:
    text = f"{headline} {summary}".lower()
    return any(kw in text for kw in RELEVANT_KEYWORDS)


def fetch_relevant_news():
    """
    Fetch news across categories and return only items that look genuinely
    relevant to crypto/macro trading — not just anything Finnhub returns.
    """
    all_items = []
    for cat in ("crypto", "forex", "general"):
        try:
            items = fetch_latest_news(category=cat)
            all_items.extend(items)
        except Exception as e:
            print(f"[news_source] Failed to fetch category={cat}: {e}")

    relevant = [
        item for item in all_items
        if is_relevant(item.get("headline", ""), item.get("summary", ""))
    ]

    # Sort newest first, dedupe by id
    seen_ids = set()
    unique = []
    for item in sorted(relevant, key=lambda x: x.get("datetime", 0), reverse=True):
        if item.get("id") not in seen_ids:
            seen_ids.add(item.get("id"))
            unique.append(item)

    return unique
