"""
setup_generator.py

Generates short, natural Binance Square trade-setup posts.

Uses:
- Technical indicators
- Multi-timeframe support/resistance
- BTC market context
- Advanced market data when available
- Relevant news

Final post format:
COIN: LONG TITLE?

LONG SETUP — COIN

Entry: $X–$Y
Stop Loss: $X
Take Profit: $X (2R)

Key Levels: Support $X | Resistance $X

Technical analysis.

NEWS: Short relevant news headline/summary.

Long $COIN 👆
OR
Short $COIN 👇
"""

import json
import re

from groq import Groq

from src import bot_config as cfg


# =========================================================
# SYSTEM PROMPT
# =========================================================

SYSTEM_PROMPT = """
You are a professional crypto market analyst writing short
Binance Square educational market-analysis posts.

The writing must feel natural, human and concise.

IMPORTANT RULES:
- Do not tell readers to invest.
- Do not promise profit.
- Do not use exaggerated claims.
- Do not fabricate news or market data.
- Use ONLY the data provided.
- If information is missing, do not invent it.
- Focus mainly on the selected coin.
- BTC is only broader market context.
- Keep the post around 100–140 words when possible.
- Do NOT generate hashtags.
- Do NOT use emojis except the final directional emoji.
- Do NOT use "NFA" or "DYOR".
- Do NOT use "guaranteed".
- Do NOT use "will definitely".
- Do not make the post sound like AI-generated text.

TITLE:
Create a SHORT attention-grabbing title.

Good examples:
"NOTCOIN: MOMENTUM OR PULLBACK?"
"ZEC: BREAKOUT OR FAKEOUT?"
"AVAX: BULLS BACK IN CONTROL?"
"ETH: MOMENTUM UNDER PRESSURE?"

Avoid long titles.

POST STRUCTURE:

COIN: SHORT TITLE?

LONG SETUP — COIN
OR
SHORT SETUP — COIN

Entry: $X–$Y
Stop Loss: $X
Take Profit: $X (2R)

Key Levels: Support $X | Resistance $X

Technical analysis:
2–3 natural sentences using the strongest indicators.

NEWS:
One short relevant news headline/summary.
Only include this when relevant news is actually supplied.
Do not invent a headline.

Market context:
Only mention BTC or broader market conditions when useful.

Final line:
Long $COIN 👆
OR
Short $COIN 👇

Do not add anything after the final directional line.
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

    return f"{number:.8f}".rstrip("0").rstrip(".")


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
            ""
        )

        summary = news.get(
            "summary",
            ""
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
                    ""
                )

                summary = item.get(
                    "summary",
                    ""
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
        "atr",
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

    # Multi-timeframe S/R
    sr = advanced.get(
        "multi_timeframe_sr"
    )

    if sr:
        result["multi_timeframe_sr"] = sr

    # BTC context
    btc = advanced.get(
        "btc_context"
    )

    if btc:
        result["btc_context"] = btc

    # Open Interest
    oi = advanced.get(
        "open_interest"
    )

    if oi is not None:
        result["open_interest"] = oi

    oi_change = advanced.get(
        "oi_change_1h_pct"
    )

    if oi_change is not None:
        result["oi_change_1h_pct"] = oi_change

    # Funding
    funding = advanced.get(
        "funding_rate"
    )

    if funding is not None:
        result["funding_rate"] = funding

    # Long / Short
    long_short = advanced.get(
        "long_short_ratio"
    )

    if long_short:
        result["long_short_ratio"] = long_short

    # Liquidations
    liquidations = advanced.get(
        "liquidations"
    )

    if liquidations:
        result["liquidations"] = liquidations

    # Orderbook
    orderbook = advanced.get(
        "orderbook"
    )

    if orderbook:
        result["orderbook"] = orderbook

    return result


# =========================================================
# MAJOR SUPPORT / RESISTANCE
# =========================================================

def _select_major_levels(
    indicators,
    advanced_market_data,
):
    """
    Select useful support/resistance levels.

    Priority:
    4H -> 1D -> 1W -> 1H -> 15M

    Falls back to indicator levels.
    """

    priority = [
        "4h",
        "1d",
        "1w",
        "1h",
        "15m",
    ]

    sr = (
        advanced_market_data or {}
    ).get(
        "multi_timeframe_sr",
        {}
    )

    support = None
    resistance = None

    for timeframe in priority:

        levels = sr.get(
            timeframe
        )

        if not levels:
            continue

        if support is None:
            support = levels.get(
                "support"
            )

        if resistance is None:
            resistance = levels.get(
                "resistance"
            )

        if (
            support is not None
            and resistance is not None
        ):
            break

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
# RISK / REWARD
# =========================================================

def _apply_risk_reward(
    direction,
    entry_low,
    entry_high,
    atr,
):
    """
    Build a numerical 2R baseline using ATR.
    """

    entry_low = _safe_float(
        entry_low
    )

    entry_high = _safe_float(
        entry_high
    )

    atr = _safe_float(
        atr
    )

    if (
        entry_low is None
        or entry_high is None
        or atr is None
        or atr <= 0
    ):
        return {
            "stop_loss": None,
            "take_profit": None,
            "rr": 2,
        }

    entry = (
        entry_low + entry_high
    ) / 2

    stop_distance = (
        atr * cfg.ATR_MULTIPLIER
    )

    rr = 2

    if direction == "LONG":

        stop_loss = (
            entry - stop_distance
        )

        take_profit = (
            entry
            + stop_distance * rr
        )

    else:

        stop_loss = (
            entry + stop_distance
        )

        take_profit = (
            entry
            - stop_distance * rr
        )

    return {
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "rr": rr,
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
    Ask Groq to generate one complete setup.
    """

    client = _get_client()

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

