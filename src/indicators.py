"""
indicators.py

Fetches recent candles for a symbol from Binance and computes a broad set
of indicators using plain pandas, no extra TA dependency.

Includes:
- RSI
- EMA9 / EMA20 / EMA21 / EMA50 / EMA200
- SMA50
- MACD
- Bollinger Bands
- Stochastic
- ADX
- ATR
- OBV
- Support / Resistance
- EMA20 / EMA200 relationship and crossover context
"""

import requests
import pandas as pd
import numpy as np
from src import bot_config as cfg


def fetch_klines(symbol, interval=None, limit=None):
    interval = interval or cfg.KLINE_INTERVAL
    limit = limit or cfg.KLINE_LIMIT

    url = f"{cfg.BINANCE_FAPI_BASE}/api/v3/klines"
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit,
    }

    res = requests.get(url, params=params, timeout=15)
    res.raise_for_status()
    raw = res.json()

    df = pd.DataFrame(
        raw,
        columns=[
            "open_time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "quote_volume",
            "trades",
            "taker_base",
            "taker_quote",
            "ignore",
        ],
    )

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)

    return df


def compute_indicators(df: pd.DataFrame) -> dict:
    closes = df["close"]
    highs = df["high"]
    lows = df["low"]
    volumes = df["volume"]

    # ---------------------------------------------------------
    # RSI
    # ---------------------------------------------------------
    rsi14 = _rsi(closes, period=14)

    # ---------------------------------------------------------
    # EMAs
    # ---------------------------------------------------------
    ema9 = closes.ewm(span=9, adjust=False).mean()
    ema20 = closes.ewm(span=20, adjust=False).mean()
    ema21 = closes.ewm(span=21, adjust=False).mean()
    ema50 = closes.ewm(span=50, adjust=False).mean()
    ema200 = closes.ewm(span=200, adjust=False).mean()

    # ---------------------------------------------------------
    # SMA
    # ---------------------------------------------------------
    sma50 = closes.rolling(50).mean()

    # ---------------------------------------------------------
    # MACD
    # ---------------------------------------------------------
    ema12 = closes.ewm(span=12, adjust=False).mean()
    ema26 = closes.ewm(span=26, adjust=False).mean()

    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    histogram = macd_line - signal_line

    # ---------------------------------------------------------
    # Bollinger Bands
    # ---------------------------------------------------------
    bb_mid = closes.rolling(20).mean()
    bb_std = closes.rolling(20).std()

    bb_upper = bb_mid + 2 * bb_std
    bb_lower = bb_mid - 2 * bb_std

    # ---------------------------------------------------------
    # Stochastic
    # ---------------------------------------------------------
    stoch_k, stoch_d = _stochastic(
        highs,
        lows,
        closes,
    )

    # ---------------------------------------------------------
    # ATR / ADX / OBV
    # ---------------------------------------------------------
    atr14 = _atr(
        highs,
        lows,
        closes,
        period=14,
    )

    adx14 = _adx(
        highs,
        lows,
        closes,
        period=14,
    )

    obv = _obv(
        closes,
        volumes,
    )

    # ---------------------------------------------------------
    # Support / Resistance
    # ---------------------------------------------------------
    support, resistance = _support_resistance(
        highs,
        lows,
        closes,
    )

    # ---------------------------------------------------------
    # Last values
    # ---------------------------------------------------------
    last = lambda s: s.iloc[-1]

    last_price = last(closes)

    last_ema9 = last(ema9)
    last_ema20 = last(ema20)
    last_ema21 = last(ema21)
    last_ema50 = last(ema50)
    last_ema200 = last(ema200)

    last_atr = last(atr14)

    # ---------------------------------------------------------
    # EMA20 / EMA200 relationship
    # ---------------------------------------------------------
    if last_ema20 > last_ema200:
        ema20_200_relation = "EMA20 above EMA200"
    elif last_ema20 < last_ema200:
        ema20_200_relation = "EMA20 below EMA200"
    else:
        ema20_200_relation = "EMA20 equal to EMA200"

    # ---------------------------------------------------------
    # Detect latest EMA20 / EMA200 crossover
    #
    # Uses the last two CLOSED candle values available in df.
    # ---------------------------------------------------------
    if len(ema20) >= 2 and len(ema200) >= 2:
        prev_ema20 = ema20.iloc[-2]
        prev_ema200 = ema200.iloc[-2]

        if (
            prev_ema20 <= prev_ema200
            and last_ema20 > last_ema200
        ):
            ema20_200_cross = "bullish crossover"

        elif (
            prev_ema20 >= prev_ema200
            and last_ema20 < last_ema200
        ):
            ema20_200_cross = "bearish crossover"

        else:
            ema20_200_cross = "no fresh crossover"
    else:
        ema20_200_cross = "insufficient data"

    # ---------------------------------------------------------
    # Price relative to EMA200
    # ---------------------------------------------------------
    if last_price > last_ema200:
        price_vs_ema200 = "price above EMA200"
    elif last_price < last_ema200:
        price_vs_ema200 = "price below EMA200"
    else:
        price_vs_ema200 = "price at EMA200"

    # ---------------------------------------------------------
    # Final indicator package
    # ---------------------------------------------------------
    return {
        "price": round(last_price, 6),

        "high24Approx": round(
            highs.tail(24).max(),
            6,
        ),

        "low24Approx": round(
            lows.tail(24).min(),
            6,
        ),

        "rsi14": round(
            last(rsi14),
            2,
        ),

        # EMA values
        "ema9": round(
            last_ema9,
            6,
        ),

        "ema20": round(
            last_ema20,
            6,
        ),

        "ema21": round(
            last_ema21,
            6,
        ),

        "ema50": round(
            last_ema50,
            6,
        ),

        "ema200": round(
            last_ema200,
            6,
        ),

        "sma50": (
            round(last(sma50), 6)
            if not pd.isna(last(sma50))
            else None
        ),

        # Existing short-term trend
        "emaTrend": (
            "bullish (EMA9 > EMA21)"
            if last_ema9 > last_ema21
            else "bearish (EMA9 < EMA21)"
        ),

        # EMA20 / EMA200 context
        "ema20_200_relation": ema20_200_relation,
        "ema20_200_cross": ema20_200_cross,
        "price_vs_ema200": price_vs_ema200,

        "macd": {
            "MACD": round(
                last(macd_line),
                6,
            ),
            "signal": round(
                last(signal_line),
                6,
            ),
            "histogram": round(
                last(histogram),
                6,
            ),
        },

        "bollinger": {
            "upper": round(
                last(bb_upper),
                6,
            ),
            "mid": round(
                last(bb_mid),
                6,
            ),
            "lower": round(
                last(bb_lower),
                6,
            ),
        },

        "stochastic": {
            "k": round(
                last(stoch_k),
                2,
            ),
            "d": round(
                last(stoch_d),
                2,
            ),
        },

        "atr14": round(
            last_atr,
            6,
        ),

        "adx14": round(
            last(adx14),
            2,
        ),

        "obvTrend": (
            "rising"
            if obv.iloc[-1] > obv.iloc[-6]
            else "falling"
        ),

        "support": (
            round(support, 6)
            if support
            else None
        ),

        "resistance": (
            round(resistance, 6)
            if resistance
            else None
        ),
    }


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1 / period,
        adjust=False,
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / period,
        adjust=False,
    ).mean()

    rs = avg_gain / avg_loss.replace(
        0,
        1e-9,
    )

    return 100 - (100 / (1 + rs))


