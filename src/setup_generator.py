"""
setup_generator.py

Generates concise, natural Binance Square crypto market-analysis posts.

Features:
- Technical indicators
- 1H and 4H Swing support/resistance
- BTC market context
- Advanced market data when available
- Relevant supplied news
- 25 LONG title templates
- 25 SHORT title templates
- Title rotation
- No emojis
- Exactly 3 $COIN mentions in the final post:
    1. Title
    2. Technical-analysis/body section
    3. Final LONG/SHORT line

Important:
- This module does not place trades.
- It does not tell readers to invest.
- It does not fabricate news or market data.
- ATR is not used for setup fallback calculations.
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
- Always aim for clean wide swing trade setups with solid Risk-to-Reward ratios.
- Do NOT output micro-scalp setups or extremely narrow SL/TP ranges.

TITLE:
A title will be selected from the supplied title library.
Do not invent a different title.

NEWS:
Only use news supplied in the input.
If no relevant news is supplied, news_line must be empty.

TECHNICAL ANALYSIS:
Use the strongest available technical information.
Mention indicators such as EMA, SMA, MACD, RSI, Stochastic,
volume, orderbook or other advanced data only when supplied.

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
        raise RuntimeError(
            "GROQ_API_KEY is missing."
        )

    return Groq(
        api_key=cfg.GROQ_API_KEY
    )


# =========================================================
# NUMBER HELPERS
# =========================================================

def _safe_float(value):
    try:
        return float(value)
    except Exception:
        return None


def _format_price(value):
    """
    Format prices without unnecessary zeros.
    """

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
    """
    Convert BTCUSDT -> BTC.
    """

    symbol = str(
        symbol or ""
    ).upper()

    if symbol.endswith("USDT"):
        return symbol[:-4]

    return symbol


def _replace_coin_placeholder(
    title,
    coin,
):
    """
    Replace $XXX with the real $COIN.
    """

    return str(title).replace(
        "$XXX",
        f"${coin}",
    )


# =========================================================
# TITLE ROTATION
# =========================================================

def _select_title(
    direction,
    coin,
):
    """
    Select a title from the user's 25-title library.

    The selection is deterministic for a given symbol/day,
    while different symbols rotate through different titles.
    """

    if direction == "LONG":
        titles = LONG_TITLES
    else:
        titles = SHORT_TITLES

    today = datetime.now(
        timezone.utc
    ).strftime(
        "%Y-%m-%d"
    )

    seed_text = (
        f"{coin}-{today}-{direction}"
    )

    seed_value = sum(
        ord(char)
        for char in seed_text
    )

    index = (
        seed_value
        % len(titles)
    )

    return _replace_coin_placeholder(
        titles[index],
        coin,
    )


# =========================================================
# NEWS
# =========================================================

def _summarize_news(news):
    """
    Convert different news formats into compact text.
    """

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

def _build_indicator_summary(
    indicators,
):

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

def _build_advanced_summary(
    advanced,
):

    if not advanced:
        return {}

    result = {}

    # -----------------------------------------------------
    # 1H / 4H SUPPORT / RESISTANCE
    # -----------------------------------------------------

    sr = advanced.get(
        "multi_timeframe_sr"
    )

    if sr:

        one_hour = sr.get("1h")
        four_hour = sr.get("4h")

        if one_hour:
            result["1h_support_resistance"] = one_hour
        if four_hour:
            result["4h_support_resistance"] = four_hour

    # -----------------------------------------------------
    # BTC CONTEXT
    # -----------------------------------------------------

    btc = advanced.get(
        "btc_context"
    )

    if btc:
        result[
            "btc_context"
        ] = btc

    # -----------------------------------------------------
    # OPEN INTEREST
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # FUNDING
    # -----------------------------------------------------

    funding = advanced.get(
        "funding_rate"
    )

    if funding is not None:
        result[
            "funding_rate"
        ] = funding

    # -----------------------------------------------------
    # LONG / SHORT
    # -----------------------------------------------------

    long_short = advanced.get(
        "long_short_ratio"
    )

    if long_short:
        result[
            "long_short_ratio"
        ] = long_short

    # -----------------------------------------------------
    # LIQUIDATIONS
    # -----------------------------------------------------

    liquidations = advanced.get(
        "liquidations"
    )

    if liquidations:
        result[
            "liquidations"
        ] = liquidations

    # -----------------------------------------------------
    # ORDERBOOK
    # -----------------------------------------------------

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
    """
    Select support/resistance using 1H/4H levels.

    Priority:
    1H/4H -> indicator fallback
    """

    sr = (
        advanced_market_data or {}
    ).get(
        "multi_timeframe_sr",
        {}
    )

    one_hour = sr.get(
        "1h",
        {}
    )

    support = one_hour.get(
        "support"
    )

    resistance = one_hour.get(
        "resistance"
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
# GENERATE SETUP
# =========================================================

def generate_setup(
    symbol,
    indicators,
    news=None,
    market_context=None,
    advanced_market_data=None,
):
    """
    Ask Groq to generate one complete market-analysis setup.

    ATR is not used for fallback calculations.
    """

    client = _get_client()

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

3. Set Stop Loss and Take Profit (Swing Structure):
   - Place Stop-Loss below the recent 1H/4H swing low (for LONG) or above the swing high (for SHORT).
   - Ensure Stop-Loss distance is at least 3.5% to 5% away from entry.
   - Set Take-Profit at 2R target (exactly double the Stop-Loss distance).
   - NEVER create tight scalping/micro-trades.

4. Identify major 1H and 4H swing support and resistance levels.

5. Use only the strongest 3–5 technical signals.

6. Use OI, funding, long/short ratio, liquidation or
   orderbook data only if supplied and useful.

7. Use BTC only as broader market context.

8. NEWS RULE:
   If relevant news is supplied, create a short NEWS line
   using ONLY the supplied information.

   If no relevant news is supplied:
   return an empty news_line.

9. TITLE RULE:
   After deciding LONG or SHORT, select the appropriate
   title style.

   Do not create an unrelated title.
   Do not use emojis.
   Do not use hashtags.

10. Keep the final content around 100–140 words.

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
  "news_line": "short verified news headline or empty",
  "technical_analysis": "2-3 natural sentences",
  "market_context": "1-2 short sentences"
}}
"""

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

    content = response.choices[0].message.content

    content = (
        content
        .replace(
            "```json",
            "",
        )
        .replace(
            "```",
            "",
        )
        .strip()
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

    # =====================================================
    # DIRECTION
    # =====================================================

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
        direction = "LONG"

    setup["direction"] = direction

    # =====================================================
    # ENTRY
    # =====================================================

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

        entry_low = _safe_float(
            indicators.get(
                "current_price"
            )
        )

    if entry_low is None:

        entry_low = _safe_float(
            indicators.get(
                "price"
            )
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

    # =====================================================
    # STOP LOSS / TAKE PROFIT (STRICT 1:2 RR SWING ENFORCER)
    # =====================================================

    ai_stop = _safe_float(
        setup.get(
            "stop_loss"
        )
    )

    if entry_low and entry_low > 0:
        # 1. Check if Stop Loss exists and is at least 3.5% away
        if ai_stop is None or abs(entry_low - ai_stop) / entry_low < 0.035:
            if direction == "LONG":
                ai_stop = round(entry_low * 0.96, 8)       # 4.0% Stop Loss below
            else:
                ai_stop = round(entry_low * 1.04, 8)       # 4.0% Stop Loss above

        # 2. Calculate actual Risk Distance (SL Gap)
        sl_distance = abs(entry_low - ai_stop)

        # 3. Force Take Profit to be EXACTLY double the SL Distance (Strict 1:2 RR)
        if direction == "LONG":
            ai_target = round(entry_low + (sl_distance * 2.0), 8)
        else:
            ai_target = round(entry_low - (sl_distance * 2.0), 8)

    setup["stop_loss"] = ai_stop
    setup["take_profit"] = ai_target

    # Keep this field for compatibility with
    # existing backtest/state code.
    setup["rr"] = 2

    # =====================================================
    # MAJOR LEVELS
    # =====================================================

    if setup.get(
        "support"
    ) is None:

        setup["support"] = (
            major_levels[
                "support"
            ]
        )

    if setup.get(
        "resistance"
    ) is None:

        setup["resistance"] = (
            major_levels[
                "resistance"
            ]
        )

    # =====================================================
    # TITLE
    # =====================================================

    # Ignore whatever title the model generated.
    # Select one from the user's title library instead.

    setup["title"] = _select_title(
        direction,
        coin,
    )

    # =====================================================
    # CLEAN TEXT
    # =====================================================

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

    # =====================================================
    # REMOVE HASHTAGS
    # =====================================================

    setup["hashtags"] = []

    return setup


# =========================================================
# FORMAT FINAL BINANCE SQUARE POST
# =========================================================

def format_post_text(
    setup,
):
    """
    Convert setup JSON into final Binance Square format.

    The final post contains exactly three $COIN mentions:

    1. Title
    2. Technical-analysis/body section
    3. Final LONG/SHORT line
    """

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

    # -----------------------------------------------------
    # PRICE VALUES
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # TEXT
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # TITLE
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # DIRECTION LINE
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # TECHNICAL BODY
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # BUILD POST
    # -----------------------------------------------------

    lines = []

    # 1. First $COIN mention
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

    # 2. Second $COIN mention
    lines.append(
        technical_line
    )

    # -----------------------------------------------------
    # NEWS
    # -----------------------------------------------------

    if news_line:

        lines.append("")

        lines.append(
            f"NEWS: {news_line}"
        )

    # -----------------------------------------------------
    # MARKET CONTEXT
    # -----------------------------------------------------

    if market:

        lines.append("")

        lines.append(
            f"Market Context: {market}"
        )

    lines.append("")

    # 3. Third $COIN mention
    lines.append(
        final_line
    )

    text = "\n".join(
        lines
    ).strip()

    # -----------------------------------------------------
    # REMOVE HASHTAGS
    # -----------------------------------------------------

    text = re.sub(
        r"#\w+",
        "",
        text,
    )

    # -----------------------------------------------------
    # REMOVE EMOJIS / NON-ASCII
    # -----------------------------------------------------

    text = re.sub(
        r"[^\x00-\x7F]+",
        "",
        text,
    )

    # -----------------------------------------------------
    # CLEAN EXTRA SPACES
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # CHARACTER LIMIT
    # -----------------------------------------------------

    if len(text) > cfg.CHAR_LIMIT:

        text = text[
            :cfg.CHAR_LIMIT
        ].rstrip()

    return text
