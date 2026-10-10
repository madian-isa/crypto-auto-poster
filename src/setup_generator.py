"""
setup_generator.py

Generates concise Binance Square crypto market-analysis posts.

Features:
- Groq AI generation
- Automatic Python fallback when Groq fails
- Technical indicators
- 1H and 4H swing support/resistance
- BTC market context
- Advanced market data when available
- Relevant supplied news
- 25 LONG title templates
- 25 SHORT title templates
- Deterministic title rotation
- No hashtags in published posts
- No emojis
- Exactly 3 $COIN mentions in the final post
- Strict 1:2 RR
- Minimum 3.5% SL distance
- ATR is NOT used for fallback calculations
- Does not place trades
"""

import json
import re
from datetime import datetime, timezone

from groq import Groq

from src import bot_config as cfg


# =========================================================
# TITLE LIBRARY
# =========================================================

LONG_TITLES = [
    "Technical Signals Turn Positive as Market Momentum Builds",
    "Bullish Momentum Is Building: Can $XXX Continue Its Breakout?",
    "$XXX Buying Pressure Rises as Bulls Test Key Resistance",
    "Strong Accumulation Detected: $XXX Prepares for Next Wave Up",
    "Major Breakout Signals Emerge on $XXX Higher Timeframes",
    "Key Support Holds Firm: $XXX Bullish Continuation Setup Active",
    "$XXX Liquidation Squeeze: Bears Trapped Near Critical Resistance",
    "Trend Reversal Confirmed for $XXX as Volume Spikes Upward",
    "$XXX Holds Moving Average Support: High Probability Long Setup",
    "Bullish Divergence Flashed on $XXX Daily Chart Structure",
    "$XXX Breaks Out of Falling Wedge Pattern: Targets Set Higher",
    "Buyers Defend Key Demand Zone: $XXX Ready for Extension",
    "On-Chain Metrics Confirm Strong Whale Accumulation on $XXX",
    "$XXX Higher Low Structure Confirmed: Long Entry Level Reached",
    "Smart Money Flow Increases into $XXX Ahead of Catalysts",
    "$XXX Reclaims Key Resistance Level: Flip to Support Complete",
    "Bullish Momentum Accelerates as $XXX Liquidity Sweep Completes",
    "$XXX Volume Expansion Signals High Conviction Upward Move",
    "Golden Cross Formation Confirmed on $XXX 4-Hour Timeframe",
    "$XXX Breakout Confirmation: Bulls Target Next Supply Zone",
    "High R-Multiple Long Trade Setup Forming on $XXX",
    "$XXX Outperformance Signal: Buying Momentum Beats Broader Market",
    "Critical Resistance Test: $XXX Preparing to Surge Higher",
    "Spot Inflows Surge for $XXX as Futures Open Interest Rises",
    "$XXX Prepares for Parabolic Phase: Key Technical Trigger Met",
]


SHORT_TITLES = [
    "$XXX Resistance Test Fails: Bearish Momentum Building Fast",
    "Technical Signals Turn Negative as $XXX Selling Pressure Rises",
    "$XXX Rejection at Key Supply Zone: Short Setup Activated",
    "Bearish Divergence Spotted on $XXX: Downside Targets Ahead",
    "$XXX Breaks Below Critical Support: Further Drop Expected",
    "Smart Money Distribution Visible on $XXX On-Chain Data",
    "$XXX Fakeout Confirmed: Bulls Trapped at Local Highs",
    "High Volume Selling Sweep Breaks $XXX Market Structure",
    "$XXX Lower High Pattern Confirmed: Short Target in View",
    "Moving Average Death Cross Signals Downward Trend for $XXX",
    "$XXX Loses Key Demand Zone: Next Support Level Unprotected",
    "Bearish Continuation Pattern Confirmed on $XXX Chart Structure",
    "$XXX Derivative Data Shows Heavy Long Liquidations Incoming",
    "Strong Rejection at Trendline Resistance: $XXX Short Entry",
    "$XXX Volume Decreases on Rally: Weak Buyers Exposed",
    "$XXX Prepares for Breakdown: Downside Risk Escalates",
    "Bears Retake Control as $XXX Fails to Hold Moving Averages",
    "$XXX Open Interest Drops Rapidly: Long Squeeze Underway",
    "Major Support Breakdown Confirmed on $XXX Higher Timeframes",
    "$XXX Distribution Phase Ends: Downside Target Zone Set",
    "High Conviction Short Opportunity as $XXX Tests Supply Wall",
    "$XXX Fails Resistance Retest: Bearish Extension Imminent",
    "Overbought Indicators Signal Impending Correction for $XXX",
    "$XXX Breaks Ascending Support Line: Bearish Momentum Surge",
    "Panic Selling Risk Increases as $XXX Tests Critical Floor",
]


# =========================================================
# SYSTEM PROMPT
# =========================================================

SYSTEM_PROMPT = """
You are a professional crypto market analyst writing concise,
natural Binance Square educational market-analysis posts.

The writing must feel human, natural and varied.

IMPORTANT RULES:
- Do not tell readers to invest.
- Do not promise profit.
- Do not fabricate news.
- Do not fabricate market data.
- Use ONLY the supplied data.
- If information is missing, do not invent it.
- Keep the technical analysis.
- Keep relevant supplied news when available.
- Keep useful BTC/broader-market context when available.
- Do NOT generate or include hashtags.
- Do NOT use emojis.
- Do NOT use NFA or DYOR.
- Do not use guaranteed-profit language.
- Do not make the post sound repetitive or AI-generated.

TIMEFRAME RULE:
- Identify swing high and swing low structures using 1H and 4H market structure.
- Focus on key major swing levels rather than tiny micro-ranges.
- Always aim for clean wide swing trade setups.
- Do NOT output micro-scalp setups or extremely narrow SL/TP ranges.

TITLE:
A title will be selected from the supplied title library.
Do not invent a different title.

NEWS:
Only use news supplied in the input.
If no relevant news is supplied, news_line must be empty.

TECHNICAL ANALYSIS:
Use the strongest available technical information.
Mention EMA, SMA, MACD, RSI, Stochastic, volume,
orderbook or advanced data only when supplied.
Write an original, easy-to-follow take of 50-60 words.
Explain the strongest supporting signals, one relevant
counter-signal or risk when available, and what level or
confirmation would matter next. Use short sentences and
plain language. Never claim the bot entered a real trade.

MARKET CONTEXT:
BTC and broader market information should be used only
as context and only when supplied.
Keep the complete post readable in about 30 seconds:
avoid repetition, long lists, and unnecessary jargon.

Return JSON only.
"""


