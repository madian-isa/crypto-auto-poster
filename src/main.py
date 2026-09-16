"""
main.py

Full cycle: pick POSTS_PER_CYCLE symbols from the screener shortlist,
build a chart + AI trade setup for each, and publish text+image posts
MINUTES_BETWEEN_POSTS apart.

In production, trigger run_cycle() from a scheduler (cron / Render cron job)
rather than the sleep-based loop below, so it doesn't depend on one process
staying alive for the full ~40+ minute cycle.
"""

import time
import traceback

import bot_config as cfg
from screener import get_screener_shortlist
from indicators import fetch_klines, compute_indicators
from setup_generator import generate_setup, format_post_text
from chart import render_chart_image
from square_post_ext import post_with_images


def run_cycle():
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
    setup["symbol"] = symbol  # make sure it's exactly right, don't trust the model to echo it back
    text = format_post_text(setup)

    chart_path = render_chart_image(symbol, klines_df, setup["direction"])

    if cfg.DRY_RUN:
        print(f"\n[DRY RUN] would post for {symbol} ({setup['direction']}):")
        print("-" * 40)
        print(text)
        print("-" * 40)
        print(f"[DRY RUN] chart image saved at: {chart_path}")
        print("[DRY RUN] nothing uploaded or posted to Binance Square.\n")
        return

    result = post_with_images(text, [chart_path])
    print(f"[cycle] published {symbol} ({setup['direction']}) -> {result.get('link')}")


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
    run_cycle()
