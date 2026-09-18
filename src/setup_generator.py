"""
setup_generator.py

Generates Binance Square trade-setup posts using:

- RSI
- EMA9 / EMA21
- SMA50
- MACD
- Bollinger Bands
- Stochastic
- ADX
- ATR
- OBV
- Support / Resistance
- BTC market context
- Market breadth
- BTC Open Interest
- BTC Funding
- Multi-timeframe Support / Resistance
- BTC 4H / 1D trend
- Symbol Open Interest
- OI change
- Long/Short ratio
- Liquidation activity
- Order-book liquidity

The AI decides:
- Long / Short
- Entry range
- Title
- Analysis
- Relevant market context
- Relevant hashtags

SL and TP are calculated in code.
"""

import json
import random

from groq import Groq

from src import bot_config as cfg


SYSTEM_PROMPT = """
You are a professional crypto market analyst writing Binance Square
trade-setup posts.

Your writing must feel like a real human trader's market note,
not an AI-generated template.

CORE RULES
----------
- Analyze the complete technical data before choosing Long or Short.
- Never base the direction on one indicator alone.
- Compare multiple indicators and explain how they agree or conflict.
- Never invent missing data.
- If a data point is missing, simply ignore it.
- Do not tell readers to invest.
- Do not promise profit.
- Do not use guaranteed-profit language.
- Do not add disclaimers or warnings.
- Keep the post concise but informative.

TECHNICAL DATA
--------------
Consider when relevant:

- RSI
- EMA9
- EMA21
- SMA50
- MACD
- Bollinger Bands
- Stochastic
- ADX
- ATR
- OBV
- Support
- Resistance
- Current price
- 24H high / low

ADVANCED MARKET DATA
--------------------
When available, consider:

- 15M Support / Resistance
- 1H Support / Resistance
- 4H Support / Resistance
- 1D Support / Resistance
- 1W Support / Resistance
- BTC 4H trend
- BTC 1D trend
- Symbol Open Interest
- OI change
- Funding Rate
- Long / Short ratio
- Recent liquidation activity
- Order-book imbalance
- Bid / Ask liquidity

IMPORTANT:
Do NOT mention every metric in every post.

Choose only the information that is actually relevant to
the current setup.

MULTI-TIMEFRAME LEVELS
----------------------
Compare 15M, 1H, 4H, 1D and 1W levels when available.

Select the most important major Support/Resistance level.

Do NOT list every timeframe.

For example:

Major Level: 4H Support $0.2410 | 4H Resistance $0.2600

or:

Major Resistance: 1D $0.2600

or:

Key Support: 1H $0.2410

The timeframe must be included when a level is used.

BTC CONTEXT
-----------
Use BTC 4H and 1D trend as broader market context.

Also consider:
- BTC direction
- Market breadth
- BTC Open Interest
- BTC Funding

FUTURES DATA
------------
Open Interest must be interpreted together with price.

Funding Rate is contextual only.

Long/Short ratio is positioning context only.

Liquidations should only be mentioned when they are meaningful.

ORDER BOOK
----------
Order-book imbalance and nearby liquidity can be used when meaningful.

Do not claim that order-book liquidity guarantees price movement.

NEWS
----
If real news is provided:

- Include it briefly.
- Do not rewrite the headline into a fake event.
- Do not invent details.

If no real news exists:

- Do not mention news.
- Do not create a fake headline.

TITLE
-----
Create a unique, interesting title.

Maximum 12 words.

The title should describe the actual market situation.

Examples of style:

$DOGE Momentum Builds as Buyers Approach a Key Resistance Zone

$ZEC Buyers Regain Momentum Near a Major 4H Level

$FET Structure Improves as Momentum Turns Positive

Do NOT reuse the exact same title structure every time.

Avoid excessive hype.

ANALYSIS
--------
Write TWO short natural paragraphs.

Paragraph 1:
Explain the technical setup using actual indicator values.

Paragraph 2:
Explain the most relevant market context.

Use actual numbers when available.

Example style:

RSI is holding near 60, while EMA9 remains above EMA21 and MACD
stays positive. Price structure remains constructive as momentum
gradually strengthens toward the nearby resistance zone.

BTC remains bullish, with market breadth around 63% green.
BTC Open Interest is rising while Funding remains positive,
providing additional context for the current market structure.

Do not simply list indicators.

Explain the relationship between them.

POST STYLE
----------
The final post will use this structure:

$COIN TITLE

LONG SETUP — $COIN

Entry: ...
Stop Loss: ...
Take Profit: ...

Major Level: ...

📰 News headline.........

Technical analysis paragraph.

Market context paragraph.

Long $COIN 👆

#COIN #RelevantTag #RelevantTag #RelevantTag

For Short:

SHORT SETUP — $COIN

Short $COIN 👇

HASHTAGS
--------
Return exactly 4 hashtags.

Rules:

1. First hashtag must always be the coin.
2. Remaining three must match the actual coin,
   narrative, sector, or analysis.
3. Do not use irrelevant hashtags.
4. Change hashtags according to the coin and narrative.
5. Avoid repeating the exact same four hashtags when unnecessary.

OUTPUT
------
Return ONLY valid JSON.

Exactly this structure:

{
  "symbol": string,
  "direction": "Long" | "Short",
  "entry_low": number,
  "entry_high": number,
  "title": string,
  "analysis_technical": string,
  "analysis_market": string,
  "hashtags": [
    string,
    string,
    string,
    string
  ]
}

Do not return Markdown.
Do not return code fences.
Do not return explanations.
"""


