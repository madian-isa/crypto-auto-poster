"""
main.py

Single-run / cycle mode for Binance Square educational
crypto market-analysis posts.

Data sources:
- Binance market data
- Binance advanced market data
- CoinGlass market data
- Finnhub news
- Groq AI

CoinGlass is optional:
- Missing API key does not stop the bot.
- CoinGlass API failures do not stop the bot.
- Existing Binance advanced data remains active.
"""

import os
import random
import time
import traceback


from src import bot_config as cfg

from src.screener import (
    get_screener_shortlist,
)

from src.indicators import (
    fetch_klines,
    compute_indicators,
)

from src.setup_generator import (
    generate_setup,
    format_post_text,
)

from src.news import (
    get_relevant_news,
)

from src.square_post_ext import (
    post_with_images,
)

from src.backtest import (
    save_setup,
)

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

from src.coinglass_data import (
    get_coinglass_market_data,
)

from src.chart import (
    render_chart_image,
)


# ============================================================
# RUNTIME
# ============================================================

RUN_MODE = os.environ.get(
    "RUN_MODE",
    "once",
).lower().strip()


# ============================================================
# HELPERS
# ============================================================

def _safe_symbol(value):
    return str(
        value or ""
    ).upper().strip()


def _get_pick_symbol(pick):
    """
    Extract symbol from screener result.

    Supports common screener structures.
    """

    if not isinstance(
        pick,
        dict,
    ):
        return None

    for key in (
        "symbol",
        "ticker",
        "pair",
    ):

        value = pick.get(
            key
        )

        if value:

            return _safe_symbol(
                value
            )

    return None


def _print_market_data_status(
    symbol,
    advanced_market_data,
    coinglass_market_data,
):
    """
    Print a compact data-source summary.
    """

    print(
        f"[main] market data status for {symbol}"
    )

    # --------------------------------------------------------
    # Binance advanced data
    # --------------------------------------------------------

    if isinstance(
        advanced_market_data,
        dict,
    ):

        status = (
            advanced_market_data
            .get("source_status", {})
        )

        print(
            "[main] Binance advanced "
            f"spot={status.get('spot')} "
            f"futures={status.get('futures')}"
        )

    else:

        print(
            "[main] Binance advanced data "
            "unavailable"
        )

    # --------------------------------------------------------
    # CoinGlass
    # --------------------------------------------------------

    if isinstance(
        coinglass_market_data,
        dict,
    ):

        status = (
            coinglass_market_data
            .get(
                "source_status",
                "unknown",
            )
        )

        print(
            "[main] CoinGlass status="
            f"{status}"
        )

        available = []

        for key, value in (
            coinglass_market_data
            .items()
        ):

            if key in (
                "source",
                "source_status",
                "symbol",
            ):
                continue

            if value is not None:

                available.append(
                    key
                )

        print(
            "[main] CoinGlass fields="
            f"{', '.join(available) if available else 'none'}"
        )

    else:

        print(
            "[main] CoinGlass data "
            "unavailable"
        )


# ============================================================
# DIVERSE PICKING
# ============================================================

def _pick_diverse(
    shortlist,
    posted_symbols,
    limit,
):
    """
    Select symbols while avoiding symbols already posted today.

    Existing daily-post protection is preserved.
    """

    if not shortlist:

        return []

    fresh = []

    for pick in shortlist:

        symbol = _get_pick_symbol(
            pick
        )

        if not symbol:
            continue

        if symbol in posted_symbols:
            continue

        fresh.append(
            pick
        )

    random.shuffle(
        fresh
    )

    return fresh[
        :limit
    ]


# ============================================================
# BUILD + PUBLISH
# ============================================================

