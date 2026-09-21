"""
backtest_results.py

Historical backtest for generated crypto setups using Binance 1-m Spot Candles.
"""

import json
import os
import time
from datetime import datetime, timezone, timedelta

import requests


INPUT_FILE = "backtest_setups.json"
OUTPUT_FILE = "backtest_results.json"

# Set to 0 or None to test ALL setups without 30 limit
MAX_SETUPS = int(os.environ.get("MAX_SETUPS", "0"))

# Test horizon window (in minutes)
HORIZON_MINUTES = int(os.environ.get("HORIZON_MINUTES", "360"))

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
    """Load setups from backtest_setups.json."""
    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"[backtest] ERROR: {INPUT_FILE} not found.")
        return []
    except Exception as err:
        print(f"[backtest] ERROR loading {INPUT_FILE}: {err}")
        return []

    setups = data.get("setups", [])
    if not isinstance(setups, list):
        return []

    if MAX_SETUPS > 0:
        return setups[:MAX_SETUPS]
    return setups


def parse_time(value):
    """Convert ISO timestamp to timezone-aware datetime."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception as err:
        print(f"[backtest] invalid timestamp {value}: {err}")
        return None


def to_milliseconds(dt):
    """Convert datetime to Unix milliseconds."""
    return int(dt.timestamp() * 1000)


def get_klines(symbol, start_ms, end_ms):
    """Download 1-minute Spot candles from Binance API."""
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
            url = f"{base_url}/api/v3/klines"
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
            except Exception:
                continue

        if rows is None or not rows:
            break

        all_rows.extend(rows)

        if len(rows) < 1000:
            break

        last_open_time = int(rows[-1][0])
        next_start = last_open_time + 60_000
        if next_start <= current_start:
            break
        current_start = next_start
        time.sleep(0.05)

    return all_rows


def candle_values(row):
    return {
        "time": int(row[0]),
        "open": float(row[1]),
        "high": float(row[2]),
        "low": float(row[3]),
        "close": float(row[4]),
    }


def entry_touched(candle, entry_low, entry_high):
    return candle["high"] >= entry_low and candle["low"] <= entry_high


def evaluate_setup(setup, candles):
    direction = str(setup.get("direction", "")).upper()

    try:
        entry_low = float(setup["entry_low"])
        entry_high = float(setup["entry_high"])
        stop_loss = float(setup["stop_loss"])
        take_profit = float(setup["take_profit"])
    except Exception as err:
        return {
            "result": "NO_DATA",
            "entry_time": None,
            "entry_price": None,
            "result_time": None,
            "error": f"Invalid setup values: {err}",
        }

    if direction not in ("LONG", "SHORT"):
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
        candle = candle_values(candle_row)

        if entry_time is None:
            if not entry_touched(candle, entry_low, entry_high):
                continue

            entry_time = candle["time"]
            entry_price = (entry_low + entry_high) / 2

            if direction == "LONG":
                tp_hit = candle["high"] >= take_profit
                sl_hit = candle["low"] <= stop_loss
            else:
                tp_hit = candle["low"] <= take_profit
                sl_hit = candle["high"] >= stop_loss

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

        if direction == "LONG":
            tp_hit = candle["high"] >= take_profit
            sl_hit = candle["low"] <= stop_loss
        else:
            tp_hit = candle["low"] <= take_profit
            sl_hit = candle["high"] >= stop_loss

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

    if entry_time is not None:
        return {
            "result": "PENDING",
            "entry_time": entry_time,
            "entry_price": entry_price,
            "result_time": None,
        }

    return {
        "result": "NO_ENTRY",
        "entry_time": None,
        "entry_price": None,
        "result_time": None,
    }


def format_time(ms):
    if ms is None:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()


def run_backtest():
    setups = load_setups()
    if not setups:
        print("[backtest] No setups found.")
        return

    results = []
    now = datetime.now(timezone.utc)

    print(f"[backtest] Testing {len(setups)} setups...")
    print(f"[backtest] Horizon: {HORIZON_MINUTES} minutes")

    for index, setup in enumerate(setups, start=1):
        setup_id = setup.get("id", index)
        symbol = str(setup.get("symbol", "")).upper()
        created_at = parse_time(setup.get("created_at"))

        if not created_at:
            results.append({
                "id": setup_id,
                "symbol": symbol,
                "result": "NO_DATA",
                "reason": "Invalid created_at timestamp",
            })
            continue

        horizon_end = created_at + timedelta(minutes=HORIZON_MINUTES)
        fetch_end = min(now, horizon_end)

        start_ms = to_milliseconds(created_at)
        end_ms = to_milliseconds(fetch_end)

        candles = get_klines(symbol, start_ms, end_ms)

        if not candles:
            results.append({
                "id": setup_id,
                "symbol": symbol,
                "direction": setup.get("direction"),
                "created_at": created_at.isoformat(),
                "result": "NO_DATA",
            })
            continue

        evaluation = evaluate_setup(setup, candles)

        result = {
            "id": setup_id,
            "symbol": symbol,
            "direction": setup.get("direction"),
            "created_at": created_at.isoformat(),
            "result": evaluation.get("result"),
            "entry_time": format_time(evaluation.get("entry_time")),
            "entry_price": evaluation.get("entry_price"),
            "result_time": format_time(evaluation.get("result_time")),
        }
        results.append(result)
        print(f"[backtest] #{setup_id} {symbol} -> {result['result']}")

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
        status = result.get("result")
        if status in summary:
            summary[status] += 1

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_file": INPUT_FILE,
        "summary": summary,
        "results": results,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print("\n================================")
    print("BACKTEST SUMMARY REPORT")
    print("================================")
    print(f"Total Trades Evaluated : {summary['total']}")
    print(f"TP_HIT                 : {summary['TP_HIT']}")
    print(f"SL_HIT                 : {summary['SL_HIT']}")
    print(f"NO_ENTRY               : {summary['NO_ENTRY']}")
    print(f"PENDING                : {summary['PENDING']}")
    print(f"AMBIGUOUS              : {summary['AMBIGUOUS']}")
    print(f"NO_DATA                : {summary['NO_DATA']}")
    print("================================\n")


if __name__ == "__main__":
    run_backtest()
