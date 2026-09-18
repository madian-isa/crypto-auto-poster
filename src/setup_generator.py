"""
setup_generator.py

Generates short, natural and professional Binance Square trade-setup posts.

Style:
- Coin-specific analysis comes first.
- News stays short and relevant.
- BTC is used only as broader market context.
- Avoids dumping every indicator into the post.
- Keeps the existing setup format.
"""

import json
import re

from src import bot_config as cfg

try:
    from groq import Groq
except ImportError:
    Groq = None


SYSTEM_PROMPT = """
You are a professional crypto market analyst writing short Binance Square posts.

Your writing must feel human, natural and concise — NOT like an AI-generated
indicator report.

IMPORTANT STYLE RULES:

1. Focus mainly on the selected coin.
2. Technical analysis should explain the coin's actual price structure.
3. Do NOT mention every available indicator.
4. Select only the 3-5 most useful indicators for the current setup.
5. News must be relevant to the coin or its sector.
6. If no real relevant coin news exists, do not invent news.
7. BTC should only be used as broader market context.
8. BTC analysis should normally be only 1-2 short sentences.
9. Do not spend more space analyzing BTC than the selected coin.
10. Avoid repetitive AI phrases such as:
   "This indicates..."
   "This suggests..."
   "Furthermore..."
   "Additionally..."
11. Use natural trader-style wording.
12. Do not use investment advice or guaranteed-profit language.
13. Do not tell readers to buy or sell.
14. Do not add a disclaimer.
15. Do not add emojis except where the final format already provides them.
16. Do not fabricate data.
17. Keep the analysis compact and readable.

TITLE:
- 7-12 words.
- Make it interesting but factual.
- Mention the coin.
- Vary wording naturally.

TECHNICAL ANALYSIS:
- 2-3 sentences.
- Focus on price structure, momentum and the most relevant indicators.
- Mention support/resistance when useful.
- Avoid listing all indicators.

MARKET ANALYSIS:
- 1-2 sentences.
- BTC direction, market breadth, OI or funding may be mentioned if useful.
- Explain how the broader market context relates to the selected coin.
- Do not turn this into a BTC news article.

NEWS:
- One short line.
- Use only real supplied news.
- Prefer coin-specific or sector-specific news.
- If the supplied news is not clearly relevant, return an empty string.

HASHTAGS:
- Exactly 4 hashtags.
- First hashtag must be the coin ticker.
- Remaining hashtags should match the coin/topic.
"""


def _get_client():
    if Groq is None:
        raise RuntimeError(
            "groq package is not installed."
        )

    if not cfg.GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is missing."
        )

    return Groq(
        api_key=cfg.GROQ_API_KEY
    )


def _clean_json(text):
    """
    Removes accidental markdown code fences
    around JSON returned by the model.
    """

    text = text.strip()

    if text.startswith("```"):
        text = re.sub(
            r"^```(?:json)?",
            "",
            text,
            flags=re.IGNORECASE,
        )

        text = re.sub(
            r"```$",
            "",
            text,
        )

    return text.strip()


def _safe_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _format_price(value):
    """
    Formats crypto prices without unnecessary trailing zeros.
    """

    value = _safe_float(value)

    if value is None:
        return "N/A"

    if value >= 1000:
        return f"{value:,.2f}"

    if value >= 1:
        return f"{value:.4f}".rstrip("0").rstrip(".")

    if value >= 0.1:
        return f"{value:.5f}".rstrip("0").rstrip(".")

    if value >= 0.01:
        return f"{value:.6f}".rstrip("0").rstrip(".")

    return f"{value:.8f}".rstrip("0").rstrip(".")


def _extract_coin(symbol):
    if symbol.endswith("USDT"):
        return symbol[:-4]

    return symbol


