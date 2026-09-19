"""
backtest_results.py

Historical backtest for generated crypto setups.

Purpose:
- Test the first 30 generated setups.
- Use 1-minute historical Spot candles.
- Determine whether the entry was reached.
- After entry:
    TP_HIT
    SL_HIT
    AMBIGUOUS
    PENDING
- If entry was never reached:
    NO_ENTRY

Important:
This is historical analysis only.
It does not place trades or generate live signals.
"""

import json
import time
from datetime import datetime, timezone

import requests


INPUT_FILE = "backtest_setups.json"
OUTPUT_FILE = "backtest_results.json"

MAX_SETUPS = 30

# Maximum time after setup creation to wait for entry/TP/SL.
# 6 hours = 360 minutes.
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


# ============================================================
# LOAD SETUPS
# ============================================================

def load_setups():
    with open(
        INPUT_FILE,
        "r",
        encoding="utf-8",
    ) as f:
        data = json.load(f)

    setups = data.get(
        "setups",
        [],
    )

    return setups[:MAX_SETUPS]


# ============================================================
# TIME
# ============================================================

def parse_time(value):
    return datetime.fromisoformat(
        value.replace(
            "Z",
            "+00:00",
        )
    )


def to_milliseconds(dt):
    return int(
        dt.timestamp() * 1000
    )


# ============================================================
# BINANCE DATA
# ============================================================

