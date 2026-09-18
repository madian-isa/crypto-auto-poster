"""
main.py

Single-run mode:
Each invocation of `python -m src.main` builds and publishes
ONE trade-setup post, then exits.

Daily rules:
- Maximum posts per day are controlled by cfg.MAX_POSTS_PER_DAY.
- The same crypto symbol can be posted only ONCE per day.
- A new UTC day resets the daily symbol history.

For local testing:
RUN_MODE=cycle can still run the older multi-post cycle.
"""

import os
import random
import time
import traceback

from src import bot_config as cfg
from src.screener import get_screener_shortlist
from src.indicators import fetch_klines, compute_indicators
from src.setup_generator import (
    generate_setup,
    format_post_text,
)
from src.advanced_market_data import (
    get_advanced_market_data,
)
from src.news import get_relevant_news
from src.square_post_ext import post_text_v2
from src.state import (
    load_state,
    save_state,
    can_post_more_today,
    record_post,
)


# =========================================================
# RUN ONCE
# =========================================================

def run_once():
    """
    Build and publish exactly one setup.

    Rules:
    1. Respect daily post limit.
    2. Do not post the same symbol twice in one day.
    """

    state = load_state()

    # -----------------------------------------------------
    # Daily limit
    # -----------------------------------------------------

    if not can_post_more_today(state):

        print(
            f"[run_once] daily cap reached "
            f"({cfg.MAX_POSTS_PER_DAY}) "
            f"— skipping this run."
        )

        return

    # -----------------------------------------------------
    # Screener
    # -----------------------------------------------------

    shortlist = get_screener_shortlist()

    if not shortlist:

        print(
            "[run_once] screener returned nothing "
            "— skipping."
        )

        return

    # -----------------------------------------------------
    # Remove coins already posted today
    # -----------------------------------------------------

    posted_today = set(
        state.get(
            "posted_symbols_today",
            [],
        )
    )

    fresh = [
        item
        for item in shortlist
        if item["symbol"] not in posted_today
    ]

    if not fresh:

        print(
            "[run_once] all current candidates were "
            "already posted today — skipping this run."
        )

        return

    # Randomize candidates so the same coin is not
    # always selected when several are available.
    pool = fresh.copy()

    random.shuffle(pool)

    # -----------------------------------------------------
    # Try candidates
    # -----------------------------------------------------

    for pick in pool:

        symbol = pick["symbol"]

        if symbol in posted_today:

            print(
                f"[run_once] {symbol} already posted today "
                "— skipping."
            )

            continue

        try:

            _build_and_publish(
                symbol,
                pick,
            )

            # Record only after the build/publish function
            # completes successfully.
            state = record_post(
                state,
                symbol,
            )

            save_state(state)

            print(
                f"[run_once] {symbol} recorded "
                "as posted today."
            )

            return

        except Exception as err:

            print(
                f"[run_once] {symbol} failed: {err}"
            )

            traceback.print_exc()

            print(
                "[run_once] trying next candidate..."
            )

            continue

    print(
        "[run_once] every fresh candidate failed "
        "this run — nothing posted."
    )


# =========================================================
# OLD CYCLE MODE
# =========================================================

def run_cycle():
    """
    Old multi-post mode for local testing.

    GitHub Actions should normally use RUN_MODE=once.
    """

    mode = (
        "DRY RUN (nothing will be posted)"
        if cfg.DRY_RUN
        else "LIVE (posting for real)"
    )

    print(
        f"[cycle] starting — mode: {mode}"
    )

    shortlist = get_screener_shortlist()

    if not shortlist:

        print(
            "[cycle] screener returned nothing."
        )

        return

    picks = _pick_diverse(
        shortlist,
        cfg.POSTS_PER_CYCLE,
    )

    for i, pick in enumerate(picks):

        symbol = pick["symbol"]

        try:

            _build_and_publish(
                symbol,
                pick,
            )

        except Exception as err:

            print(
                f"[cycle] skipping {symbol}: {err}"
            )

            traceback.print_exc()

        is_last = (
            i == len(picks) - 1
        )

        if not is_last:

            print(
                f"[cycle] waiting "
                f"{cfg.MINUTES_BETWEEN_POSTS} "
                f"min before next post..."
            )

            time.sleep(
                cfg.MINUTES_BETWEEN_POSTS * 60
            )

    print(
        "[cycle] done"
    )