# =========================================================
# GROQ CLIENT
# =========================================================

def _get_client():
    if not cfg.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is missing.")

    return Groq(api_key=cfg.GROQ_API_KEY)


# Backup models used when the main model hits its limit (429), returns
# an empty/invalid answer, or does not exist on this account.
# The bot checks which models your Groq account really has and only
# tries those, in this order (then any other available text model).
GROQ_BACKUP_MODELS = [
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-20b",
]

_NON_CHAT_MARKERS = (
    "whisper", "guard", "tts", "orpheus", "playai",
    "compound", "safeguard", "embed",
)


def _available_backup_models(client, primary):
    try:
        ids = [m.id for m in client.models.list().data]
    except Exception as err:
        print(f"[setup_generator] could not list Groq models: {str(err)[:80]}")
        return [m for m in GROQ_BACKUP_MODELS if m != primary]
    chat_ids = [
        i for i in ids
        if i != primary and not any(k in i.lower() for k in _NON_CHAT_MARKERS)
    ]
    preferred = [m for m in GROQ_BACKUP_MODELS if m in chat_ids]
    others = [m for m in chat_ids if m not in preferred]
    return (preferred + others)[:5]


def _usable_response(response):
    """Return True when the response holds non-empty, parseable JSON."""
    if not response.choices:
        return False
    message = response.choices[0].message
    text = (message.content or "")
    if "</think>" in text:
        text = text.split("</think>", 1)[1]
        try:
            message.content = text
        except Exception:
            pass
    text = text.strip()
    if not text:
        return False
    try:
        _parse_ai_response(text)
        return True
    except Exception:
        return False


def _chat_with_fallback(client, messages, temperature):
    primary = cfg.GROQ_MODEL
    models = [primary]
    backups_loaded = False
    last_err = RuntimeError("AI returned an empty response.")
    index = 0
    while index < len(models):
        model = models[index]
        index += 1
        try:
            kwargs = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
            }
            if model != primary:
                # Reasoning models can spend every token on "thinking" and
                # return an empty answer. Keep reasoning minimal and leave
                # enough room for the final JSON.
                kwargs["max_completion_tokens"] = 2000
                if "qwen" in model.lower():
                    kwargs["extra_body"] = {"reasoning_effort": "none"}
                elif "gpt-oss" in model.lower():
                    kwargs["extra_body"] = {"reasoning_effort": "low"}
            response = client.chat.completions.create(**kwargs)
            if _usable_response(response):
                if model != primary:
                    print(f"[setup_generator] using backup model {model}")
                return response
            print(f"[setup_generator] {model} gave empty/invalid output; trying next model...")
            last_err = RuntimeError("AI returned an empty response.")
        except Exception as err:
            last_err = err
            print(f"[setup_generator] {model} unavailable ({str(err)[:60]}); trying next model...")
        if not backups_loaded and index >= len(models):
            backups_loaded = True
            models.extend(_available_backup_models(client, primary))
    raise last_err


# =========================================================
# NUMBER HELPERS
# =========================================================

def _safe_float(value):
    try:
        if value is None:
            return None

        if isinstance(value, bool):
            return None

        number = float(value)

        if number != number:
            return None

        return number

    except Exception:
        return None


def _format_price(value):
    number = _safe_float(value)

    if number is None:
        return "N/A"

    if number >= 1000:
        return f"{number:.2f}"

    if number >= 100:
        return f"{number:.3f}"

    if number >= 1:
        return f"{number:.4f}"

    if number >= 0.01:
        return f"{number:.5f}"

    return (
        f"{number:.8f}"
        .rstrip("0")
        .rstrip(".")
    )


def _clean_text(value, max_length=500):
    if value is None:
        return ""

    text = str(value)

    text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    return text[:max_length]


def _limit_words(value, max_words):
    text = _clean_text(value, max_length=2000)
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]).rstrip(" ,;:-")


