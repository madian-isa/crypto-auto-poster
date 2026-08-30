"""
dedupe.py

Tracks which news item IDs have already been posted, so the same news
never gets posted twice.

IMPORTANT LIMITATION: Render's free tier has an EPHEMERAL disk — if the
service restarts or redeploys, this file resets to empty. That means a
restart could theoretically cause a couple of already-posted items to be
reconsidered. To fully prevent that, upgrade to a Render persistent disk,
or swap this for a tiny external store (e.g. a Supabase table, since a
Supabase project already exists) — ask if you want that wired in instead.
"""

import json
import os

SEEN_FILE = os.path.join(os.path.dirname(__file__), "..", "seen_events.json")


def load_seen() -> set:
    if not os.path.exists(SEEN_FILE):
        return set()
    try:
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    except Exception:
        return set()


def save_seen(seen: set):
    # Keep the file from growing forever — only keep the most recent 500 IDs
    trimmed = list(seen)[-500:]
    with open(SEEN_FILE, "w") as f:
        json.dump(trimmed, f)


def mark_seen(seen: set, item_id) -> set:
    seen.add(item_id)
    save_seen(seen)
    return seen