3. Create a stop loss.

4. Create a 2R take-profit.

5. Identify useful support and resistance.

6. Use only the strongest 3–5 technical signals.

7. Use OI, funding, long/short ratio, liquidation or
   orderbook data only if supplied and useful.

8. Use BTC only as broader market context.

9. NEWS RULE:
   If relevant news is supplied, create a short NEWS headline
   using ONLY that supplied information.

   If no relevant news is supplied:
   return an empty news_line.

10. Create a SHORT attention-grabbing title.

11. Do NOT generate hashtags.

12. Keep the final content around 100–140 words.

Return JSON only:

{{
  "direction": "LONG or SHORT",
  "title": "SHORT ATTENTION-GRABBING TITLE",
  "entry_low": 0,
  "entry_high": 0,
  "stop_loss": 0,
  "take_profit": 0,
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
            ""
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
    # ATR FALLBACK
    # =====================================================

    atr = _safe_float(
        indicators.get(
            "atr"
        )
    )

    risk_data = _apply_risk_reward(
        direction,
        entry_low,
        entry_high,
        atr,
    )

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

    if ai_stop is None:

        ai_stop = risk_data[
            "stop_loss"
        ]

    if ai_target is None:

        ai_target = risk_data[
            "take_profit"
        ]

    setup["stop_loss"] = ai_stop
    setup["take_profit"] = ai_target
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
    # CLEAN TEXT
    # =====================================================

    coin = symbol.replace(
        "USDT",
        "",
    )

    title = _clean_text(
        setup.get(
            "title",
            f"{coin}: MARKET SETUP?",
        ),
        100,
    )

    # Remove accidental hashtags from title.
    title = re.sub(
        r"#\w+",
        "",
        title,
    ).strip()

    # Remove accidental "$COIN" from title
    # because formatter adds the coin name.
    title = re.sub(
        rf"^\$?{re.escape(coin)}\s*[:\-]?\s*",
        "",
        title,
        flags=re.IGNORECASE,
    ).strip()

    if not title:
        title = "MOMENTUM OR PULLBACK?"

    setup["title"] = title

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
    # REMOVE HASHTAGS COMPLETELY
    # =====================================================

    setup["hashtags"] = []

    return setup


# =========================================================
# FORMAT FINAL BINANCE SQUARE POST
# =========================================================

def format_post_text(setup):
    """
    Convert setup JSON into the final Binance Square format.

    Example:

    NOT: MOMENTUM OR PULLBACK?

    LONG SETUP — NOT

    Entry: $0.000471–$0.000474
    Stop Loss: $0.000469
    Take Profit: $0.000478 (2R)

    Key Levels: Support $0.000471 | Resistance $0.000475

    Price is holding above EMA9, EMA21 and SMA50,
    keeping the short-term structure constructive.

    NEWS: TON ecosystem momentum has recently supported NOT
    sentiment.

    Long $NOT 👆
    """

    symbol = setup.get(
        "symbol",
        "",
    )

    coin = symbol.replace(
        "USDT",
        "",
    )

    direction = setup.get(
        "direction",
        "LONG",
    )

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

    news_line = setup.get(
        "news_line",
        "",
    ).strip()

    technical = setup.get(
        "technical_analysis",
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
        "MOMENTUM OR PULLBACK?",
    ).strip()

    title = re.sub(
        r"#\w+",
        "",
        title,
    ).strip()

    title = re.sub(
        rf"^\$?{re.escape(coin)}\s*[:\-]?\s*",
        "",
        title,
        flags=re.IGNORECASE,
    ).strip()

    if not title:
        title = "MOMENTUM OR PULLBACK?"

    # -----------------------------------------------------
    # DIRECTION
    # -----------------------------------------------------

    if direction == "LONG":

        direction_line = (
            f"LONG SETUP — {coin}"
        )

        action_line = (
            f"Long ${coin} 👆"
        )

    else:

        direction_line = (
            f"SHORT SETUP — {coin}"
        )

        action_line = (
            f"Short ${coin} 👇"
        )

    # -----------------------------------------------------
    # BUILD POST
    # -----------------------------------------------------

    lines = []

    # Short title
    lines.append(
        f"{coin}: {title}"
    )

    lines.append("")

    # Setup
    lines.append(
        direction_line
    )

    lines.append("")

    # Entry
    lines.append(
        f"Entry: ${entry_low}–${entry_high}"
    )

    # Stop
    lines.append(
        f"Stop Loss: ${stop_loss}"
    )

    # Take profit
    lines.append(
        f"Take Profit: ${take_profit} (2R)"
    )

    lines.append("")

    # Key levels
    lines.append(
        f"Key Levels: Support ${support} | "
        f"Resistance ${resistance}"
    )

    # Technical analysis
    if technical:

        lines.append("")

        lines.append(
            technical
        )

    # News
    if news_line:

        lines.append("")

        lines.append(
            f"NEWS: {news_line}"
        )

    # Market context
    if market:

        lines.append("")

        lines.append(
            market
        )

    lines.append("")

    # Final action line
    lines.append(
        action_line
    )

    text = "\n".join(
        lines
    ).strip()

    # -----------------------------------------------------
    # REMOVE ANY ACCIDENTAL HASHTAGS
    # -----------------------------------------------------

    text = re.sub(
        r"[ \t]+#\w+",
        "",
        text,
    )

    text = re.sub(
        r"\n+#\w+",
        "",
        text,
    )

    # -----------------------------------------------------
    # CLEAN EXTRA BLANK LINES
    # -----------------------------------------------------

    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text,
    ).strip()

    # -----------------------------------------------------
    # BINANCE CHARACTER SAFETY
    # -----------------------------------------------------

    if len(text) > cfg.CHAR_LIMIT:

        text = text[
            :cfg.CHAR_LIMIT
        ].rstrip()

    return text
