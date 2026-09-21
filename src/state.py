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
    """Returns today's UTC date as a string (YYYY-MM-DD)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def load_state() -> dict:
    """Load state and reset daily data when a new UTC day begins."""
    today = _today_str()

    default_state = {
        "date": today,
        "count": 0,
        "posted_symbols_today": [],
    }

    if not os.path.exists(cfg.STATE_FILE):
        return default_state

    try:
        with open(cfg.STATE_FILE, "r") as f:
            state = json.load(f)
    except Exception:
        return default_state

    if state.get("date") != today:
        state = default_state
        save_state(state)

    state.setdefault("date", today)
    state.setdefault("count", 0)
    state.setdefault("posted_symbols_today", [])

    return state


def save_state(state: dict) -> None:
    """Save the updated state directly into the state file."""
    with open(cfg.STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def can_post_more_today(state: dict) -> bool:
    """Checks if daily max post limit reached."""
    return state.get("count", 0) < cfg.MAX_POSTS_PER_DAY


def is_symbol_posted_today(state: dict, symbol: str) -> bool:
    """Checks if a coin symbol has already been posted today."""
    if not symbol:
        return False
    clean_symbol = symbol.strip().upper()
    posted_today = [s.strip().upper() for s in state.get("posted_symbols_today", [])]
    return clean_symbol in posted_today


def record_post(state: dict, symbol: str) -> dict:
    """Record one successful post, save to JSON, and prevent duplicate posts today."""
    state["date"] = _today_str()

    if symbol:
        clean_symbol = symbol.strip().upper()
        posted_today = state.get("posted_symbols_today", [])

        if clean_symbol not in [s.strip().upper() for s in posted_today]:
            posted_today.append(clean_symbol)
            state["posted_symbols_today"] = posted_today
            state["count"] = len(posted_today)

    save_state(state)
    return state
