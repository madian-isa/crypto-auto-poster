"""
main.py

Single-run mode:
Each invocation builds and publishes ONE educational market-analysis post.

The post can include a neutral market-data chart:
- Candlesticks
- EMA 21
- SMA 50
- Volume

No ATR volatility filter is used here.
No automated entry/SL/TP chart instructions are generated here.
"""

import os
import random
import time
import traceback

from src import bot_config as cfg

from src.screener import get_screener_shortlist

from src.indicators import (
    fetch_klines,
    compute_indicators,
)

from src.setup_generator import (
    generate_setup,
    format_post_text,
)

from src.news import get_relevant_news

from src.square_post_ext import post_with_images

from src.backtest import save_setup

from src.state import (
    load_state,
    save_state,
    can_post_more_today,
    record_post,
    is_symbol_posted_today,
)

from src.advanced_market_data import (
    get_advanced_market_data,
)

from src.chart import render_chart_image


def run_once():
    state = load_state()

    if not can_post_more_today(state):
        print(
            f"[run_once] daily cap reached "
            f"({cfg.MAX_POSTS_PER_DAY}) — skipping this run."
        )
        return

    shortlist = get_screener_shortlist()

    if not shortlist:
        print(
            "[run_once] screener returned nothing "
            "— skipping."
        )
        return

    # Filter candidates to ensure they haven't been posted today
    fresh = [
        item
        for item in shortlist
        if not is_symbol_posted_today(state, item.get("symbol"))
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

        if is_symbol_posted_today(state, symbol):
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
                    f"[run_once] {symbol} "
                    "recorded as posted today."
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

    state = load_state()

    if not can_post_more_today(state):
        print(
            f"[cycle] daily cap reached "
            f"({cfg.MAX_POSTS_PER_DAY}) — skipping cycle."
        )
        return

    shortlist = get_screener_shortlist()

    if not shortlist:
        print(
            "[cycle] screener returned nothing."
        )
        return

    # Exclude already posted coins
    fresh_shortlist = [
        item for item in shortlist
        if not is_symbol_posted_today(state, item.get("symbol"))
    ]

    if not fresh_shortlist:
        print("[cycle] no fresh candidates available for today.")
        return

    picks = _pick_diverse(
        fresh_shortlist,
        cfg.POSTS_PER_CYCLE,
    )

    for i, pick in enumerate(picks):
        symbol = pick["symbol"]

        # Reload state to verify inside cycle
        state = load_state()
        if is_symbol_posted_today(state, symbol):
            print(f"[cycle] {symbol} already posted today — skipping.")
            continue

        try:
            posted = _build_and_publish(
                symbol,
                pick,
            )

            if posted:
                state = record_post(state, symbol)
                save_state(state)
                print(f"[cycle] {symbol} recorded as posted today.")

        except Exception as err:
            print(
                f"[cycle] skipping {symbol}: {err}"
            )

            traceback.print_exc()

        is_last = i == len(picks) - 1

        if not is_last:
            print(
                f"[cycle] waiting "
                f"{cfg.MINUTES_BETWEEN_POSTS} min..."
            )

            time.sleep(
                cfg.MINUTES_BETWEEN_POSTS * 60
            )

    print("[cycle] done")


def _build_and_publish(
    symbol: str,
    pick=None,
):

    print(
        f"\n[run] starting analysis for {symbol}"
    )

    # -----------------------------
    # Technical data
    # -----------------------------

    print(
        f"[run] fetching technical data "
        f"for {symbol}..."
    )

    klines_df = fetch_klines(symbol)

    indicators = compute_indicators(
        klines_df
    )

    print(
        f"[run] technical indicators ready "
        f"for {symbol}"
    )

    # -----------------------------
    # News
    # -----------------------------

    print(
        f"[run] checking relevant news "
        f"for {symbol}..."
    )

    news = get_relevant_news(symbol)

    print(
        f"[run] news data ready for {symbol}"
    )

    # -----------------------------
    # Market context
    # -----------------------------

    market_context = (
        pick.get("market_context")
        if pick
        else None
    )

    # -----------------------------
    # Advanced market data
    # -----------------------------

    print(
        f"[run] collecting advanced market data "
        f"for {symbol}..."
    )

    advanced_market_data = None

    try:
        advanced_market_data = (
            get_advanced_market_data(symbol)
        )

        if advanced_market_data:
            print(
                f"[run] advanced market data "
                f"collected for {symbol}"
            )

        else:
            print(
                f"[run] advanced market data "
                f"unavailable for {symbol}"
            )

    except Exception as err:
        print(
            f"[run] advanced market data failed "
            f"for {symbol}: {err}"
        )

        print(
            "[run] continuing without advanced "
            "market data..."
        )

    # -----------------------------
    # Generate analysis
    # -----------------------------

    print(
        f"[run] generating AI analysis "
        f"for {symbol}..."
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

    # -----------------------------
    # Save backtest data
    # -----------------------------

    saved = save_setup(
        symbol,
        setup,
    )

    if saved:
        print(
            f"[run] setup saved to backtest "
            f"data for {symbol}"
        )

    else:
        print(
            f"[run] backtest collection already "
            f"complete or setup was not saved "
            f"for {symbol}"
        )

    # -----------------------------
    # Generate post text
    # -----------------------------

    text = format_post_text(
        setup
    )

    print(
        f"[run] final post generated "
        f"for {symbol}"
    )

    # -----------------------------
    # Generate neutral chart
    # -----------------------------

    print(
        f"[run] generating market chart "
        f"for {symbol}..."
    )

    chart_path = render_chart_image(
        symbol=symbol,
        klines_df=klines_df,
        setup=setup,
    )

    print(
        f"[run] chart ready: {chart_path}"
    )

    # -----------------------------
    # DRY RUN
    # -----------------------------

    if cfg.DRY_RUN:

        print(
            "\n" + "=" * 60
        )

        print(
            f"[DRY RUN] {symbol}"
        )

        print(
            "=" * 60
        )

        print(text)

        print(
            "=" * 60
        )

        print(
            f"[DRY RUN] Chart: {chart_path}"
        )

        print(
            "[DRY RUN] Nothing was posted "
            "to Binance Square."
        )

        print()

        return False

    # -----------------------------
    # Publish text + image
    # -----------------------------

    print(
        f"[run] publishing {symbol} "
        "with market chart..."
    )

    result = post_with_images(
        text,
        [chart_path],
    )

    print(
        f"[run] published {symbol} "
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