def _build_and_publish(
    symbol,
    pick,
):
    """
    Build one setup and publish one post.

    CoinGlass is optional and isolated from the
    existing Binance advanced-data layer.
    """

    symbol = _safe_symbol(
        symbol
    )

    if not symbol:

        print(
            "[main] invalid symbol"
        )

        return False

    print(
        ""
    )

    print(
        "=" * 70
    )

    print(
        f"[main] processing {symbol}"
    )

    print(
        "=" * 70
    )


    # ========================================================
    # KLINES
    # ========================================================

    try:

        klines = fetch_klines(
            symbol,
            interval=cfg.KLINE_INTERVAL,
            limit=cfg.KLINE_LIMIT,
        )

    except Exception as err:

        print(
            f"[main] kline fetch failed "
            f"{symbol}: {err}"
        )

        return False

    if not klines:

        print(
            f"[main] no klines for "
            f"{symbol}"
        )

        return False


    # ========================================================
    # INDICATORS
    # ========================================================

    try:

        indicators = compute_indicators(
            klines
        )

    except Exception as err:

        print(
            f"[main] indicator calculation "
            f"failed {symbol}: {err}"
        )

        traceback.print_exc()

        return False


    if not indicators:

        print(
            f"[main] no indicators for "
            f"{symbol}"
        )

        return False


    # ========================================================
    # NEWS
    # ========================================================

    news = None

    try:

        news = get_relevant_news(
            symbol
        )

    except Exception as err:

        print(
            f"[main] news failed "
            f"{symbol}: {err}"
        )

        news = None


    # ========================================================
    # MARKET CONTEXT FROM SCREENER
    # ========================================================

    market_context = None

    if isinstance(
        pick,
        dict,
    ):

        market_context = pick.get(
            "market_context"
        )


    # ========================================================
    # BINANCE ADVANCED MARKET DATA
    # ========================================================

    advanced_market_data = None

    try:

        print(
            "[main] collecting Binance "
            f"advanced data for {symbol}"
        )

        advanced_market_data = (
            get_advanced_market_data(
                symbol
            )
        )

    except Exception as err:

        print(
            "[main] Binance advanced "
            f"data failed {symbol}: {err}"
        )

        advanced_market_data = None


    # ========================================================
    # COINGLASS MARKET DATA
    # ========================================================

    coinglass_market_data = None

    try:

        print(
            "[main] collecting CoinGlass "
            f"data for {symbol}"
        )

        coinglass_market_data = (
            get_coinglass_market_data(
                symbol
            )
        )

    except Exception as err:

        print(
            "[main] CoinGlass failed "
            f"{symbol}: {err}"
        )

        # IMPORTANT:
        # CoinGlass must never stop the bot.
        coinglass_market_data = None


    # ========================================================
    # DATA STATUS
    # ========================================================

    _print_market_data_status(
        symbol,
        advanced_market_data,
        coinglass_market_data,
    )


    # ========================================================
    # GENERATE SETUP
    # ========================================================

    try:

        setup = generate_setup(
            symbol,
            indicators,
            news,
            market_context,
            advanced_market_data,
            coinglass_market_data,
        )

    except TypeError as err:

        print(
            "[main] setup_generator signature "
            f"does not yet accept CoinGlass: {err}"
        )

        print(
            "[main] CoinGlass integration "
            "requires the updated "
            "setup_generator.py."
        )

        return False

    except Exception as err:

        print(
            f"[main] setup generation "
            f"failed {symbol}: {err}"
        )

        traceback.print_exc()

        return False


    # ========================================================
    # VALIDATE SETUP
    # ========================================================

    if not isinstance(
        setup,
        dict,
    ):

        print(
            f"[main] invalid setup "
            f"for {symbol}"
        )

        return False


    direction = str(
        setup.get(
            "direction",
            "",
        )
    ).upper().strip()


    if direction not in (
        "LONG",
        "SHORT",
    ):

        print(
            f"[main] invalid direction "
            f"for {symbol}: "
            f"{direction}"
        )

        return False


    entry = setup.get(
        "entry"
    )

    stop_loss = setup.get(
        "stop_loss"
    )

    take_profit = setup.get(
        "take_profit"
    )


    if (
        entry is None
        or stop_loss is None
        or take_profit is None
    ):

        print(
            f"[main] incomplete setup "
            f"for {symbol}"
        )

        return False


    # ========================================================
    # SAVE SETUP / BACKTEST STATE
    # ========================================================

    try:

        save_setup(
            setup
        )

    except TypeError:

        try:

            save_setup(
                symbol,
                setup,
            )

        except Exception as err:

            print(
                f"[main] save_setup failed "
                f"{symbol}: {err}"
            )

    except Exception as err:

        print(
            f"[main] save_setup failed "
            f"{symbol}: {err}"
        )


    # ========================================================
    # FORMAT POST
    # ========================================================

    try:

        post_text = format_post_text(
            setup
        )

    except Exception as err:

        print(
            f"[main] post formatting "
            f"failed {symbol}: {err}"
        )

        traceback.print_exc()

        return False


    if not post_text:

        print(
            f"[main] empty post for "
            f"{symbol}"
        )

        return False


    # ========================================================
    # RENDER CHART
    # ========================================================

    chart_path = None

    try:

        chart_path = render_chart_image(
            symbol,
            klines,
            indicators,
            output_dir=cfg.CHART_OUTPUT_DIR,
        )

    except TypeError:

        # Compatibility with chart.py versions
        # using a different function signature.

        try:

            chart_path = render_chart_image(
                symbol,
                klines,
                indicators,
            )

        except Exception as err:

            print(
                f"[main] chart failed "
                f"{symbol}: {err}"
            )

            chart_path = None

    except Exception as err:

        print(
            f"[main] chart failed "
            f"{symbol}: {err}"
        )

        chart_path = None


    # ========================================================
    # PREVIEW
    # ========================================================

    print(
        ""
    )

    print(
        "-" * 70
    )

    print(
        f"[main] generated post for "
        f"{symbol}"
    )

    print(
        post_text
    )

    print(
        "-" * 70
    )


    # ========================================================
    # DRY RUN
    # ========================================================

    if cfg.DRY_RUN:

        print(
            "[main] DRY_RUN enabled. "
            "No Binance Square post sent."
        )

        return True


    # ========================================================
    # PUBLISH
    # ========================================================

    try:

        result = post_with_images(
            post_text,
            image_paths=(
                [chart_path]
                if chart_path
                else []
            ),
        )

    except TypeError:

        try:

            result = post_with_images(
                post_text,
                (
                    [chart_path]
                    if chart_path
                    else []
                ),
            )

        except Exception as err:

            print(
                f"[main] publish failed "
                f"{symbol}: {err}"
            )

            traceback.print_exc()

            return False

    except Exception as err:

        print(
            f"[main] publish failed "
            f"{symbol}: {err}"
        )

        traceback.print_exc()

        return False


    # ========================================================
    # POST SUCCESS
    # ========================================================

    if result is False:

        print(
            f"[main] publish returned "
            f"False for {symbol}"
        )

        return False


    print(
        f"[main] published successfully: "
        f"{symbol}"
    )

    return True


