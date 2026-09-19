"""
advanced_market_data.py

Advanced market data collector.

Purpose:
- Collect market data for research/backtesting.
- Advanced data is optional.
- API failures must never stop the main bot.
- 451 responses fail fast instead of retrying multiple blocked hosts.
- Requests are made concurrently where possible to reduce runtime.

Collected data:
- Multi-timeframe support/resistance
- BTC 4H/1D context
- Open Interest
- OI change
- Funding rate
- Long/Short account ratio
- Liquidation data
- Order book imbalance
"""

import os
from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)

import requests


# =========================================================
# CONFIG
# =========================================================

BINANCE_FAPI_URLS = [
    "https://fapi.binance.com",
    "https://fapi1.binance.com",
    "https://fapi2.binance.com",
    "https://fapi3.binance.com",
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
        "8",
    )
)

HEADERS = {
    "User-Agent": "trade-setup-bot/1.0",
    "Accept": "application/json",
}


# =========================================================
# REQUEST HELPER
# =========================================================

def _get(
    endpoint,
    params=None,
    timeout=None,
):
    """
    Request one Binance Futures endpoint.

    Important:
    - 451 fails immediately.
    - Other connection errors may try the next host.
    - Successful response returns JSON.
    - Failure returns None.
    """

    timeout = (
        timeout
        if timeout is not None
        else REQUEST_TIMEOUT
    )

    last_error = None

    for base_url in BINANCE_FAPI_URLS:

        url = (
            f"{base_url}{endpoint}"
        )

        try:

            response = requests.get(
                url,
                params=params or {},
                timeout=timeout,
                headers=HEADERS,
            )

            # -------------------------------------------------
            # 451 = access restriction
            #
            # Trying the other Binance hosts usually does not
            # solve the same environment restriction.
            # Fail fast instead.
            # -------------------------------------------------

            if response.status_code == 451:

                print(
                    f"[advanced_market_data] "
                    f"451 blocked: {base_url}"
                )

                return None

            response.raise_for_status()

            return response.json()

        except requests.RequestException as err:

            last_error = err

            continue

        except Exception as err:

            last_error = err

            continue

    print(
        f"[advanced_market_data] "
        f"unavailable {endpoint}: "
        f"{last_error}"
    )

    return None


# =========================================================
# SAFE FLOAT
# =========================================================

def _safe_float(value):

    try:

        return float(value)

    except Exception:

        return None


# =========================================================
# KLINES
# =========================================================

def get_klines(
    symbol,
    interval,
    limit=100,
):

    return _get(
        "/fapi/v1/klines",
        {
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
        },
    )


# =========================================================
# SWING LEVELS
# =========================================================

def _swing_levels(
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


# =========================================================
# MULTI-TIMEFRAME S/R
# =========================================================

def get_multi_timeframe_sr(
    symbol,
):

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

            klines = get_klines(
                symbol,
                timeframe,
                limit,
            )

            result[timeframe] = (
                _swing_levels(
                    klines,
                    min(
                        60,
                        limit,
                    ),
                )
            )

        except Exception as err:

            print(
                f"[advanced_market_data] "
                f"S/R failed {symbol} "
                f"{timeframe}: {err}"
            )

            result[timeframe] = {
                "support": None,
                "resistance": None,
            }

    return result


# =========================================================
# EMA
# =========================================================

def _ema(
    values,
    period,
):

    if not values:

        return None

    multiplier = (
        2 / (period + 1)
    )

    ema = values[0]

    for price in values[1:]:

        ema = (
            price - ema
        ) * multiplier + ema

    return ema


# =========================================================
# TREND
# =========================================================

def get_trend(
    symbol,
    interval,
):

    klines = get_klines(
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


# =========================================================
# BTC CONTEXT
# =========================================================

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


# =========================================================
# OPEN INTEREST
# =========================================================

def get_open_interest(
    symbol,
):

    data = _get(
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


# =========================================================
# OI CHANGE
# =========================================================

def get_oi_change(
    symbol,
):

    data = _get(
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
                (new - old)
                / old
            ) * 100,
            2,
        )

    except Exception:

        return None


# =========================================================
# FUNDING
# =========================================================

def get_funding(
    symbol,
):

    data = _get(
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


# =========================================================
# LONG / SHORT ACCOUNT RATIO
# =========================================================

def get_long_short_ratio(
    symbol,
):

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


# =========================================================
# LIQUIDATIONS
# =========================================================

def get_liquidations(
    symbol,
):

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
                price * quantity
            )

            side = row.get(
                "side",
                "",
            )

            # SELL force order generally
            # corresponds to a long position
            # being liquidated.

            if side == "SELL":

                long_liq += value

            # BUY force order generally
            # corresponds to a short position
            # being liquidated.

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


# =========================================================
# ORDER BOOK
# =========================================================

def get_orderbook(
    symbol,
):

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
        }

    except Exception:

        return None


# =========================================================
# COLLECT ONE SYMBOL
# =========================================================

def _collect_symbol_data(
    symbol,
):

    results = {}

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

        "orderbook":
            lambda: get_orderbook(
                symbol
            ),
    }

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
                    f"{symbol}: {err}"
                )

                results[name] = None

    return results


# =========================================================
# MAIN FUNCTION
# =========================================================

def get_advanced_market_data(
    symbol,
):

    print(
        f"[advanced_market_data] "
        f"collecting data for {symbol}..."
    )

    data = {
        "multi_timeframe_sr": {},
        "btc_context": {},
        "open_interest": None,
        "oi_change_1h_pct": None,
        "funding_rate": None,
        "long_short_ratio": None,
        "liquidations": None,
        "orderbook": None,
    }

    # -----------------------------------------------------
    # SYMBOL ADVANCED DATA
    # -----------------------------------------------------

    try:

        symbol_data = (
            _collect_symbol_data(
                symbol
            )
        )

        data.update(
            symbol_data
        )

    except Exception as err:

        print(
            f"[advanced_market_data] "
            f"symbol data failed: {err}"
        )

    # -----------------------------------------------------
    # MULTI-TIMEFRAME S/R
    # -----------------------------------------------------

    try:

        data[
            "multi_timeframe_sr"
        ] = get_multi_timeframe_sr(
            symbol
        )

    except Exception as err:

        print(
            f"[advanced_market_data] "
            f"S/R collection failed: {err}"
        )

    # -----------------------------------------------------
    # BTC CONTEXT
    # -----------------------------------------------------

    try:

        data[
            "btc_context"
        ] = get_btc_context()

    except Exception as err:

        print(
            f"[advanced_market_data] "
            f"BTC context failed: {err}"
        )

    # -----------------------------------------------------
    # SUMMARY
    # -----------------------------------------------------

    available = []

    for key, value in data.items():

        if value:

            available.append(
                key
            )

    print(
        f"[advanced_market_data] "
        f"completed for {symbol}"
    )

    print(
        f"[advanced_market_data] "
        f"available fields: "
        f"{', '.join(available) if available else 'none'}"
    )

    return data
