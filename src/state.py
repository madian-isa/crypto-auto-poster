"""
state.py

Tracks daily posting state in a small JSON file.

Rules:
- Maximum daily posts are controlled by cfg.MAX_POSTS_PER_DAY.
- Each crypto symbol can be posted only ONCE per day.
- When a new UTC day starts, the daily counter and posted-symbol list reset.

The GitHub Actions workflow commits this file back to the repo after each
run, so the state persists between scheduled invocations.
"""

import json
import os
from datetime import datetime, timezone

from src import bot_config as cfg


def _today_str() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def load_state() -> dict:
    """Load state and reset daily data when a new UTC day begins."""

    if not os.path.exists(cfg.STATE_FILE):
        return {
            "date": _today_str(),
            "count": 0,
            "posted_symbols_today": [],
        }

    try:
        with open(cfg.STATE_FILE, "r") as f:
            state = json.load(f)
    except Exception:
        return {
            "date": _today_str(),
            "count": 0,
            "posted_symbols_today": [],
        }

    today = _today_str()

    if state.get("date") != today:
        state = {
            "date": today,
            "count": 0,
            "posted_symbols_today": [],
        }

    state.setdefault("date", today)
    state.setdefault("count", 0)
    state.setdefault("posted_symbols_today", [])

    return state


def save_state(state: dict) -> None:
    with open(cfg.STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def can_post_more_today(state: dict) -> bool:
    return state.get("count", 0) < cfg.MAX_POSTS_PER_DAY


def record_post(state: dict, symbol: str) -> dict:
    """Record one successful post and remember the symbol for today."""

    state["count"] = state.get("count", 0) + 1

    posted_today = state.get("posted_symbols_today", [])

    if symbol not in posted_today:
        posted_today.append(symbol)

    state["posted_symbols_today"] = posted_today

    return state
