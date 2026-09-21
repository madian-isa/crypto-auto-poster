"""
backtest.py

Stores generated trade setups for later performance testing without losing previous history.
"""

import json
import os
from datetime import datetime, timezone


BACKTEST_FILE = os.environ.get(
    "BACKTEST_FILE",
    "backtest_setups.json",
)


def _now_utc():
    return datetime.now(
        timezone.utc
    ).isoformat()


def load_backtest_data():
    if not os.path.exists(
        BACKTEST_FILE
    ):
        return {
            "setups": []
        }

    try:
        with open(
            BACKTEST_FILE,
            "r",
            encoding="utf-8",
        ) as f:
            data = json.load(f)

        if not isinstance(data, dict):
            return {
                "setups": []
            }

        data.setdefault(
            "setups",
            []
        )

        return data

    except Exception as err:
        print(
            f"[backtest] failed to load "
            f"{BACKTEST_FILE}: {err}"
        )

        return {
            "setups": []
        }


def save_backtest_data(data):
    with open(
        BACKTEST_FILE,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False,
        )


def save_setup(
    symbol,
    setup,
):
    data = load_backtest_data()

    setups = data.get(
        "setups",
        [],
    )

    setup_record = {
        "id": (setups[-1]["id"] + 1) if setups else 1,
        "created_at": _now_utc(),

        "symbol": symbol,

        "direction": setup.get(
            "direction"
        ),

        "title": setup.get(
            "title"
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

        "support": setup.get(
            "support"
        ),

        "resistance": setup.get(
            "resistance"
        ),

        "news_line": setup.get(
            "news_line"
        ),

        "technical_analysis": setup.get(
            "technical_analysis"
        ),

        "market_context": setup.get(
            "market_context"
        ),

        "result": "PENDING",
    }

    setups.append(
        setup_record
    )

    data["setups"] = setups

    save_backtest_data(
        data
    )

    print(
        f"[backtest] saved setup "
        f"#{setup_record['id']} "
        f"{symbol} "
        f"({setup_record['direction']})"
    )

    print(
        f"[backtest] Total setups stored so far: {len(setups)}"
    )

    return True


def get_setup_count():
    data = load_backtest_data()

    return len(
        data.get(
            "setups",
            [],
        )
    )
