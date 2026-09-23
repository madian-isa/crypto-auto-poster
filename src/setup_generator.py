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
- Do NOT generate hashtags.
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

MARKET CONTEXT:
BTC and broader market information should be used only
as context and only when supplied.

Return JSON only.
"""


# =========================================================
# GROQ CLIENT
# =========================================================

def _get_client():
    if not cfg.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is missing.")

    return Groq(api_key=cfg.GROQ_API_KEY)


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

def _fallback_direction(
    indicators,
    advanced_market_data,
):
    """
    Deterministic technical direction.

    This does NOT use random direction.
    Only supplied technical values are used.
    """

    indicators = indicators or {}
    advanced = advanced_market_data or {}

    score = 0

    rsi = _safe_float(
        indicators.get("rsi")
    )

    if rsi is not None:

        if rsi >= 55:
            score += 2

        elif rsi <= 45:
            score -= 2

    price = _get_current_price(
        indicators
    )

    ema21 = _safe_float(
        indicators.get("ema21")
    )

    ema50 = _safe_float(
        indicators.get("ema50")
    )

    ema200 = _safe_float(
        indicators.get("ema200")
    )

    if price is not None and ema21 is not None:

        if price > ema21:
            score += 1
        elif price < ema21:
            score -= 1

    if ema21 is not None and ema50 is not None:

        if ema21 > ema50:
            score += 1
        elif ema21 < ema50:
            score -= 1

    if price is not None and ema200 is not None:

        if price > ema200:
            score += 1
        elif price < ema200:
            score -= 1

    macd = _safe_float(
        indicators.get("macd")
    )

    macd_signal = _safe_float(
        indicators.get("macd_signal")
    )

    if (
        macd is not None
        and macd_signal is not None
    ):

        if macd > macd_signal:
            score += 2

        elif macd < macd_signal:
            score -= 2

    stochastic = _safe_float(
        indicators.get("stochastic")
    )

    if stochastic is not None:

        if stochastic >= 60:
            score += 1

        elif stochastic <= 40:
            score -= 1

    volume_change = _safe_float(
        indicators.get(
            "volume_change"
        )
    )

    if volume_change is not None:

        if volume_change > 10:
            if score > 0:
                score += 1
            elif score < 0:
                score -= 1

    oi_change = _safe_float(
        advanced.get(
            "oi_change_1h_pct"
        )
    )

    if oi_change is not None:

        if oi_change > 5:

            if score > 0:
                score += 1
            elif score < 0:
                score -= 1

    funding = _safe_float(
        advanced.get(
            "funding_rate"
        )
    )

    if funding is not None:

        if funding > 0.01:
            score -= 1

        elif funding < -0.01:
            score += 1

    if score >= 0:
        return "LONG"

    return "SHORT"


# =========================================================
# FALLBACK: ENTRY
# =========================================================

def _fallback_entry(
    indicators,
    levels,
    direction,
):
    """
    Uses supplied current price first.
    No fabricated market price.
    """

    price = _get_current_price(
        indicators
    )

    support = _safe_float(
        levels.get("support")
    )

    resistance = _safe_float(
        levels.get("resistance")
    )

    if price is None:
        return None, None

    if direction == "LONG":

        if (
            support is not None
            and 0 < support < price
        ):
            low = support
            high = price

        else:
            low = price
            high = price

    else:

        if (
            resistance is not None
            and resistance > price
        ):
            low = price
            high = resistance

        else:
            low = price
            high = price

    return (
        round(low, 8),
        round(high, 8),
    )


# =========================================================
# FALLBACK: STOP LOSS / TAKE PROFIT
# =========================================================

def _fallback_risk_levels(
    entry_low,
    entry_high,
    direction,
    support,
    resistance,
):
    """
    Creates a wide swing setup.

    Rules:
    - Minimum 3.5% SL distance (MIN_SL_PCT).
    - Maximum 6% SL distance (MAX_SL_PCT) — this is the fix: without a
      ceiling, a distant/bad support or resistance value could blow the
      stop out to 20-30%+, which also drags the 2R take-profit just as
      far away, making both unrealistic to ever reach cleanly.
    - 1:2 RR exactly, measured off the (now-capped) risk distance.
    - No ATR.
    """

    MIN_SL_PCT = 0.035
    DEFAULT_SL_PCT = 0.04
    MAX_SL_PCT = 0.06

    if entry_low is None:
        return None, None

    if entry_high is None:
        entry_high = entry_low

    entry_low = float(entry_low)
    entry_high = float(entry_high)

    if entry_low <= 0:
        return None, None

    support = _safe_float(support)
    resistance = _safe_float(resistance)

    if direction == "LONG":

        reference = entry_low

        if (
            support is not None
            and support > 0
            and support < reference
        ):
            stop_loss = support * 0.995
        else:
            stop_loss = reference * (1 - DEFAULT_SL_PCT)

        # Clamp into the [MIN_SL_PCT, MAX_SL_PCT] band.
        min_sl = reference * (1 - MAX_SL_PCT)
        max_sl = reference * (1 - MIN_SL_PCT)
        stop_loss = max(min_sl, min(stop_loss, max_sl))

        risk = reference - stop_loss
        take_profit = reference + risk * 2.0

    else:

        reference = entry_high

        if (
            resistance is not None
            and resistance > reference
        ):
            stop_loss = resistance * 1.005
        else:
            stop_loss = reference * (1 + DEFAULT_SL_PCT)

        min_sl = reference * (1 + MIN_SL_PCT)
        max_sl = reference * (1 + MAX_SL_PCT)
        stop_loss = max(min_sl, min(stop_loss, max_sl))

        risk = stop_loss - reference
        take_profit = reference - risk * 2.0

    return (
        round(stop_loss, 8),
        round(take_profit, 8),
    )


# =========================================================
# FALLBACK: TECHNICAL TEXT
# =========================================================

def _fallback_technical_text(
    coin,
    indicators,
    direction,
):
    indicators = indicators or {}

    parts = []

    rsi = _safe_float(
        indicators.get("rsi")
    )

    if rsi is not None:
        parts.append(
            f"RSI is {rsi:.1f}"
        )

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

        if price > ema21:
            parts.append(
                "price is above the 21 EMA"
            )
        else:
            parts.append(
                "price is below the 21 EMA"
            )

    macd = _safe_float(
        indicators.get("macd")
    )

    macd_signal = _safe_float(
        indicators.get("macd_signal")
    )

    if (
        macd is not None
        and macd_signal is not None
    ):

        if macd > macd_signal:
            parts.append(
                "MACD is above its signal line"
            )

        elif macd < macd_signal:
            parts.append(
                "MACD is below its signal line"
            )

    volume_change = _safe_float(
        indicators.get(
            "volume_change"
        )
    )

    if volume_change is not None:

        parts.append(
            f"volume change is {volume_change:.1f}%"
        )

    if not parts:

        return (
            f"${coin} is being evaluated from "
            f"the available market structure."
        )

    if len(parts) == 1:

        return (
            f"${coin} technical structure shows "
            f"{parts[0]}."
        )

    selected = parts[:3]

    return (
        f"${coin} technical structure shows "
        + ", ".join(selected[:-1])
        + f", with {selected[-1]}."
    )


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
    coin = _coin_name(
        symbol
    )

    indicators = indicators or {}

    advanced_market_data = (
        advanced_market_data or {}
    )

    major_levels = _select_major_levels(
        indicators,
        advanced_market_data,
    )

    direction = _fallback_direction(
        indicators,
        advanced_market_data,
    )

    entry_low, entry_high = (
        _fallback_entry(
            indicators,
            major_levels,
            direction,
        )
    )

    stop_loss, take_profit = (
        _fallback_risk_levels(
            entry_low,
            entry_high,
            direction,
            major_levels.get(
                "support"
            ),
            major_levels.get(
                "resistance"
            ),
        )
    )

    technical = _fallback_technical_text(
        coin,
        indicators,
        direction,
    )

    news_line = _fallback_news_line(
        news
    )

    btc_context = _fallback_market_context(
        advanced_market_data
    )

    if market_context:

        if isinstance(
            market_context,
            str,
        ):

            extra_context = _clean_text(
                market_context,
                250,
            )

            if extra_context:
                btc_context = (
                    f"{btc_context} "
                    f"{extra_context}"
                ).strip()

    setup = {
        "symbol": symbol,
        "direction": direction,
        "title": _select_title(
            direction,
            coin,
        ),
        "entry_low": entry_low,
        "entry_high": entry_high,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "support": major_levels.get(
            "support"
        ),
        "resistance": major_levels.get(
            "resistance"
        ),
        "news_line": news_line,
        "technical_analysis": technical,
        "market_context": btc_context,
        "rr": 2,
        "hashtags": [],
    }

    print(
        f"[setup_generator] "
        f"Using Python fallback for ${coin}."
    )

    return setup


# =========================================================
# VALIDATE AI OUTPUT
# =========================================================

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

10. Keep the content concise.

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

        response = client.chat.completions.create(
            model=cfg.GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            temperature=0.75,
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

        direction = _fallback_direction(
            indicators,
            advanced_market_data,
        )

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

        MIN_SL_PCT = 0.035
        MAX_SL_PCT = 0.06
        DEFAULT_SL_PCT = 0.04

        if ai_stop is not None:
            distance = abs(entry_low - ai_stop) / entry_low

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
                    ai_stop = round(entry_low * (1 - MAX_SL_PCT), 8)
                else:
                    ai_stop = round(entry_low * (1 + MAX_SL_PCT), 8)

        if ai_stop is None:

            if direction == "LONG":
                ai_stop = round(entry_low * (1 - DEFAULT_SL_PCT), 8)
            else:
                ai_stop = round(entry_low * (1 + DEFAULT_SL_PCT), 8)

        sl_distance = abs(
            entry_low - ai_stop
        )

        if direction == "LONG":

            ai_target = round(
                entry_low
                + (sl_distance * 2.0),
                8,
            )

        else:

            ai_target = round(
                entry_low
                - (sl_distance * 2.0),
                8,
            )

    else:

        return _python_fallback_setup(
            symbol=symbol,
            indicators=indicators,
            news=news,
            market_context=market_context,
            advanced_market_data=advanced_market_data,
        )

    setup["stop_loss"] = ai_stop
    setup["take_profit"] = ai_target

    setup["rr"] = 2

    setup["title"] = _select_title(
        direction,
        coin,
    )

    setup["news_line"] = _clean_text(
        setup.get(
            "news_line",
            "",
        ),
        300,
    )

    setup["technical_analysis"] = _clean_text(
        setup.get(
            "technical_analysis",
            "",
        ),
        600,
    )

    setup["market_context"] = _clean_text(
        setup.get(
            "market_context",
            "",
        ),
        400,
    )

    setup["hashtags"] = []

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

    technical = setup.get(
        "technical_analysis",
        "",
    ).strip()

    news_line = setup.get(
        "news_line",
        "",
    ).strip()

    market = setup.get(
        "market_context",
        "",
    ).strip()

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

    lines.append("")

    lines.append(
        final_line
    )

    text = "\n".join(
        lines
    ).strip()

    text = re.sub(
        r"#\w+",
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

    if len(text) > cfg.CHAR_LIMIT:

        text = text[
            :cfg.CHAR_LIMIT
        ].rstrip()

    return text
