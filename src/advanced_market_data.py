"""
advanced_market_data.py

Advanced market-data collector.

Design:
- Advanced data is optional.
- API failures never stop the main bot.
- Futures 451 responses are detected once and cached for
  the current process.
- Public Spot market data is used for:
    - 1H support/resistance
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
            continue
        except Exception as err:
            last_error = err
            continue

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

    if len(rows) < 7:
        return {
            "support": None,
            "resistance": None,
        }

    candles = []
    for row in rows:
        try:
            candles.append(
                {
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                }
            )
        except Exception:
            continue

    if len(candles) < 7:
        return {
            "support": None,
            "resistance": None,
        }

    current_price = candles[-1]["close"]
    swing_lows = []
    swing_highs = []

    for i in range(2, len(candles) - 2):
        current = candles[i]
        previous_1 = candles[i - 1]
        previous_2 = candles[i - 2]
        next_1 = candles[i + 1]
        next_2 = candles[i + 2]

        is_swing_low = (
            current["low"] <= previous_1["low"]
            and current["low"] <= previous_2["low"]
            and current["low"] <= next_1["low"]
            and current["low"] <= next_2["low"]
        )
        if is_swing_low:
            swing_lows.append(current["low"])

        is_swing_high = (
            current["high"] >= previous_1["high"]
            and current["high"] >= previous_2["high"]
            and current["high"] >= next_1["high"]
            and current["high"] >= next_2["high"]
        )
        if is_swing_high:
            swing_highs.append(current["high"])

    supports = [l for l in swing_lows if l < current_price]
    resistances = [l for l in swing_highs if l > current_price]

    support = max(supports) if supports else None
    resistance = min(resistances) if resistances else None

    if support is None:
        below = [c["low"] for c in candles if c["low"] < current_price]
        if below:
            support = min(below)

    if resistance is None:
        above = [c["high"] for c in candles if c["high"] > current_price]
        if above:
            resistance = max(above)

    return {
        "support": support,
        "resistance": resistance,
    }


def get_multi_timeframe_sr(symbol):
    timeframe = "1h"
    limit = 100
    try:
        klines = get_spot_klines(symbol, timeframe, limit)
        levels = _spot_swing_levels(klines, min(60, limit))
        return {"1h": levels}
    except Exception:
        return {
            "1h": {
                "support": None,
                "resistance": None,
            }
        }


# ============================================================
# EMA / TREND
# ============================================================

def _ema(values, period):
    if not values:
        return None
    multiplier = 2 / (period + 1)
    ema = values[0]
    for price in values[1:]:
        ema = (price - ema) * multiplier + ema
    return ema


def get_trend(symbol, interval):
    klines = get_spot_klines(symbol, interval, 100)
    if not klines or len(klines) < 50:
        return {
            "trend": "Unknown",
            "price": None,
            "ema20": None,
            "ema50": None,
        }

    closes = []
    for row in klines:
        try:
            closes.append(float(row[4]))
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
    ema20 = _ema(closes, 20)
    ema50 = _ema(closes, 50)

    if ema20 is not None and ema50 is not None and price > ema20 and ema20 > ema50:
        trend = "Bullish"
    elif ema20 is not None and ema50 is not None and price < ema20 and ema20 < ema50:
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
    return {
        "4h": get_trend("BTCUSDT", "4h"),
        "1d": get_trend("BTCUSDT", "1d"),
    }


# ============================================================
# ORDER BOOK
# ============================================================

def _parse_orderbook(data):
    if not data:
        return None
    try:
        bids = [(float(p), float(q)) for p, q in data.get("bids", [])]
        asks = [(float(p), float(q)) for p, q in data.get("asks", [])]

        bid_value = sum(p * q for p, q in bids)
        ask_value = sum(p * q for p, q in asks)
        total = bid_value + ask_value

        imbalance = ((bid_value - ask_value) / total) * 100 if total > 0 else 0.0
        best_bid = bids[0][0] if bids else None
        best_ask = asks[0][0] if asks else None
        spread = (best_ask - best_bid) if best_bid and best_ask else None

        return {
            "bid_value_usdt": round(bid_value, 2),
            "ask_value_usdt": round(ask_value, 2),
            "imbalance_pct": round(imbalance, 2),
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread": spread,
            "source": "spot",
        }
    except Exception:
        return None


def get_orderbook(symbol):
    data = get_spot_orderbook(symbol, limit=100)
    return _parse_orderbook(data)


# ============================================================
# FUTURES API
# ============================================================

def _futures_get(endpoint, params=None):
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
                    f"[advanced_market_data] Futures API returned 451. Disabling Futures requests for this run."
                )
                _FUTURES_BLOCKED = True
                return None

            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            continue
        except Exception:
            continue

    return None


def get_open_interest(symbol):
    data = _futures_get("/fapi/v1/openInterest", {"symbol": symbol})
    if not data:
        return None
    return _safe_float(data.get("openInterest"))


def get_oi_change(symbol):
    data = _futures_get("/futures/data/openInterestHist", {"symbol": symbol, "period": "1h", "limit": 5})
    if not data or len(data) < 2:
        return None
    try:
        old = _safe_float(data[0].get("sumOpenInterest"))
        new = _safe_float(data[-1].get("sumOpenInterest"))
        if old is None or new is None or old == 0:
            return None
        return round(((new - old) / old) * 100, 2)
    except Exception:
        return None


def get_funding(symbol):
    data = _futures_get("/fapi/v1/premiumIndex", {"symbol": symbol})
    if not data:
        return None
    return _safe_float(data.get("lastFundingRate"))


def get_long_short_ratio(symbol):
    data = _futures_get("/futures/data/globalLongShortAccountRatio", {"symbol": symbol, "period": "1h", "limit": 1})
    if not data:
        return None
    try:
        row = data[-1]
        return {
            "long_account": _safe_float(row.get("longAccount")),
            "short_account": _safe_float(row.get("shortAccount")),
            "ratio": _safe_float(row.get("longShortRatio")),
        }
    except Exception:
        return None


def get_liquidations(symbol):
    data = _futures_get("/fapi/v1/allForceOrders", {"symbol": symbol, "limit": 100})
    if not data:
        return None
    long_liq = 0.0
    short_liq = 0.0
    for row in data:
        try:
            price = _safe_float(row.get("price"))
            quantity = _safe_float(row.get("origQty"))
            if price is None or quantity is None:
                continue
            value = price * quantity
            side = row.get("side", "")
            if side == "SELL":
                long_liq += value
            elif side == "BUY":
                short_liq += value
        except Exception:
            continue
    return {
        "long_liquidation_usdt": round(long_liq, 2),
        "short_liquidation_usdt": round(short_liq, 2),
        "total_usdt": round(long_liq + short_liq, 2),
    }


def _collect_futures_data(symbol):
    tasks = {
        "open_interest": lambda: get_open_interest(symbol),
        "oi_change_1h_pct": lambda: get_oi_change(symbol),
        "funding_rate": lambda: get_funding(symbol),
        "long_short_ratio": lambda: get_long_short_ratio(symbol),
        "liquidations": lambda: get_liquidations(symbol),
    }

    results = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_map = {executor.submit(func): name for name, func in tasks.items()}
        for future in as_completed(future_map):
            name = future_map[future]
            try:
                results[name] = future.result()
            except Exception:
                results[name] = None
    return results


# ============================================================
# MAIN FUNCTION
# ============================================================

def get_advanced_market_data(symbol):
    print(f"[advanced_market_data] collecting data for {symbol}...")

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

    try:
        data["multi_timeframe_sr"] = get_multi_timeframe_sr(symbol)
        data["source_status"]["spot"] = "available"
    except Exception:
        pass

    try:
        data["btc_context"] = get_btc_context()
    except Exception:
        pass

    try:
        data["orderbook"] = get_orderbook(symbol)
    except Exception:
        pass

    try:
        futures_data = _collect_futures_data(symbol)
        data.update(futures_data)

        futures_available = any(value is not None for value in futures_data.values())
        if futures_available:
            data["source_status"]["futures"] = "partially_available"
        elif _FUTURES_BLOCKED:
            data["source_status"]["futures"] = "blocked_451"
        else:
            data["source_status"]["futures"] = "unavailable"
    except Exception:
        data["source_status"]["futures"] = "error"

    available = [key for key, value in data.items() if key != "source_status" and value]

    print(f"[advanced_market_data] completed for {symbol}")
    print(f"[advanced_market_data] spot status: {data['source_status']['spot']}")
    print(f"[advanced_market_data] futures status: {data['source_status']['futures']}")
    print(f"[advanced_market_data] available fields: {', '.join(available) if available else 'none'}")

    return data
