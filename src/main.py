"""
main.py

Single-run mode:
Each invocation of `python -m src.main` builds and publishes
ONE trade-setup post, then exits.

Daily rules:
- Maximum posts per day are controlled by cfg.MAX_POSTS_PER_DAY.
- The same crypto symbol can be posted only ONCE per day.
- A new UTC day resets the daily symbol history.

Backtest collection:
- When DRY_RUN=true, generated setups are saved to
  backtest_setups.json.
- Advanced market data is DISABLED for now.
- TP/SL result checking will be added in Step 3.

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
from src.news import get_relevant_news
from src.square_post_ext import post_text_v2
from src.backtest import save_setup
from src.state import (
    load_state,
    save_state,
    can_post_more_today,
    record_post,
)


def run_once():
    state = load_state()

    if not can_post_more_today(state):
        print(
            f"[run_once] daily cap reached "
            f"({cfg.MAX_POSTS_PER_DAY}) "
            "— skipping this run."
        )
        return

    shortlist = get_screener_shortlist()

    if not shortlist:
        print(
            "[run_once] screener returned nothing "
            "— skipping."
        )
        return

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

    pool = fresh.copy()
    random.shuffle(pool)

    for pick in pool:
        symbol = pick["symbol"]

        if symbol in posted_today:
            print(
                f"[run_once] {symbol} already posted today "
                "— skipping."
            )
            continue

        try:
            posted = _build_and_publish(
                symbol,
                pick,
            )

            if posted:
                state = record_post(
                    state,
                    symbol,
                )

                save_state(state)

                print(
                    f"[run_once] {symbol} recorded "
                    "as posted today."
                )
            else:
                print(
                    f"[run_once] {symbol} was DRY RUN "
                    "— not recorded as posted."
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


def run_cycle():
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
                "min before next post..."
            )

            time.sleep(
                cfg.MINUTES_BETWEEN_POSTS * 60
            )

    print(
        "[cycle] done"
    )


def _build_and_publish(
    symbol: str,
    pick=None,
):
    print(
        f"\n[run] starting analysis for {symbol}"
    )

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

    print(
        f"[run] checking relevant news for {symbol}..."
    )

    news = get_relevant_news(
        symbol
    )

    print(
        f"[run] news data ready for {symbol}"
    )

    market_context = (
        pick.get(
            "market_context"
        )
        if pick
        else None
    )

    # -------------------------------------------------
    # ADVANCED MARKET DATA DISABLED
    # -------------------------------------------------
    # Binance Futures API is currently returning HTTP 451
    # from GitHub Actions.
    #
    # Advanced data such as:
    # - Open Interest
    # - Funding Rate
    # - Long/Short Ratio
    # - Liquidations
    # - Order Book
    #
    # will be added again later after a reliable data
    # source is selected.
    # -------------------------------------------------

    print(
        f"[run] advanced market data disabled for {symbol}"
    )

    advanced_market_data = None

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

    setup["symbol"] = symbol

    setup["timeframe"] = (
        cfg.KLINE_INTERVAL.upper()
    )

    # -------------------------------------------------
    # SAVE BASELINE BACKTEST SETUP
    # -------------------------------------------------

    if cfg.DRY_RUN:
        save_setup(
            symbol,
            setup,
        )

    text = format_post_text(
        setup
    )

    print(
        f"[run] final post generated for {symbol}"
    )

    # -------------------------------------------------
    # DRY RUN
    # -------------------------------------------------

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

        return False

    # -------------------------------------------------
    # LIVE POST
    # -------------------------------------------------

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

    return True


def _pick_diverse(
    shortlist,
    count,
):
    seen = set()
    picks = []

    for item in shortlist:
        symbol = item["symbol"]

        if symbol in seen:
            continue

        seen.add(symbol)

        picks.append(item)

        if len(picks) >= count:
            break

    return picks


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
