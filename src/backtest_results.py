"""
backtest_results.py

Historical backtest for generated crypto setups.

Purpose:
- Test the first 30 generated setups.
- Use 1-minute historical Binance Spot candles.
- Determine:
    TP_HIT
    SL_HIT
    AMBIGUOUS
    NO_ENTRY
    PENDING
    NO_DATA

Important:
This is historical analysis only.
It does not place trades or generate live signals.
"""

import json
import time
from datetime import datetime, timezone, timedelta

import requests


INPUT_FILE = "backtest_setups.json"
OUTPUT_FILE = "backtest_results.json"

MAX_SETUPS = 30

# Test each setup for 6 hours after creation.
HORIZON_MINUTES = 360

INTERVAL = "1m"

BASE_URLS = [
    "https://data-api.binance.vision",
    "https://api.binance.com",
]

HEADERS = {
    "User-Agent": "trade-setup-backtester/1.0",
    "Accept": "application/json",
}

TIMEOUT = 10


def load_setups():
    """Load the first MAX_SETUPS setups."""

    try:
        with open(
            INPUT_FILE,
            "r",
            encoding="utf-8",
        ) as f:
            data = json.load(f)

    except FileNotFoundError:
        print(
            f"[backtest] ERROR: {INPUT_FILE} not found."
        )
        return []

    except Exception as err:
        print(
            f"[backtest] ERROR loading {INPUT_FILE}: {err}"
        )
        return []

    setups = data.get(
        "setups",
        [],
    )

    if not isinstance(setups, list):
        return []

    return setups[:MAX_SETUPS]


def load_previous_results():
    """Load existing results so completed results are not unnecessarily replaced."""

    try:
        with open(
            OUTPUT_FILE,
            "r",
            encoding="utf-8",
        ) as f:
            data = json.load(f)

        if not isinstance(data, dict):
            return {}

        return data

    except Exception:
        return {}


def parse_time(value):
    """Convert ISO timestamp to timezone-aware datetime."""

    if not value:
        return None

    try:
        dt = datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00",
            )
        )

        if dt.tzinfo is None:
            dt = dt.replace(
                tzinfo=timezone.utc
            )

        return dt

    except Exception as err:
        print(
            f"[backtest] invalid timestamp "
            f"{value}: {err}"
        )
        return None


def to_milliseconds(dt):
    """Convert datetime to Unix milliseconds."""

    return int(
        dt.timestamp() * 1000
    )


def get_klines(
    symbol,
    start_ms,
    end_ms,
):
    """
    Download 1-minute Spot candles.

    Binance normally returns up to 1000 candles per request,
    so this function paginates when necessary.
    """

    all_rows = []

    current_start = start_ms

    while current_start < end_ms:

        params = {
            "symbol": symbol,
            "interval": INTERVAL,
            "startTime": current_start,
            "endTime": end_ms,
            "limit": 1000,
        }

        rows = None

        for base_url in BASE_URLS:

            url = (
                f"{base_url}/api/v3/klines"
            )

            try:
                response = requests.get(
                    url,
                    params=params,
                    headers=HEADERS,
                    timeout=TIMEOUT,
                )

                response.raise_for_status()

                rows = response.json()

                break

            except Exception as err:

                print(
                    f"[backtest] "
                    f"{symbol} request failed "
                    f"via {base_url}: {err}"
                )

        if rows is None:
            return []

        if not rows:
            break

        all_rows.extend(rows)

        if len(rows) < 1000:
            break

        last_open_time = int(
            rows[-1][0]
        )

        next_start = (
            last_open_time + 60_000
        )

        if next_start <= current_start:
            break

        current_start = next_start

        time.sleep(0.05)

    return all_rows


def candle_values(row):
    """Convert Binance kline row into a simpler dictionary."""

    return {
        "time": int(row[0]),
        "open": float(row[1]),
        "high": float(row[2]),
        "low": float(row[3]),
        "close": float(row[4]),
    }


def entry_touched(
    candle,
    entry_low,
    entry_high,
):
    """Check whether the candle touched the entry zone."""

    return (
        candle["high"] >= entry_low
        and
        candle["low"] <= entry_high
    )