def _build_market_summary(market_context):
    if not market_context:
        return "No broader market context is available."

    parts = []

    btc_direction = market_context.get(
        "btc_direction"
    )

    btc_change = market_context.get(
        "btc_change_24h"
    )

    green_pct = market_context.get(
        "market_green_pct"
    )

    breadth = market_context.get(
        "market_breadth"
    )

    if btc_direction and btc_direction != "Unknown":
        if btc_change is not None:
            parts.append(
                f"BTC is {btc_direction.lower()} "
                f"over 24h ({btc_change:+.2f}%)."
            )
        else:
            parts.append(
                f"BTC is currently "
                f"{btc_direction.lower()}."
            )

    if green_pct is not None:
        parts.append(
            f"Market breadth is "
            f"{green_pct:.1f}% green."
        )
    elif breadth and breadth != "Unknown":
        parts.append(
            f"Market breadth is {breadth.lower()}."
        )

    btc_oi = market_context.get(
        "btc_open_interest"
    )

    if btc_oi is not None:
        parts.append(
            f"BTC open interest is around "
            f"{btc_oi:,.0f} contracts."
        )

    funding = market_context.get(
        "btc_funding_rate"
    )

    if funding is not None:
        funding_pct = funding * 100

        parts.append(
            f"BTC funding is "
            f"{funding_pct:+.4f}%."
        )

    if not parts:
        return "Broader market data is limited."

    return " ".join(parts)


def _build_indicator_summary(indicators):
    """
    Creates a compact input for the model.

    The model receives the available indicators but is instructed
    to select only the most relevant ones.
    """

    if not indicators:
        return "No indicator data available."

    keys = [
        "price",
        "current_price",
        "rsi",
        "ema9",
        "ema21",
        "sma50",
        "macd",
        "macd_signal",
        "macd_histogram",
        "adx",
        "stochastic_k",
        "stochastic_d",
        "atr",
        "obv",
        "bb_upper",
        "bb_middle",
        "bb_lower",
        "support",
        "resistance",
        "volume",
    ]

    data = {}

    for key in keys:
        if key in indicators:
            data[key] = indicators[key]

    if not data:
        data = indicators

    return json.dumps(
        data,
        ensure_ascii=False,
        default=str,
    )


def _build_advanced_summary(advanced_market_data):
    """
    Converts advanced market data into a compact model input.
    """

    if not advanced_market_data:
        return "No advanced market data available."

    selected = {}

    if "multi_timeframe_sr" in advanced_market_data:
        selected[
            "multi_timeframe_sr"
        ] = advanced_market_data[
            "multi_timeframe_sr"
        ]

    if "btc_context" in advanced_market_data:
        selected[
            "btc_context"
        ] = advanced_market_data[
            "btc_context"
        ]

    if "open_interest" in advanced_market_data:
        selected[
            "open_interest"
        ] = advanced_market_data[
            "open_interest"
        ]

    if "oi_change_1h_pct" in advanced_market_data:
        selected[
            "oi_change_1h_pct"
        ] = advanced_market_data[
            "oi_change_1h_pct"
        ]

    if "funding_rate" in advanced_market_data:
        selected[
            "funding_rate"
        ] = advanced_market_data[
            "funding_rate"
        ]

    if "long_short_ratio" in advanced_market_data:
        selected[
            "long_short_ratio"
        ] = advanced_market_data[
            "long_short_ratio"
        ]

    if "liquidations" in advanced_market_data:
        selected[
            "liquidations"
        ] = advanced_market_data[
            "liquidations"
        ]

    if "orderbook" in advanced_market_data:
        selected[
            "orderbook"
        ] = advanced_market_data[
            "orderbook"
        ]

    return json.dumps(
        selected,
        ensure_ascii=False,
        default=str,
    )


