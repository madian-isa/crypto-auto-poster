"""
main.py

The orchestrator loop:
  1. Fetch relevant news (Finnhub free tier)
  2. Skip anything already posted (dedupe.py)
  3. Generate honest post content (content_generator.py -> Claude, or fallback)
  4. Build final text (post_template.py) — 2000 char limit, 3 cashtags, 5 hashtags
  5. Publish to Binance Square (square_post.py)
  6. Mark as seen, respect daily post cap, sleep, repeat

Run with:  python -m src.main
"""

import time
import random
import datetime
from src import config, news_source, dedupe, content_generator, post_template, square_post, telegram_approval

_posts_today = 0
_today_date = datetime.date.today()
_telegram_offset = None  # tracks which Telegram updates we've already processed


def _reset_daily_counter_if_needed():
    global _posts_today, _today_date
    if datetime.date.today() != _today_date:
        _today_date = datetime.date.today()
        _posts_today = 0
        print(f"[main] New day ({_today_date}) — daily post counter reset.")


def _wait_for_approval(draft_id: str, timeout_minutes: int) -> bool | None:
    """
    Polls Telegram for a button press matching this draft_id.
    Returns True (approved), False (rejected), or None (timed out — no response).
    """
    global _telegram_offset
    deadline = time.time() + timeout_minutes * 60

    while time.time() < deadline:
        try:
            updates = telegram_approval.get_updates(offset=_telegram_offset)
        except Exception as e:
            print(f"[main] Telegram getUpdates failed: {e}")
            time.sleep(10)
            continue

        for update in updates.get("result", []):
            _telegram_offset = update["update_id"] + 1
            cq = update.get("callback_query")
            if not cq:
                continue

            data = cq.get("data", "")
            if not data.endswith(f":{draft_id}"):
                continue  # button press for a different/old draft — ignore

            try:
                telegram_approval.answer_callback(cq["id"], "Got it!")
            except Exception:
                pass

            if data.startswith("approve:"):
                return True
            if data.startswith("reject:"):
                return False

        time.sleep(5)

    return None  # timed out


def run_once():
    global _posts_today
    _reset_daily_counter_if_needed()

    if _posts_today >= config.MAX_POSTS_PER_DAY:
        print(f"[main] Daily cap of {config.MAX_POSTS_PER_DAY} posts reached. Skipping this cycle.")
        return

    seen = dedupe.load_seen()

    try:
        items = news_source.fetch_relevant_news()
    except Exception as e:
        print(f"[main] Failed to fetch news: {e}")
        return

    new_items = [item for item in items if item.get("id") not in seen]

    if not new_items:
        print("[main] No new relevant news this cycle.")
        return

    # Post the single most recent new item per cycle — avoids flooding the feed
    item = new_items[0]
    headline = item.get("headline", "").strip()
    summary = item.get("summary", "").strip()
    source = item.get("source", "Finnhub")

    if not headline:
        dedupe.mark_seen(seen, item.get("id"))
        return

    print(f"[main] New item: {headline}")

    try:
        content = content_generator.generate_post_content(headline, summary, source)
        final_text = post_template.build_post_text(
            headline=content["headline"],
            points=content["points"],
            my_take=content["my_take"],
            source=source,
        )

        # --- Send to Telegram for approval before posting anything ---
        draft_id = str(item.get("id"))
        try:
            telegram_approval.send_draft_for_approval(draft_id, final_text)
            print(f"[main] Draft sent to Telegram for approval (id={draft_id}). Waiting...")
        except Exception as e:
            print(f"[main] Failed to send draft to Telegram: {e}")
            return  # don't post anything if the approval message couldn't even be sent

        decision = _wait_for_approval(draft_id, config.APPROVAL_TIMEOUT_MINUTES)

        if decision is None:
            print(f"[main] No response within {config.APPROVAL_TIMEOUT_MINUTES} min — skipping this draft.")
            telegram_approval.notify(f"⏱️ No response in time — draft skipped:\n\n{headline}")
            dedupe.mark_seen(seen, item.get("id"))
            return

        if decision is False:
            print("[main] Draft rejected.")
            telegram_approval.notify(f"❌ Rejected: {headline}")
            dedupe.mark_seen(seen, item.get("id"))
            return

        # Approved — publish now
        result = square_post.post_text(final_text)
        _posts_today += 1

        if result.get("link"):
            print(f"[main] Posted successfully: {result['link']}")
            telegram_approval.notify(f"✅ Posted: {result['link']}")
        else:
            print("[main] Posted (soft success — no link returned, verify manually).")
            telegram_approval.notify("✅ Posted (couldn't confirm link — check Binance Square manually).")

    except Exception as e:
        print(f"[main] Failed to generate/post for '{headline}': {e}")
        # Do NOT mark as seen on failure — retry next cycle
        return

    dedupe.mark_seen(seen, item.get("id"))


def run_forever():
    config.validate()
    print(
        f"[main] Starting. Polling every {config.POLL_INTERVAL_MINUTES} min. "
        f"Daily cap: {config.MAX_POSTS_PER_DAY} posts."
    )
    while True:
        try:
            run_once()
        except Exception as e:
            # Never let one bad cycle kill the whole worker
            print(f"[main] Unexpected error in cycle: {e}")

        # Add random jitter on top of the base interval so posts don't land
        # on a suspiciously exact, machine-like schedule (helps avoid
        # looking bot-like to Binance's recommendation algorithm).
        jitter = random.randint(config.MIN_JITTER_MINUTES, config.MAX_JITTER_MINUTES)
        sleep_minutes = config.POLL_INTERVAL_MINUTES + jitter
        print(f"[main] Sleeping {sleep_minutes} min (base {config.POLL_INTERVAL_MINUTES} + jitter {jitter}).")
        time.sleep(sleep_minutes * 60)


if __name__ == "__main__":
    run_forever()
