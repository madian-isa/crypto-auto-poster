"""
advanced_market_data.py

Advanced market-data collector.

Design:
- Advanced data is optional.
- API failures never stop the main bot.
- Futures 451 responses are detected once and cached for
  the current process.
- Public Spot market data is used for:
    - multi-timeframe S/R
    - BTC context
    - order book
- Futures-only data is optional:
    - Open Interest
    - OI change
    - Funding
    - Long/Short ratio
    - Liquidations

This module is intended for market-data research/backtesting.
"""

import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests


# ============================================================
# CONFIG
# ============================================================

FUTURES_BASE_URLS = [
    "https://fapi.binance.com",
    "https://fapi1.binance.com",
    "https://fapi2.binance.com",
    "https://fapi3.binance.com",
]

SPOT_BASE_URLS = [
    "https://data-api.binance.vision",
    "https://api.binance.com",
]

REQUEST_TIMEOUT = float(
    os.environ.get(
        "ADVANCED_DATA_TIMEOUT",
        "5",
    )
)

MAX_WORKERS = int(
    os.environ.get(
        "ADVANCED_DATA_WORKERS",
        "6",
    )
)

HEADERS = {
    "User-Agent": "trade-setup-bot/1.0",
    "Accept": "application/json",
}


# ============================================================
# PROCESS STATUS
# ============================================================

_FUTURES_BLOCKED = False


# ============================================================
# HELPERS
# ============================================================

def _safe_float(value):
    try:
        return float(value)
    except Exception:
        return None


def _request_json(
    base_urls,
    endpoint,
    params=None,
    timeout=None,
    service_name="api",
):
    """
    Generic GET helper.

    451:
        Stop trying the current service immediately.

    Other request errors:
        Try the next available base URL.
    """

    timeout = (
        timeout
        if timeout is not None
        else REQUEST_TIMEOUT
    )

    last_error = None

    for base_url in base_urls:

        url = f"{base_url}{endpoint}"

        try:

            response = requests.get(
                url,
                params=params or {},
                timeout=timeout,
                headers=HEADERS,
            )

            if response.status_code == 451:

                print(
                    f"[advanced_market_data] "
                    f"{service_name} 451 blocked: "
                    f"{base_url}"
                )

                return None

            response.raise_for_status()

            return response.json()

        except requests.RequestException as err:

            last_error = err

            print(
                f"[advanced_market_data] "
                f"{service_name} request failed: "
                f"{base_url} -> {err}"
            )

            continue

        except Exception as err:

            last_error = err

            print(
                f"[advanced_market_data] "
                f"{service_name} unexpected error: "
                f"{err}"
            )

            continue

    print(
        f"[advanced_market_data] "
        f"{service_name} unavailable: "
        f"{last_error}"
    )

    return None


# ============================================================
# SPOT MARKET DATA
# ============================================================

def _spot_get(
    endpoint,
    params=None,
    timeout=None,
):
    return _request_json(
        SPOT_BASE_URLS,
        endpoint,
        params=params,
        timeout=timeout,
        service_name="spot",
    )


def get_spot_klines(
    symbol,
    interval,
    limit=100,
):
    return _spot_get(
        "/api/v3/klines",
        {
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
        },
    )


def get_spot_orderbook(
    symbol,
    limit=100,
):
    return _spot_get(
        "/api/v3/depth",
        {
            "symbol": symbol,
            "limit": limit,
        },
    )


# ============================================================
# SUPPORT / RESISTANCE
# ============================================================

def _spot_swing_levels(
    klines,
    lookback=60,
):
    if not klines:
        return {
            "support": None,
            "resistance": None,
        }

    rows = klines[-lookback:]

    lows = []
    highs = []

    for row in rows:

        try:
            lows.append(
                float(row[3])
            )

            highs.append(
                float(row[2])
            )

        except Exception:
            continue

    if not lows or not highs:
        return {
            "support": None,
            "resistance": None,
        }

    return {
        "support": min(lows),
        "resistance": max(highs),
    }