def _build_news_summary(news):
    if not news:
        return "No relevant verified news found."

    if isinstance(news, str):
        return news[:800]

    if isinstance(news, list):
        cleaned = []

        for item in news[:5]:

            if isinstance(item, str):
                cleaned.append(item)

            elif isinstance(item, dict):
                title = (
                    item.get("title")
                    or item.get("headline")
                    or item.get("name")
                )

                if title:
                    cleaned.append(
                        str(title)
                    )

        if cleaned:
            return "\n".join(cleaned)

    if isinstance(news, dict):
        title = (
            news.get("title")
            or news.get("headline")
            or news.get("name")
        )

        if title:
            return str(title)

    return "No relevant verified news found."


def _select_major_levels(indicators, advanced_market_data):
    """
    Selects useful support/resistance levels.

    Preference:
    1. Advanced multi-timeframe data.
    2. Basic indicator support/resistance.
    """

    support = None
    resistance = None
    support_tf = None
    resistance_tf = None

    mtf = {}

    if advanced_market_data:
        mtf = advanced_market_data.get(
            "multi_timeframe_sr"
        ) or {}

    current_price = (
        _safe_float(
            indicators.get("price")
        )
        or _safe_float(
            indicators.get("current_price")
        )
    )

    candidates_support = []
    candidates_resistance = []

    timeframe_priority = {
        "15m": 1,
        "1h": 2,
        "4h": 3,
        "1d": 4,
        "1w": 5,
    }

    for timeframe, levels in mtf.items():

        if not isinstance(levels, dict):
            continue

        s = _safe_float(
            levels.get("support")
        )

        r = _safe_float(
            levels.get("resistance")
        )

        if s is not None:
            candidates_support.append(
                (
                    timeframe_priority.get(
                        timeframe,
                        0,
                    ),
                    timeframe,
                    s,
                )
            )

        if r is not None:
            candidates_resistance.append(
                (
                    timeframe_priority.get(
                        timeframe,
                        0,
                    ),
                    timeframe,
                    r,
                )
            )

    if current_price is not None:

        below = [
            x for x in candidates_support
            if x[2] <= current_price
        ]

        above = [
            x for x in candidates_resistance
            if x[2] >= current_price
        ]

        if below:
            below.sort(
                key=lambda x: (
                    abs(current_price - x[2]),
                    -x[0],
                )
            )

            _, support_tf, support = below[0]

        if above:
            above.sort(
                key=lambda x: (
                    abs(x[2] - current_price),
                    -x[0],
                )
            )

            _, resistance_tf, resistance = above[0]

    if support is None:
        support = _safe_float(
            indicators.get("support")
        )

    if resistance is None:
        resistance = _safe_float(
            indicators.get("resistance")
        )

    return {
        "support": support,
        "resistance": resistance,
        "support_tf": support_tf,
        "resistance_tf": resistance_tf,
    }


def _build_prompt(
    symbol,
    indicators,
    news,
    market_context,
    advanced_market_data=None,
):
    coin = _extract_coin(symbol)

    indicator_summary = _build_indicator_summary(
        indicators
    )

    market_summary = _build_market_summary(
        market_context
    )

    news_summary = _build_news_summary(
        news
    )

    advanced_summary = _build_advanced_summary(
        advanced_market_data
    )

    return f"""
Create a short Binance Square trade-setup post for {coin} ({symbol}).

IMPORTANT:
The selected coin must be the main subject.
BTC must only be broader market context.

COIN:
{coin}

BASIC INDICATORS:
{indicator_summary}

ADVANCED MARKET DATA:
{advanced_summary}

BTC / MARKET SUMMARY:
{market_summary}

VERIFIED NEWS:
{news_summary}

Choose either Long or Short based on the available data.

Use the strongest relevant evidence rather than mentioning every metric.

For technical analysis:
- Write only 2-3 natural sentences.
- Focus on the coin.
- Mention only the most useful indicators.
- Mention important support/resistance if relevant.

For market analysis:
- Write only 1-2 short sentences.
- Mention BTC only as broader market context.
- Explain its relevance to {coin}.

For news:
- Use one short headline only if it is genuinely relevant.
- Prefer {coin}-specific or sector-specific information.
- Never invent news.

Return ONLY valid JSON.

Required JSON:

{{
  "symbol": "{symbol}",
  "direction": "Long",
  "entry_low": 0,
  "entry_high": 0,
  "title": "Short natural title",
  "analysis_technical": "2-3 short natural sentences about {coin}.",
  "analysis_market": "1-2 short sentences about BTC and the broader market.",
  "news": "One short relevant news line or empty string.",
  "hashtags": [
    "#{coin}",
    "#CryptoTrading",
    "#TechnicalAnalysis",
    "#Crypto"
  ]
}}
"""