# ============================================================
# RUN ONCE
# ============================================================

def run_once():
    """
    Single-run mode.

    One invocation attempts one post.
    """

    print(
        "[main] RUN_MODE=once"
    )


    # ========================================================
    # STATE
    # ========================================================

    state = load_state()


    # ========================================================
    # DAILY CAP
    # ========================================================

    if not can_post_more_today(
        state
    ):

        print(
            f"[run_once] daily cap reached "
            f"({cfg.MAX_POSTS_PER_DAY}) "
            f"— skipping this run"
        )

        return


    # ========================================================
    # SCREENER
    # ========================================================

    try:

        shortlist = (
            get_screener_shortlist()
        )

    except Exception as err:

        print(
            f"[run_once] screener failed: "
            f"{err}"
        )

        traceback.print_exc()

        return


    if not shortlist:

        print(
            "[run_once] "
            "screener returned no candidates"
        )

        return


    print(
        f"[run_once] shortlist size: "
        f"{len(shortlist)}"
    )


    # ========================================================
    # POSTED TODAY
    # ========================================================

    posted_symbols = set()

    for pick in shortlist:

        symbol = _get_pick_symbol(
            pick
        )

        if not symbol:
            continue

        try:

            if is_symbol_posted_today(
                state,
                symbol,
            ):

                posted_symbols.add(
                    symbol
                )

        except Exception as err:

            print(
                "[run_once] state check "
                f"failed for {symbol}: {err}"
            )


    # ========================================================
    # FRESH CANDIDATES
    # ========================================================

    candidates = _pick_diverse(
        shortlist,
        posted_symbols,
        max(
            1,
            cfg.PICK_FROM_TOP_N,
        ),
    )


    if not candidates:

        print(
            "[run_once] "
            "all shortlisted symbols "
            "were already posted today"
        )

        return


    # ========================================================
    # SHUFFLE
    # ========================================================

    random.shuffle(
        candidates
    )


    # ========================================================
    # TRY CANDIDATES
    # ========================================================

    for pick in candidates:

        symbol = _get_pick_symbol(
            pick
        )

        if not symbol:
            continue

        # Re-check state immediately before
        # processing the symbol.

        latest_state = load_state()

        if not can_post_more_today(
            latest_state
        ):

            print(
                "[run_once] "
                "daily cap reached "
                "before posting"
            )

            return


        try:

            if is_symbol_posted_today(
                latest_state,
                symbol,
            ):

                print(
                    f"[run_once] {symbol} "
                    "already posted today. "
                    "Skipping."
                )

                continue

        except Exception as err:

            print(
                "[run_once] latest state "
                f"check failed for {symbol}: {err}"
            )

            continue


        # ----------------------------------------------------
        # Build + publish
        # ----------------------------------------------------

        success = _build_and_publish(
            symbol,
            pick,
        )


        if not success:

            print(
                f"[run_once] "
                f"{symbol} failed."
            )

            continue


        # ----------------------------------------------------
        # Record successful post
        # ----------------------------------------------------

        try:

            state = load_state()

            record_post(
                state,
                symbol,
            )

            save_state(
                state
            )

            print(
                f"[run_once] "
                f"{symbol} recorded in state."
            )

        except Exception as err:

            print(
                f"[run_once] "
                f"failed to record {symbol}: "
                f"{err}"
            )

        return


    print(
        "[run_once] "
        "no candidate successfully processed"
    )


