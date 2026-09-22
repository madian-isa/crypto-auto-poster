"""
backtest_results.py

Historical backtest for generated crypto setups
using Binance 1-minute Spot candles.

Important:
- This file evaluates historical setups only.
- It does NOT generate new trading signals.
- PENDING is used only when the evaluation window
  has not finished yet.
- If the full horizon finishes without TP/SL,
  the result becomes TIMEOUT.
"""

import json
import os
import time
from datetime import datetime, timezone, timedelta

import requests


INPUT_FILE = "backtest_setups.json"
OUTPUT_FILE = "backtest_results.json"


# 0 = test all setups
MAX_SETUPS = int(
    os.environ.get(
        "MAX_SETUPS",
        "0",
    )
)


# Evaluation window in minutes.
# Default = 6 hours.
HORIZON_MINUTES = int(
    os.environ.get(
        "HORIZON_MINUTES",
        "360",
    )
)


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


# ---------------------------------------------------------
# LOAD SETUPS
# ---------------------------------------------------------

def load_setups():
    """
    Load setups from backtest_setups.json.
    """

    try:
        with open(
            INPUT_FILE,
            "r",
            encoding="utf-8",
        ) as f:
            data = json.load(f)

    except FileNotFoundError:
        print(
            f"[backtest] ERROR: "
            f"{INPUT_FILE} not found."
        )
        return []

    except Exception as err:
        print(
            f"[backtest] ERROR loading "
            f"{INPUT_FILE}: {err}"
        )
        return []

    setups = data.get(
        "setups",
        [],
    )

    if not isinstance(
        setups,
        list,
    ):
        return []

    if MAX_SETUPS > 0:
        return setups[:MAX_SETUPS]

    return setups


# ---------------------------------------------------------
# TIME HELPERS
# ---------------------------------------------------------

def parse_time(value):
    """
    Convert ISO timestamp to timezone-aware datetime.
    """

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
    """
    Convert datetime to Unix milliseconds.
    """

    return int(
        dt.timestamp() * 1000
    )


def format_time(ms):
    """
    Convert Binance millisecond timestamp
    into ISO UTC string.
    """

    if ms is None:
        return None

    return datetime.fromtimestamp(
        ms / 1000,
        tz=timezone.utc,
    ).isoformat()


# ---------------------------------------------------------
# BINANCE DATA
# ---------------------------------------------------------

