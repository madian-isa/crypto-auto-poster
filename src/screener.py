"""
screener.py

Builds a shortlist from Binance 24h USDT market data.

The screener uses available Spot ticker data as the fallback market
universe because Binance Futures endpoints may be unavailable from
GitHub Actions.

Futures-specific BTC OI / funding data is optional.
"""

import math
import requests

from src import bot_config as cfg


def get_screener_shortlist(limit=None):
    limit = limit or cfg.SCREENER_SHORTLIST_SIZE

    tickers = _fetch_all_24hr_tickers()

    # ---------------------------------------------------------
    # Build usable USDT universe
    # ---------------------------------------------------------
    #
    # Do NOT require FUTURES_PERPETUAL_WHITELIST here.
    # That whitelist may be empty when Futures API is unavailable.
    #

    usdt_pairs = []

    for t in tickers:
        symbol = t.get("symbol", "")

        if not symbol.endswith("USDT"):
            continue

        if symbol in cfg.EXCLUDE_SYMBOLS:
            continue

        try:
            quote_volume = float(t.get("quoteVolume", 0))
            last_price = float(t.get("lastPrice", 0))
            pct_change = float(t.get("priceChangePercent", 0))
        except (TypeError, ValueError):
            continue

        if quote_volume <= 0 or last_price <= 0:
            continue

        usdt_pairs.append(t)

    print(
        f"[screener] total tickers: {len(tickers)}"
    )

    print(
        f"[screener] usable USDT pairs: "
        f"{len(usdt_pairs)}"
    )

    # ---------------------------------------------------------
    # Market context
    # ---------------------------------------------------------

    market_context = get_market_context(
        tickers
    )

    scored = []

    # ---------------------------------------------------------
    # Score candidates
    # ---------------------------------------------------------

    for t in usdt_pairs:
        symbol = t["symbol"]

        try:
            quote_volume = float(
                t["quoteVolume"]
            )

            pct_change = abs(
                float(t["priceChangePercent"])
            )

            weighted_avg = float(
                t.get("weightedAvgPrice") or 1
            ) or 1

            base_volume = float(
                t.get("volume") or 0
            )

        except (TypeError, ValueError):
            continue

        # Simple volume-spike proxy.
        volume_spike = (
            base_volume / weighted_avg
            if weighted_avg > 0
            else 0
        )

        # Existing screener score.
        score = (
            _norm_log(quote_volume) * 0.50
            + _norm(pct_change, 20) * 0.35
            + _norm(volume_spike, 1e6) * 0.15
        )

        # Small priority boost for major coins.
        if symbol in cfg.MAJOR_HIGH_VOLUME:
            score += cfg.MAJOR_COIN_SCORE_BOOST

        scored.append({
            "symbol": symbol,
            "quote_volume": quote_volume,
            "pct_change": pct_change,
            "last_price": float(
                t["lastPrice"]
            ),
            "score": score,
            "market_context": market_context,
        })

    scored.sort(
        key=lambda x: x["score"],
        reverse=True,
    )

    result = scored[:limit]

    print(
        f"[screener] shortlist size: "
        f"{len(result)}"
    )

    if result:
        print(
            "[screener] top candidates: "
            + ", ".join(
                row["symbol"]
                for row in result[:10]
            )
        )

    return result


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

    # ---------------------------------------------------------
    # BTC direction
    # ---------------------------------------------------------

    btc = next(
        (
            t for t in tickers
            if t.get("symbol") == cfg.BTC_SYMBOL
        ),
        None,
    )

    btc_change = None
    btc_direction = "Unknown"

    if btc:
        try:
            btc_change = float(
                btc["priceChangePercent"]
            )

            if btc_change > 0:
                btc_direction = "Bullish"
            elif btc_change < 0:
                btc_direction = "Bearish"
            else:
                btc_direction = "Flat"

        except (TypeError, ValueError):
            pass

    # ---------------------------------------------------------
    # Market breadth
    # ---------------------------------------------------------
    #
    # Use available USDT tickers instead of the Futures
    # whitelist so breadth still works when Futures API
    # is blocked.
    #

    breadth_tickers = [
        t for t in tickers
        if (
            t.get("symbol", "").endswith("USDT")
            and t.get("symbol")
            not in cfg.EXCLUDE_SYMBOLS
        )
    ]

    green = 0
    red = 0

    for t in breadth_tickers:
        try:
            change = float(
                t["priceChangePercent"]
            )

            if change > 0:
                green += 1
            elif change < 0:
                red += 1

        except (TypeError, ValueError):
            continue

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

    # ---------------------------------------------------------
    # BTC Futures data
    # ---------------------------------------------------------

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
                params={
                    "symbol": "BTCUSDT"
                },
                timeout=5,
            )

            if res.ok:
                data = res.json()

                value = data.get(
                    "openInterest"
                )

                if value is not None:
                    return float(value)

        except Exception:
            continue

    print(
        "[screener] BTC Futures OI unavailable."
    )

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
                params={
                    "symbol": "BTCUSDT"
                },
                timeout=5,
            )

            if res.ok:
                data = res.json()

                value = data.get(
                    "lastFundingRate"
                )

                if value is not None:
                    return float(value)

        except Exception:
            continue

    print(
        "[screener] BTC funding rate unavailable."
    )

    return None


def _fetch_all_24hr_tickers():
    """
    Fetch Binance 24h ticker data.

    Uses the Binance data API Spot endpoint because it
    remains accessible when Futures endpoints return 451.
    """

    url = (
        f"{cfg.BINANCE_FAPI_BASE}"
        "/api/v3/ticker/24hr"
    )

    res = requests.get(
        url,
        timeout=15,
    )

    res.raise_for_status()

    return res.json()


def _norm_log(value):
    return math.log10(
        max(value, 0) + 1
    ) / 10


def _norm(value, cap):
    if cap <= 0:
        return 0

    return min(
        max(value, 0) / cap,
        1,
    )


if __name__ == "__main__":
    rows = get_screener_shortlist()

    for row in rows:
        print(row)