# ============================================================
# RUN CYCLE
# ============================================================

def run_cycle():
    """
    Multi-post cycle.

    Posts up to POSTS_PER_CYCLE symbols,
    while respecting:
    - daily cap
    - already-posted-today protection
    - posting interval
    """

    print(
        "[main] RUN_MODE=cycle"
    )

    print(
        f"[run_cycle] "
        f"target posts: "
        f"{cfg.POSTS_PER_CYCLE}"
    )


    posts_done = 0


    while (
        posts_done
        < cfg.POSTS_PER_CYCLE
    ):

        # ====================================================
        # STATE
        # ====================================================

        state = load_state()


        # ====================================================
        # DAILY CAP
        # ====================================================

        if not can_post_more_today(
            state
        ):

            print(
                "[run_cycle] "
                "daily cap reached."
            )

            break


        # ====================================================
        # SCREENER
        # ====================================================

        try:

            shortlist = (
                get_screener_shortlist()
            )

        except Exception as err:

            print(
                f"[run_cycle] "
                f"screener failed: {err}"
            )

            traceback.print_exc()

            break


        if not shortlist:

            print(
                "[run_cycle] "
                "no candidates."
            )

            break


        # ====================================================
        # REMOVE POSTED SYMBOLS
        # ====================================================

        posted_symbols = set()

        for pick in shortlist:

            symbol = _get_pick_symbol(
                pick
            )

            if not symbol:
                continue

            try:

                if is_symbol_posted_today(
                    state,
                    symbol,
                ):

                    posted_symbols.add(
                        symbol
                    )

            except Exception:

                continue


        # ====================================================
        # PICK
        # ====================================================

        candidates = _pick_diverse(
            shortlist,
            posted_symbols,
            max(
                1,
                cfg.PICK_FROM_TOP_N,
            ),
        )


        if not candidates:

            print(
                "[run_cycle] "
                "no fresh symbols remain."
            )

            break


        random.shuffle(
            candidates
        )


        # ====================================================
        # TRY CANDIDATES
        # ====================================================

        posted_this_round = False

        for pick in candidates:

            symbol = _get_pick_symbol(
                pick
            )

            if not symbol:
                continue


            # ------------------------------------------------
            # Re-load state before every post.
            # ------------------------------------------------

            state = load_state()


            if not can_post_more_today(
                state
            ):

                print(
                    "[run_cycle] "
                    "daily cap reached."
                )

                return


            try:

                if is_symbol_posted_today(
                    state,
                    symbol,
                ):

                    print(
                        f"[run_cycle] "
                        f"{symbol} already posted "
                        "today. Skipping."
                    )

                    continue

            except Exception:

                continue


            # ------------------------------------------------
            # Build + publish
            # ------------------------------------------------

            success = _build_and_publish(
                symbol,
                pick,
            )


            if not success:

                print(
                    f"[run_cycle] "
                    f"{symbol} failed."
                )

                continue


            # ------------------------------------------------
            # Record successful post
            # ------------------------------------------------

            try:

                state = load_state()

                record_post(
                    state,
                    symbol,
                )

                save_state(
                    state
                )

            except Exception as err:

                print(
                    f"[run_cycle] "
                    f"state save failed "
                    f"{symbol}: {err}"
                )


            posts_done += 1

            posted_this_round = True


            print(
                f"[run_cycle] "
                f"posts completed: "
                f"{posts_done}/"
                f"{cfg.POSTS_PER_CYCLE}"
            )


            # ------------------------------------------------
            # Wait before next post
            # ------------------------------------------------

            if (
                posts_done
                < cfg.POSTS_PER_CYCLE
            ):

                wait_seconds = (
                    max(
                        0,
                        cfg.MINUTES_BETWEEN_POSTS,
                    )
                    * 60
                )

                if wait_seconds > 0:

                    print(
                        "[run_cycle] "
                        f"waiting "
                        f"{cfg.MINUTES_BETWEEN_POSTS} "
                        "minutes before next post..."
                    )

                    time.sleep(
                        wait_seconds
                    )


            break


        if not posted_this_round:

            print(
                "[run_cycle] "
                "no candidate successfully "
                "processed in this round."
            )

            break


    print(
        "[run_cycle] completed. "
        f"posts_done={posts_done}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        ""
    )

    print(
        "=" * 70
    )

    print(
        "TRADE SETUP BOT"
    )

    print(
        "=" * 70
    )

    print(
        f"RUN_MODE={RUN_MODE}"
    )

    print(
        f"DRY_RUN={cfg.DRY_RUN}"
    )

    print(
        f"MAX_POSTS_PER_DAY="
        f"{cfg.MAX_POSTS_PER_DAY}"
    )

    print(
        f"POSTS_PER_CYCLE="
        f"{cfg.POSTS_PER_CYCLE}"
    )

    print(
        f"MINUTES_BETWEEN_POSTS="
        f"{cfg.MINUTES_BETWEEN_POSTS}"
    )

    print(
        "CoinGlass="
        + (
            "configured"
            if cfg.COINGLASS_API_KEY
            else "not configured"
        )
    )

    print(
        "=" * 70
    )


    if RUN_MODE == "cycle":

        run_cycle()

    else:

        run_once()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    try:

        main()

    except KeyboardInterrupt:

        print(
            "[main] stopped by user."
        )

    except Exception as err:

        print(
            f"[main] fatal error: {err}"
        )

        traceback.print_exc()

        raise