def _strip_opposite_direction_claims(text, direction):
    text = _clean_text(text, max_length=2000)
    if not text:
        return ""

    direction = str(direction or "").upper().strip()
    if direction == "LONG":
        opposite_pattern = (
            r"(?i)\b(?:short(?:-term)?|shorts|sell(?:ing|s)?|seller(?:s)?|"
            r"bearish|downtrend|downside|weakness|negative momentum|"
            r"selling pressure|lower lows|lower highs)\b|"
            r"\b(?:RSI|stochastic(?:\s+K)?|MACD(?:\s+histogram)?)\b"
            r".{0,35}\b(?:below|under|negative|bearish)\b|"
            r"\b(?:below|under|break(?:s|ing)? below)\s+(?:the\s+)?"
            r"(?:EMA\d{1,3}|support|key support)\b"
        )
        fallback = "Risk remains limited while buyers hold the key support zone."
    elif direction == "SHORT":
        opposite_pattern = (
            r"(?i)\b(?:long(?:-term)?|longs|buy(?:ing|s)?|buyer(?:s)?|"
            r"bullish|uptrend|upside|positive momentum|buying pressure|"
            r"strong buyers|bounce|rebound|recovery|reversal|"
            r"higher highs|higher lows)\b|"
            r"\b(?:RSI|stochastic(?:\s+K)?|MACD(?:\s+histogram)?)\b"
            r".{0,35}\b(?:above|over|positive|bullish)\b|"
            r"\b(?:above|over|break(?:s|ing)? above|hold(?:s|ing)? above)\s+"
            r"(?:the\s+)?(?:EMA\d{1,3}|resistance|key resistance)\b"
        )
        fallback = "Risk remains limited while sellers hold the key resistance zone."
    else:
        return text

    sentences = re.split(r"(?<=[.!?])\s+", text)
    kept = []
    for sentence in sentences:
        if re.search(opposite_pattern, sentence):
            continue
        kept.append(sentence.strip())

    filtered = " ".join(part for part in kept if part)
    if not filtered:
        return fallback

    return _clean_text(filtered, max_length=2000)


def _ensure_analysis_length(value, direction=None):
    text = _strip_opposite_direction_claims(_limit_words(value, 60), direction)
    if direction == "LONG":
        supplements = (
            "LONG bias targets continuation toward resistance, with support as the invalidation level.",
            "The stop loss defines the risk level for this setup.",
            "The listed entry and target provide the trade plan.",
        )
    elif direction == "SHORT":
        supplements = (
            "SHORT bias targets continuation toward support, with resistance as the invalidation level.",
            "The stop loss defines the risk level for this setup.",
            "The listed entry and target provide the trade plan.",
        )
    else:
        supplements = (
            "The supplied signals favor the selected direction toward the stated target.",
            "The key level invalidates the setup; the stop loss defines the risk level.",
            "Watch the listed support and resistance for the next price milestone.",
            "The listed entry and target provide the trade plan.",
        )
    for sentence in supplements:
        if len(text.split()) >= 50:
            break
        text = f"{text} {sentence}".strip()
    return _limit_words(_strip_opposite_direction_claims(text, direction), 60)


# =========================================================
# COIN HELPERS
# =========================================================

def _coin_name(symbol):
    symbol = str(symbol or "").upper()

    if symbol.endswith("USDT"):
        return symbol[:-4]

    if symbol.endswith("USDC"):
        return symbol[:-4]

    if symbol.endswith("BUSD"):
        return symbol[:-4]

    return symbol


def _replace_coin_placeholder(title, coin):
    return str(title).replace(
        "$XXX",
        f"${coin}",
    )


# =========================================================
# TITLE ROTATION
# =========================================================

def _select_title(direction, coin):

    if direction == "LONG":
        titles = LONG_TITLES
    else:
        titles = SHORT_TITLES

    today = datetime.now(
        timezone.utc
    ).strftime("%Y-%m-%d")

    seed_text = (
        f"{coin}-{today}-{direction}"
    )

    seed_value = sum(
        ord(char)
        for char in seed_text
    )

    index = (
        seed_value % len(titles)
    )

    return _replace_coin_placeholder(
        titles[index],
        coin,
    )


# =========================================================
# NEWS
# =========================================================

def _summarize_news(news):

    if not news:
        return ""

    if isinstance(news, str):
        return _clean_text(
            news,
            600,
        )

    if isinstance(news, dict):

        title = news.get(
            "title",
            "",
        )

        summary = news.get(
            "summary",
            "",
        )

        if title and summary:
            return _clean_text(
                f"{title} — {summary}",
                600,
            )

        return _clean_text(
            title or summary,
            600,
        )

    if isinstance(news, list):

        items = []

        for item in news[:3]:

            if isinstance(item, str):

                items.append(
                    _clean_text(
                        item,
                        250,
                    )
                )

            elif isinstance(item, dict):

                title = item.get(
                    "title",
                    "",
                )

                summary = item.get(
                    "summary",
                    "",
                )

                text = title

                if summary:
                    text += (
                        f" — {summary}"
                    )

                if text:
                    items.append(
                        _clean_text(
                            text,
                            250,
                        )
                    )

        return " | ".join(items)

    return ""


# =========================================================
# INDICATOR SUMMARY
# =========================================================

def _build_indicator_summary(indicators):

    if not indicators:
        return {}

    keys = [
        "price",
        "current_price",
        "rsi",
        "rsi14",
        "macd_line",
        "stochastic_k",
        "ema9",
        "ema21",
        "ema50",
        "ema200",
        "sma50",
        "sma200",
        "macd",
        "macd_signal",
        "bollinger_upper",
        "bollinger_lower",
        "stochastic",
        "adx",
        "obv",
        "volume",
        "volume_change",
        "high_24h",
        "low_24h",
        "support",
        "resistance",
    ]

    result = {}

    for key in keys:

        if key in indicators:
            result[key] = indicators[key]

    return result


# =========================================================
# ADVANCED DATA SUMMARY
# =========================================================

def _build_advanced_summary(advanced):

    if not advanced:
        return {}

    result = {}

    sr = advanced.get(
        "multi_timeframe_sr"
    )

    if sr:

        one_hour = sr.get("1h")
        four_hour = sr.get("4h")

        if one_hour:
            result[
                "1h_support_resistance"
            ] = one_hour

        if four_hour:
            result[
                "4h_support_resistance"
            ] = four_hour

    btc = advanced.get(
        "btc_context"
    )

    if btc:
        result[
            "btc_context"
        ] = btc

    oi = advanced.get(
        "open_interest"
    )

    if oi is not None:
        result[
            "open_interest"
        ] = oi

    oi_change = advanced.get(
        "oi_change_1h_pct"
    )

    if oi_change is not None:
        result[
            "oi_change_1h_pct"
        ] = oi_change

    funding = advanced.get(
        "funding_rate"
    )

    if funding is not None:
        result[
            "funding_rate"
        ] = funding

    long_short = advanced.get(
        "long_short_ratio"
    )

    if long_short:
        result[
            "long_short_ratio"
        ] = long_short

    liquidations = advanced.get(
        "liquidations"
    )

    if liquidations:
        result[
            "liquidations"
        ] = liquidations

    orderbook = advanced.get(
        "orderbook"
    )

    if orderbook:
        result[
            "orderbook"
        ] = orderbook

    return result


