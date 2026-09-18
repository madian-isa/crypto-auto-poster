"""
advanced_market_data.py

Advanced market data for the trade-setup bot.

Includes:
- Multi-timeframe Support / Resistance
- BTC 4H / 1D trend
- Open Interest
- OI change
- Funding Rate
- Long/Short ratio
- Recent liquidation activity
- Order-book liquidity / imbalance

If one data source fails, the bot continues with the remaining data.
"""

import requests

from src import bot_config as cfg


BINANCE_FAPI = "https://fapi.binance.com"


def _get(endpoint, params=None, timeout=10):
    url = f"{BINANCE_FAPI}{endpoint}"

    try:
        response = requests.get(
            url,
            params=params or {},
            timeout=timeout,
        )

        response.raise_for_status()

        return response.json()

    except Exception as err:
        print(
            f"[advanced_market_data] failed "
            f"{endpoint}: {err}"
        )

        return None


# ---------------------------------------------------------
# KLINES
# ---------------------------------------------------------

def get_klines(symbol, interval, limit=200):
    return _get(
        "/fapi/v1/klines",
        {
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
        },
    )


# ---------------------------------------------------------
# SUPPORT / RESISTANCE
# ---------------------------------------------------------

def _swing_levels(klines, lookback=60):
    if not klines:
        return {
            "support": None,
            "resistance": None,
        }

    rows = klines[-lookback:]

    lows = [
        float(row[3])
        for row in rows
    ]

    highs = [
        float(row[2])
        for row in rows
    ]

    if not lows or not highs:
        return {
            "support": None,
            "resistance": None,
        }

    return {
        "support": min(lows),
        "resistance": max(highs),
    }


def get_multi_timeframe_sr(symbol):
    """
    Basic support/resistance from multiple timeframes.
    """

    timeframes = {
        "15m": 100,
        "1h": 100,
        "4h": 100,
        "1d": 100,
        "1w": 100,
    }

    result = {}

    for timeframe, limit in timeframes.items():

        klines = get_klines(
            symbol,
            timeframe,
            limit,
        )

        result[timeframe] = _swing_levels(
            klines,
            lookback=min(60, limit),
        )

    return result


# ---------------------------------------------------------
# TREND
# ---------------------------------------------------------

def get_trend(symbol, interval):
    """
    Simple EMA20 / EMA50 trend classification.
    """

    klines = get_klines(
        symbol,
        interval,
        100,
    )

    if not klines or len(klines) < 50:
        return {
            "trend": "Unknown",
            "price": None,
            "ema20": None,
            "ema50": None,
        }

    closes = [
        float(row[4])
        for row in klines
    ]

    price = closes[-1]

    ema20 = _ema(
        closes,
        20,
    )

    ema50 = _ema(
        closes,
        50,
    )

    if ema20 > ema50 and price > ema20:
        trend = "Bullish"

    elif ema20 < ema50 and price < ema20:
        trend = "Bearish"

    else:
        trend = "Mixed"

    return {
        "trend": trend,
        "price": price,
        "ema20": ema20,
        "ema50": ema50,
    }


# ---------------------------------------------------------
# BTC MARKET CONTEXT
# ---------------------------------------------------------

def get_btc_context():
    return {
        "4h": get_trend(
            "BTCUSDT",
            "4h",
        ),
        "1d": get_trend(
            "BTCUSDT",
            "1d",
        ),
    }


# ---------------------------------------------------------
# OPEN INTEREST
# ---------------------------------------------------------

def get_open_interest(symbol):
    data = _get(
        "/fapi/v1/openInterest",
        {
            "symbol": symbol,
        },
    )

    if not data:
        return None

    try:
        return float(
            data["openInterest"]
        )

    except Exception:
        return None


def get_oi_change(symbol):
    """
    Approximate OI change over recent 1-hour observations.
    """

    data = _get(
        "/futures/data/openInterestHist",
        {
            "symbol": symbol,
            "period": "1h",
            "limit": 5,
        },
    )

    if not data or len(data) < 2:
        return None

    try:
        old = float(
            data[0]["sumOpenInterest"]
        )

        new = float(
            data[-1]["sumOpenInterest"]
        )

        if old == 0:
            return None

        return round(
            (new - old) / old * 100,
            2,
        )

    except Exception:
        return None


# ---------------------------------------------------------
# FUNDING RATE
# ---------------------------------------------------------

def get_funding(symbol):
    data = _get(
        "/fapi/v1/premiumIndex",
        {
            "symbol": symbol,
        },
    )

    if not data:
        return None

    try:
        return float(
            data["lastFundingRate"]
        )

    except Exception:
        return None


