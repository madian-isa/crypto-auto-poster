"""
setup_generator.py

Generates concise Binance Square crypto market-analysis posts.

Data sources:
- Technical indicators
- Binance advanced market data
- CoinGlass market data
- BTC market context
- Relevant news

Design:
- Professional crypto-analysis style
- No direct investment language
- No guaranteed-profit claims
- No fabricated data/news
- LONG/SHORT setup formatting preserved
- Exactly 1:2 risk/reward
- Minimum 3.5% stop-loss distance
- CoinGlass is optional
- CoinGlass failure never stops setup generation
"""

import json
import os
import re
import time

import requests


# ============================================================
# CONFIG
# ============================================================

try:
    from src import bot_config as cfg
except Exception:
    cfg = None


GROQ_API_KEY = (
    getattr(
        cfg,
        "GROQ_API_KEY",
        "",
    )
    if cfg
    else os.environ.get(
        "GROQ_API_KEY",
        "",
    )
)

GROQ_MODEL = (
    getattr(
        cfg,
        "GROQ_MODEL",
        "openai/gpt-oss-120b",
    )
    if cfg
    else os.environ.get(
        "GROQ_MODEL",
        "openai/gpt-oss-120b",
    )
)


GROQ_URL = (
    "https://api.groq.com/openai/v1/chat/completions"
)


# ============================================================
# TITLE LIBRARY
# ============================================================

LONG_TITLES = [
    "$COIN Momentum Is Building — What the Market Structure Shows",
    "$COIN Buyers Are Stepping In — Key Levels to Watch",
    "$COIN Is Holding Strong — The Next Market Test Matters",
    "$COIN Market Structure Turns Constructive — Key Levels Ahead",
    "$COIN Demand Is Picking Up — Here’s What to Watch",
    "$COIN Reclaims Key Ground — Market Structure in Focus",
    "$COIN Pushes Higher — Volume and Structure Tell the Story",
    "$COIN Strength Returns — The Important Levels Are Clear",
    "$COIN Buyers Defend Support — Momentum Enters Focus",
    "$COIN Builds a Stronger Structure — What Comes Next?",
    "$COIN Shows Relative Strength — Key Technical Levels",
    "$COIN Momentum Improves — The Market Is Testing Resistance",
    "$COIN Holds Its Structure — Buyers Face the Next Barrier",
    "$COIN Recovery Gains Attention — Volume Becomes Important",
    "$COIN Moves Back Into Focus — Structure vs Resistance",
    "$COIN Demand Strengthens — Watching the Next Break",
    "$COIN Technical Structure Improves — Levels That Matter",
    "$COIN Attempts a Recovery — Market Data Under the Lens",
    "$COIN Buyers Gain Control — But Resistance Still Matters",
    "$COIN Setup Develops — Momentum Meets Key Resistance",
    "$COIN Strength Builds — OI, Volume and Price in Focus",
    "$COIN Market Momentum Improves — What the Data Shows",
    "$COIN Holds Buyers’ Zone — The Next Move Depends on Resistance",
    "$COIN Structure Is Improving — Here Are the Levels to Watch",
    "$COIN Starts Showing Strength — Market Data Gives Context",
]


SHORT_TITLES = [
    "$COIN Momentum Weakens — Key Support Is Now in Focus",
    "$COIN Sellers Step In — The Market Structure Matters",
    "$COIN Faces Selling Pressure — Levels to Watch Next",
    "$COIN Loses Momentum — Support Becomes the Main Test",
    "$COIN Structure Turns Weaker — What the Market Data Shows",
    "$COIN Rejection Gains Attention — Key Levels Ahead",
    "$COIN Buyers Lose Control — Resistance Continues to Hold",
    "$COIN Selling Pressure Builds — Volume and OI in Focus",
    "$COIN Drops From Resistance — The Next Support Matters",
    "$COIN Momentum Fades — Market Structure Under Pressure",
    "$COIN Struggles at Resistance — Sellers Remain Active",
    "$COIN Weakness Appears — Key Support Could Decide the Next Move",
    "$COIN Faces a Technical Breakdown Risk — Levels to Watch",
    "$COIN Market Structure Deteriorates — Data Under the Lens",
    "$COIN Rejection Continues — Buyers Need to Defend Support",
    "$COIN Loses Key Ground — Momentum Becomes the Main Question",
    "$COIN Selling Activity Increases — Watch the Next Support",
    "$COIN Attempts to Break Down — Market Structure in Focus",
    "$COIN Weakens Below Resistance — What Comes Next?",
    "$COIN Bears Gain Momentum — But Support Still Matters",
    "$COIN Pressure Builds — OI, Volume and Price in Focus",
    "$COIN Struggles to Recover — The Market Is Testing Support",
    "$COIN Downside Momentum Develops — Key Levels Ahead",
    "$COIN Sellers Gain Ground — Technical Data Turns Cautious",
    "$COIN Faces Increasing Pressure — Structure vs Support",
]


# ============================================================
# PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are a professional crypto market analyst writing a concise
Binance Square market-analysis post.