def generate_setup(
    symbol,
    indicators,
    news=None,
    market_context=None,
    advanced_market_data=None,
):
    """
    Generate a complete trade setup using Groq.
    """

    client = _get_client()

    prompt = _build_prompt(
        symbol=symbol,
        indicators=indicators,
        news=news,
        market_context=market_context,
        advanced_market_data=advanced_market_data,
    )

    response = client.chat.completions.create(
        model=cfg.GROQ_MODEL,
        temperature=0.75,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
    )

    content = response.choices[0].message.content

    content = _clean_json(content)

    try:
        setup = json.loads(content)

    except json.JSONDecodeError as err:
        raise RuntimeError(
            f"Groq returned invalid JSON: {err}\n"
            f"Response: {content}"
        )

    setup["symbol"] = symbol

    if setup.get("direction") not in (
        "Long",
        "Short",
    ):
        setup["direction"] = "Long"

    setup = _apply_risk_reward(
        setup,
        indicators,
    )

    levels = _select_major_levels(
        indicators,
        advanced_market_data,
    )

    setup["support"] = levels["support"]
    setup["resistance"] = levels["resistance"]

    setup["support_tf"] = levels[
        "support_tf"
    ]

    setup["resistance_tf"] = levels[
        "resistance_tf"
    ]

    return setup


def _apply_risk_reward(setup, indicators):
    """
    Builds stop loss and take profit using ATR.

    Uses either 2R or 3R.
    """

    entry_low = _safe_float(
        setup.get("entry_low")
    )

    entry_high = _safe_float(
        setup.get("entry_high")
    )

    if entry_low is None:
        entry_low = _safe_float(
            indicators.get("price")
        )

    if entry_high is None:
        entry_high = entry_low

    atr = _safe_float(
        indicators.get("atr")
    )

    if atr is None or atr <= 0:
        atr = entry_low * 0.02

    direction = setup.get(
        "direction",
        "Long",
    )

    rr = 2

    risk_multiplier = getattr(
        cfg,
        "ATR_MULTIPLIER",
        1.5,
    )

    risk = atr * risk_multiplier

    entry = (
        entry_low + entry_high
    ) / 2

    if direction == "Long":

        stop_loss = entry - risk

        take_profit = (
            entry + risk * rr
        )

    else:

        stop_loss = entry + risk

        take_profit = (
            entry - risk * rr
        )

    setup["entry_low"] = entry_low
    setup["entry_high"] = entry_high
    setup["stop_loss"] = stop_loss
    setup["take_profit"] = take_profit
    setup["rr"] = rr

    return setup


def _clean_sentence(text):
    if not text:
        return ""

    text = str(text).strip()

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text


def _clean_title(title, coin):
    if not title:
        return f"${coin} Momentum Builds Near Key Levels"

    title = _clean_sentence(title)

    title = title.replace(
        f"**${coin}**",
        f"${coin}",
    )

    title = title.replace(
        f"**{coin}**",
        f"${coin}",
    )

    if "$" not in title:
        title = f"${coin} {title}"

    return title


