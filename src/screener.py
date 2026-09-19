"""
screener.py

Builds a shortlist from Binance 24h Spot ticker data.

The screener:
- Uses Binance Spot exchangeInfo to verify currently tradable symbols.
- Keeps only TRADING USDT pairs.
- Excludes configured stablecoin pairs.
- Scores candidates using liquidity + momentum + volume proxy.
- Provides BTC and market-breadth context.
- Treats Futures OI/funding as optional because Futures endpoints
  may be unavailable from GitHub Actions.
"""

import math
import requests

from src import bot_config as cfg


# =========================================================
# Binance Spot endpoints
# =========================================================

SPOT_BASE_URL = "https://data-api.binance.vision"

EXCHANGE_INFO_URL = (
    f"{SPOT_BASE_URL}/api/v3/exchangeInfo"
)

TICKER_24HR_URL = (
    f"{SPOT_BASE_URL}/api/v3/ticker/24hr"
)


# =========================================================
# Main screener
# =========================================================

def get_screener_shortlist(limit=None):
    limit = limit or cfg.SCREENER_SHORTLIST_SIZE

    # -----------------------------------------------------
    # Fetch currently tradable Binance Spot symbols
    # -----------------------------------------------------

    active_symbols = _fetch_active_usdt_symbols()

    print(
        f"[screener] active Binance USDT symbols: "
        f"{len(active_symbols)}"
    )

    if not active_symbols:
        print(
            "[screener] no active USDT symbols found."
        )
        return []

    # -----------------------------------------------------
    # Fetch 24h ticker data
    # -----------------------------------------------------

    tickers = _fetch_all_24hr_tickers()

    print(
        f"[screener] total tickers: "
        f"{len(tickers)}"
    )

    # -----------------------------------------------------
    # Keep only active Binance symbols
    # -----------------------------------------------------

    usdt_pairs = []

    for ticker in tickers:
        symbol = ticker.get("symbol", "")

        if symbol not in active_symbols:
            continue

        if symbol in cfg.EXCLUDE_SYMBOLS:
            continue

        try:
            quote_volume = float(
                ticker.get("quoteVolume", 0)
            )

            last_price = float(
                ticker.get("lastPrice", 0)
            )

            pct_change = float(
                ticker.get("priceChangePercent", 0)
            )

        except (TypeError, ValueError):
            continue

        if quote_volume <= 0:
            continue

        if last_price <= 0:
            continue

        usdt_pairs.append(ticker)

    print(
        f"[screener] usable active USDT pairs: "
        f"{len(usdt_pairs)}"
    )

    if not usdt_pairs:
        print(
            "[screener] no usable active USDT pairs."
        )
        return []

    # -----------------------------------------------------
    # Market context
    # -----------------------------------------------------

    market_context = get_market_context(
        tickers,
        active_symbols,
    )

    # -----------------------------------------------------
    # Score candidates
    # -----------------------------------------------------

    scored = []

    for ticker in usdt_pairs:
        symbol = ticker["symbol"]

        try:
            quote_volume = float(
                ticker["quoteVolume"]
            )

            pct_change = abs(
                float(
                    ticker["priceChangePercent"]
                )
            )

            weighted_avg = float(
                ticker.get("weightedAvgPrice") or 1
            )

            base_volume = float(
                ticker.get("volume") or 0
            )

            last_price = float(
                ticker["lastPrice"]
            )

        except (TypeError, ValueError):
            continue

        if weighted_avg <= 0:
            weighted_avg = 1

        # Simple volume proxy.
        volume_spike = (
            base_volume / weighted_avg
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
            "last_price": last_price,
            "score": score,
            "market_context": market_context,
        })

    # -----------------------------------------------------
    # Sort
    # -----------------------------------------------------

    scored.sort(
        key=lambda row: row["score"],
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


# =========================================================
# Active Binance Spot symbols
# =========================================================

def _fetch_active_usdt_symbols():
    """
    Fetch Binance Spot exchange information.

    Only symbols satisfying all of these are accepted:

    - status == TRADING
    - quoteAsset == USDT
    - symbol is not in EXCLUDE_SYMBOLS

    This prevents inactive/delisted symbols from entering
    the screener.
    """

    try:
        response = requests.get(
            EXCHANGE_INFO_URL,
            timeout=15,
        )

        response.raise_for_status()

        data = response.json()

    except Exception as exc:
        print(
            "[screener] failed to fetch exchangeInfo: "
            f"{exc}"
        )
        return set()

    symbols = data.get(
        "symbols",
        [],
    )

    active = set()

    for item in symbols:
        symbol = item.get(
            "symbol",
            "",
        )

        status = item.get(
            "status",
            "",
        )

        quote_asset = item.get(
            "quoteAsset",
            "",
        )

        if status != "TRADING":
            continue

        if quote_asset != "USDT":
            continue

        if symbol in cfg.EXCLUDE_SYMBOLS:
            continue

        active.add(symbol)

    return active


# =========================================================
# Market context
# =========================================================

def get_market_context(
    tickers,
    active_symbols,
):
    """
    Build market-wide context.

    Futures OI and funding are optional.
    """

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

    # -----------------------------------------------------
    # BTC direction
    # -----------------------------------------------------

    btc = next(
        (
            ticker
            for ticker in tickers
            if ticker.get("symbol")
            == cfg.BTC_SYMBOL
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

    # -----------------------------------------------------
    # Market breadth
    # -----------------------------------------------------

    breadth_tickers = [
        ticker
        for ticker in tickers
        if (
            ticker.get("symbol")
            in active_symbols
            and ticker.get("symbol")
            not in cfg.EXCLUDE_SYMBOLS
        )
    ]

    green = 0
    red = 0

    for ticker in breadth_tickers:
        try:
            change = float(
                ticker["priceChangePercent"]
            )

        except (TypeError, ValueError):
            continue

        if change > 0:
            green += 1

        elif change < 0:
            red += 1

    total = green + red

    if total > 0:

        green_pct = round(
            (green / total) * 100,
            1,
        )

        red_pct = round(
            (red / total) * 100,
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

    # -----------------------------------------------------
    # Optional BTC Futures data
    # -----------------------------------------------------

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


# =========================================================
# BTC Futures Open Interest
# =========================================================

def _fetch_btc_open_interest():
    """Fetch current BTCUSDT Futures open interest."""

    urls = [
        "https://fapi.binance.com/fapi/v1/openInterest",
        "https://data-api.binance.vision/fapi/v1/openInterest",
    ]

    for url in urls:
        try:
            response = requests.get(
                url,
                params={
                    "symbol": "BTCUSDT"
                },
                timeout=5,
            )

            if not response.ok:
                continue

            data = response.json()

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


# =========================================================
# BTC Funding Rate
# =========================================================

def _fetch_btc_funding_rate():
    """Fetch latest BTCUSDT Futures funding rate."""

    urls = [
        "https://fapi.binance.com/fapi/v1/premiumIndex",
        "https://data-api.binance.vision/fapi/v1/premiumIndex",
    ]

    for url in urls:
        try:
            response = requests.get(
                url,
                params={
                    "symbol": "BTCUSDT"
                },
                timeout=5,
            )

            if not response.ok:
                continue

            data = response.json()

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


# =========================================================
# 24h ticker data
# =========================================================

def _fetch_all_24hr_tickers():
    """Fetch Binance Spot 24h ticker statistics."""

    response = requests.get(
        TICKER_24HR_URL,
        timeout=15,
    )

    response.raise_for_status()

    return response.json()


# =========================================================
# Score helpers
# =========================================================

def _norm_log(value):
    return (
        math.log10(
            max(value, 0) + 1
        ) / 10
    )


def _norm(value, cap):
    if cap <= 0:
        return 0

    return min(
        max(value, 0) / cap,
        1,
    )


# =========================================================
# Manual test
# =========================================================

if __name__ == "__main__":

    rows = get_screener_shortlist()

    for row in rows:
        print(row)