Your job is to analyze supplied market data only.

IMPORTANT:
- Never invent data.
- Never invent news.
- Never claim certainty.
- Never promise profit.
- Never tell readers to invest.
- Never use guaranteed-profit language.
- Do not use emojis.
- Do not use hashtags.
- Do not use NFA/DYOR filler.
- Do not describe a setup as guaranteed, confirmed,
  certain, imminent or high probability.
- Treat CoinGlass data as market context/confirmation,
  not as proof of future price direction.
- If CoinGlass data conflicts with technical structure,
  explicitly acknowledge the conflict.
- Use 1H and 4H structure where supplied.
- Prefer meaningful swing levels over tiny intraday noise.
- Use supplied news only.
- Keep the writing natural and human.

The setup is an analytical scenario, not an instruction
to place a trade.

Return valid JSON only.
"""


# ============================================================
# HELPERS
# ============================================================

def _safe_float(value):
    try:
        return float(value)
    except Exception:
        return None


def _clean_text(value):
    if value is None:
        return ""

    text = str(
        value
    ).strip()

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text


def _round_price(value):
    value = _safe_float(
        value
    )

    if value is None:
        return None

    if value >= 1000:
        return round(
            value,
            2,
        )

    if value >= 1:
        return round(
            value,
            4,
        )

    if value >= 0.01:
        return round(
            value,
            6,
        )

    return round(
        value,
        8,
    )


def _coin_name(symbol):
    symbol = str(
        symbol or ""
    ).upper()

    for suffix in (
        "USDT",
        "USDC",
        "BUSD",
        "FDUSD",
    ):

        if symbol.endswith(
            suffix
        ):

            return symbol[
                :-len(suffix)
            ]

    return symbol


# ============================================================
# INDICATOR SUMMARY
# ============================================================

def _build_indicator_summary(
    indicators,
):
    if not isinstance(
        indicators,
        dict,
    ):
        return {}

    keys = [
        "price",
        "current_price",

        "rsi",

        "ema21",
        "ema50",
        "ema200",

        "sma50",

        "ema_structure",

        "macd",
        "macd_signal",
        "macd_histogram",

        "bollinger_upper",
        "bollinger_middle",
        "bollinger_lower",

        "stochastic_k",
        "stochastic_d",

        "adx",

        "atr",

        "volume",
        "volume_change",

        "obv",

        "high_24h",
        "low_24h",

        "support",
        "resistance",
    ]

    summary = {}

    for key in keys:

        if key in indicators:

            summary[key] = indicators.get(
                key
            )

    return summary


# ============================================================
# BINANCE ADVANCED DATA
# ============================================================

def _build_advanced_summary(
    advanced,
):
    if not isinstance(
        advanced,
        dict,
    ):
        return {}

    result = {}

    # --------------------------------------------------------
    # Source status
    # --------------------------------------------------------

    if advanced.get(
        "source_status"
    ):

        result[
            "source_status"
        ] = advanced.get(
            "source_status"
        )

    # --------------------------------------------------------
    # S/R
    # --------------------------------------------------------

    sr = advanced.get(
        "multi_timeframe_sr"
    )

    if isinstance(
        sr,
        dict,
    ):

        result[
            "multi_timeframe_sr"
        ] = sr

    # --------------------------------------------------------
    # BTC context
    # --------------------------------------------------------

    btc = advanced.get(
        "btc_context"
    )

    if isinstance(
        btc,
        dict,
    ):

        result[
            "btc_context"
        ] = btc

    # --------------------------------------------------------
    # Futures data
    # --------------------------------------------------------

    for key in (
        "open_interest",
        "oi_change_1h_pct",
        "funding_rate",
        "long_short_ratio",
        "liquidations",
        "orderbook",
    ):

        value = advanced.get(
            key
        )

        if value is not None:

            result[
                key
            ] = value

    return result


# ============================================================
# COINGLASS SUMMARY
# ============================================================

def _build_coinglass_summary(
    coinglass,
):
    """
    Keep CoinGlass separate from Binance advanced data.

    Only useful values are forwarded to the AI.
    """

    if not isinstance(
        coinglass,
        dict,
    ):
        return {}

    result = {
        "source": "CoinGlass",
    }

    status = coinglass.get(
        "source_status"
    )

    if status:

        result[
            "source_status"
        ] = status

    # --------------------------------------------------------
    # Open interest
    # --------------------------------------------------------

    oi = coinglass.get(
        "open_interest"
    )

    if isinstance(
        oi,
        dict,
    ):

        result[
            "open_interest"
        ] = oi

    # --------------------------------------------------------
    # Funding
    # --------------------------------------------------------

    funding = coinglass.get(
        "funding_rate"
    )

    if isinstance(
        funding,
        dict,
    ):

        result[
            "funding_rate"
        ] = funding

    # --------------------------------------------------------
    # Long / short
    # --------------------------------------------------------

    ls = coinglass.get(
        "long_short_ratio"
    )

    if isinstance(
        ls,
        dict,
    ):

        result[
            "long_short_ratio"
        ] = ls

    # --------------------------------------------------------
    # Liquidations
    # --------------------------------------------------------

    liquidations = coinglass.get(
        "liquidations"
    )

    if isinstance(
        liquidations,
        dict,
    ):

        result[
            "liquidations"
        ] = liquidations

    # --------------------------------------------------------
    # Taker flow
    # --------------------------------------------------------

    taker = coinglass.get(
        "taker_buy_sell"
    )

    if isinstance(
        taker,
        dict,
    ):

        result[
            "taker_buy_sell"
        ] = taker

    # --------------------------------------------------------
    # CVD
    # --------------------------------------------------------

    cvd = coinglass.get(
        "cvd"
    )

    if isinstance(
        cvd,
        dict,
    ):

        result[
            "cvd"
        ] = cvd

    return result


# ============================================================
# LEVEL SELECTION
# ============================================================

def _select_major_levels(
    indicators,
    advanced,
):
    """
    Prefer 4H/1H structural levels when available.
    """

    support = None
    resistance = None

    # --------------------------------------------------------
    # Advanced S/R
    # --------------------------------------------------------

    sr = {}

    if isinstance(
        advanced,
        dict,
    ):

        sr = advanced.get(
            "multi_timeframe_sr",
            {},
        )

    if isinstance(
        sr,
        dict,
    ):

        # Prefer 4H if supplied by another version.
        for timeframe in (
            "4h",
            "1h",
        ):

            levels = sr.get(
                timeframe
            )

            if not isinstance(
                levels,
                dict,
            ):
                continue

            if support is None:

                support = _safe_float(
                    levels.get(
                        "support"
                    )
                )

            if resistance is None:

                resistance = _safe_float(
                    levels.get(
                        "resistance"
                    )
                )

    # --------------------------------------------------------
    # Indicator fallback
    # --------------------------------------------------------

    if support is None:

        support = _safe_float(
            indicators.get(
                "support"
            )
        )

    if resistance is None:

        resistance = _safe_float(
            indicators.get(
                "resistance"
            )
        )

    return {
        "support": _round_price(
            support
        ),
        "resistance": _round_price(
            resistance
        ),
    }


# ============================================================
# COINGLASS SIGNAL CONTEXT
# ============================================================

def _coinglass_direction_context(
    coinglass,
):
    """
    Convert CoinGlass data into a cautious directional
    context.

    This is NOT used as a standalone signal.

    Returns:
        bullish
        bearish
        mixed
        unavailable
    """

    if not isinstance(
        coinglass,
        dict,
    ):
        return "unavailable"

    scores = []

    # --------------------------------------------------------
    # OI
    # --------------------------------------------------------

    oi = coinglass.get(
        "open_interest"
    )

    if isinstance(
        oi,
        dict,
    ):

        oi_change = _safe_float(
            oi.get(
                "oi_change_1h_pct"
            )
        )

        if oi_change is not None:

            if oi_change > 1:
                scores.append(
                    1
                )

            elif oi_change < -1:
                scores.append(
                    -1
                )

    # --------------------------------------------------------
    # Long / short
    # --------------------------------------------------------

    ls = coinglass.get(
        "long_short_ratio"
    )

    if isinstance(
        ls,
        dict,
    ):

        ratio = _safe_float(
            ls.get(
                "ratio"
            )
        )

        if ratio is not None:

            if ratio > 1.05:
                scores.append(
                    1
                )

            elif ratio < 0.95:
                scores.append(
                    -1
                )

    # --------------------------------------------------------
    # Taker flow
    # --------------------------------------------------------

    taker = coinglass.get(
        "taker_buy_sell"
    )

    if isinstance(
        taker,
        dict,
    ):

        ratio = _safe_float(
            taker.get(
                "buy_sell_ratio"
            )
        )

        if ratio is not None:

            if ratio > 1.05:
                scores.append(
                    1
                )

            elif ratio < 0.95:
                scores.append(
                    -1
                )

    # --------------------------------------------------------
    # CVD
    # --------------------------------------------------------

    cvd = coinglass.get(
        "cvd"
    )

    if isinstance(
        cvd,
        dict,
    ):

        value = _safe_float(
            cvd.get(
                "cum_vol_delta"
            )
        )

        if value is not None:

            if value > 0:
                scores.append(
                    1
                )

            elif value < 0:
                scores.append(
                    -1
                )

    if not scores:

        return "unavailable"

    total = sum(
        scores
    )

    if total >= 2:

        return "bullish"

    if total <= -2:

        return "bearish"

    return "mixed"


# ============================================================
# FALLBACK DIRECTION
# ============================================================

def _fallback_direction(
    indicators,
    advanced=None,
    coinglass=None,
):
    """
    Deterministic fallback direction.

    CoinGlass acts as confirmation, not as the sole driver.
    """

    score = 0.0

    # --------------------------------------------------------
    # RSI
    # --------------------------------------------------------

    rsi = _safe_float(
        indicators.get(
            "rsi"
        )
    )

    if rsi is not None:

        if rsi >= 55:
            score += 1

        elif rsi <= 45:
            score -= 1


    # --------------------------------------------------------
    # EMA structure
    # --------------------------------------------------------

    price = _safe_float(
        indicators.get(
            "price",
            indicators.get(
                "current_price"
            ),
        )
    )

    ema21 = _safe_float(
        indicators.get(
            "ema21"
        )
    )

    ema50 = _safe_float(
        indicators.get(
            "ema50"
        )
    )

    ema200 = _safe_float(
        indicators.get(
            "ema200"
        )
    )

    if (
        price is not None
        and ema21 is not None
        and ema50 is not None
    ):

        if (
            price > ema21
            and ema21 > ema50
        ):

            score += 1

        elif (
            price < ema21
            and ema21 < ema50
        ):

            score -= 1

    if (
        price is not None
        and ema200 is not None
    ):

        if price > ema200:
            score += 0.5

        elif price < ema200:
            score -= 0.5


    # --------------------------------------------------------
    # MACD
    # --------------------------------------------------------

    macd_hist = _safe_float(
        indicators.get(
            "macd_histogram"
        )
    )

    if macd_hist is not None:

        if macd_hist > 0:
            score += 1

        elif macd_hist < 0:
            score -= 1


    # --------------------------------------------------------
    # Stochastic
    # --------------------------------------------------------

    stochastic_k = _safe_float(
        indicators.get(
            "stochastic_k"
        )
    )

    if stochastic_k is not None:

        if stochastic_k > 55:
            score += 0.5

        elif stochastic_k < 45:
            score -= 0.5


    # --------------------------------------------------------
    # Volume
    # --------------------------------------------------------

    volume_change = _safe_float(
        indicators.get(
            "volume_change"
        )
    )

    if volume_change is not None:

        if volume_change > 10:
            score += 0.5

        elif volume_change < -10:
            score -= 0.5


    # --------------------------------------------------------
    # Binance OI
    # --------------------------------------------------------

    if isinstance(
        advanced,
        dict,
    ):

        oi_change = _safe_float(
            advanced.get(
                "oi_change_1h_pct"
            )
        )

        if oi_change is not None:

            if oi_change > 1:
                score += 0.5

            elif oi_change < -1:
                score -= 0.5


        # ----------------------------------------------------
        # Funding
        # ----------------------------------------------------

        funding = _safe_float(
            advanced.get(
                "funding_rate"
            )
        )

        if funding is not None:

            # Very positive funding can indicate
            # crowded longs, so don't automatically
            # treat positive funding as bullish.

            if funding > 0.001:
                score -= 0.25

            elif funding < -0.001:
                score += 0.25


    # --------------------------------------------------------
    # CoinGlass confirmation
    # --------------------------------------------------------

    cg_context = (
        _coinglass_direction_context(
            coinglass
        )
    )

    if cg_context == "bullish":

        score += 0.75

    elif cg_context == "bearish":

        score -= 0.75


    # --------------------------------------------------------
    # Final
    # --------------------------------------------------------

    if score >= 0:

        return "LONG"

    return "SHORT"


# ============================================================
# FALLBACK ENTRY
# ============================================================

def _fallback_entry(
    indicators,
    major_levels,
):
    price = _safe_float(
        indicators.get(
            "price",
            indicators.get(
                "current_price"
            ),
        )
    )

    support = _safe_float(
        major_levels.get(
            "support"
        )
    )

    resistance = _safe_float(
        major_levels.get(
            "resistance"
        )
    )

    if price is None:

        return None

    # Prefer current market price.
    # Structural levels are used only when
    # reasonably close to price.

    if support is not None:

        distance = (
            abs(
                price - support
            )
            / price
        ) * 100

        if distance <= 8:

            lower = min(
                price,
                support,
            )

            upper = max(
                price,
                support,
            )

            return [
                _round_price(
                    lower
                ),
                _round_price(
                    upper
                ),
            ]

    if resistance is not None:

        distance = (
            abs(
                resistance - price
            )
            / price
        ) * 100

        if distance <= 8:

            lower = min(
                price,
                resistance,
            )

            upper = max(
                price,
                resistance,
            )

            return [
                _round_price(
                    lower
                ),
                _round_price(
                    upper
                ),
            ]

    return [
        _round_price(
            price * 0.995
        ),
        _round_price(
            price * 1.005
        ),
    ]


# ============================================================
# FALLBACK RISK LEVELS
# ============================================================

def _fallback_risk_levels(
    entry,
    direction,
    major_levels,
):
    """
    Minimum 3.5% stop distance.
    Exact 1:2 RR.
    """

    if not entry:

        return None, None

    direction = str(
        direction
    ).upper()

    if isinstance(
        entry,
        (list, tuple),
    ):

        entry_low = _safe_float(
            entry[0]
        )

        entry_high = _safe_float(
            entry[1]
        )

        if (
            entry_low is None
            or entry_high is None
        ):
            return None, None

        entry_price = (
            entry_low
            + entry_high
        ) / 2

    else:

        entry_price = _safe_float(
            entry
        )

    if entry_price is None:

        return None, None

    support = _safe_float(
        major_levels.get(
            "support"
        )
    )

    resistance = _safe_float(
        major_levels.get(
            "resistance"
        )
    )

    minimum_risk = (
        entry_price * 0.035
    )

    if direction == "LONG":

        structural_sl = None

        if (
            support is not None
            and support < entry_price
        ):

            structural_sl = (
                support * 0.995
            )

        if structural_sl is not None:

            risk = (
                entry_price
                - structural_sl
            )

            if risk >= minimum_risk:

                stop_loss = (
                    structural_sl
                )

            else:

                stop_loss = (
                    entry_price
                    - minimum_risk
                )

        else:

            stop_loss = (
                entry_price
                - minimum_risk
            )

        risk = (
            entry_price
            - stop_loss
        )

        take_profit = (
            entry_price
            + (risk * 2)
        )

    else:

        structural_sl = None

        if (
            resistance is not None
            and resistance > entry_price
        ):

            structural_sl = (
                resistance * 1.005
            )

        if structural_sl is not None:

            risk = (
                structural_sl
                - entry_price
            )

            if risk >= minimum_risk:

                stop_loss = (
                    structural_sl
                )

            else:

                stop_loss = (
                    entry_price
                    + minimum_risk
                )

        else:

            stop_loss = (
                entry_price
                + minimum_risk
            )

        risk = (
            stop_loss
            - entry_price
        )

        take_profit = (
            entry_price
            - (risk * 2)
        )

    return (
        _round_price(
            stop_loss
        ),
        _round_price(
            take_profit
        ),
    )


# ============================================================
# FALLBACK MARKET CONTEXT
# ============================================================

def _fallback_market_context(
    advanced,
    coinglass=None,
):
    parts = []

    if isinstance(
        advanced,
        dict,
    ):

        btc = advanced.get(
            "btc_context"
        )

        if isinstance(
            btc,
            dict,
        ):

            for timeframe in (
                "4h",
                "1d",
            ):

                context = btc.get(
                    timeframe
                )

                if not isinstance(
                    context,
                    dict,
                ):
                    continue

                trend = context.get(
                    "trend"
                )

                if trend:

                    parts.append(
                        f"BTC {timeframe} trend: "
                        f"{trend}"
                    )


    cg_context = (
        _coinglass_direction_context(
            coinglass
        )
    )

    if cg_context != "unavailable":

        parts.append(
            "CoinGlass derivatives context: "
            f"{cg_context}"
        )

    return " | ".join(
        parts
    )


# ============================================================
# PYTHON FALLBACK
# ============================================================

def _python_fallback_setup(
    symbol,
    indicators,
    news=None,
    market_context=None,
    advanced_market_data=None,
    coinglass_market_data=None,
):
    direction = _fallback_direction(
        indicators,
        advanced_market_data,
        coinglass_market_data,
    )

    major_levels = _select_major_levels(
        indicators,
        advanced_market_data,
    )

    entry = _fallback_entry(
        indicators,
        major_levels,
    )

    stop_loss, take_profit = (
        _fallback_risk_levels(
            entry,
            direction,
            major_levels,
        )
    )

    if direction == "LONG":

        title = (
            f"${_coin_name(symbol)} "
            "Market Structure Is Improving"
        )

    else:

        title = (
            f"${_coin_name(symbol)} "
            "Market Structure Faces Pressure"
        )

    technical_parts = []

    rsi = _safe_float(
        indicators.get(
            "rsi"
        )
    )

    if rsi is not None:

        technical_parts.append(
            f"RSI {rsi:.1f}"
        )

    ema_structure = indicators.get(
        "ema_structure"
    )

    if ema_structure:

        technical_parts.append(
            f"EMA structure: "
            f"{ema_structure}"
        )

    volume_change = _safe_float(
        indicators.get(
            "volume_change"
        )
    )

    if volume_change is not None:

        technical_parts.append(
            f"volume {volume_change:+.1f}%"
        )

    cg_context = (
        _coinglass_direction_context(
            coinglass_market_data
        )
    )

    if cg_context != "unavailable":

        technical_parts.append(
            f"CoinGlass context: "
            f"{cg_context}"
        )

    technical_analysis = (
        "; ".join(
            technical_parts
        )
        if technical_parts
        else
        "Technical and derivatives data are mixed."
    )

    setup = {
        "symbol": symbol.upper(),

        "direction": direction,

        "entry": entry,

        "stop_loss": stop_loss,

        "take_profit": take_profit,

        "risk_reward": "1:2",

        "title": title,

        "key_levels": major_levels,

        "technical_analysis":
            technical_analysis,

        "news": news,

        "market_context":
            market_context
            or _fallback_market_context(
                advanced_market_data,
                coinglass_market_data,
            ),

        "coin_mentions": 3,
    }

    return setup


# ============================================================
# TITLE SELECTION
# ============================================================

def _title_index(
    symbol,
):
    """
    Deterministic title rotation.
    """

    value = sum(
        ord(char)
        for char in str(
            symbol or ""
        ).upper()
    )

    return value


def _select_title(
    symbol,
    direction,
):
    titles = (
        LONG_TITLES
        if direction == "LONG"
        else SHORT_TITLES
    )

    if not titles:

        return (
            f"${_coin_name(symbol)} "
            "Market Analysis"
        )

    index = (
        _title_index(
            symbol
        )
        % len(titles)
    )

    return titles[
        index
    ].replace(
        "$COIN",
        f"${_coin_name(symbol)}",
    )


# ============================================================
# GROQ
# ============================================================

def _call_groq(
    prompt,
):
    if not GROQ_API_KEY:

        print(
            "[setup_generator] "
            "GROQ_API_KEY not configured."
        )

        return None

    headers = {
        "Authorization":
            f"Bearer {GROQ_API_KEY}",

        "Content-Type":
            "application/json",
    }

    payload = {
        "model": GROQ_MODEL,

        "temperature": 0.25,

        "max_tokens": 900,

        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
    }

    try:

        response = requests.post(
            GROQ_URL,
            headers=headers,
            json=payload,
            timeout=30,
        )

        response.raise_for_status()

        data = response.json()

        choices = data.get(
            "choices",
            [],
        )

        if not choices:

            return None

        message = choices[0].get(
            "message",
            {},
        )

        content = message.get(
            "content"
        )

        if not content:

            return None

        return content

    except Exception as err:

        print(
            "[setup_generator] "
            f"Groq request failed: {err}"
        )

        return None


# ============================================================
# JSON EXTRACTION
# ============================================================

def _extract_json(
    text,
):
    if not text:

        return None

    text = text.strip()

    # --------------------------------------------------------
    # Direct JSON
    # --------------------------------------------------------

    try:

        return json.loads(
            text
        )

    except Exception:

        pass


    # --------------------------------------------------------
    # Markdown code block
    # --------------------------------------------------------

    match = re.search(
        r"```(?:json)?\s*(.*?)\s*```",
        text,
        flags=re.DOTALL,
    )

    if match:

        try:

            return json.loads(
                match.group(1)
            )

        except Exception:

            pass


    # --------------------------------------------------------
    # First object
    # --------------------------------------------------------

    start = text.find(
        "{"
    )

    end = text.rfind(
        "}"
    )

    if (
        start >= 0
        and end > start
    ):

        try:

            return json.loads(
                text[
                    start:end + 1
                ]
            )

        except Exception:

            return None

    return None


# ============================================================
# VALIDATION
# ============================================================

def _validate_setup(
    setup,
    symbol,
):
    if not isinstance(
        setup,
        dict,
    ):

        return False

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

        return False

    entry = setup.get(
        "entry"
    )

    stop_loss = _safe_float(
        setup.get(
            "stop_loss"
        )
    )

    take_profit = _safe_float(
        setup.get(
            "take_profit"
        )
    )

    if (
        entry is None
        or stop_loss is None
        or take_profit is None
    ):

        return False

    if isinstance(
        entry,
        (list, tuple),
    ):

        if len(entry) < 2:

            return False

        entry_low = _safe_float(
            entry[0]
        )

        entry_high = _safe_float(
            entry[1]
        )

        if (
            entry_low is None
            or entry_high is None
        ):

            return False

        entry_price = (
            entry_low
            + entry_high
        ) / 2

    else:

        entry_price = _safe_float(
            entry
        )

    if entry_price is None:

        return False

    # --------------------------------------------------------
    # Direction validity
    # --------------------------------------------------------

    if direction == "LONG":

        if not (
            stop_loss
            < entry_price
            < take_profit
        ):

            return False

    else:

        if not (
            take_profit
            < entry_price
            < stop_loss
        ):

            return False

    # --------------------------------------------------------
    # Minimum 3.5% stop distance
    # --------------------------------------------------------

    stop_distance = (
        abs(
            entry_price
            - stop_loss
        )
        / entry_price
    ) * 100

    if stop_distance < 3.5:

        return False

    # --------------------------------------------------------
    # Exact 1:2 RR
    # --------------------------------------------------------

    risk = abs(
        entry_price
        - stop_loss
    )

    reward = abs(
        take_profit
        - entry_price
    )

    if risk <= 0:

        return False

    rr = reward / risk

    if abs(
        rr - 2
    ) > 0.05:

        return False

    return True


# ============================================================
# CLEAN COIN MENTIONS
# ============================================================

def _ensure_coin_mentions(
    text,
    symbol,
):
    coin = _coin_name(
        symbol
    )

    token = f"${coin}"

    text = str(
        text or ""
    )

    # Remove existing variants first.
    text = re.sub(
        rf"\${re.escape(coin)}\b",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    # Exactly 3 mentions.
    text = (
        text
        + f" {token} {token} {token}"
    )

    return text.strip()


# ============================================================
# GENERATE SETUP
# ============================================================

def generate_setup(
    symbol,
    indicators,
    news=None,
    market_context=None,
    advanced_market_data=None,
    coinglass_market_data=None,
):
    """
    Main setup generator.

    New argument:
        coinglass_market_data

    Existing arguments remain compatible.
    """

    symbol = str(
        symbol or ""
    ).upper().strip()


    # ========================================================
    # SUMMARIES
    # ========================================================

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

    coinglass_summary = (
        _build_coinglass_summary(
            coinglass_market_data
        )
    )

    major_levels = (
        _select_major_levels(
            indicators,
            advanced_market_data,
        )
    )


    # ========================================================
    # FALLBACK FIRST DIRECTION
    # ========================================================

    fallback_direction = (
        _fallback_direction(
            indicators,
            advanced_market_data,
            coinglass_market_data,
        )
    )

    fallback_title = _select_title(
        symbol,
        fallback_direction,
    )


    # ========================================================
    # PROMPT DATA
    # ========================================================

    prompt_data = {
        "symbol": symbol,

        "technical_indicators":
            indicator_summary,

        "major_levels":
            major_levels,

        "binance_advanced_market_data":
            advanced_summary,

        "coinglass_market_data":
            coinglass_summary,

        "market_context":
            market_context,

        "relevant_news":
            news,
    }


    # ========================================================
    # AI PROMPT
    # ========================================================

    prompt = f"""
