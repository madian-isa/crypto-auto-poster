"""
screener.py

Pulls 24h ticker stats for every USDT-margined perpetual on Binance Futures
and ranks them by liquidity + momentum + a simple volume-spike proxy.

Also calculates basic market context:
- BTC 24h direction
- Market breadth
- BTC Open Interest
- BTC Funding Rate

If Futures-specific data is unavailable, the bot continues using
the normal screener data.
"""

import math
import requests

from src import bot_config as cfg


def get_screener_shortlist(limit=None):
    limit = limit or cfg.SCREENER_SHORTLIST_SIZE

    tickers = _fetch_all_24hr_tickers()

    usdt_pairs = [
        t for t in tickers
        if t["symbol"] in cfg.FUTURES_PERPETUAL_WHITELIST
    ]

    # Calculate market-wide context once per run.
    market_context = get_market_context(tickers)

    scored = []

    for t in usdt_pairs:
        symbol = t["symbol"]

        quote_volume = float(t["quoteVolume"])
        pct_change = abs(float(t["priceChangePercent"]))

        weighted_avg = float(
            t.get("weightedAvgPrice") or 1
        ) or 1

        volume_spike = float(t["volume"]) / weighted_avg

        # Existing screener score
        score = (
            _norm_log(quote_volume) * 0.50
            + _norm(pct_change, 20) * 0.35
            + _norm(volume_spike, 1e6) * 0.15
        )

        # Small priority boost for major/high-volume coins.
        if symbol in cfg.MAJOR_HIGH_VOLUME:
            score += cfg.MAJOR_COIN_SCORE_BOOST

        scored.append({
            "symbol": symbol,
            "quote_volume": quote_volume,
            "pct_change": pct_change,
            "last_price": float(t["lastPrice"]),
            "score": score,
            "market_context": market_context,
        })

    scored.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return scored[:limit]


def get_market_context(tickers):
    """Build market-wide context for the setup generator."""

    if not cfg.MARKET_CONTEXT_ENABLED:
        return {
            "btc_change_24h": None,
            "btc_direction": "Unknown",
            "market_green_pct": None,
            "market_red_pct": None,
            "market_breadth": "Unknown",
            "btc_open_interest": None,
            "btc_funding_rate": None,
        }

    # -------------------------
    # BTC direction
    # -------------------------

    btc = next(
        (
            t for t in tickers
            if t["symbol"] == cfg.BTC_SYMBOL
        ),
        None,
    )

    btc_change = None
    btc_direction = "Unknown"

    if btc:
        btc_change = float(btc["priceChangePercent"])

        if btc_change > 0:
            btc_direction = "Bullish"
        elif btc_change < 0:
            btc_direction = "Bearish"
        else:
            btc_direction = "Flat"

    # -------------------------
    # Market breadth
    # -------------------------

    breadth_tickers = [
        t for t in tickers
        if t["symbol"] in cfg.FUTURES_PERPETUAL_WHITELIST
    ]

    green = sum(
        1
        for t in breadth_tickers
        if float(t["priceChangePercent"]) > 0
    )

    red = sum(
        1
        for t in breadth_tickers
        if float(t["priceChangePercent"]) < 0
    )

    total = green + red

    if total:
        green_pct = round(
            green / total * 100,
            1,
        )

        red_pct = round(
            red / total * 100,
            1,
        )
    else:
        green_pct = None
        red_pct = None

    if green_pct is None:
        breadth = "Unknown"
    elif green_pct >= 60:
        breadth = "Broadly Positive"
    elif red_pct >= 60:
        breadth = "Broadly Negative"
    else:
        breadth = "Mixed"

    # -------------------------
    # BTC Futures data
    # -------------------------

    btc_oi = _fetch_btc_open_interest()
    btc_funding = _fetch_btc_funding_rate()

    return {
        "btc_change_24h": btc_change,
        "btc_direction": btc_direction,
        "market_green_pct": green_pct,
        "market_red_pct": red_pct,
        "market_breadth": breadth,
        "btc_open_interest": btc_oi,
        "btc_funding_rate": btc_funding,
    }


def _fetch_btc_open_interest():
    """Fetch current BTCUSDT Futures open interest."""

    urls = [
        "https://fapi.binance.com/fapi/v1/openInterest",
        "https://data-api.binance.vision/fapi/v1/openInterest",
    ]

    for url in urls:
        try:
            res = requests.get(
                url,
                params={"symbol": "BTCUSDT"},
                timeout=10,
            )

            if res.ok:
                data = res.json()
                return float(data["openInterest"])

        except Exception:
            continue

    return None


def _fetch_btc_funding_rate():
    """Fetch latest BTCUSDT Futures funding rate."""

    urls = [
        "https://fapi.binance.com/fapi/v1/premiumIndex",
        "https://data-api.binance.vision/fapi/v1/premiumIndex",
    ]

    for url in urls:
        try:
            res = requests.get(
                url,
                params={"symbol": "BTCUSDT"},
                timeout=10,
            )

            if res.ok:
                data = res.json()

                value = data.get("lastFundingRate")

                if value is not None:
                    return float(value)

        except Exception:
            continue

    return None


def _fetch_all_24hr_tickers():
    url = f"{cfg.BINANCE_FAPI_BASE}/api/v3/ticker/24hr"

    res = requests.get(
        url,
        timeout=15,
    )

    res.raise_for_status()

    return res.json()


def _norm_log(value):
    return math.log10(value + 1) / 10


def _norm(value, cap):
    return min(value / cap, 1)


if __name__ == "__main__":
    for row in get_screener_shortlist():
        print(row)