def get_klines(
    symbol,
    start_ms,
    end_ms,
):
    """
    Fetch 1-minute candles.

    1000 candles are enough for the 6-hour horizon,
    but pagination is included for safety.
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
                "/api/v3/klines"
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
                    f"{symbol} request failed: "
                    f"{err}"
                )

                continue

        if not rows:
            break

        all_rows.extend(rows)

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

        time.sleep(0.05)

    return all_rows


# ============================================================
# CANDLE HELPERS
# ============================================================

def candle_values(row):
    return {
        "time": int(row[0]),
        "open": float(row[1]),
        "high": float(row[2]),
        "low": float(row[3]),
        "close": float(row[4]),
    }


# ============================================================
# ENTRY CHECK
# ============================================================

def entry_touched(
    candle,
    entry_low,
    entry_high,
):
    return (
        candle["high"] >= entry_low
        and
        candle["low"] <= entry_high
    )


# ============================================================
# RESULT ENGINE
# ============================================================

def evaluate_setup(
    setup,
    candles,
):
    direction = (
        setup["direction"]
        .upper()
    )

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

    entry_time = None
    entry_price = None

    for candle_row in candles:

        candle = candle_values(
            candle_row
        )

        # ----------------------------------------------------
        # BEFORE ENTRY
        # ----------------------------------------------------

        if entry_time is None:

            if entry_touched(
                candle,
                entry_low,
                entry_high,
            ):

                entry_time = (
                    candle["time"]
                )

                # Use midpoint of entry range
                # for reporting only.
                entry_price = (
                    entry_low
                    + entry_high
                ) / 2

                # Check if the same candle also
                # touched TP and SL.
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
                        "result_time": entry_time,
                    }

                if tp_hit:

                    return {
                        "result": "TP_HIT",
                        "entry_time": entry_time,
                        "entry_price": entry_price,
                        "result_time": entry_time,
                    }

                if sl_hit:

                    return {
                        "result": "SL_HIT",
                        "entry_time": entry_time,
                        "entry_price": entry_price,
                        "result_time": entry_time,
                    }

                continue

        # ----------------------------------------------------
        # AFTER ENTRY
        # ----------------------------------------------------

        else:

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

            # If both occur in one 1-minute candle,
            # the exact order is unknown.
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

    # --------------------------------------------------------
    # NO ENTRY
    # --------------------------------------------------------

    if entry_time is None:

        return {
            "result": "NO_ENTRY",
            "entry_time": None,
            "entry_price": None,
            "result_time": None,
        }

    # --------------------------------------------------------
    # STILL OPEN / NO TP OR SL
    # --------------------------------------------------------

    return {
        "result": "PENDING",
        "entry_time": entry_time,
        "entry_price": entry_price,
        "result_time": None,
    }


# ============================================================
# FORMAT RESULT
# ============================================================

def format_time(ms):
    if ms is None:
        return None

    return datetime.fromtimestamp(
        ms / 1000,
        tz=timezone.utc,
    ).isoformat()


# ============================================================
# MAIN BACKTEST
# ============================================================

def run_backtest():

    setups = load_setups()

    print(
        f"[backtest] loaded "
        f"{len(setups)} setups"
    )

    results = []

    for index, setup in enumerate(
        setups,
        start=1,
    ):

        symbol = setup[
            "symbol"
        ]

        created_at = parse_time(
            setup["created_at"]
        )

        start_ms = to_milliseconds(
            created_at
        )

        end_ms = to_milliseconds(
            created_at
            + __import__(
                "datetime"
            ).timedelta(
                minutes=HORIZON_MINUTES
            )
        )

        print(
            f"\n[backtest] "
            f"{index}/{len(setups)} "
            f"{symbol}"
        )

        print(
            f"[backtest] "
            f"direction: "
            f"{setup['direction']}"
        )

        candles = get_klines(
            symbol,
            start_ms,
            end_ms,
        )

        if not candles:

            print(
                "[backtest] "
                "no historical data"
            )

            result_data = {
                "result": "NO_DATA",
                "entry_time": None,
                "entry_price": None,
                "result_time": None,
            }

        else:

            result_data = evaluate_setup(
                setup,
                candles,
            )

            print(
                f"[backtest] "
                f"result: "
                f"{result_data['result']}"
            )

        record = dict(setup)

        record.update(
            {
                "backtest_result":
                    result_data[
                        "result"
                    ],

                "entry_time":
                    format_time(
                        result_data[
                            "entry_time"
                        ]
                    ),

                "entry_price":
                    result_data[
                        "entry_price"
                    ],

                "result_time":
                    format_time(
                        result_data[
                            "result_time"
                        ]
                    ),

                "horizon_minutes":
                    HORIZON_MINUTES,

                "candle_interval":
                    INTERVAL,
            }
        )

        results.append(
            record
        )

    # ========================================================
    # SUMMARY
    # ========================================================

    counts = {
        "TP_HIT": 0,
        "SL_HIT": 0,
        "NO_ENTRY": 0,
        "AMBIGUOUS": 0,
        "PENDING": 0,
        "NO_DATA": 0,
    }

    for record in results:

        result = record[
            "backtest_result"
        ]

        if result in counts:
            counts[result] += 1

    completed = (
        counts["TP_HIT"]
        + counts["SL_HIT"]
    )

    if completed > 0:

        tp_rate = (
            counts["TP_HIT"]
            / completed
        ) * 100

        sl_rate = (
            counts["SL_HIT"]
            / completed
        ) * 100

    else:

        tp_rate = 0
        sl_rate = 0

    output = {
        "metadata": {
            "setups_tested":
                len(results),

            "candle_interval":
                INTERVAL,

            "horizon_minutes":
                HORIZON_MINUTES,

            "completed":
                completed,

            "tp_hit":
                counts["TP_HIT"],

            "sl_hit":
                counts["SL_HIT"],

            "no_entry":
                counts["NO_ENTRY"],

            "ambiguous":
                counts["AMBIGUOUS"],

            "pending":
                counts["PENDING"],

            "no_data":
                counts["NO_DATA"],

            "tp_rate_among_completed":
                round(
                    tp_rate,
                    2,
                ),

            "sl_rate_among_completed":
                round(
                    sl_rate,
                    2,
                ),
        },

        "setups": results,
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
        "\n"
        + "=" * 60
    )

    print(
        "30-SETUP BACKTEST SUMMARY"
    )

    print(
        "=" * 60
    )

    print(
        f"Total tested: "
        f"{len(results)}"
    )

    print(
        f"TP hit: "
        f"{counts['TP_HIT']}"
    )

    print(
        f"SL hit: "
        f"{counts['SL_HIT']}"
    )

    print(
        f"No entry: "
        f"{counts['NO_ENTRY']}"
    )

    print(
        f"Ambiguous: "
        f"{counts['AMBIGUOUS']}"
    )

    print(
        f"Pending: "
        f"{counts['PENDING']}"
    )

    print(
        f"No data: "
        f"{counts['NO_DATA']}"
    )

    print(
        f"TP rate among completed: "
        f"{tp_rate:.2f}%"
    )

    print(
        f"SL rate among completed: "
        f"{sl_rate:.2f}%"
    )

    print(
        f"\nSaved to: "
        f"{OUTPUT_FILE}"
    )


if __name__ == "__main__":
    run_backtest()
