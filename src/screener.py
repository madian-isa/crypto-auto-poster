"""
screener.py

Build a Binance Spot shortlist that prioritizes liquid, actively traded,
currently moving USDT pairs. Unit price is deliberately not used as a
popularity signal: a low-priced token can still be popular and liquid.
"""

import bisect
import math
import requests

from src import bot_config as cfg


SPOT_BASE_URL = "https://data-api.binance.vision"
EXCHANGE_INFO_URL = f"{SPOT_BASE_URL}/api/v3/exchangeInfo"
TICKER_24HR_URL = f"{SPOT_BASE_URL}/api/v3/ticker/24hr"

# Dynamic gates exclude the least active fraction of eligible Binance pairs,
# rather than applying a nominal coin-price cutoff.
MIN_ACTIVITY_PERCENTILE = 0.35


def get_screener_shortlist(limit=None):
    limit = limit or cfg.SCREENER_SHORTLIST_SIZE
    active_symbols = _fetch_active_usdt_symbols()

    print(
        f"[screener] active Binance USDT symbols: "
        f"{len(active_symbols)}"
    )
    if not active_symbols:
        print("[screener] no active USDT symbols found.")
        return []

    tickers = _fetch_all_24hr_tickers()
    print(f"[screener] total tickers: {len(tickers)}")

    usdt_pairs = []
    for ticker in tickers:
        symbol = ticker.get("symbol", "")
        if symbol not in active_symbols or symbol in cfg.EXCLUDE_SYMBOLS:
            continue
        try:
            quote_volume = float(ticker.get("quoteVolume", 0))
            last_price = float(ticker.get("lastPrice", 0))
            trade_count = int(ticker.get("count", 0))
            pct_change = float(ticker.get("priceChangePercent", 0))
        except (TypeError, ValueError):
            continue
        if quote_volume <= 0 or last_price <= 0 or trade_count <= 0:
            continue
        ticker["_quote_volume"] = quote_volume
        ticker["_last_price"] = last_price
        ticker["_trade_count"] = trade_count
        ticker["_pct_change"] = pct_change
        usdt_pairs.append(ticker)

    print(
        f"[screener] usable active USDT pairs: "
        f"{len(usdt_pairs)}"
    )
    if not usdt_pairs:
        print("[screener] no usable active USDT pairs.")
        return []

    market_context = get_market_context(tickers, active_symbols)

    # Rank by turnover and number of actual trades, then reward meaningful
    # 24-hour movement. Absolute movement includes both rising and falling
    # trending coins so the setup generator can decide LONG versus SHORT.
    sorted_quote_volumes = sorted(
        row["_quote_volume"] for row in usdt_pairs
    )
    sorted_trade_counts = sorted(
        row["_trade_count"] for row in usdt_pairs
    )
    quote_volume_floor = _percentile(
        sorted_quote_volumes,
        MIN_ACTIVITY_PERCENTILE,
    )
    trade_count_floor = _percentile(
        sorted_trade_counts,
        MIN_ACTIVITY_PERCENTILE,
    )

    active_pairs = [
        row
        for row in usdt_pairs
        if (
            row["_quote_volume"] >= quote_volume_floor
            and row["_trade_count"] >= trade_count_floor
        )
    ]
    excluded_count = len(usdt_pairs) - len(active_pairs)
    print(
        "[screener] popularity gates: "
        f"quote volume >= {quote_volume_floor:,.0f} USDT, "
        f"24h trades >= {trade_count_floor:,}; "
        f"excluded {excluded_count} low-activity pairs"
    )

    if not active_pairs:
        print("[screener] no pairs passed popularity gates.")
        return []

    scored = []
    for ticker in active_pairs:
        quote_volume = ticker["_quote_volume"]
        trade_count = ticker["_trade_count"]
        pct_change = ticker["_pct_change"]

        volume_rank = _percentile_rank(
            quote_volume,
            sorted_quote_volumes,
        )
        trade_rank = _percentile_rank(
            trade_count,
            sorted_trade_counts,
        )
        movement_score = min(abs(pct_change) / 20.0, 1.0)

        # Popularity/activity dominates; momentum separates currently
        # moving pairs from merely large but quiet pairs.
        score = (
            volume_rank * 0.45
            + trade_rank * 0.35
            + movement_score * 0.20
        )

        scored.append({
            "symbol": ticker["symbol"],
            "quote_volume": quote_volume,
            "trade_count": trade_count,
            "pct_change": pct_change,
            "last_price": ticker["_last_price"],
            "score": score,
            "market_context": market_context,
        })

    scored.sort(
        key=lambda row: (
            row["score"],
            row["quote_volume"],
            row["trade_count"],
        ),
        reverse=True,
    )
    result = scored[:limit]

    print(f"[screener] shortlist size: {len(result)}")
    if result:
        print(
            "[screener] top candidates: "
            + ", ".join(row["symbol"] for row in result[:10])
        )
    return result