# =========================================================
# MAJOR SUPPORT / RESISTANCE
# =========================================================

def _select_major_levels(
    indicators,
    advanced_market_data,
):

    advanced_market_data = (
        advanced_market_data or {}
    )

    sr = advanced_market_data.get(
        "multi_timeframe_sr",
        {}
    ) or {}

    one_hour = sr.get(
        "1h",
        {}
    ) or {}

    four_hour = sr.get(
        "4h",
        {}
    ) or {}

    # Prefer 4H for major swing structure.
    support = (
        four_hour.get("support")
        if four_hour.get("support") is not None
        else one_hour.get("support")
    )

    resistance = (
        four_hour.get("resistance")
        if four_hour.get("resistance") is not None
        else one_hour.get("resistance")
    )

    if support is None and indicators:
        support = indicators.get(
            "support"
        )

    if resistance is None and indicators:
        resistance = indicators.get(
            "resistance"
        )

    return {
        "support": support,
        "resistance": resistance,
    }


# =========================================================
# CURRENT PRICE
# =========================================================

def _get_current_price(indicators):

    if not indicators:
        return None

    for key in (
        "current_price",
        "price",
    ):

        value = _safe_float(
            indicators.get(key)
        )

        if value is not None and value > 0:
            return value

    return None


# =========================================================
# FALLBACK: DIRECTION
# =========================================================

def _indicator_number(indicators, *keys):
    indicators = indicators or {}
    for key in keys:
        value = indicators.get(key)
        if isinstance(value, dict):
            for nested_key in (key, key.lower(), key.upper(), "value", "line", "MACD", "signal", "k"):
                if nested_key in value:
                    number = _safe_float(value.get(nested_key))
                    if number is not None:
                        return number
        else:
            number = _safe_float(value)
            if number is not None:
                return number
    return None


def _get_macd_values(indicators):
    indicators = indicators or {}
    macd_data = indicators.get("macd")
    line = _indicator_number(indicators, "macd_line")
    signal = _indicator_number(indicators, "macd_signal")
    if isinstance(macd_data, dict):
        if line is None:
            line = _safe_float(macd_data.get("MACD"))
        if signal is None:
            signal = _safe_float(macd_data.get("signal"))
    return line, signal


def _get_stochastic_k(indicators):
    value = _indicator_number(indicators or {}, "stochastic_k")
    if value is not None:
        return value
    stochastic = (indicators or {}).get("stochastic")
    if isinstance(stochastic, dict):
        return _safe_float(stochastic.get("k"))
    return _safe_float(stochastic)


def _signal_quality_ok(indicators, direction):
    """Reject setups when the primary indicators disagree."""
    direction = str(direction or "").upper()
    if direction not in ("LONG", "SHORT"):
        return False

    price = _get_current_price(indicators)
    rsi = _indicator_number(indicators, "rsi", "rsi14")
    ema21 = _indicator_number(indicators, "ema21")
    ema50 = _indicator_number(indicators, "ema50")
    ema200 = _indicator_number(indicators, "ema200")
    macd_line, macd_signal = _get_macd_values(indicators)
    stochastic_k = _get_stochastic_k(indicators)

    required = (price, rsi, ema21, ema50, macd_line, macd_signal)
    if any(value is None for value in required):
        return False

    if direction == "LONG":
        if not (52 <= rsi <= 72):
            return False
        if not (price > ema21 > ema50):
            return False
        if ema200 is not None and price <= ema200:
            return False
        if macd_line <= macd_signal:
            return False
        if stochastic_k is not None and stochastic_k < 55:
            return False
        return True

    if not (28 <= rsi <= 48):
        return False
    if not (price < ema21 < ema50):
        return False
    if ema200 is not None and price >= ema200:
        return False
    if macd_line >= macd_signal:
        return False
    if stochastic_k is not None and stochastic_k > 45:
        return False
    return True


def _fallback_direction(
    indicators,
    advanced_market_data,
):
    indicators = indicators or {}
    advanced = advanced_market_data or {}
    score = 0
    evidence = 0

    price = _get_current_price(indicators)
    rsi = _indicator_number(indicators, "rsi", "rsi14")
    ema21 = _indicator_number(indicators, "ema21")
    ema50 = _indicator_number(indicators, "ema50")
    ema200 = _indicator_number(indicators, "ema200")

    if rsi is not None:
        evidence += 1
        score += 2 if rsi >= 55 else -2 if rsi <= 45 else 0
    if price is not None and ema21 is not None:
        evidence += 1
        score += 1 if price > ema21 else -1 if price < ema21 else 0
    if ema21 is not None and ema50 is not None:
        evidence += 1
        score += 1 if ema21 > ema50 else -1 if ema21 < ema50 else 0
    if price is not None and ema200 is not None:
        evidence += 1
        score += 1 if price > ema200 else -1 if price < ema200 else 0

    macd_line, macd_signal = _get_macd_values(indicators)
    if macd_line is not None and macd_signal is not None:
        evidence += 1
        score += 2 if macd_line > macd_signal else -2 if macd_line < macd_signal else 0

    stochastic_k = _get_stochastic_k(indicators)
    if stochastic_k is not None:
        evidence += 1
        score += 1 if stochastic_k >= 60 else -1 if stochastic_k <= 40 else 0

    funding = _safe_float(advanced.get("funding_rate"))
    if funding is not None:
        score += -1 if funding > 0.01 else 1 if funding < -0.01 else 0

    # Relaxed: when AI is unavailable, always pick the side the
    # indicators lean toward instead of rejecting the setup.
    if evidence < 3:
        return None
    if score > 0:
        return "LONG"
    if score < 0:
        return "SHORT"
    # Tie-break: MACD first, then price vs EMA21.
    if macd_line is not None and macd_signal is not None and macd_line != macd_signal:
        return "LONG" if macd_line > macd_signal else "SHORT"
    if price is not None and ema21 is not None and price != ema21:
        return "LONG" if price > ema21 else "SHORT"
    return None