def get_klines(
    symbol,
    start_ms,
    end_ms,
):
    """
    Download 1-minute Spot candles
    from Binance.

    Handles Binance's 1000-candle limit
    by requesting multiple pages.
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
                f"{base_url}"
                f"/api/v3/klines"
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
                    f"[backtest] Binance request "
                    f"failed for {symbol} "
                    f"via {base_url}: {err}"
                )

                continue

        if rows is None or not rows:
            break

        all_rows.extend(
            rows
        )

        if len(rows) < 1000:
            break

        last_open_time = int(
            rows[-1][0]
        )

        next_start = (
            last_open_time
            + 60_000
        )

        if next_start <= current_start:
            break

        current_start = next_start

        time.sleep(
            0.05
        )

    return all_rows


# ---------------------------------------------------------
# CANDLE HELPERS
# ---------------------------------------------------------

def candle_values(row):
    """
    Convert Binance kline row into
    a simple dictionary.
    """

    return {
        "time": int(row[0]),
        "open": float(row[1]),
        "high": float(row[2]),
        "low": float(row[3]),
        "close": float(row[4]),
    }


# ---------------------------------------------------------
# ENTRY
# ---------------------------------------------------------

def entry_touched(
    candle,
    entry_low,
    entry_high,
):
    """
    Check whether candle price range
    touched the entry zone.
    """

    return (
        candle["high"] >= entry_low
        and
        candle["low"] <= entry_high
    )


# ---------------------------------------------------------
# SETUP EVALUATION
# ---------------------------------------------------------

def evaluate_setup(
    setup,
    candles,
    horizon_end_ms,
    now,
):
    """
    Evaluate one historical setup.

    Possible results:

    TP_HIT
    SL_HIT
    NO_ENTRY
    TIMEOUT
    PENDING
    AMBIGUOUS
    NO_DATA
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
                f"Invalid setup values: "
                f"{err}"
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

    # -----------------------------------------------------
    # PROCESS CANDLES
    # -----------------------------------------------------

    for candle_row in candles:

        candle = candle_values(
            candle_row
        )

        candle_time = candle["time"]

        # Do not evaluate candles beyond
        # the requested horizon.
        if (
            candle_time
            >= horizon_end_ms
        ):
            break

        # -------------------------------------------------
        # ENTRY
        # -------------------------------------------------

        if entry_time is None:

            if not entry_touched(
                candle,
                entry_low,
                entry_high,
            ):
                continue

            entry_time = candle_time

            entry_price = (
                entry_low
                + entry_high
            ) / 2.0

            # ---------------------------------------------
            # Check TP / SL on entry candle
            # ---------------------------------------------

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
                    "result_time": candle_time,
                }

            if tp_hit:

                return {
                    "result": "TP_HIT",
                    "entry_time": entry_time,
                    "entry_price": entry_price,
                    "result_time": candle_time,
                }

            if sl_hit:

                return {
                    "result": "SL_HIT",
                    "entry_time": entry_time,
                    "entry_price": entry_price,
                    "result_time": candle_time,
                }

            continue

        # -------------------------------------------------
        # AFTER ENTRY
        # -------------------------------------------------

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

        # -------------------------------------------------
        # BOTH TP AND SL
        # -------------------------------------------------

        if tp_hit and sl_hit:

            return {
                "result": "AMBIGUOUS",
                "entry_time": entry_time,
                "entry_price": entry_price,
                "result_time": candle_time,
            }

        # -------------------------------------------------
        # TP
        # -------------------------------------------------

        if tp_hit:

            return {
                "result": "TP_HIT",
                "entry_time": entry_time,
                "entry_price": entry_price,
                "result_time": candle_time,
            }

        # -------------------------------------------------
        # SL
        # -------------------------------------------------

        if sl_hit:

            return {
                "result": "SL_HIT",
                "entry_time": entry_time,
                "entry_price": entry_price,
                "result_time": candle_time,
            }

    # -----------------------------------------------------
    # NO TP/SL RESULT
    # -----------------------------------------------------

    if entry_time is not None:

        # The full evaluation window has ended.
        if now >= datetime.fromtimestamp(
            horizon_end_ms / 1000,
            tz=timezone.utc,
        ):

            return {
                "result": "TIMEOUT",
                "entry_time": entry_time,
                "entry_price": entry_price,
                "result_time": None,
            }

        # Horizon has NOT ended yet.
        return {
            "result": "PENDING",
            "entry_time": entry_time,
            "entry_price": entry_price,
            "result_time": None,
        }

    # -----------------------------------------------------
    # NO ENTRY
    # -----------------------------------------------------

    if now >= datetime.fromtimestamp(
        horizon_end_ms / 1000,
        tz=timezone.utc,
    ):

        return {
            "result": "NO_ENTRY",
            "entry_time": None,
            "entry_price": None,
            "result_time": None,
        }

    # Horizon has not finished, and entry
    # may still happen later.
    return {
        "result": "PENDING",
        "entry_time": None,
        "entry_price": None,
        "result_time": None,
    }


# ---------------------------------------------------------
# MAIN BACKTEST
# ---------------------------------------------------------