def get_multi_timeframe_sr(
    symbol,
):
    """
    Multi-timeframe S/R using public Spot klines.
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

        try:

            klines = get_spot_klines(
                symbol,
                timeframe,
                limit,
            )

            result[timeframe] = _spot_swing_levels(
                klines,
                min(60, limit),
            )

        except Exception as err:

            print(
                f"[advanced_market_data] "
                f"S/R failed "
                f"{symbol} "
                f"{timeframe}: "
                f"{err}"
            )

            result[timeframe] = {
                "support": None,
                "resistance": None,
            }

    return result


# ============================================================
# EMA / TREND
# ============================================================

def _ema(
    values,
    period,
):
    if not values:
        return None

    multiplier = 2 / (
        period + 1
    )

    ema = values[0]

    for price in values[1:]:

        ema = (
            price - ema
        ) * multiplier + ema

    return ema


def get_trend(
    symbol,
    interval,
):
    """
    Trend calculation using public Spot klines.
    """

    klines = get_spot_klines(
        symbol,
        interval,
        100,
    )

    if (
        not klines
        or len(klines) < 50
    ):
        return {
            "trend": "Unknown",
            "price": None,
            "ema20": None,
            "ema50": None,
        }

    closes = []

    for row in klines:

        try:
            closes.append(
                float(row[4])
            )

        except Exception:
            continue

    if len(closes) < 50:

        return {
            "trend": "Unknown",
            "price": None,
            "ema20": None,
            "ema50": None,
        }

    price = closes[-1]

    ema20 = _ema(
        closes,
        20,
    )

    ema50 = _ema(
        closes,
        50,
    )

    if (
        ema20 is not None
        and ema50 is not None
        and price > ema20
        and ema20 > ema50
    ):

        trend = "Bullish"

    elif (
        ema20 is not None
        and ema50 is not None
        and price < ema20
        and ema20 < ema50
    ):

        trend = "Bearish"

    else:

        trend = "Mixed"

    return {
        "trend": trend,
        "price": price,
        "ema20": ema20,
        "ema50": ema50,
    }


def get_btc_context():
    """
    BTC context using public Spot data.
    """

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


# ============================================================
# ORDER BOOK
# ============================================================

def _parse_orderbook(
    data,
):
    if not data:
        return None

    try:

        bids = [
            (
                float(price),
                float(quantity),
            )
            for price, quantity
            in data.get(
                "bids",
                [],
            )
        ]

        asks = [
            (
                float(price),
                float(quantity),
            )
            for price, quantity
            in data.get(
                "asks",
                [],
            )
        ]

        bid_value = sum(
            price * quantity
            for price, quantity
            in bids
        )

        ask_value = sum(
            price * quantity
            for price, quantity
            in asks
        )

        total = (
            bid_value
            + ask_value
        )

        if total > 0:

            imbalance = (
                (
                    bid_value
                    - ask_value
                )
                / total
            ) * 100

        else:

            imbalance = 0.0

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

        if (
            best_bid is not None
            and best_ask is not None
        ):

            spread = (
                best_ask
                - best_bid
            )

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
            "source": "spot",
        }

    except Exception as err:

        print(
            f"[advanced_market_data] "
            f"orderbook parse failed: "
            f"{err}"
        )

        return None


def get_orderbook(
    symbol,
):
    data = get_spot_orderbook(
        symbol,
        limit=100,
    )

    return _parse_orderbook(
        data
    )


# ============================================================
# FUTURES API
# ============================================================

def _futures_get(
    endpoint,
    params=None,
):
    """
    Futures request.

    Once a 451 is received, Futures requests are disabled
    for the rest of the current Python process.
    """

    global _FUTURES_BLOCKED

    if _FUTURES_BLOCKED:

        return None

    for base_url in FUTURES_BASE_URLS:

        url = f"{base_url}{endpoint}"

        try:

            response = requests.get(
                url,
                params=params or {},
                timeout=REQUEST_TIMEOUT,
                headers=HEADERS,
            )

            if response.status_code == 451:

                print(
                    "[advanced_market_data] "
                    "Futures API returned 451."
                )

                print(
                    "[advanced_market_data] "
                    "Disabling Futures requests "
                    "for this run."
                )

                _FUTURES_BLOCKED = True

                return None

            response.raise_for_status()

            return response.json()

        except requests.RequestException as err:

            print(
                f"[advanced_market_data] "
                f"Futures request failed: "
                f"{base_url} -> {err}"
            )

            continue

        except Exception as err:

            print(
                f"[advanced_market_data] "
                f"Futures unexpected error: "
                f"{err}"
            )

            continue

    return None


# ============================================================
# OPEN INTEREST
# ============================================================

def get_open_interest(
    symbol,
):
    data = _futures_get(
        "/fapi/v1/openInterest",
        {
            "symbol": symbol,
        },
    )

    if not data:
        return None

    return _safe_float(
        data.get(
            "openInterest"
        )
    )


# ============================================================
# OI CHANGE
# ============================================================

def get_oi_change(
    symbol,
):
    data = _futures_get(
        "/futures/data/openInterestHist",
        {
            "symbol": symbol,
            "period": "1h",
            "limit": 5,
        },
    )

    if (
        not data
        or len(data) < 2
    ):
        return None

    try:

        old = _safe_float(
            data[0].get(
                "sumOpenInterest"
            )
        )

        new = _safe_float(
            data[-1].get(
                "sumOpenInterest"
            )
        )

        if (
            old is None
            or new is None
            or old == 0
        ):

            return None

        return round(
            (
                (
                    new - old
                )
                / old
            ) * 100,
            2,
        )

    except Exception:

        return None


# ============================================================
# FUNDING
# ============================================================

def get_funding(
    symbol,
):
    data = _futures_get(
        "/fapi/v1/premiumIndex",
        {
            "symbol": symbol,
        },
    )

    if not data:
        return None

    return _safe_float(
        data.get(
            "lastFundingRate"
        )
    )


# ============================================================
# LONG / SHORT RATIO
# ============================================================

def get_long_short_ratio(
    symbol,
):
    data = _futures_get(
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

        long_account = _safe_float(
            row.get(
                "longAccount"
            )
        )

        short_account = _safe_float(
            row.get(
                "shortAccount"
            )
        )

        ratio = _safe_float(
            row.get(
                "longShortRatio"
            )
        )

        return {
            "long_account": long_account,
            "short_account": short_account,
            "ratio": ratio,
        }

    except Exception:

        return None


# ============================================================
# LIQUIDATIONS
# ============================================================

def get_liquidations(
    symbol,
):
    data = _futures_get(
        "/fapi/v1/allForceOrders",
        {
            "symbol": symbol,
            "limit": 100,
        },
    )

    if not data:
        return None

    long_liq = 0.0
    short_liq = 0.0

    for row in data:

        try:

            price = _safe_float(
                row.get(
                    "price"
                )
            )

            quantity = _safe_float(
                row.get(
                    "origQty"
                )
            )

            if (
                price is None
                or quantity is None
            ):

                continue

            value = (
                price
                * quantity
            )

            side = row.get(
                "side",
                "",
            )

            if side == "SELL":

                long_liq += value

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


# ============================================================
# FUTURES COLLECTION
# ============================================================

def _collect_futures_data(
    symbol,
):
    """
    Collect Futures-only data concurrently.
    """

    tasks = {
        "open_interest":
            lambda: get_open_interest(
                symbol
            ),

        "oi_change_1h_pct":
            lambda: get_oi_change(
                symbol
            ),

        "funding_rate":
            lambda: get_funding(
                symbol
            ),

        "long_short_ratio":
            lambda: get_long_short_ratio(
                symbol
            ),

        "liquidations":
            lambda: get_liquidations(
                symbol
            ),
    }

    results = {}

    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:

        future_map = {
            executor.submit(
                func
            ): name
            for name, func
            in tasks.items()
        }

        for future in as_completed(
            future_map
        ):

            name = future_map[
                future
            ]

            try:

                results[name] = (
                    future.result()
                )

            except Exception as err:

                print(
                    f"[advanced_market_data] "
                    f"{name} failed for "
                    f"{symbol}: "
                    f"{err}"
                )

                results[name] = None

    return results


# ============================================================
# MAIN FUNCTION
# ============================================================

def get_advanced_market_data(
    symbol,
):
    """
    Main advanced-data collector.

    Always returns a dictionary.
    """

    print(
        f"[advanced_market_data] "
        f"collecting data for "
        f"{symbol}..."
    )

    data = {
        "source_status": {
            "spot": "pending",
            "futures": "pending",
        },

        "multi_timeframe_sr": {},

        "btc_context": {},

        "open_interest": None,

        "oi_change_1h_pct": None,

        "funding_rate": None,

        "long_short_ratio": None,

        "liquidations": None,

        "orderbook": None,
    }


    # ========================================================
    # SPOT S/R
    # ========================================================

    try:

        data[
            "multi_timeframe_sr"
        ] = get_multi_timeframe_sr(
            symbol
        )

        data[
            "source_status"
        ][
            "spot"
        ] = "available"

    except Exception as err:

        print(
            f"[advanced_market_data] "
            f"Spot S/R failed: "
            f"{err}"
        )


    # ========================================================
    # BTC CONTEXT
    # ========================================================

    try:

        data[
            "btc_context"
        ] = get_btc_context()

    except Exception as err:

        print(
            f"[advanced_market_data] "
            f"BTC context failed: "
            f"{err}"
        )


    # ========================================================
    # ORDER BOOK
    # ========================================================

    try:

        data[
            "orderbook"
        ] = get_orderbook(
            symbol
        )

    except Exception as err:

        print(
            f"[advanced_market_data] "
            f"Orderbook failed: "
            f"{err}"
        )


    # ========================================================
    # FUTURES
    # ========================================================

    try:

        futures_data = (
            _collect_futures_data(
                symbol
            )
        )

        data.update(
            futures_data
        )

        futures_available = any(
            value is not None
            for value in futures_data.values()
        )

        if futures_available:

            data[
                "source_status"
            ][
                "futures"
            ] = "partially_available"

        elif _FUTURES_BLOCKED:

            data[
                "source_status"
            ][
                "futures"
            ] = "blocked_451"

        else:

            data[
                "source_status"
            ][
                "futures"
            ] = "unavailable"

    except Exception as err:

        print(
            f"[advanced_market_data] "
            f"Futures collection failed: "
            f"{err}"
        )

        data[
            "source_status"
        ][
            "futures"
        ] = "error"


    # ========================================================
    # SUMMARY
    # ========================================================

    available = []

    for key, value in data.items():

        if key == "source_status":
            continue

        if value:
            available.append(
                key
            )


    print(
        f"[advanced_market_data] "
        f"completed for "
        f"{symbol}"
    )

    print(
        f"[advanced_market_data] "
        f"spot status: "
        f"{data['source_status']['spot']}"
    )

    print(
        f"[advanced_market_data] "
        f"futures status: "
        f"{data['source_status']['futures']}"
    )

    print(
        f"[advanced_market_data] "
        f"available fields: "
        f"{', '.join(available) if available else 'none'}"
    )

    return data