def _fallback_entry(
    indicators,
    levels,
    direction,
):
    price = _get_current_price(indicators)
    if price is None or price <= 0:
        return None, None
    zone = 0.0025
    return (
        round(price * (1 - zone), 8),
        round(price * (1 + zone), 8),
    )

def _fallback_risk_levels(
    entry_low,
    entry_high,
    direction,
    support,
    resistance,
):
    minimum = 0.035
    default = 0.04
    maximum = 0.06
    try:
        low = float(entry_low)
        high = float(entry_high if entry_high is not None else entry_low)
    except (TypeError, ValueError):
        return None, None
    if low <= 0 or high <= 0:
        return None, None
    low, high = sorted((low, high))
    entry = (low + high) / 2.0
    if direction == "LONG":
        stop = entry * (1 - default)
        if support is not None:
            candidate = _safe_float(support)
            if candidate is not None and 0 < candidate < entry:
                candidate *= 0.995
                distance = (entry - candidate) / entry
                if minimum <= distance <= maximum:
                    stop = candidate
        stop = max(entry * (1 - maximum), min(stop, entry * (1 - minimum)))
        target = entry + ((entry - stop) * 2.0)
    else:
        stop = entry * (1 + default)
        if resistance is not None:
            candidate = _safe_float(resistance)
            if candidate is not None and candidate > entry:
                candidate *= 1.005
                distance = (candidate - entry) / entry
                if minimum <= distance <= maximum:
                    stop = candidate
        stop = max(entry * (1 + minimum), min(stop, entry * (1 + maximum)))
        target = entry - ((stop - entry) * 2.0)
    if target <= 0:
        return None, None
    return round(stop, 8), round(target, 8)

def _fallback_technical_text(
    coin,
    indicators,
    direction,
):
    indicators = indicators or {}

    parts = []
    direction = str(direction or "").upper().strip()

    rsi = _indicator_number(
        indicators,
        "rsi",
        "rsi14",
    )

    if rsi is not None:
        if direction == "LONG":
            rsi_read = (
                "RSI is {:.1f}, showing bullish momentum without "
                "being deeply overbought"
            ).format(rsi)
        else:
            rsi_read = (
                "RSI is {:.1f}, showing weakening momentum without "
                "being deeply oversold"
            ).format(rsi)
        parts.append(rsi_read)

    price = _get_current_price(
        indicators
    )

    ema21 = _safe_float(
        indicators.get("ema21")
    )

    if (
        price is not None
        and ema21 is not None
    ):

        if direction == "LONG" and price > ema21:
            parts.append(
                "price is holding above the 21 EMA, supporting the bullish bias"
            )
        elif direction == "SHORT" and price < ema21:
            parts.append(
                "price is trading below the 21 EMA, supporting the bearish bias"
            )
        elif price > ema21:
            parts.append(
                "price is above the 21 EMA, but this needs confirmation"
            )
        else:
            parts.append(
                "price is below the 21 EMA, so recovery strength remains limited"
            )

    macd, macd_signal = _get_macd_values(indicators)

    if (
        macd is not None
        and macd_signal is not None
    ):

        if direction == "LONG" and macd > macd_signal:
            parts.append(
                "MACD is above its signal line, confirming positive momentum"
            )
        elif direction == "SHORT" and macd < macd_signal:
            parts.append(
                "MACD is below its signal line, confirming negative momentum"
            )
        elif macd > macd_signal:
            parts.append(
                "MACD is above its signal line, although the move still needs follow-through"
            )
        elif macd < macd_signal:
            parts.append(
                "MACD is below its signal line, so upside recovery remains weak"
            )

    volume_change = _safe_float(
        indicators.get(
            "volume_change"
        )
    )

    if volume_change is not None:

        volume_word = "expanding" if volume_change > 0 else "contracting"
        parts.append(
            f"volume is {volume_word} by {abs(volume_change):.1f}%"
        )

    ema50 = _safe_float(indicators.get("ema50"))
    ema200 = _safe_float(indicators.get("ema200"))
    if price is not None and ema50 is not None:
        if direction == "LONG" and price > ema50:
            parts.append("price is above the 50 EMA, keeping the short-term structure constructive")
        elif direction == "SHORT" and price < ema50:
            parts.append("price is below the 50 EMA, keeping the short-term structure weak")
    if price is not None and ema200 is not None:
        if direction == "LONG" and price > ema200:
            parts.append("price is above the 200 EMA, supporting the broader bullish trend")
        elif direction == "SHORT" and price < ema200:
            parts.append("price is below the 200 EMA, supporting the broader bearish trend")

    adx = _safe_float(indicators.get("adx"))
    if adx is not None:
        parts.append(
            f"ADX is {adx:.1f}, indicating "
            + ("a developing trend" if adx >= 20 else "limited trend strength")
        )

    stochastic = _get_stochastic_k(indicators)
    if stochastic is not None:
        if direction == "LONG":
            parts.append(f"Stochastic is {stochastic:.1f}, leaving room for upside continuation")
        else:
            parts.append(f"Stochastic is {stochastic:.1f}, leaving room for further downside")

    if not parts:
        analysis = (
            f"${coin} available price structure favors the {direction.lower()} "
            f"setup. The listed target is the objective, while the stop loss "
            "defines the risk and the level that invalidates this view. "
            "Watch support and resistance for the next price milestone."
        )
        return _limit_words(analysis, 60)

    selected = parts[:5]
    if len(selected) == 1:
        evidence = selected[0]
    elif len(selected) == 2:
        evidence = f"{selected[0]}, while {selected[1]}"
    else:
        evidence = ", ".join(selected[:-1]) + f", and {selected[-1]}"

    if direction == "LONG":
        conclusion = (
            "Together, these signals favor LONG continuation toward the stated target. "
            "Support is the key level; a break below it invalidates this view."
        )
    else:
        conclusion = (
            "Together, these signals favor SHORT continuation toward the stated target. "
            "Resistance is the key level; a break above it invalidates this view."
        )

    analysis = (
        f"${coin} fallback technical analysis: {evidence}. "
        f"{conclusion}"
    )
    if len(analysis.split()) < 50:
        analysis += (
            " The listed entry and target provide the trade plan. "
            "The stop loss defines the risk level and the point that invalidates "
            "the directional view."
        )
    return _limit_words(analysis, 60)


