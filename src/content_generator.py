"""
content_generator.py

Turns a raw news item (headline + summary + source) into the 3 pieces
post_template.py needs: a hook headline, 2-3 factual points, and one
honest "my take" line.

Uses the Claude API (ANTHROPIC_API_KEY) so the writing quality matches the
house style already established: fact-based, no fear/greed manipulation,
no guaranteed price predictions, honest hedging where the situation is
genuinely uncertain.

If ANTHROPIC_API_KEY is not set, falls back to a plain rule-based version
(lower quality, but the bot still works — better than posting nothing).
"""

import json
import random
import requests
from src import config

# Varied opening styles so headlines don't all follow the exact same
# "🎙️ X says Y" pattern — that repetition is itself a bot tell.
HEADLINE_PREFIXES = ["", "", "", "📊 ", "🎙️ ", "⚠️ "]  # empty = no emoji, most common

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"

SYSTEM_PROMPT = """You write short, honest Binance Square posts about crypto/macro news.

Rules — follow strictly:
- Only use facts present in the provided headline/summary. Never invent numbers, quotes, or predictions.
- No fear or greed manipulation. Never use phrases like "is your money safe", "golden opportunity", "final crash", "turn on notifications or miss out".
- No guaranteed price targets or "will pump/crash" claims. If discussing potential market impact, hedge honestly ("could", "historically tends to") — never present it as certain.
- Keep it tight: a punchy but honest headline, 2-3 factual bullet points, one short "my take" sentence.
- The "my take" must be a genuine, hedged read — not a trade signal.

Return ONLY valid JSON, no markdown, no preamble, in this exact shape:
{"headline": "...", "points": ["...", "...", "..."], "my_take": "..."}
"""


FALLBACK_TAKES = [
    "Worth tracking as this develops — not a standalone trade signal.",
    "One data point, not the full picture — watching for confirmation before reading too much into it.",
    "Early days on this one. Keeping an eye on how it plays out rather than reacting to the headline alone.",
    "Context matters more than the headline here — worth following up as more details come in.",
]


def _rule_based_fallback(headline: str, summary: str) -> dict:
    points = [summary[:180]] if summary else [headline]
    prefix = random.choice(HEADLINE_PREFIXES)
    return {
        "headline": f"{prefix}{headline}",
        "points": points,
        "my_take": random.choice(FALLBACK_TAKES),
    }


def generate_post_content(headline: str, summary: str, source: str) -> dict:
    if not config.ANTHROPIC_API_KEY:
        return _rule_based_fallback(headline, summary)

    user_msg = (
        f"Headline: {headline}\n"
        f"Summary: {summary}\n"
        f"Source: {source}\n\n"
        "Write the post content now, following the rules exactly."
    )

    try:
        resp = requests.post(
            ANTHROPIC_URL,
            headers={
                "x-api-key": config.ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-6",
                "max_tokens": 500,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": user_msg}],
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        text = "".join(
            block.get("text", "") for block in data.get("content", []) if block.get("type") == "text"
        )
        cleaned = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(cleaned)

        if not all(k in parsed for k in ("headline", "points", "my_take")):
            raise ValueError("Model response missing required fields.")

        return parsed

    except Exception as e:
        print(f"[content_generator] Claude generation failed ({e}), using fallback.")
        return _rule_based_fallback(headline, summary)
