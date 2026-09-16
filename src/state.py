"""
state.py

Tracks how many posts have gone out today, in a small JSON file. Needed
because each `python main.py` run is a fresh process (triggered by GitHub
Actions on a schedule) — there's no long-lived process to hold this in
memory between runs.

The GitHub Actions workflow commits this file back to the repo after each
run, so the count persists across scheduled invocations.
"""

import json
import os
from datetime import date, datetime, timezone

from src import bot_config as cfg


def _today_str() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def load_state() -> dict:
    if not os.path.exists(cfg.STATE_FILE):
        return {"date": _today_str(), "count": 0, "recent_symbols": []}

    with open(cfg.STATE_FILE, "r") as f:
        state = json.load(f)

    if state.get("date") != _today_str():
        # New day — reset the counter, but keep a short memory of recent
        # symbols so we don't immediately repost the same coin.
        state = {"date": _today_str(), "count": 0, "recent_symbols": state.get("recent_symbols", [])[-3:]}

    return state


def save_state(state: dict) -> None:
    with open(cfg.STATE_FILE, "w") as f:
        json.dump(state, f)


def can_post_more_today(state: dict) -> bool:
    return state.get("count", 0) < cfg.MAX_POSTS_PER_DAY


def record_post(state: dict, symbol: str) -> dict:
    state["count"] = state.get("count", 0) + 1
    recent = state.get("recent_symbols", [])
    recent.append(symbol)
    state["recent_symbols"] = recent[-5:]  # keep it short
    return state
