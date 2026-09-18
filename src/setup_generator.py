"""
setup_generator.py

Sends the full indicator set (10+ indicators, support/resistance, and any
real matching news) to Groq and gets back direction + a short caption +
a one-line analysis blurb. Entry range comes from the model; SL and TP are
computed in code — SL at a volatility-proportionate ATR distance, TP at a
randomized 2x or 3x reward multiple — so stops/targets stay realistic
instead of the wide, arbitrary levels a free-form model tends to produce.

Post formatting uses a few different layouts, chosen at random, so
consecutive posts don't look templated.
"""

import json
import random
from groq import Groq
from src import bot_config as cfg

SYSTEM_PROMPT = """You are a crypto market analyst writing Binance Square trade-setup posts.
Rules:
- Base direction (Long/Short) strictly on the full indicator set given (RSI, EMA9/21, SMA50, MACD, Bollinger Bands, Stochastic, ADX, ATR, OBV trend) plus the support/resistance levels — do not invent price action not implied by the data.
- If a real news headline is provided, factor it in briefly. If none is given, do not mention news at all — never invent a news event.
- Entry should be a tight 2-value range around current price.
- "analysis" must be ONE short sentence (max ~18 words) explaining the call using 2-3 of the actual indicator values/levels given (e.g. mention RSI level, ADX trend strength, or the support/resistance number) — sound like a trader's quick technical note, not a generic statement.
- "caption" is a SHORT hook (max ~10 words), punchy, and DIFFERENT in wording/style every time — vary tone (confident, curious, urgent, casual) so posts never look templated. Original wording only — never reuse or paraphrase a real post you may have seen elsewhere.
- Output ONLY valid JSON, no markdown fences, no preamble."""


def generate_setup(symbol: str, indicators: dict, news: dict | None = None) -> dict:
    client = Groq(api_key=cfg.GROQ_API_KEY)

    news_block = (
        f'Real recent news headline: "{news["headline"]}"' if news else
        "No relevant news found — do not mention any news."
    )

    user_prompt = f"""Symbol: {symbol}
Current price: {indicators['price']}
Timeframe: {cfg.KLINE_INTERVAL}
24h approx high: {indicators['high24Approx']}
24h approx low: {indicators['low24Approx']}
RSI(14): {indicators['rsi14']}
EMA9: {indicators['ema9']} | EMA21: {indicators['ema21']} | SMA50: {indicators['sma50']}
EMA trend: {indicators['emaTrend']}
MACD: {json.dumps(indicators['macd'])}
Bollinger Bands: {json.dumps(indicators['bollinger'])}
Stochastic: {json.dumps(indicators['stochastic'])}
ADX(14) [trend strength, >25 = trending]: {indicators['adx14']}
ATR(14) [volatility]: {indicators['atr14']}
OBV trend: {indicators['obvTrend']}
Support: {indicators['support']}
Resistance: {indicators['resistance']}
{news_block}

Return JSON with exactly this shape:
{{
  "symbol": string,
  "direction": "Long" | "Short",
  "entry_low": number,
  "entry_high": number,
  "caption": string,
  "analysis": string
}}"""

    completion = client.chat.completions.create(
        model=cfg.GROQ_MODEL,
        temperature=0.9,
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

    _apply_risk_reward(setup, indicators)
    setup["support"] = indicators.get("support")
    setup["resistance"] = indicators.get("resistance")
    setup["news"] = news
    return setup


def _apply_risk_reward(setup: dict, indicators: dict) -> None:
    """SL at ATR_MULTIPLIER x ATR(14) from entry; TP at a randomized 2x/3x
    reward multiple. Computed here — never trusted from the model — so
    stops/targets stay proportionate to real recent volatility."""
    entry = (float(setup["entry_low"]) + float(setup["entry_high"])) / 2
    atr = float(indicators["atr14"]) or (entry * 0.01)
    risk = atr * cfg.ATR_MULTIPLIER
    rr = random.choice(cfg.RISK_REWARD_CHOICES)
    reward = risk * rr

    if setup.get("direction") == "Short":
        sl = entry + risk
        tp = entry - reward
    else:
        sl = entry - risk
        tp = entry + reward

    setup["sl"] = round(sl, 8)
    setup["tp"] = round(tp, 8)
    setup["risk_reward"] = rr


def format_post_text(setup: dict) -> str:
    base = setup["symbol"].replace("USDT", "")
    direction = "Short" if setup.get("direction") == "Short" else "Long"
    arrow = "👇" if direction == "Short" else "👆"
    tf = setup.get("timeframe", "1H")

    entry_range = f"{setup['entry_low']}-{setup['entry_high']}"
    setup_line = f"Entry {entry_range} | SL {setup['sl']} | TP {setup['tp']} ({direction[0]}:{setup['risk_reward']}R)"

    sr_bits = []
    if setup.get("support") is not None:
        sr_bits.append(f"S {setup['support']}")
    if setup.get("resistance") is not None:
        sr_bits.append(f"R {setup['resistance']}")
    sr_line = " | ".join(sr_bits)

    news = setup.get("news")
    news_line = f"📰 {news['headline']}" if news else None

    templates = [_template_classic, _template_setup_first]
    if news_line:
        templates.append(_template_news_led)

    template = random.choice(templates)
    return template(base, direction, arrow, tf, setup, setup_line, sr_line, news_line)


def _template_classic(base, direction, arrow, tf, setup, setup_line, sr_line, news_line):
    lines = [f"${base} {setup['caption']}", ""]
    if news_line:
        lines += [news_line, ""]
    lines += [setup["analysis"]]
    if sr_line:
        lines += [f"{sr_line} · {tf}"]
    lines += ["", setup_line, "", f"{direction} ${base} {arrow}"]
    return "\n".join(lines)


def _template_setup_first(base, direction, arrow, tf, setup, setup_line, sr_line, news_line):
    lines = [f"{direction} ${base} {arrow}", setup_line, ""]
    lines += [f"${base}: {setup['caption']}", setup["analysis"]]
    if sr_line:
        lines += [f"{sr_line} · {tf}"]
    if news_line:
        lines += ["", news_line]
    return "\n".join(lines)


def _template_news_led(base, direction, arrow, tf, setup, setup_line, sr_line, news_line):
    lines = [news_line, "", f"${base} {setup['caption']}", setup["analysis"]]
    if sr_line:
        lines += [f"{sr_line} · {tf}"]
    lines += ["", setup_line, "", f"{direction} ${base} {arrow}"]
    return "\n".join(lines)
