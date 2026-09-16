"""
setup_generator.py

Sends computed indicators to Groq and gets back a trade setup (direction,
entry/SL/TP) plus a fresh, non-repetitive caption, as JSON.
"""

import json
from groq import Groq
import bot_config as cfg

SYSTEM_PROMPT = """You are a crypto market analyst writing short Binance Square trade-setup posts.
Rules:
- Base direction (Long/Short) and levels strictly on the indicator data given — do not invent price action not implied by the data.
- Entry should be a tight 2-value range around current price. SL and TP must be logically placed (SL beyond recent swing, TP toward next level, sensible risk:reward).
- The hook/caption must be SHORT (max ~12 words), punchy, and DIFFERENT in wording/style every time — vary tone (confident, curious, urgent, casual) so posts never look templated.
- Write the caption entirely in your own words. Never reuse or closely paraphrase wording from any real post you may have seen elsewhere — it must be an original line every time.
- Output ONLY valid JSON, no markdown fences, no preamble."""


def generate_setup(symbol: str, indicators: dict) -> dict:
    client = Groq(api_key=cfg.GROQ_API_KEY)

    user_prompt = f"""Symbol: {symbol}
Current price: {indicators['price']}
24h approx high: {indicators['high24Approx']}
24h approx low: {indicators['low24Approx']}
RSI(14): {indicators['rsi14']}
EMA9: {indicators['ema9']}
EMA21: {indicators['ema21']}
EMA trend: {indicators['emaTrend']}
MACD: {json.dumps(indicators['macd'])}

Return JSON with exactly this shape:
{{
  "symbol": string,
  "direction": "Long" | "Short",
  "entry_low": number,
  "entry_high": number,
  "sl": number,
  "tp_low": number,
  "tp_high": number,
  "caption": string
}}"""

    completion = client.chat.completions.create(
        model=cfg.GROQ_MODEL,
        temperature=0.9,  # higher temp so captions vary run to run
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )

    raw = completion.choices[0].message.content or ""
    cleaned = raw.replace("```json", "").replace("```", "").strip()

    try:
        setup = json.loads(cleaned)
    except json.JSONDecodeError as err:
        raise RuntimeError(f"Model did not return valid JSON for {symbol}: {raw}") from err

    return setup


def format_post_text(setup: dict) -> str:
    """Matches the reference post layout: headline, entry/sl/tp, hook, disclaimer."""
    base = setup["symbol"].replace("USDT", "")
    direction = "Short" if setup.get("direction") == "Short" else "Long"
    arrow = "👇" if direction == "Short" else "👆"

    lines = [
        f"${base} {setup['caption']}",
        "",
        f"entry {setup['entry_low']}-{setup['entry_high']}",
        f"sl {setup['sl']}",
        f"tp {setup['tp_low']}-{setup['tp_high']}",
        "",
        f"{direction} ${base} {arrow}",
    ]
    return "\n".join(lines)
