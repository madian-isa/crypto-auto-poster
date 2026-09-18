```python
"""
main.py

Single-run mode: each invocation of `python main.py` builds and publishes
ONE trade-setup post, then exits. A scheduler (GitHub Actions cron) re-runs
this every ~20 minutes.

Daily rules:
- Maximum posts per day are controlled by cfg.MAX_POSTS_PER_DAY.
- The same crypto symbol can be posted only ONCE per day.
- A new day resets the daily symbol history.

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
from src.advanced_market_data import get_advanced_market_data
from src.news import get_relevant_news
from src.square_post_ext import post_text_v2
from src.state import (
    load_state,
    save_state,
    can_post_more_today,
    record_post,
)


def run_once():
    """Post exactly one setup while respecting:
    1. The daily post cap.
    2. The rule that each crypto can appear only once per day.
    """

    state = load_state()

    # Check daily maximum
    if not can_post_more_today(state):
        print(
            f"[run_once] daily cap reached "
            f"({cfg.MAX_POSTS_PER_DAY}) — skipping this run."
        )
        return

    shortlist = get_screener_shortlist()

    if not shortlist:
        print(
            "[run_once] screener returned nothing — skipping."
        )
        return

    # Use the ENTIRE screener shortlist.
    # Do not limit selection to PICK_FROM_TOP_N here.
    candidates = shortlist

    # Only use coins that have NOT been posted today.
    posted_today = set(
        state.get(
            "posted_symbols_today",
            [],
        )
    )

    fresh = [
        c
        for c in candidates
        if c["symbol"] not in posted_today
    ]

    # If every available candidate was already posted today,
    # skip this run instead of reposting any coin.
    if not fresh:
        print(
            "[run_once] all current candidates were already "
            "posted today — skipping this run."
        )
        return

    # Randomize fresh candidates so the same top-ranked coin
    # does not always get selected first.
    pool = fresh.copy()
    random.shuffle(pool)

    for pick in pool:
        symbol = pick["symbol"]

        # Extra safety check before building/posting.
        if symbol in posted_today:
            print(
                f"[run_once] {symbol} already posted today "
                f"— skipping."
            )
            continue

        try:
            _build_and_publish(
                symbol,
                pick,
            )

            # Only record the symbol AFTER successful completion.
            state = record_post(
                state,
                symbol,
            )

            save_state(state)

            print(
                f"[run_once] {symbol} recorded "
                f"as posted today."
            )

            return

        except Exception as err:
            print(
                f"[run_once] {symbol} failed, "
                f"trying next candidate: {err}"
            )

            traceback.print_exc()

            continue

    print(
        "[run_once] every fresh candidate failed this run "
        "— nothing posted."
    )


def run_cycle():
    """Old behavior, kept for local testing: 3 posts, 20 min apart, in one
    long-lived process. Not what the GitHub Actions workflow uses.
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

    print("[cycle] done")


def _build_and_publish(
    symbol: str,
    pick=None,
):
    """
    Build one complete trade setup.

    Data flow:
    1. Binance klines
    2. Technical indicators
    3. Relevant news
    4. Basic BTC / market context
    5. Advanced market data
    6. AI-generated setup
    7. Final Binance Square post
    """

    # ---------------------------------------------------------
    # 1. Get candle data
    # ---------------------------------------------------------

    klines_df = fetch_klines(
        symbol
    )

    # ---------------------------------------------------------
    # 2. Calculate technical indicators
    # ---------------------------------------------------------

    indicators = compute_indicators(
        klines_df
    )

    # ---------------------------------------------------------
    # 3. Get real relevant news
    # ---------------------------------------------------------

    news = get_relevant_news(
        symbol
    )

    # None if nothing real found.
    # News must never be fabricated.

    # ---------------------------------------------------------
    # 4. Basic market context from screener
    # ---------------------------------------------------------

    market_context = (
        pick.get("market_context")
        if pick
        else None
    )

    # ---------------------------------------------------------
    # 5. Advanced market data
    # ---------------------------------------------------------

    advanced_market_data = (
        get_advanced_market_data(
            symbol
        )
    )

    # Advanced data includes:
    # - 15M / 1H / 4H / 1D / 1W support/resistance
    # - BTC 4H / 1D trend
    # - Symbol open interest
    # - OI change
    # - Funding rate
    # - Long/short ratio
    # - Recent liquidation activity
    # - Order-book liquidity

    # ---------------------------------------------------------
    # 6. Generate AI trade setup
    # ---------------------------------------------------------

    setup = generate_setup(
        symbol,
        indicators,
        news,
        market_context,
        advanced_market_data,
    )

    # ---------------------------------------------------------
    # 7. Never trust the model to echo the symbol correctly
    # ---------------------------------------------------------

    setup["symbol"] = symbol

    setup["timeframe"] = (
        cfg.KLINE_INTERVAL.upper()
    )

    # ---------------------------------------------------------
    # 8. Format final Binance Square post
    # ---------------------------------------------------------

    text = format_post_text(
        setup
    )

    # ---------------------------------------------------------
    # 9. Dry run or real posting
    # ---------------------------------------------------------

    if cfg.DRY_RUN:

        print(
            f"\n[DRY RUN] would post for "
            f"{symbol} "
            f"({setup['direction']}):"
        )

        print(
            "-" * 40
        )

        print(text)

        print(
            "-" * 40
        )

        print(
            "[DRY RUN] nothing posted "
            "to Binance Square.\n"
        )

        return

    # ---------------------------------------------------------
    # 10. Publish to Binance Square
    # ---------------------------------------------------------

    result = post_text_v2(
        text
    )

    print(
        f"[run] published {symbol} "
        f"({setup['direction']}) "
        f"-> {result.get('link')}"
    )


def _pick_diverse(
    shortlist,
    count,
):
    """
    Pick unique symbols from the shortlist.
    Used only by RUN_MODE=cycle.
    """

    seen = set()

    picks = []

    for item in shortlist:

        if item["symbol"] in seen:
            continue

        seen.add(
            item["symbol"]
        )

        picks.append(
            item
        )

        if len(picks) == count:
            break

    return picks


if __name__ == "__main__":

    if os.environ.get(
        "RUN_MODE",
        "once",
    ) == "cycle":

        run_cycle()

    else:

        run_once()
```