def _stochastic(
    high,
    low,
    close,
    k_period=14,
    d_period=3,
):
    lowest_low = low.rolling(
        k_period
    ).min()

    highest_high = high.rolling(
        k_period
    ).max()

    k = (
        100
        * (close - lowest_low)
        / (highest_high - lowest_low).replace(
            0,
            1e-9,
        )
    )

    d = k.rolling(
        d_period
    ).mean()

    return k, d


def _atr(
    high,
    low,
    close,
    period=14,
):
    prev_close = close.shift(1)

    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    return tr.ewm(
        alpha=1 / period,
        adjust=False,
    ).mean()


def _adx(
    high,
    low,
    close,
    period=14,
):
    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = np.where(
        (up_move > down_move) & (up_move > 0),
        up_move,
        0.0,
    )

    minus_dm = np.where(
        (down_move > up_move) & (down_move > 0),
        down_move,
        0.0,
    )

    atr = _atr(
        high,
        low,
        close,
        period,
    )

    plus_di = (
        100
        * pd.Series(
            plus_dm,
            index=high.index,
        ).ewm(
            alpha=1 / period,
            adjust=False,
        ).mean()
        / atr.replace(0, 1e-9)
    )

    minus_di = (
        100
        * pd.Series(
            minus_dm,
            index=high.index,
        ).ewm(
            alpha=1 / period,
            adjust=False,
        ).mean()
        / atr.replace(0, 1e-9)
    )

    dx = (
        100
        * (plus_di - minus_di).abs()
        / (plus_di + minus_di).replace(
            0,
            1e-9,
        )
    )

    return dx.ewm(
        alpha=1 / period,
        adjust=False,
    ).mean()


def _obv(close, volume):
    direction = np.sign(
        close.diff().fillna(0)
    )

    return (
        direction * volume
    ).cumsum()


def _support_resistance(
    high,
    low,
    close,
    lookback=40,
):
    """Simple swing-based support/resistance."""

    window = min(
        lookback,
        len(close),
    )

    recent_high = high.tail(window)
    recent_low = low.tail(window)

    current = close.iloc[-1]

    highs_above = recent_high[
        recent_high > current
    ]

    lows_below = recent_low[
        recent_low < current
    ]

    resistance = (
        highs_above.min()
        if not highs_above.empty
        else recent_high.max()
    )

    support = (
        lows_below.max()
        if not lows_below.empty
        else recent_low.min()
    )

    return support, resistance