def _fetch_active_usdt_symbols():
    """Return currently trading Binance Spot USDT symbols."""
    try:
        response = requests.get(EXCHANGE_INFO_URL, timeout=15)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        print(
            "[screener] failed to fetch exchangeInfo: "
            f"{exc}"
        )
        return set()

    active = set()
    for item in data.get("symbols", []):
        symbol = item.get("symbol", "")
        if (
            item.get("status") != "TRADING"
            or item.get("quoteAsset") != "USDT"
            or symbol in cfg.EXCLUDE_SYMBOLS
        ):
            continue
        active.add(symbol)
    return active


def get_market_context(tickers, active_symbols):
    """Build market-wide context; Futures values are optional."""
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

    btc = next(
        (
            ticker
            for ticker in tickers
            if ticker.get("symbol") == cfg.BTC_SYMBOL
        ),
        None,
    )
    btc_change = None
    btc_direction = "Unknown"
    if btc:
        try:
            btc_change = float(btc["priceChangePercent"])
            if btc_change > 0:
                btc_direction = "Bullish"
            elif btc_change < 0:
                btc_direction = "Bearish"
            else:
                btc_direction = "Flat"
        except (TypeError, ValueError):
            pass

    breadth_tickers = [
        ticker
        for ticker in tickers
        if (
            ticker.get("symbol") in active_symbols
            and ticker.get("symbol") not in cfg.EXCLUDE_SYMBOLS
        )
    ]
    green = 0
    red = 0
    for ticker in breadth_tickers:
        try:
            change = float(ticker["priceChangePercent"])
        except (KeyError, TypeError, ValueError):
            continue
        if change > 0:
            green += 1
        elif change < 0:
            red += 1

    total = green + red
    if total:
        green_pct = round(green / total * 100, 1)
        red_pct = round(red / total * 100, 1)
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

    return {
        "btc_change_24h": btc_change,
        "btc_direction": btc_direction,
        "market_green_pct": green_pct,
        "market_red_pct": red_pct,
        "market_breadth": breadth,
        "btc_open_interest": _fetch_btc_open_interest(),
        "btc_funding_rate": _fetch_btc_funding_rate(),
    }


def _fetch_btc_open_interest():
    """Fetch current BTCUSDT Futures open interest if available."""
    urls = (
        "https://fapi.binance.com/fapi/v1/openInterest",
        "https://data-api.binance.vision/fapi/v1/openInterest",
    )
    for url in urls:
        try:
            response = requests.get(
                url,
                params={"symbol": "BTCUSDT"},
                timeout=5,
            )
            if not response.ok:
                continue
            value = response.json().get("openInterest")
            if value is not None:
                return float(value)
        except Exception:
            continue
    print("[screener] BTC Futures OI unavailable.")
    return None


def _fetch_btc_funding_rate():
    """Fetch latest BTCUSDT Futures funding rate if available."""
    urls = (
        "https://fapi.binance.com/fapi/v1/premiumIndex",
        "https://data-api.binance.vision/fapi/v1/premiumIndex",
    )
    for url in urls:
        try:
            response = requests.get(
                url,
                params={"symbol": "BTCUSDT"},
                timeout=5,
            )
            if not response.ok:
                continue
            value = response.json().get("lastFundingRate")
            if value is not None:
                return float(value)
        except Exception:
            continue
    print("[screener] BTC funding rate unavailable.")
    return None


def _fetch_all_24hr_tickers():
    """Fetch Binance Spot 24-hour ticker statistics."""
    response = requests.get(TICKER_24HR_URL, timeout=15)
    response.raise_for_status()
    return response.json()


def _percentile(sorted_values, fraction):
    if not sorted_values:
        return 0
    index = int((len(sorted_values) - 1) * fraction)
    return sorted_values[index]


def _percentile_rank(value, sorted_values):
    if not sorted_values:
        return 0
    return bisect.bisect_right(sorted_values, value) / len(sorted_values)


if __name__ == "__main__":
    for row in get_screener_shortlist():
        print(row)