def run_backtest():

    setups = load_setups()

    if not setups:

        print(
            "[backtest] No setups found."
        )

        return

    results = []

    now = datetime.now(
        timezone.utc
    )

    print(
        f"[backtest] Testing "
        f"{len(setups)} setups..."
    )

    print(
        f"[backtest] Horizon: "
        f"{HORIZON_MINUTES} minutes"
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

        # -------------------------------------------------
        # INVALID CREATED TIME
        # -------------------------------------------------

        if not created_at:

            results.append(
                {
                    "id": setup_id,
                    "symbol": symbol,
                    "result": "NO_DATA",
                    "reason": (
                        "Invalid "
                        "created_at timestamp"
                    ),
                }
            )

            continue

        # -------------------------------------------------
        # HORIZON
        # -------------------------------------------------

        horizon_end = (
            created_at
            + timedelta(
                minutes=HORIZON_MINUTES
            )
        )

        # We cannot evaluate future candles
        # that have not happened yet.
        fetch_end = min(
            now,
            horizon_end,
        )

        start_ms = to_milliseconds(
            created_at
        )

        end_ms = to_milliseconds(
            fetch_end
        )

        # -------------------------------------------------
        # DOWNLOAD CANDLES
        # -------------------------------------------------

        candles = get_klines(
            symbol,
            start_ms,
            end_ms,
        )

        # -------------------------------------------------
        # NO CANDLES
        # -------------------------------------------------

        if not candles:

            if now < horizon_end:

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
                        "result": "PENDING",
                        "entry_time": None,
                        "entry_price": None,
                        "result_time": None,
                    }
                )

            else:

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
                        "result": "NO_DATA",
                    }
                )

            continue

        # -------------------------------------------------
        # EVALUATE
        # -------------------------------------------------

        evaluation = evaluate_setup(
            setup,
            candles,
            to_milliseconds(
                horizon_end
            ),
            now,
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

        results.append(
            result
        )

        print(
            f"[backtest] "
            f"#{setup_id} "
            f"{symbol} -> "
            f"{result['result']}"
        )

    # -----------------------------------------------------
    # SUMMARY
    # -----------------------------------------------------

    summary = {
        "total": len(results),
        "TP_HIT": 0,
        "SL_HIT": 0,
        "NO_ENTRY": 0,
        "TIMEOUT": 0,
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

    # -----------------------------------------------------
    # RESOLVED STATISTICS
    # -----------------------------------------------------

    resolved = (
        summary["TP_HIT"]
        + summary["SL_HIT"]
    )

    if resolved > 0:

        tp_rate = (
            summary["TP_HIT"]
            / resolved
        ) * 100

        sl_rate = (
            summary["SL_HIT"]
            / resolved
        ) * 100

    else:

        tp_rate = 0.0
        sl_rate = 0.0

    summary["resolved"] = resolved
    summary["tp_rate_resolved_pct"] = round(
        tp_rate,
        2,
    )
    summary["sl_rate_resolved_pct"] = round(
        sl_rate,
        2,
    )

    # -----------------------------------------------------
    # SAVE
    # -----------------------------------------------------

    output = {
        "generated_at": (
            datetime.now(
                timezone.utc
            ).isoformat()
        ),
        "input_file": INPUT_FILE,
        "horizon_minutes": HORIZON_MINUTES,
        "interval": INTERVAL,
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

    # -----------------------------------------------------
    # REPORT
    # -----------------------------------------------------

    print(
        "\n================================"
    )

    print(
        "BACKTEST SUMMARY REPORT"
    )

    print(
        "================================"
    )

    print(
        f"Total Trades Evaluated : "
        f"{summary['total']}"
    )

    print(
        f"TP_HIT                 : "
        f"{summary['TP_HIT']}"
    )

    print(
        f"SL_HIT                 : "
        f"{summary['SL_HIT']}"
    )

    print(
        f"NO_ENTRY               : "
        f"{summary['NO_ENTRY']}"
    )

    print(
        f"TIMEOUT                : "
        f"{summary['TIMEOUT']}"
    )

    print(
        f"PENDING                : "
        f"{summary['PENDING']}"
    )

    print(
        f"AMBIGUOUS              : "
        f"{summary['AMBIGUOUS']}"
    )

    print(
        f"NO_DATA                : "
        f"{summary['NO_DATA']}"
    )

    print(
        "--------------------------------"
    )

    print(
        f"Resolved TP/SL         : "
        f"{summary['resolved']}"
    )

    print(
        f"TP Rate (resolved)     : "
        f"{summary['tp_rate_resolved_pct']}%"
    )

    print(
        f"SL Rate (resolved)     : "
        f"{summary['sl_rate_resolved_pct']}%"
    )

    print(
        "================================\n"
    )


# ---------------------------------------------------------
# RUN
# ---------------------------------------------------------

if __name__ == "__main__":
    run_backtest()