def _normalize_hashtags(
    hashtags,
    coin,
):
    result = []

    if isinstance(hashtags, list):
        raw_tags = hashtags
    else:
        raw_tags = []

    for tag in raw_tags:

        tag = str(tag).strip()

        if not tag:
            continue

        if not tag.startswith("#"):
            tag = "#" + tag

        tag = re.sub(
            r"[^#A-Za-z0-9_]",
            "",
            tag,
        )

        if tag.lower() not in [
            x.lower()
            for x in result
        ]:
            result.append(tag)

    coin_tag = f"#{coin}"

    result = [
        x for x in result
        if x.lower() != coin_tag.lower()
    ]

    result.insert(
        0,
        coin_tag,
    )

    defaults = [
        "#CryptoTrading",
        "#TechnicalAnalysis",
        "#Crypto",
    ]

    for tag in defaults:

        if len(result) >= 4:
            break

        if tag.lower() not in [
            x.lower()
            for x in result
        ]:
            result.append(tag)

    return result[:4]


def _format_level(
    level,
    timeframe=None,
):
    if level is None:
        return "N/A"

    price = _format_price(level)

    if timeframe:
        return f"{timeframe.upper()} {price}"

    return price


def format_post_text(setup):
    """
    Converts generated setup data into the final Binance Square post.
    """

    symbol = setup["symbol"]

    coin = _extract_coin(symbol)

    direction = setup.get(
        "direction",
        "Long",
    )

    entry_low = setup.get(
        "entry_low"
    )

    entry_high = setup.get(
        "entry_high"
    )

    stop_loss = setup.get(
        "stop_loss"
    )

    take_profit = setup.get(
        "take_profit"
    )

    rr = setup.get(
        "rr",
        2,
    )

    title = _clean_title(
        setup.get("title"),
        coin,
    )

    technical = _clean_sentence(
        setup.get(
            "analysis_technical",
            "",
        )
    )

    market = _clean_sentence(
        setup.get(
            "analysis_market",
            "",
        )
    )

    news = _clean_sentence(
        setup.get(
            "news",
            "",
        )
    )

    support = setup.get(
        "support"
    )

    resistance = setup.get(
        "resistance"
    )

    support_tf = setup.get(
        "support_tf"
    )

    resistance_tf = setup.get(
        "resistance_tf"
    )

    hashtags = _normalize_hashtags(
        setup.get("hashtags"),
        coin,
    )

    entry_text = (
        f"${_format_price(entry_low)}"
        f"–"
        f"${_format_price(entry_high)}"
    )

    stop_text = (
        f"${_format_price(stop_loss)}"
    )

    tp_text = (
        f"${_format_price(take_profit)}"
    )

    direction_upper = (
        direction.upper()
    )

    level_text = (
        f"Support "
        f"{_format_level(support, support_tf)}"
        f" | Resistance "
        f"{_format_level(resistance, resistance_tf)}"
    )

    lines = []

    lines.append(title)
    lines.append("")

    lines.append(
        f"{direction_upper} SETUP — ${coin}"
    )

    lines.append("")

    lines.append(
        f"Entry: {entry_text}"
    )

    lines.append(
        f"Stop Loss: {stop_text}"
    )

    lines.append(
        f"Take Profit: {tp_text} "
        f"({'L' if direction == 'Long' else 'S'}:{rr}R)"
    )

    lines.append("")

    lines.append(
        f"Major Level: {level_text}"
    )

    if news:
        lines.append("")
        lines.append(
            f"📰 {news}"
        )

    if technical:
        lines.append("")
        lines.append(
            technical
        )

    if market:
        lines.append("")
        lines.append(
            market
        )

    lines.append("")

    if direction == "Long":
        lines.append(
            f"Long ${coin} 👆"
        )
    else:
        lines.append(
            f"Short ${coin} 👇"
        )

    lines.append("")

    lines.append(
        " ".join(hashtags)
    )

    text = "\n".join(lines)

    # Respect Binance character limit.
    char_limit = getattr(
        cfg,
        "CHAR_LIMIT",
        2000,
    )

    if len(text) > char_limit:
        text = text[:char_limit].rstrip()

    return text
