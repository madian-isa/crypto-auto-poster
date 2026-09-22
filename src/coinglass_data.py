"""
coinglass_data.py

Optional CoinGlass market-data collector.

Design:
- CoinGlass is completely optional.
- Missing/invalid API key never stops the bot.
- API failures return None instead of crashing the bot.
- Uses CoinGlass V4 API.
- Keeps CoinGlass data separate from Binance advanced_market_data.py.

Collected data:
- Open Interest
- OI change
- Funding rate
- Global long/short account ratio
- Liquidations
- Futures taker buy/sell volume
- Futures CVD
"""

import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests


# ============================================================
# CONFIG
# ============================================================

COINGLASS_BASE_URL = (
    "https://open-api-v4.coinglass.com"
)

REQUEST_TIMEOUT = float(
    os.environ.get(
        "COINGLASS_TIMEOUT",
        "6",
    )
)

MAX_WORKERS = int(
    os.environ.get(
        "COINGLASS_WORKERS",
        "6",
    )
)

COINGLASS_API_KEY = os.environ.get(
    "COINGLASS_API_KEY",
    "",
)

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "trade-setup-bot/1.0",
}


# ============================================================
# HELPERS
# ============================================================

def _safe_float(value):
    try:
        if value is None:
            return None

        return float(value)

    except (TypeError, ValueError):
        return None


def _coin_from_symbol(symbol):
    """
    BTCUSDT -> BTC
    ETHUSDT -> ETH
    SOLUSDT -> SOL
    """

    symbol = str(
        symbol or ""
    ).upper().strip()

    for suffix in (
        "USDT",
        "USDC",
        "BUSD",
        "FDUSD",
    ):
        if symbol.endswith(suffix):
            return symbol[:-len(suffix)]

    return symbol