# =========================================================
# BUILD + PUBLISH
# =========================================================

def _build_and_publish(
    symbol: str,
    pick=None,
):
    """
    Complete analysis pipeline:

    1. Binance klines
    2. Technical indicators
    3. Relevant news
    4. Basic market context
    5. Advanced market data
    6. AI setup generation
    7. Binance Square formatting
    8. Publish or DRY RUN
    """

    print(
        f"\n[run] starting analysis for {symbol}"
    )

    # -----------------------------------------------------
    # Technical data
    # -----------------------------------------------------

    print(
        f"[run] fetching technical data for {symbol}..."
    )

    klines_df = fetch_klines(
        symbol
    )

    indicators = compute_indicators(
        klines_df
    )

    print(
        f"[run] technical indicators ready for {symbol}"
    )

    # -----------------------------------------------------
    # News
    # -----------------------------------------------------

    print(
        f"[run] checking relevant news for {symbol}..."
    )

    news = get_relevant_news(
        symbol
    )

    print(
        f"[run] news data ready for {symbol}"
    )

    # -----------------------------------------------------
    # Basic market context
    # -----------------------------------------------------

    market_context = (
        pick.get(
            "market_context"
        )
        if pick
        else None
    )

    # -----------------------------------------------------
    # Advanced market data
    # -----------------------------------------------------

    print(
        f"[run] collecting advanced market data "
        f"for {symbol}..."
    )

    advanced_market_data = (
        get_advanced_market_data(
            symbol
        )
    )

    print(
        f"[run] advanced market data ready for {symbol}"
    )

    # -----------------------------------------------------
    # AI setup
    # -----------------------------------------------------

    print(
        f"[run] generating AI setup for {symbol}..."
    )

    setup = generate_setup(
        symbol,
        indicators,
        news,
        market_context,
        advanced_market_data,
    )

    # Add symbol/timeframe for formatter.
    setup["symbol"] = symbol

    setup["timeframe"] = (
        cfg.KLINE_INTERVAL.upper()
    )

    # -----------------------------------------------------
    # Final post
    # -----------------------------------------------------

    text = format_post_text(
        setup
    )

    print(
        f"[run] final post generated for {symbol}"
    )

    # -----------------------------------------------------
    # DRY RUN
    # -----------------------------------------------------

    if cfg.DRY_RUN:

        print(
            "\n"
            + "=" * 60
        )

        print(
            f"[DRY RUN] {symbol}"
        )

        print(
            "=" * 60
        )

        print(
            text
        )

        print(
            "=" * 60
        )

        print(
            "[DRY RUN] Nothing was posted "
            "to Binance Square."
        )

        print()

        return

    # -----------------------------------------------------
    # LIVE POST
    # -----------------------------------------------------

    print(
        f"[run] publishing {symbol} "
        "to Binance Square..."
    )

    result = post_text_v2(
        text
    )

    print(
        f"[run] published {symbol} "
        f"({setup.get('direction', 'UNKNOWN')}) "
        f"-> {result.get('link')}"
    )


# =========================================================
# PICK DIVERSE COINS
# =========================================================

def _pick_diverse(
    shortlist,
    count,
):
    """
    Select unique symbols from the screener shortlist.
    """

    seen = set()

    picks = []

    for item in shortlist:

        symbol = item["symbol"]

        if symbol in seen:
            continue

        seen.add(
            symbol
        )

        picks.append(
            item
        )

        if len(picks) >= count:
            break

    return picks


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":

    run_mode = os.environ.get(
        "RUN_MODE",
        "once",
    ).lower()

    print(
        f"[main] RUN_MODE={run_mode}"
    )

    if run_mode == "cycle":

        run_cycle()

    else:

        run_once()