# ---------------------------------------------------------
# LONG / SHORT RATIO
# ---------------------------------------------------------

def get_long_short_ratio(symbol):
    data = _get(
        "/futures/data/globalLongShortAccountRatio",
        {
            "symbol": symbol,
            "period": "1h",
            "limit": 1,
        },
    )

    if not data:
        return None

    try:
        row = data[-1]

        return {
            "long_account": float(
                row["longAccount"]
            ),
            "short_account": float(
                row["shortAccount"]
            ),
            "ratio": float(
                row["longShortRatio"]
            ),
        }

    except Exception:
        return None


# ---------------------------------------------------------
# LIQUIDATIONS
# ---------------------------------------------------------

def get_liquidations(symbol):
    """
    Recent forced liquidation activity.

    This is NOT a complete liquidation heatmap.
    """

    data = _get(
        "/fapi/v1/allForceOrders",
        {
            "symbol": symbol,
            "limit": 100,
        },
    )

    if not data:
        return {
            "long_liquidation_usdt": 0,
            "short_liquidation_usdt": 0,
            "total_usdt": 0,
        }

    long_liq = 0.0
    short_liq = 0.0

    for row in data:

        try:
            price = float(
                row["price"]
            )

            quantity = float(
                row["origQty"]
            )

            value = price * quantity

            side = row.get(
                "side",
                "",
            )

            # SELL liquidation generally represents
            # a long position being liquidated.
            if side == "SELL":
                long_liq += value

            # BUY liquidation generally represents
            # a short position being liquidated.
            elif side == "BUY":
                short_liq += value

        except Exception:
            continue

    return {
        "long_liquidation_usdt": round(
            long_liq,
            2,
        ),
        "short_liquidation_usdt": round(
            short_liq,
            2,
        ),
        "total_usdt": round(
            long_liq + short_liq,
            2,
        ),
    }


# ---------------------------------------------------------
# ORDER BOOK
# ---------------------------------------------------------

def get_orderbook(symbol):
    data = _get(
        "/fapi/v1/depth",
        {
            "symbol": symbol,
            "limit": 100,
        },
    )

    if not data:
        return None

    try:
        bids = [
            (
                float(price),
                float(quantity),
            )
            for price, quantity in data["bids"]
        ]

        asks = [
            (
                float(price),
                float(quantity),
            )
            for price, quantity in data["asks"]
        ]

        bid_value = sum(
            price * quantity
            for price, quantity in bids
        )

        ask_value = sum(
            price * quantity
            for price, quantity in asks
        )

        total = bid_value + ask_value

        if total:
            imbalance = (
                (bid_value - ask_value)
                / total
                * 100
            )
        else:
            imbalance = 0

        best_bid = (
            bids[0][0]
            if bids
            else None
        )

        best_ask = (
            asks[0][0]
            if asks
            else None
        )

        spread = None

        if best_bid is not None and best_ask is not None:
            spread = best_ask - best_bid

        return {
            "bid_value_usdt": round(
                bid_value,
                2,
            ),
            "ask_value_usdt": round(
                ask_value,
                2,
            ),
            "imbalance_pct": round(
                imbalance,
                2,
            ),
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread": spread,
        }

    except Exception:
        return None


# ---------------------------------------------------------
# MAIN ADVANCED DATA FUNCTION
# ---------------------------------------------------------

def get_advanced_market_data(symbol):
    """
    Collect all advanced market data for one symbol.
    """

    print(
        f"[advanced_market_data] collecting data "
        f"for {symbol}..."
    )

    data = {
        "multi_timeframe_sr":
            get_multi_timeframe_sr(symbol),

        "btc_context":
            get_btc_context(),

        "open_interest":
            get_open_interest(symbol),

        "oi_change_1h_pct":
            get_oi_change(symbol),

        "funding_rate":
            get_funding(symbol),

        "long_short_ratio":
            get_long_short_ratio(symbol),

        "liquidations":
            get_liquidations(symbol),

        "orderbook":
            get_orderbook(symbol),
    }

    print(
        f"[advanced_market_data] completed "
        f"for {symbol}"
    )

    return data


# ---------------------------------------------------------
# EMA HELPER
# ---------------------------------------------------------

def _ema(values, period):
    if not values:
        return 0

    multiplier = 2 / (
        period + 1
    )

    ema = values[0]

    for price in values[1:]:
        ema = (
            price - ema
        ) * multiplier + ema

    return ema
