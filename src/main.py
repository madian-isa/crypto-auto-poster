"""
main.py

Single-run mode: each invocation of `python main.py` builds and publishes
ONE trade-setup post, then exits. A scheduler (GitHub Actions cron) re-runs
this every ~20 minutes. A small state file (state.py) enforces a daily cap
and avoids immediately repeating the same coin.

For local testing without a scheduler, RUN_MODE=cycle still runs the old
3-posts-with-sleep behavior.
"""

import os
import random
import time
import traceback

from src import bot_config as cfg
from src.screener import get_screener_shortlist
from src.indicators import fetch_klines, compute_indicators
from src.setup_generator import generate_setup, format_post_text
from src.chart import render_chart_image
from src.square_post import post_text
from src.state import load_state, save_state, can_post_more_today, record_post


def run_once():
    """Post exactly one setup, respecting the daily cap. Meant to be called
    on a schedule (e.g. every 20 minutes) by an external scheduler."""
    state = load_state()

    if not can_post_more_today(state):
        print(f"[run_once] daily cap reached ({cfg.MAX_POSTS_PER_DAY}) — skipping this run.")
        return

    shortlist = get_screener_shortlist()
    if not shortlist:
        print("[run_once] screener returned nothing — skipping.")
        return

    candidates = shortlist[: cfg.PICK_FROM_TOP_N]
    fresh = [c for c in candidates if c["symbol"] not in state.get("recent_symbols", [])]
    pool = fresh or candidates
    random.shuffle(pool)

    for pick in pool:
        symbol = pick["symbol"]
        try:
            _build_and_publish(symbol)
            state = record_post(state, symbol)
            save_state(state)
            return
        except Exception as err:
            print(f"[run_once] {symbol} failed, trying next candidate: {err}")
            continue

    print("[run_once] every candidate failed this run — nothing posted.")


def run_cycle():
    """Old behavior, kept for local testing: 3 posts, 20 min apart, in one
    long-lived process. Not what the GitHub Actions workflow uses."""
    mode = "DRY RUN (nothing will be posted)" if cfg.DRY_RUN else "LIVE (posting for real)"
    print(f"[cycle] starting — mode: {mode}")

    shortlist = get_screener_shortlist()
    picks = _pick_diverse(shortlist, cfg.POSTS_PER_CYCLE)

    for i, pick in enumerate(picks):
        symbol = pick["symbol"]
        try:
            _build_and_publish(symbol)
        except Exception as err:
            print(f"[cycle] skipping {symbol}: {err}")
            traceback.print_exc()

        is_last = i == len(picks) - 1
        if not is_last:
            print(f"[cycle] waiting {cfg.MINUTES_BETWEEN_POSTS} min before next post...")
            time.sleep(cfg.MINUTES_BETWEEN_POSTS * 60)

    print("[cycle] done")


def _build_and_publish(symbol: str):
    klines_df = fetch_klines(symbol)
    indicators = compute_indicators(klines_df)

    setup = generate_setup(symbol, indicators)
    setup["symbol"] = symbol  # don't trust the model to echo it back correctly
    text = format_post_text(setup)

    chart_path = render_chart_image(symbol, klines_df, setup["direction"], setup)

    if cfg.DRY_RUN:
        print(f"\n[DRY RUN] would post for {symbol} ({setup['direction']}):")
        print("-" * 40)
        print(text)
        print("-" * 40)
        print(f"[DRY RUN] chart image saved at: {chart_path}")
        print("[DRY RUN] nothing uploaded or posted to Binance Square.\n")
        return

    result = post_text(text)
    print(f"[run] published {symbol} ({setup['direction']}) -> {result.get('link')} (chart saved at {chart_path}, not yet attached — image payload format still unverified)")


def _pick_diverse(shortlist, count):
    seen = set()
    picks = []
    for item in shortlist:
        if item["symbol"] in seen:
            continue
        seen.add(item["symbol"])
        picks.append(item)
        if len(picks) == count:
            break
    return picks


if __name__ == "__main__":
    if os.environ.get("RUN_MODE", "once") == "cycle":
        run_cycle()
    else:
        run_once()