# =========================================================
# FALLBACK: MARKET CONTEXT
# =========================================================

def _fallback_market_context(
    advanced_market_data,
):
    advanced = (
        advanced_market_data or {}
    )

    btc = advanced.get(
        "btc_context"
    )

    if not btc:
        return ""

    if isinstance(btc, str):

        return _clean_text(
            btc,
            300,
        )

    if isinstance(btc, dict):

        pieces = []

        for key in (
            "price",
            "change_24h",
            "trend",
            "rsi",
            "market_structure",
        ):

            if key in btc:

                value = btc.get(key)

                if value is not None:
                    pieces.append(
                        f"{key}: {value}"
                    )

        if pieces:
            return (
                "BTC context: "
                + ", ".join(pieces[:4])
                + "."
            )

    return ""


# =========================================================
# FALLBACK: NEWS
# =========================================================

def _fallback_news_line(news):

    if not news:
        return ""

    if isinstance(news, str):

        return _clean_text(
            news,
            280,
        )

    if isinstance(news, dict):

        title = news.get(
            "title",
            "",
        )

        if title:
            return _clean_text(
                title,
                280,
            )

        summary = news.get(
            "summary",
            "",
        )

        return _clean_text(
            summary,
            280,
        )

    if isinstance(news, list):

        for item in news[:3]:

            if isinstance(item, str):
                return _clean_text(
                    item,
                    280,
                )

            if isinstance(item, dict):

                title = item.get(
                    "title",
                    "",
                )

                if title:
                    return _clean_text(
                        title,
                        280,
                    )

    return ""


# =========================================================
# PYTHON FALLBACK SETUP
# =========================================================

def _python_fallback_setup(
    symbol,
    indicators,
    news=None,
    market_context=None,
    advanced_market_data=None,
):
    coin = _coin_name(symbol)
    indicators = indicators or {}
    advanced_market_data = advanced_market_data or {}
    direction = _fallback_direction(indicators, advanced_market_data)
    if direction is None:
        raise RuntimeError(f"Technical structure is unclear for ${coin}; setup rejected.")
    levels = _select_major_levels(indicators, advanced_market_data)
    entry_low, entry_high = _fallback_entry(indicators, levels, direction)
    if entry_low is None or entry_high is None:
        raise RuntimeError(f"Could not create a valid entry for ${coin}.")
    stop_loss, take_profit = _fallback_risk_levels(
        entry_low, entry_high, direction,
        levels.get("support"), levels.get("resistance"),
    )
    if stop_loss is None or take_profit is None:
        raise RuntimeError(f"Could not create valid risk levels for ${coin}.")
    btc_context = _fallback_market_context(advanced_market_data)
    if isinstance(market_context, str):
        extra = _clean_text(market_context, 250)
        if extra:
            btc_context = f"{btc_context} {extra}".strip()
    return {
        "symbol": symbol,
        "direction": direction,
        "title": _select_title(direction, coin),
        "entry_low": entry_low,
        "entry_high": entry_high,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "support": levels.get("support"),
        "resistance": levels.get("resistance"),
        "news_line": _fallback_news_line(news),
        "technical_analysis": _fallback_technical_text(coin, indicators, direction),
        "market_context": btc_context,
        "rr": 2,
    }

def _parse_ai_response(content):

    if not content:
        raise RuntimeError(
            "AI returned an empty response."
        )

    content = str(content).strip()

    content = re.sub(
        r"^```json\s*",
        "",
        content,
        flags=re.IGNORECASE,
    )

    content = re.sub(
        r"^```\s*",
        "",
        content,
    )

    content = re.sub(
        r"\s*```$",
        "",
        content,
    )

    content = content.strip()

    if not content:
        raise RuntimeError(
            "AI returned an empty response."
        )

    try:

        setup = json.loads(
            content
        )

    except Exception as err:

        raise RuntimeError(
            "AI returned invalid JSON: "
            f"{err}\nResponse: {content}"
        )

    if not isinstance(
        setup,
        dict,
    ):
        raise RuntimeError(
            "AI JSON response is not an object."
        )

    return setup


# =========================================================
# GENERATE SETUP
# =========================================================