def evaluate_setup(
    setup,
    candles,
):
    """
    Evaluate one setup.

    Logic:

    1. Wait until price touches the entry zone.
    2. After entry:
       - LONG:
           TP if high >= TP
           SL if low <= SL
       - SHORT:
           TP if low <= TP
           SL if high >= SL

    If one candle touches both TP and SL,
    result is AMBIGUOUS because 1-minute OHLC data
    cannot reliably tell which level was reached first.
    """

    direction = str(
        setup.get(
            "direction",
            "",
        )
    ).upper()

    try:
        entry_low = float(
            setup["entry_low"]
        )

        entry_high = float(
            setup["entry_high"]
        )

        stop_loss = float(
            setup["stop_loss"]
        )

        take_profit = float(
            setup["take_profit"]
        )

    except Exception as err:

        return {
            "result": "NO_DATA",
            "entry_time": None,
            "entry_price": None,
            "result_time": None,
            "error": (
                f"Invalid setup values: {err}"
            ),
        }

    if direction not in (
        "LONG",
        "SHORT",
    ):
        return {
            "result": "NO_DATA",
            "entry_time": None,
            "entry_price": None,
            "result_time": None,
            "error": "Invalid direction",
        }

    entry_time = None

    entry_price = None

    for candle_row in candles:

        candle = candle_values(
            candle_row
        )

        # -----------------------------
        # Before entry
        # -----------------------------
        if entry_time is None:

            if not entry_touched(
                candle,
                entry_low,
                entry_high,
            ):
                continue

            entry_time = candle["time"]

            # Midpoint of the entry zone
            entry_price = (
                entry_low + entry_high
            ) / 2

            # Check whether TP or SL
            # was already touched in
            # the same candle.
            if direction == "LONG":

                tp_hit = (
                    candle["high"]
                    >= take_profit
                )

                sl_hit = (
                    candle["low"]
                    <= stop_loss
                )

            else:

                tp_hit = (
                    candle["low"]
                    <= take_profit
                )

                sl_hit = (
                    candle["high"]
                    >= stop_loss
                )

            if tp_hit and sl_hit:

                return {
                    "result": "AMBIGUOUS",
                    "entry_time": entry_time,
                    "entry_price": entry_price,
                    "result_time": candle["time"],
                }

            if tp_hit:

                return {
                    "result": "TP_HIT",
                    "entry_time": entry_time,
                    "entry_price": entry_price,
                    "result_time": candle["time"],
                }

            if sl_hit:

                return {
                    "result": "SL_HIT",
                    "entry_time": entry_time,
                    "entry_price": entry_price,
                    "result_time": candle["time"],
                }

            continue

        # -----------------------------
        # After entry
        # -----------------------------

        if direction == "LONG":

            tp_hit = (
                candle["high"]
                >= take_profit
            )

            sl_hit = (
                candle["low"]
                <= stop_loss
            )

        else:

            tp_hit = (
                candle["low"]
                <= take_profit
            )

            sl_hit = (
                candle["high"]
                >= stop_loss
            )

        # Both levels touched in
        # the same 1-minute candle.
        if tp_hit and sl_hit:

            return {
                "result": "AMBIGUOUS",
                "entry_time": entry_time,
                "entry_price": entry_price,
                "result_time": candle["time"],
            }

        if tp_hit:

            return {
                "result": "TP_HIT",
                "entry_time": entry_time,
                "entry_price": entry_price,
                "result_time": candle["time"],
            }

        if sl_hit:

            return {
                "result": "SL_HIT",
                "entry_time": entry_time,
                "entry_price": entry_price,
                "result_time": candle["time"],
            }

    # Entry happened, but neither
    # TP nor SL was reached yet.
    return {
        "result": "PENDING",
        "entry_time": entry_time,
        "entry_price": entry_price,
        "result_time": None,
    }


def format_time(ms):
    """Convert milliseconds to ISO UTC timestamp."""

    if ms is None:
        return None

    return datetime.fromtimestamp(
        ms / 1000,
        tz=timezone.utc,
    ).isoformat()