def generate_setup(
    symbol: str,
    indicators: dict,
    news: dict | None = None,
    market_context: dict | None = None,
    advanced_market_data: dict | None = None,
) -> dict:

    client = Groq(
        api_key=cfg.GROQ_API_KEY
    )

    market_context = market_context or {}
    advanced_market_data = advanced_market_data or {}

    # ---------------------------------------------------------
    # NEWS
    # ---------------------------------------------------------

    if news:
        news_block = (
            f'Real recent news headline: '
            f'"{news["headline"]}"'
        )
    else:
        news_block = (
            "No relevant news found. "
            "Do not mention news."
        )

    # ---------------------------------------------------------
    # BASIC MARKET CONTEXT
    # ---------------------------------------------------------

    market_block = f"""
BTC 24h change:
{market_context.get("btc_change_24h")}

BTC direction:
{market_context.get("btc_direction", "Unknown")}

Market breadth:
{market_context.get("market_breadth", "Unknown")}

Market green:
{market_context.get("market_green_pct")}

Market red:
{market_context.get("market_red_pct")}

BTC Open Interest:
{market_context.get("btc_open_interest")}

BTC Funding Rate:
{market_context.get("btc_funding_rate")}
"""

    # ---------------------------------------------------------
    # ADVANCED DATA
    # ---------------------------------------------------------

    advanced_block = f"""
Multi-timeframe Support / Resistance:
{json.dumps(
    advanced_market_data.get(
        "multi_timeframe_sr"
    ),
    indent=2,
)}

BTC 4H / 1D Trend:
{json.dumps(
    advanced_market_data.get(
        "btc_context"
    ),
    indent=2,
)}

Symbol Open Interest:
{advanced_market_data.get(
    "open_interest"
)}

Symbol OI Change 1H:
{advanced_market_data.get(
    "oi_change_1h_pct"
)}%

Symbol Funding Rate:
{advanced_market_data.get(
    "funding_rate"
)}

Long / Short Ratio:
{json.dumps(
    advanced_market_data.get(
        "long_short_ratio"
    ),
    indent=2,
)}

Recent Liquidations:
{json.dumps(
    advanced_market_data.get(
        "liquidations"
    ),
    indent=2,
)}

Order-book Liquidity:
{json.dumps(
    advanced_market_data.get(
        "orderbook"
    ),
    indent=2,
)}
"""

    # ---------------------------------------------------------
    # USER PROMPT
    # ---------------------------------------------------------

    user_prompt = f"""
Analyze this crypto setup.

Symbol:
{symbol}

Current price:
{indicators["price"]}

Timeframe:
{cfg.KLINE_INTERVAL}

24H Approx High:
{indicators["high24Approx"]}

24H Approx Low:
{indicators["low24Approx"]}

RSI(14):
{indicators["rsi14"]}

EMA9:
{indicators["ema9"]}

EMA21:
{indicators["ema21"]}

SMA50:
{indicators["sma50"]}

EMA Trend:
{indicators["emaTrend"]}

MACD:
{json.dumps(
    indicators["macd"],
    indent=2
)}

Bollinger Bands:
{json.dumps(
    indicators["bollinger"],
    indent=2
)}

Stochastic:
{json.dumps(
    indicators["stochastic"],
    indent=2
)}

ADX(14):
{indicators["adx14"]}

ATR(14):
{indicators["atr14"]}

OBV Trend:
{indicators["obvTrend"]}

Current Support:
{indicators["support"]}

Current Resistance:
{indicators["resistance"]}

{news_block}

BASIC MARKET CONTEXT
--------------------
{market_block}

ADVANCED MARKET DATA
--------------------
{advanced_block}

Choose the most logical Long or Short setup from the
complete available data.

Do not blindly follow one indicator.

If indicators conflict, consider the conflict before
choosing the direction.

Return the required JSON only.
"""

    # ---------------------------------------------------------
    # GROQ
    # ---------------------------------------------------------

    completion = client.chat.completions.create(
        model=cfg.GROQ_MODEL,
        temperature=0.85,
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
    )

    raw = (
        completion
        .choices[0]
        .message
        .content
        or ""
    )

    cleaned = (
        raw
        .replace("```json", "")
        .replace("```", "")
        .strip()
    )

    try:
        setup = json.loads(
            cleaned
        )

    except json.JSONDecodeError as err:
        raise RuntimeError(
            f"Model did not return valid JSON "
            f"for {symbol}: {raw}"
        ) from err

    # ---------------------------------------------------------
    # BASIC VALIDATION
    # ---------------------------------------------------------

    required_fields = [
        "symbol",
        "direction",
        "entry_low",
        "entry_high",
        "title",
        "analysis_technical",
        "analysis_market",
        "hashtags",
    ]

    for field in required_fields:
        if field not in setup:
            raise RuntimeError(
                f"Missing field '{field}' "
                f"for {symbol}"
            )

    setup["symbol"] = symbol

    if setup["direction"] not in (
        "Long",
        "Short",
    ):
        setup["direction"] = "Long"

    # ---------------------------------------------------------
    # RISK / REWARD
    # ---------------------------------------------------------

    _apply_risk_reward(
        setup,
        indicators,
    )

    # ---------------------------------------------------------
    # EXTRA DATA
    # ---------------------------------------------------------

    setup["timeframe"] = (
        cfg.KLINE_INTERVAL.upper()
    )

    setup["support"] = indicators.get(
        "support"
    )

    setup["resistance"] = indicators.get(
        "resistance"
    )

    setup["news"] = news

    return setup