def generate_setup(
    symbol,
    indicators,
    news=None,
    market_context=None,
    advanced_market_data=None,
):
    coin = _coin_name(
        symbol
    )

    indicator_summary = (
        _build_indicator_summary(
            indicators
        )
    )

    advanced_summary = (
        _build_advanced_summary(
            advanced_market_data
        )
    )

    major_levels = _select_major_levels(
        indicators,
        advanced_market_data,
    )

    news_summary = _summarize_news(
        news
    )

    market_summary = (
        market_context
        if market_context
        else {}
    )

    prompt_data = {
        "symbol": symbol,
        "technical_indicators":
            indicator_summary,
        "major_levels":
            major_levels,
        "advanced_market_data":
            advanced_summary,
        "market_context":
            market_summary,
        "relevant_news":
            news_summary,
    }

    user_prompt = f"""
Create one short crypto market-analysis setup
for {symbol}.

Use ONLY the data below.

DATA:

{json.dumps(
    prompt_data,
    indent=2,
    default=str,
)}

TASK:

1. Decide whether the technical structure is more suitable
   for LONG or SHORT.

2. Create a realistic entry range.

3. Set Stop Loss and Take Profit:
   - Use 1H/4H swing structure.
   - Stop loss must be at least 3.5% away from entry.
   - Prefer approximately 4% minimum distance when needed.
   - Take Profit must be exactly 2R.
   - Never create a micro-scalp setup.

4. Identify major 1H and 4H support/resistance.

5. Use only the strongest 3-5 supplied technical signals.

6. Use OI, funding, long/short ratio, liquidation or
   orderbook data only if supplied.

7. Use BTC only as broader context.

8. If relevant news is supplied, use only that news.
   If no news is supplied, news_line must be empty.

9. Do not invent a title. A title will be replaced by code.

10. Write technical_analysis as a clear 50-60 word original
    take. State clearly which direction the supplied signals
    favor and the expected path toward the listed target.
    Include the key reasons, the main risk/invalidation level,
    and what price level to watch next. Use direct, confident
    wording; avoid vague disclaimer phrases such as "not a
    verified trade" or "promise of direction". Never guarantee
    profit or claim the target is certain.
11. Keep the entire post short enough to read in about
    30 seconds. Use plain language and avoid repetition.
12. Do not claim that a real position was opened or filled.

Return JSON only:

{{
  "direction": "LONG or SHORT",
  "title": "",
  "entry_low": 0,
  "entry_high": 0,
  "stop_loss": null,
  "take_profit": null,
  "support": 0,
  "resistance": 0,
  "news_line": "",
  "technical_analysis": "",
  "market_context": ""
}}
"""

    try:

        if not cfg.GROQ_API_KEY:

            raise RuntimeError(
                "GROQ_API_KEY is missing."
            )

        print(
            f"[setup_generator] "
            f"Generating setup for ${coin} via Groq..."
        )

        client = _get_client()

        response = _chat_with_fallback(
            client,
            [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            0.75,
        )

        if not response.choices:

            raise RuntimeError(
                "AI returned no choices."
            )

        content = (
            response.choices[0]
            .message.content
        )

        setup = _parse_ai_response(
            content
        )

    except Exception as err:

        print(
            f"[setup_generator] "
            f"Groq failed for ${coin}: {err}"
        )

        return _python_fallback_setup(
            symbol=symbol,
            indicators=indicators,
            news=news,
            market_context=market_context,
            advanced_market_data=advanced_market_data,
        )

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
        raise RuntimeError(
            f"Groq returned an invalid direction for ${coin}; setup rejected."
        )

    if direction is None:
        raise RuntimeError(
            f"Groq did not provide a direction for ${coin}; setup rejected."
        )

    if not _signal_quality_ok(indicators, direction):
        print(
            f"[setup_generator] "
            f"{direction} setup for ${coin} conflicts with indicators; "
            f"posting AI signal anyway."
        )
        setup["indicator_conflict"] = True

    setup["direction"] = direction

    entry_low = _safe_float(
        setup.get(
            "entry_low"
        )
    )

    entry_high = _safe_float(
        setup.get(
            "entry_high"
        )
    )

    if entry_low is None:

        entry_low = _get_current_price(
            indicators
        )

    if entry_high is None:

        entry_high = entry_low

    if (
        entry_low is not None
        and entry_high is not None
        and entry_low > entry_high
    ):

        entry_low, entry_high = (
            entry_high,
            entry_low,
        )

    setup["entry_low"] = entry_low
    setup["entry_high"] = entry_high

    ai_support = _safe_float(
        setup.get(
            "support"
        )
    )

    ai_resistance = _safe_float(
        setup.get(
            "resistance"
        )
    )

    if ai_support is None:

        ai_support = _safe_float(
            major_levels.get(
                "support"
            )
        )

    if ai_resistance is None:

        ai_resistance = _safe_float(
            major_levels.get(
                "resistance"
            )
        )

    setup["support"] = ai_support
    setup["resistance"] = ai_resistance

    ai_stop = _safe_float(
        setup.get(
            "stop_loss"
        )
    )

    ai_target = _safe_float(
        setup.get(
            "take_profit"
        )
    )

    if entry_low is not None and entry_low > 0:

        if entry_high is None or entry_high <= 0:
            entry_high = entry_low

        reference_entry = (entry_low + entry_high) / 2.0

        MIN_SL_PCT = 0.035
        MAX_SL_PCT = 0.06
        DEFAULT_SL_PCT = 0.04

        if ai_stop is not None:
            distance = abs(reference_entry - ai_stop) / reference_entry

            if distance < MIN_SL_PCT:
                # Too tight — fall through to the default below.
                ai_stop = None
            elif distance > MAX_SL_PCT:
                # This is the fix: the AI (or a bad support/resistance
                # value) can suggest a stop way beyond a sane distance —
                # clamp it back to MAX_SL_PCT instead of trusting it
                # outright. Without this, a case like entry ~$0.049 with
                # a suggested stop of $0.0665 (35% away!) sailed straight
                # through the old "minimum only" check.
                if direction == "LONG":
                    ai_stop = round(reference_entry * (1 - MAX_SL_PCT), 8)
                else:
                    ai_stop = round(reference_entry * (1 + MAX_SL_PCT), 8)

        if ai_stop is None:

            if direction == "LONG":
                ai_stop = round(reference_entry * (1 - DEFAULT_SL_PCT), 8)
            else:
                ai_stop = round(reference_entry * (1 + DEFAULT_SL_PCT), 8)

        sl_distance = abs(
            reference_entry - ai_stop
        )

        if direction == "LONG":

            ai_target = round(
                reference_entry
                + (sl_distance * 2.0),
                8,
            )

        else:

            ai_target = round(
                reference_entry
                - (sl_distance * 2.0),
                8,
            )

    else:
        raise RuntimeError(
            f"Groq returned no valid entry for ${coin}; "
            "no fallback after successful AI response."
        )

    setup["stop_loss"] = ai_stop
    setup["take_profit"] = ai_target

    setup["rr"] = 2

    setup["title"] = _select_title(
        direction,
        coin,
    )

    setup["news_line"] = _limit_words(
        setup.get(
            "news_line",
            "",
        ),
        18,
    )

    setup["technical_analysis"] = _ensure_analysis_length(
        setup.get(
            "technical_analysis",
            "",
        ),
        direction,
    )
    setup["technical_analysis"] = _strip_opposite_direction_claims(
        setup["technical_analysis"],
        direction,
    )

    setup["market_context"] = _limit_words(
        setup.get(
            "market_context",
            "",
        ),
        22,
    )

    print(
        f"[setup_generator] "
        f"Groq setup ready for ${coin}."
    )

    return setup


# =========================================================
# FORMAT FINAL BINANCE SQUARE POST
# =========================================================

def format_post_text(setup):
    if not setup:
        return ""

    symbol = setup.get(
        "symbol",
        "",
    )

    coin = _coin_name(
        symbol
    )

    direction = str(
        setup.get(
            "direction",
            "LONG",
        )
    ).upper()

    if direction not in (
        "LONG",
        "SHORT",
    ):
        direction = "LONG"

    entry_low = _format_price(
        setup.get(
            "entry_low"
        )
    )

    entry_high = _format_price(
        setup.get(
            "entry_high"
        )
    )

    stop_loss = _format_price(
        setup.get(
            "stop_loss"
        )
    )

    take_profit = _format_price(
        setup.get(
            "take_profit"
        )
    )

    support = _format_price(
        setup.get(
            "support"
        )
    )

    resistance = _format_price(
        setup.get(
            "resistance"
        )
    )

    technical = _ensure_analysis_length(
        setup.get(
            "technical_analysis",
            "",
        ),
        direction,
    )
    technical = _strip_opposite_direction_claims(technical, direction)

    news_line = _limit_words(setup.get(
        "news_line",
        "",
    ), 18)

    market = _limit_words(setup.get(
        "market_context",
        "",
    ), 22)

    title = setup.get(
        "title",
        "",
    ).strip()

    title = re.sub(
        r"#\w+",
        "",
        title,
    ).strip()

    title = re.sub(
        r"[^\x00-\x7F]+",
        "",
        title,
    ).strip()

    title = re.sub(
        rf"\$?{re.escape(coin)}\s*:\s*",
        "",
        title,
        flags=re.IGNORECASE,
    ).strip()

    title = re.sub(
        rf"^\$?{re.escape(coin)}\s*",
        "",
        title,
        flags=re.IGNORECASE,
    ).strip()
    title = _limit_words(title, 12)

    if not title:
        title = "MARKET MOMENTUM UNDER REVIEW?"

    title_line = (
        f"${coin}: {title}"
    )

    if direction == "LONG":

        direction_line = (
            f"LONG SETUP — {coin}"
        )

        final_line = (
            f"LONG ${coin}"
        )

    else:

        direction_line = (
            f"SHORT SETUP — {coin}"
        )

        final_line = (
            f"SHORT ${coin}"
        )

    if technical:

        technical_line = (
            f"Technical Analysis for "
            f"${coin}: {technical}"
        )

    else:

        technical_line = (
            f"Technical Analysis for "
            f"${coin}: Market structure "
            f"remains the main focus."
        )

    lines = []

    lines.append(
        title_line
    )

    lines.append("")

    lines.append(
        direction_line
    )

    lines.append("")

    lines.append(
        f"Entry: ${entry_low} - ${entry_high}"
    )

    lines.append(
        f"Stop Loss: ${stop_loss}"
    )

    lines.append(
        f"Take Profit: ${take_profit} (2R)"
    )

    lines.append("")

    lines.append(
        f"Key Levels: Support ${support} | "
        f"Resistance ${resistance}"
    )

    lines.append("")

    lines.append(
        technical_line
    )

    if news_line:

        lines.append("")

        lines.append(
            f"NEWS: {news_line}"
        )

    if market:

        lines.append("")

        lines.append(
            f"Market Context: {market}"
        )

    text = "\n".join(
        lines
    ).strip()

    text = re.sub(
        r"(?<!\w)#\w+",
        "",
        text,
    )

    text = re.sub(
        r"[^\x00-\x7F]+",
        "",
        text,
    )

    text = re.sub(
        r"[ \t]+",
        " ",
        text,
    )

    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text,
    ).strip()

    footer = final_line
    available_body_length = max(
        0,
        cfg.CHAR_LIMIT - len(footer) - 2,
    )
    if len(text) + len(footer) + 2 > cfg.CHAR_LIMIT:
        text = text[:available_body_length].rstrip()
        text = text.rstrip("#").rstrip()
    return f"{text}\n\n{footer}".strip()