def run_backtest():

    setups = load_setups()

    if not setups:

        print(
            "[backtest] No setups found."
        )

        return

    previous_data = (
        load_previous_results()
    )

    previous_results = (
        previous_data.get(
            "results",
            {},
        )
    )

    results = []

    now = datetime.now(
        timezone.utc
    )

    print(
        f"[backtest] "
        f"Testing {len(setups)} setups..."
    )

    print(
        f"[backtest] "
        f"Horizon: {HORIZON_MINUTES} minutes"
    )

    for index, setup in enumerate(
        setups,
        start=1,
    ):

        setup_id = setup.get(
            "id",
            index,
        )

        symbol = str(
            setup.get(
                "symbol",
                "",
            )
        ).upper()

        created_at = parse_time(
            setup.get(
                "created_at"
            )
        )

        print(
            ""
        )

        print(
            f"[backtest] "
            f"{index}/{len(setups)} "
            f"#{setup_id} "
            f"{symbol}"
        )

        if not created_at:

            result = {
                "id": setup_id,
                "symbol": symbol,
                "result": "NO_DATA",
                "reason": (
                    "Invalid created_at timestamp"
                ),
            }

            results.append(result)

            continue

        horizon_end = (
            created_at
            + timedelta(
                minutes=HORIZON_MINUTES
            )
        )

        # -----------------------------
        # Important:
        # If the 6-hour window has not
        # finished yet, don't evaluate
        # the setup prematurely.
        # -----------------------------
        if now < horizon_end:

            print(
                "[backtest] "
                "6-hour window not finished. "
                "Keeping PENDING."
            )

            results.append(
                {
                    "id": setup_id,
                    "symbol": symbol,
                    "direction": setup.get(
                        "direction"
                    ),
                    "created_at": (
                        created_at.isoformat()
                    ),
                    "horizon_end": (
                        horizon_end.isoformat()
                    ),
                    "result": "PENDING",
                    "entry_time": None,
                    "entry_price": None,
                    "result_time": None,
                    "reason": (
                        "6-hour test window "
                        "has not completed yet"
                    ),
                }
            )

            continue

        start_ms = to_milliseconds(
            created_at
        )

        end_ms = to_milliseconds(
            horizon_end
        )

        print(
            f"[backtest] "
            f"Downloading candles for "
            f"{symbol}..."
        )

        candles = get_klines(
            symbol,
            start_ms,
            end_ms,
        )

        if not candles:

            print(
                f"[backtest] "
                f"No Spot candle data "
                f"available for {symbol}."
            )

            results.append(
                {
                    "id": setup_id,
                    "symbol": symbol,
                    "direction": setup.get(
                        "direction"
                    ),
                    "created_at": (
                        created_at.isoformat()
                    ),
                    "horizon_end": (
                        horizon_end.isoformat()
                    ),
                    "result": "NO_DATA",
                    "entry_time": None,
                    "entry_price": None,
                    "result_time": None,
                    "reason": (
                        "No Binance Spot "
                        "1-minute data available"
                    ),
                }
            )

            continue

        evaluation = evaluate_setup(
            setup,
            candles,
        )

        result = {
            "id": setup_id,
            "symbol": symbol,
            "direction": setup.get(
                "direction"
            ),
            "created_at": (
                created_at.isoformat()
            ),
            "horizon_end": (
                horizon_end.isoformat()
            ),
            "entry_low": setup.get(
                "entry_low"
            ),
            "entry_high": setup.get(
                "entry_high"
            ),
            "stop_loss": setup.get(
                "stop_loss"
            ),
            "take_profit": setup.get(
                "take_profit"
            ),
            "result": evaluation.get(
                "result"
            ),
            "entry_time": format_time(
                evaluation.get(
                    "entry_time"
                )
            ),
            "entry_price": evaluation.get(
                "entry_price"
            ),
            "result_time": format_time(
                evaluation.get(
                    "result_time"
                )
            ),
        }

        if evaluation.get(
            "error"
        ):
            result["error"] = (
                evaluation["error"]
            )

        results.append(result)

        print(
            f"[backtest] "
            f"{symbol} -> "
            f"{result['result']}"
        )

    # -----------------------------
    # Summary
    # -----------------------------

    summary = {
        "total": len(results),
        "TP_HIT": 0,
        "SL_HIT": 0,
        "NO_ENTRY": 0,
        "AMBIGUOUS": 0,
        "PENDING": 0,
        "NO_DATA": 0,
    }

    for result in results:

        status = result.get(
            "result"
        )

        if status in summary:
            summary[status] += 1

    output = {
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "input_file": INPUT_FILE,

        "horizon_minutes": (
            HORIZON_MINUTES
        ),

        "interval": INTERVAL,

        "method": (
            "Historical Binance Spot "
            "1-minute OHLC backtest"
        ),

        "summary": summary,

        "results": results,
    }

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            output,
            f,
            indent=2,
            ensure_ascii=False,
        )

    print(
        ""
    )

    print(
        "================================"
    )

    print(
        "BACKTEST COMPLETE"
    )

    print(
        "================================"
    )

    print(
        f"Total:      {summary['total']}"
    )

    print(
        f"TP_HIT:     {summary['TP_HIT']}"
    )

    print(
        f"SL_HIT:     {summary['SL_HIT']}"
    )

    print(
        f"NO_ENTRY:   {summary['NO_ENTRY']}"
    )

    print(
        f"AMBIGUOUS:  {summary['AMBIGUOUS']}"
    )

    print(
        f"PENDING:    {summary['PENDING']}"
    )

    print(
        f"NO_DATA:    {summary['NO_DATA']}"
    )

    print(
        "================================"
    )

    print(
        f"Saved to {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    run_backtest()