def _request(
    endpoint,
    params=None,
    service_name="api",
):
    """
    Safe CoinGlass GET request.

    Returns:
        JSON dictionary/list on success
        None on failure

    Never raises an API exception to the main bot.
    """

    if not COINGLASS_API_KEY:

        print(
            "[coinglass_data] "
            "API key not configured."
        )

        return None

    url = (
        f"{COINGLASS_BASE_URL}"
        f"{endpoint}"
    )

    headers = dict(
        HEADERS
    )

    headers[
        "CG-API-KEY"
    ] = COINGLASS_API_KEY

    try:

        response = requests.get(
            url,
            params=params or {},
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code == 401:

            print(
                "[coinglass_data] "
                f"{service_name}: "
                "401 authentication failed."
            )

            return None

        if response.status_code == 403:

            print(
                "[coinglass_data] "
                f"{service_name}: "
                "403 plan/permission denied."
            )

            return None

        if response.status_code == 429:

            print(
                "[coinglass_data] "
                f"{service_name}: "
                "429 rate limit."
            )

            return None

        response.raise_for_status()

        payload = response.json()

        if not isinstance(
            payload,
            dict,
        ):

            print(
                "[coinglass_data] "
                f"{service_name}: "
                "unexpected response format."
            )

            return None

        code = payload.get(
            "code"
        )

        if (
            code is not None
            and str(code) != "0"
        ):

            print(
                "[coinglass_data] "
                f"{service_name}: "
                f"API code={code}, "
                f"msg={payload.get('msg')}"
            )

            return None

        return payload

    except requests.RequestException as err:

        print(
            "[coinglass_data] "
            f"{service_name} request failed: "
            f"{err}"
        )

        return None

    except Exception as err:

        print(
            "[coinglass_data] "
            f"{service_name} unexpected error: "
            f"{err}"
        )

        return None


def _extract_data(payload):
    if not payload:
        return None

    data = payload.get(
        "data"
    )

    return data


# ============================================================
# OPEN INTEREST
# ============================================================

def get_open_interest(
    symbol,
):
    """
    Aggregated OI across exchanges.

    CoinGlass:
        /api/futures/open-interest/exchange-list
    """

    data = _extract_data(
        _request(
            "/api/futures/open-interest/exchange-list",
            {
                "symbol": _coin_from_symbol(
                    symbol
                ),
            },
            "open_interest",
        )
    )

    if not isinstance(
        data,
        list,
    ):
        return None

    # Prefer the aggregated "All" row.
    row = None

    for item in data:

        if (
            isinstance(item, dict)
            and str(
                item.get("exchange", "")
            ).lower()
            == "all"
        ):

            row = item
            break

    if row is None and data:

        row = data[0]

    if not isinstance(
        row,
        dict,
    ):
        return None

    return {
        "exchange": row.get(
            "exchange"
        ),

        "symbol": row.get(
            "symbol"
        ),

        "open_interest_usd":
            _safe_float(
                row.get(
                    "open_interest_usd"
                )
            ),

        "open_interest_quantity":
            _safe_float(
                row.get(
                    "open_interest_quantity"
                )
            ),

        "oi_change_1h_pct":
            _safe_float(
                row.get(
                    "open_interest_change_percent_1h"
                )
            ),

        "oi_change_4h_pct":
            _safe_float(
                row.get(
                    "open_interest_change_percent_4h"
                )
            ),

        "oi_change_24h_pct":
            _safe_float(
                row.get(
                    "open_interest_change_percent_24h"
                )
            ),
    }


# ============================================================
# FUNDING
# ============================================================

def get_funding(
    symbol,
):
    """
    Current/latest funding context.

    Uses the latest candle from CoinGlass funding history.
    """

    data = _extract_data(
        _request(
            "/api/futures/funding-rate/history",
            {
                "exchange": "Binance",
                "symbol": symbol.upper(),
                "interval": "1h",
                "limit": 1,
            },
            "funding",
        )
    )

    if not isinstance(
        data,
        list,
    ) or not data:

        return None

    row = data[-1]

    if not isinstance(
        row,
        dict,
    ):
        return None

    return {
        "time": row.get(
            "time"
        ),

        "open": _safe_float(
            row.get("open")
        ),

        "high": _safe_float(
            row.get("high")
        ),

        "low": _safe_float(
            row.get("low")
        ),

        "close": _safe_float(
            row.get("close")
        ),
    }


# ============================================================
# LONG / SHORT
# ============================================================

def get_long_short_ratio(
    symbol,
):
    """
    Global long/short account ratio.

    CoinGlass returns percentages.
    """

    data = _extract_data(
        _request(
            "/api/futures/global-long-short-account-ratio/history",
            {
                "exchange": "Binance",
                "symbol": symbol.upper(),
                "interval": "1h",
                "limit": 1,
            },
            "long_short_ratio",
        )
    )

    if not isinstance(
        data,
        list,
    ) or not data:

        return None

    row = data[-1]

    if not isinstance(
        row,
        dict,
    ):
        return None

    long_pct = _safe_float(
        row.get(
            "global_account_long_percent"
        )
    )

    short_pct = _safe_float(
        row.get(
            "global_account_short_percent"
        )
    )

    ratio = None

    if (
        long_pct is not None
        and short_pct is not None
        and short_pct != 0
    ):

        ratio = (
            long_pct
            / short_pct
        )

    return {
        "time": row.get(
            "time"
        ),

        "long_percent":
            long_pct,

        "short_percent":
            short_pct,

        "ratio":
            ratio,
    }


# ============================================================
# LIQUIDATIONS
# ============================================================

def get_liquidations(
    symbol,
):
    """
    Latest 1H pair liquidation data.
    """

    data = _extract_data(
        _request(
            "/api/futures/liquidation/history",
            {
                "exchange": "Binance",
                "symbol": symbol.upper(),
                "interval": "1h",
                "limit": 1,
            },
            "liquidations",
        )
    )

    if not isinstance(
        data,
        list,
    ) or not data:

        return None

    row = data[-1]

    if not isinstance(
        row,
        dict,
    ):
        return None

    long_liq = _safe_float(
        row.get(
            "long_liquidation_usd"
        )
    )

    short_liq = _safe_float(
        row.get(
            "short_liquidation_usd"
        )
    )

    total = None

    if (
        long_liq is not None
        and short_liq is not None
    ):

        total = (
            long_liq
            + short_liq
        )

    return {
        "time": row.get(
            "time"
        ),

        "long_liquidation_usd":
            long_liq,

        "short_liquidation_usd":
            short_liq,

        "total_usd":
            total,
    }


# ============================================================
# TAKER BUY / SELL
# ============================================================

def get_taker_buy_sell(
    symbol,
):
    """
    Futures taker buy/sell volume.
    """

    data = _extract_data(
        _request(
            "/api/futures/v2/taker-buy-sell-volume/history",
            {
                "exchange": "Binance",
                "symbol": symbol.upper(),
                "interval": "1h",
                "limit": 1,
            },
            "taker_buy_sell",
        )
    )

    if not isinstance(
        data,
        list,
    ) or not data:

        return None

    row = data[-1]

    if not isinstance(
        row,
        dict,
    ):
        return None

    buy = _safe_float(
        row.get(
            "taker_buy_volume_usd"
        )
    )

    sell = _safe_float(
        row.get(
            "taker_sell_volume_usd"
        )
    )

    ratio = None

    if (
        buy is not None
        and sell is not None
        and sell != 0
    ):

        ratio = (
            buy / sell
        )

    return {
        "time": row.get(
            "time"
        ),

        "buy_volume_usd":
            buy,

        "sell_volume_usd":
            sell,

        "buy_sell_ratio":
            ratio,
    }


# ============================================================
# CVD
# ============================================================

def get_cvd(
    symbol,
):
    """
    Futures CVD.

    If the endpoint is unavailable on the
    user's CoinGlass plan, returns None.
    """

    data = _extract_data(
        _request(
            "/api/futures/cvd/history",
            {
                "exchange": "Binance",
                "symbol": symbol.upper(),
                "interval": "1h",
                "limit": 1,
            },
            "cvd",
        )
    )

    if not isinstance(
        data,
        list,
    ) or not data:

        return None

    row = data[-1]

    if not isinstance(
        row,
        dict,
    ):
        return None

    result = {
        "time": row.get(
            "time"
        ),

        "cum_vol_delta":
            _safe_float(
                row.get(
                    "cum_vol_delta"
                )
            ),

        "taker_buy_vol":
            _safe_float(
                row.get(
                    "taker_buy_vol"
                )
            ),

        "taker_sell_vol":
            _safe_float(
                row.get(
                    "taker_sell_vol"
                )
            ),
    }

    # Don't return an empty object.
    if all(
        value is None
        for key, value in result.items()
        if key != "time"
    ):

        return None

    return result


# ============================================================
# COLLECT ALL DATA
# ============================================================

def get_coinglass_market_data(
    symbol,
):
    """
    Main CoinGlass collector.

    Always returns a dictionary.

    If CoinGlass is unavailable:
        source_status = unavailable
        other fields remain None.

    The main bot can therefore continue normally.
    """

    symbol = str(
        symbol or ""
    ).upper().strip()

    print(
        "[coinglass_data] "
        f"collecting data for {symbol}..."
    )

    data = {
        "source": "coinglass",

        "source_status": "pending",

        "symbol": symbol,

        "open_interest": None,

        "funding_rate": None,

        "long_short_ratio": None,

        "liquidations": None,

        "taker_buy_sell": None,

        "cvd": None,
    }

    if not COINGLASS_API_KEY:

        data[
            "source_status"
        ] = "no_api_key"

        print(
            "[coinglass_data] "
            "COINGLASS_API_KEY not set. "
            "Skipping CoinGlass."
        )

        return data

    tasks = {
        "open_interest":
            lambda: get_open_interest(
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

        "taker_buy_sell":
            lambda: get_taker_buy_sell(
                symbol
            ),

        "cvd":
            lambda: get_cvd(
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
                    "[coinglass_data] "
                    f"{name} failed for "
                    f"{symbol}: {err}"
                )

                results[name] = None

    data.update(
        results
    )

    available = [
        key
        for key, value
        in results.items()
        if value is not None
    ]

    if available:

        data[
            "source_status"
        ] = "partially_available"

        print(
            "[coinglass_data] "
            f"available fields: "
            f"{', '.join(available)}"
        )

    else:

        data[
            "source_status"
        ] = "unavailable"

        print(
            "[coinglass_data] "
            f"no CoinGlass data available "
            f"for {symbol}"
        )

    return data