Analyze the following crypto market data.

{json.dumps(
    prompt_data,
    ensure_ascii=False,
    default=str,
    indent=2,
)}

Create one concise market-analysis setup.

Requirements:

1. Choose LONG or SHORT from the supplied data.

2. Do not use CoinGlass as a standalone signal.

3. Use CoinGlass as confirmation/context:
   - Open Interest
   - OI change
   - Funding
   - Long/Short ratio
   - Liquidations
   - Taker flow
   - CVD

4. If Binance and CoinGlass derivatives data disagree,
   do not hide the disagreement. Mention the conflict
   briefly in technical_analysis.

5. Entry must be a realistic range around current market
   structure.

6. Stop loss must be at least 3.5% away from the midpoint
   entry.

7. Take profit must produce exactly 1:2 risk/reward.

8. Use meaningful 1H/4H structural support/resistance
   where available.

9. Use supplied news only.

10. Do not invent missing data.

11. Do not say:
    guaranteed
    confirmed
    certain
    high probability
    imminent
    risk-free
    easy profit
    smart money is definitely buying/selling

12. Return ONLY JSON in this structure:

{{
  "direction": "LONG or SHORT",
  "entry": [number, number],
  "stop_loss": number,
  "take_profit": number,
  "title": "title",
  "key_levels": {{
    "support": number or null,
    "resistance": number or null
  }},
  "technical_analysis": "short analysis",
  "news": "short relevant news context or empty string",
  "market_context": "short market context or empty string"
}}