def _apply_risk_reward(
    setup: dict,
    indicators: dict,
) -> None:

    entry = (
        float(setup["entry_low"])
        + float(setup["entry_high"])
    ) / 2

    atr = float(
        indicators["atr14"]
    ) or (
        entry * 0.01
    )

    risk = (
        atr
        * cfg.ATR_MULTIPLIER
    )

    rr = random.choice(
        cfg.RISK_REWARD_CHOICES
    )

    reward = (
        risk * rr
    )

    if setup.get(
        "direction"
    ) == "Short":

        sl = entry + risk
        tp = entry - reward

    else:

        sl = entry - risk
        tp = entry + reward

    setup["sl"] = round(
        sl,
        8,
    )

    setup["tp"] = round(
        tp,
        8,
    )

    setup["risk_reward"] = rr


def format_post_text(
    setup: dict
) -> str:

    base = setup[
        "symbol"
    ].replace(
        "USDT",
        "",
    )

    direction = (
        "Short"
        if setup.get(
            "direction"
        ) == "Short"
        else "Long"
    )

    arrow = (
        "👇"
        if direction == "Short"
        else "👆"
    )

    entry_low = setup[
        "entry_low"
    ]

    entry_high = setup[
        "entry_high"
    ]

    title = setup[
        "title"
    ].strip()

    technical = setup[
        "analysis_technical"
    ].strip()

    market = setup[
        "analysis_market"
    ].strip()

    # ---------------------------------------------------------
    # SUPPORT / RESISTANCE
    # ---------------------------------------------------------

    sr_bits = []

    if setup.get(
        "support"
    ) is not None:

        sr_bits.append(
            f"Support ${setup['support']}"
        )

    if setup.get(
        "resistance"
    ) is not None:

        sr_bits.append(
            f"Resistance ${setup['resistance']}"
        )

    sr_line = " | ".join(
        sr_bits
    )

    # ---------------------------------------------------------
    # NEWS
    # ---------------------------------------------------------

    news = setup.get(
        "news"
    )

    news_line = None

    if news:
        headline = news.get(
            "headline"
        )

        if headline:
            news_line = (
                f"📰 {headline}"
            )

    # ---------------------------------------------------------
    # HASHTAGS
    # ---------------------------------------------------------

    hashtags = setup.get(
        "hashtags",
        [],
    )

    clean_hashtags = []

    for tag in hashtags:

        tag = str(
            tag
        ).strip()

        if not tag:
            continue

        if not tag.startswith("#"):
            tag = "#" + tag

        if tag not in clean_hashtags:
            clean_hashtags.append(
                tag
            )

    # Always make sure the coin
    # hashtag exists.

    coin_tag = (
        f"#{base}"
    )

    if coin_tag not in clean_hashtags:
        clean_hashtags.insert(
            0,
            coin_tag
        )

    clean_hashtags = clean_hashtags[
        :4
    ]

    # ---------------------------------------------------------
    # POST
    # ---------------------------------------------------------

    lines = [
        f"${base} {title}",
        "",
        f"{direction.upper()} SETUP — ${base}",
        "",
        (
            f"Entry: "
            f"${entry_low}–${entry_high}"
        ),
        (
            f"Stop Loss: "
            f"${setup['sl']}"
        ),
        (
            f"Take Profit: "
            f"${setup['tp']} "
            f"({direction[0]}:"
            f"{setup['risk_reward']}R)"
        ),
    ]

    if sr_line:
        lines += [
            "",
            f"Major Level: {sr_line}",
        ]

    if news_line:
        lines += [
            "",
            news_line,
        ]

    lines += [
        "",
        technical,
        "",
        market,
        "",
        f"{direction} ${base} {arrow}",
        "",
        " ".join(
            clean_hashtags
        ),
    ]

    return "\n".join(
        lines
    )