A suitable title direction is:
{fallback_title}
"""


    # ========================================================
    # GROQ
    # ========================================================

    raw = _call_groq(
        prompt
    )

    setup = _extract_json(
        raw
    )


    # ========================================================
    # FALLBACK
    # ========================================================

    if not _validate_setup(
        setup,
        symbol,
    ):

        print(
            "[setup_generator] "
            "Groq setup invalid or unavailable. "
            "Using Python fallback."
        )

        setup = (
            _python_fallback_setup(
                symbol,
                indicators,
                news,
                market_context,
                advanced_market_data,
                coinglass_market_data,
            )
        )


    # ========================================================
    # NORMALIZE
    # ========================================================

    setup[
        "symbol"
    ] = symbol

    setup[
        "direction"
    ] = str(
        setup.get(
            "direction",
            fallback_direction,
        )
    ).upper().strip()


    # --------------------------------------------------------
    # Title
    # --------------------------------------------------------

    setup[
        "title"
    ] = _select_title(
        symbol,
        setup[
            "direction"
        ],
    )


    # --------------------------------------------------------
    # Levels
    # --------------------------------------------------------

    levels = setup.get(
        "key_levels"
    )

    if not isinstance(
        levels,
        dict,
    ):

        levels = {}

    levels[
        "support"
    ] = _round_price(
        levels.get(
            "support",
            major_levels.get(
                "support"
            ),
        )
    )

    levels[
        "resistance"
    ] = _round_price(
        levels.get(
            "resistance",
            major_levels.get(
                "resistance"
            ),
        )
    )

    setup[
        "key_levels"
    ] = levels


    # --------------------------------------------------------
    # RR
    # --------------------------------------------------------

    setup[
        "risk_reward"
    ] = "1:2"


    # --------------------------------------------------------
    # CoinGlass context
    # --------------------------------------------------------

    cg_context = (
        _coinglass_direction_context(
            coinglass_market_data
        )
    )

    if cg_context != "unavailable":

        existing_context = _clean_text(
            setup.get(
                "market_context"
            )
        )

        cg_note = (
            "CoinGlass derivatives context: "
            f"{cg_context}."
        )

        if existing_context:

            setup[
                "market_context"
            ] = (
                existing_context
                + " "
                + cg_note
            )

        else:

            setup[
                "market_context"
            ] = cg_note


    # --------------------------------------------------------
    # Technical analysis
    # --------------------------------------------------------

    setup[
        "technical_analysis"
    ] = _clean_text(
        setup.get(
            "technical_analysis",
            "",
        )
    )


    if not setup[
        "technical_analysis"
    ]:

        setup[
            "technical_analysis"
        ] = (
            "Technical structure and "
            "market derivatives data "
            "are being monitored."
        )


    # --------------------------------------------------------
    # News
    # --------------------------------------------------------

    setup[
        "news"
    ] = _clean_text(
        setup.get(
            "news",
            "",
        )
    )


    # --------------------------------------------------------
    # Market context
    # --------------------------------------------------------

    setup[
        "market_context"
    ] = _clean_text(
        setup.get(
            "market_context",
            market_context
            or "",
        )
    )


    # ========================================================
    # FINAL VALIDATION
    # ========================================================

    if not _validate_setup(
        setup,
        symbol,
    ):

        print(
            "[setup_generator] "
            "Final setup validation failed. "
            "Rebuilding deterministic fallback."
        )

        setup = (
            _python_fallback_setup(
                symbol,
                indicators,
                news,
                market_context,
                advanced_market_data,
                coinglass_market_data,
            )
        )

        setup[
            "title"
        ] = _select_title(
            symbol,
            setup[
                "direction"
            ],
        )


    return setup


# ============================================================
# POST FORMATTER
# ============================================================

def format_post_text(
    setup,
):
    """
    Format setup for Binance Square.

    Exactly 3 $COIN mentions.
    """

    if not isinstance(
        setup,
        dict,
    ):

        return ""


    symbol = str(
        setup.get(
            "symbol",
            "",
        )
    ).upper().strip()

    coin = _coin_name(
        symbol
    )

    token = f"${coin}"


    direction = str(
        setup.get(
            "direction",
            "",
        )
    ).upper().strip()


    entry = setup.get(
        "entry"
    )

    stop_loss = setup.get(
        "stop_loss"
    )

    take_profit = setup.get(
        "take_profit"
    )

    levels = setup.get(
        "key_levels",
        {},
    )

    support = levels.get(
        "support"
    )

    resistance = levels.get(
        "resistance"
    )


    title = _clean_text(
        setup.get(
            "title",
            "",
        )
    )

    technical_analysis = _clean_text(
        setup.get(
            "technical_analysis",
            "",
        )
    )

    news = _clean_text(
        setup.get(
            "news",
            "",
        )
    )

    market_context = _clean_text(
        setup.get(
            "market_context",
            "",
        )
    )


    # ========================================================
    # ENTRY
    # ========================================================

    if isinstance(
        entry,
        (list, tuple),
    ) and len(entry) >= 2:

        entry_text = (
            f"{_round_price(entry[0])} - "
            f"{_round_price(entry[1])}"
        )

    else:

        entry_text = str(
            _round_price(
                entry
            )
        )


    # ========================================================
    # BUILD
    # ========================================================

    lines = []

    lines.append(
        title
    )

    lines.append(
        ""
    )

    lines.append(
        f"{direction} SETUP"
    )

    lines.append(
        f"Entry: {entry_text}"
    )

    lines.append(
        f"Stop Loss: "
        f"{_round_price(stop_loss)}"
    )

    lines.append(
        f"Take Profit (2R): "
        f"{_round_price(take_profit)}"
    )

    lines.append(
        ""
    )

    lines.append(
        "Key Levels"
    )

    lines.append(
        f"Support: "
        f"{_round_price(support) if support is not None else 'N/A'}"
    )

    lines.append(
        f"Resistance: "
        f"{_round_price(resistance) if resistance is not None else 'N/A'}"
    )

    lines.append(
        ""
    )

    lines.append(
        "Technical Analysis"
    )

    lines.append(
        technical_analysis
    )


    if news:

        lines.append(
            ""
        )

        lines.append(
            "News Context"
        )

        lines.append(
            news
        )


    if market_context:

        lines.append(
            ""
        )

        lines.append(
            "Market Context"
        )

        lines.append(
            market_context
        )


    lines.append(
        ""
    )

    lines.append(
        f"{direction} scenario remains "
        f"dependent on the key levels above."
    )


    text = "\n".join(
        lines
    )


    # ========================================================
    # EXACTLY 3 COIN MENTIONS
    # ========================================================

    text = re.sub(
        rf"\${re.escape(coin)}\b",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    # Rebuild line breaks after whitespace cleanup.
    # Keep content readable.

    text = text.replace(
        " \n",
        "\n",
    ).replace(
        "\n ",
        "\n",
    )


    # Put three mentions naturally.
    lines = text.split(
        "\n"
    )

    if lines:

        lines[0] = (
            lines[0]
            + f" {token}"
        )

    lines.insert(
        min(
            5,
            len(lines),
        ),
        token
    )

    lines.append(
        token
    )

    text = "\n".join(
        lines
    )


    # ========================================================
    # CLEAN
    # ========================================================

    text = re.sub(
        r"[ \t]+",
        " ",
        text,
    )

    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text,
    )

    return text.strip()
