"""
Market indicators for Binance candles.

The latest still-forming candle is removed before calculations so signals
are based only on closed candles.
"""

import time

import numpy as np
import pandas as pd
import requests

from src import bot_config as cfg


KLINE_COLUMNS = [
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
]


def fetch_klines(symbol, interval=None, limit=None):
    interval = interval or cfg.KLINE_INTERVAL
    limit = limit or cfg.KLINE_LIMIT

    url = f"{cfg.BINANCE_FAPI_BASE}/api/v3/klines"

    response = requests.get(
        url,
        params={
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
        },
        timeout=15,
    )
    response.raise_for_status()

    raw = response.json()

    if not raw:
        return pd.DataFrame(columns=KLINE_COLUMNS)

    df = pd.DataFrame(raw, columns=KLINE_COLUMNS)

    numeric_columns = [
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]

    for column in numeric_columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    df["open_time"] = pd.to_numeric(
        df["open_time"],
        errors="coerce",
    )

    df["close_time"] = pd.to_numeric(
        df["close_time"],
        errors="coerce",
    )

    df = df.dropna(
        subset=[
            "open_time",
            "close_time",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]
    ).reset_index(drop=True)

    # Binance may return the currently-forming candle as the last row.
    # Never use it for a signal.
    now_ms = int(time.time() * 1000)

    if not df.empty:
        last_close_time = int(
            df.iloc[-1]["close_time"]
        )

        if last_close_time > now_ms:
            df = df.iloc[:-1].copy()

    return df.reset_index(drop=True)


def compute_indicators(df: pd.DataFrame) -> dict:
    if df is None or df.empty:
        return {}

    required = [
        "high",
        "low",
        "close",
        "volume",
    ]

    if any(column not in df.columns for column in required):
        return {}

    df = df.dropna(
        subset=required
    ).reset_index(drop=True)

    if len(df) < 50:
        return {}

    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    volume = df["volume"].astype(float)

    ema9 = close.ewm(
        span=9,
        adjust=False,
    ).mean()

    ema20 = close.ewm(
        span=20,
        adjust=False,
    ).mean()

    ema21 = close.ewm(
        span=21,
        adjust=False,
    ).mean()

    ema50 = close.ewm(
        span=50,
        adjust=False,
    ).mean()

    ema200 = close.ewm(
        span=200,
        adjust=False,
    ).mean()

    sma50 = close.rolling(
        50,
        min_periods=50,
    ).mean()

    ema12 = close.ewm(
        span=12,
        adjust=False,
    ).mean()

    ema26 = close.ewm(
        span=26,
        adjust=False,
    ).mean()

    macd_line = ema12 - ema26
    macd_signal = macd_line.ewm(
        span=9,
        adjust=False,
    ).mean()

    macd_histogram = (
        macd_line - macd_signal
    )

    bb_mid = close.rolling(
        20,
        min_periods=20,
    ).mean()

    bb_std = close.rolling(
        20,
        min_periods=20,
    ).std()

    bb_upper = bb_mid + (2 * bb_std)
    bb_lower = bb_mid - (2 * bb_std)

    stoch_k, stoch_d = _stochastic(
        high,
        low,
        close,
    )

    atr14 = _atr(
        high,
        low,
        close,
        14,
    )

    adx14 = _adx(
        high,
        low,
        close,
        14,
    )

    obv = _obv(
        close,
        volume,
    )

    support, resistance = _support_resistance(
        high,
        low,
        close,
    )

    last_price = float(close.iloc[-1])
    last_ema9 = float(ema9.iloc[-1])
    last_ema20 = float(ema20.iloc[-1])
    last_ema21 = float(ema21.iloc[-1])
    last_ema50 = float(ema50.iloc[-1])
    last_ema200 = float(ema200.iloc[-1])
    last_rsi = float(_rsi(close, 14).iloc[-1])
    last_macd = float(macd_line.iloc[-1])
    last_macd_signal = float(macd_signal.iloc[-1])
    last_histogram = float(macd_histogram.iloc[-1])
    last_stoch_k = _safe_last(stoch_k)
    last_stoch_d = _safe_last(stoch_d)
    last_atr = _safe_last(atr14)
    last_adx = _safe_last(adx14)

    if last_ema20 > last_ema200:
        ema_relation = "EMA20 above EMA200"
    elif last_ema20 < last_ema200:
        ema_relation = "EMA20 below EMA200"
    else:
        ema_relation = "EMA20 equal to EMA200"

    if len(ema20) >= 2 and len(ema200) >= 2:
        previous_ema20 = float(ema20.iloc[-2])
        previous_ema200 = float(ema200.iloc[-2])

        if (
            previous_ema20 <= previous_ema200
            and last_ema20 > last_ema200
        ):
            ema_cross = "bullish crossover"
        elif (
            previous_ema20 >= previous_ema200
            and last_ema20 < last_ema200
        ):
            ema_cross = "bearish crossover"
        else:
            ema_cross = "no fresh crossover"
    else:
        ema_cross = "insufficient data"

    if last_price > last_ema200:
        price_vs_ema200 = "price above EMA200"
    elif last_price < last_ema200:
        price_vs_ema200 = "price below EMA200"
    else:
        price_vs_ema200 = "price at EMA200"

    average_volume = volume.rolling(
        20,
        min_periods=20,
    ).mean().iloc[-1]

    if pd.isna(average_volume) or average_volume == 0:
        volume_change = None
    else:
        volume_change = (
            (volume.iloc[-1] - average_volume)
            / average_volume
        ) * 100

    obv_trend = (
        "rising"
        if len(obv) >= 6
        and obv.iloc[-1] > obv.iloc[-6]
        else "falling"
    )

    return {
        "price": round(last_price, 8),
        "current_price": round(last_price, 8),

        "high24Approx": round(
            float(high.tail(24).max()),
            8,
        ),
        "low24Approx": round(
            float(low.tail(24).min()),
            8,
        ),

        "high_24h": round(
            float(high.tail(24).max()),
            8,
        ),
        "low_24h": round(
            float(low.tail(24).min()),
            8,
        ),

        "rsi14": round(last_rsi, 2),
        "rsi": round(last_rsi, 2),

        "ema9": round(last_ema9, 8),
        "ema20": round(last_ema20, 8),
        "ema21": round(last_ema21, 8),
        "ema50": round(last_ema50, 8),
        "ema200": round(last_ema200, 8),

        "sma50": (
            round(float(sma50.iloc[-1]), 8)
            if not pd.isna(sma50.iloc[-1])
            else None
        ),

        "emaTrend": (
            "bullish (EMA9 > EMA21)"
            if last_ema9 > last_ema21
            else "bearish (EMA9 < EMA21)"
        ),

        "ema20_200_relation": ema_relation,
        "ema20_200_cross": ema_cross,
        "price_vs_ema200": price_vs_ema200,

        # Nested form kept for existing post-generation code.
        "macd": {
            "MACD": round(last_macd, 8),
            "signal": round(last_macd_signal, 8),
            "histogram": round(last_histogram, 8),
        },

        # Scalar aliases used by fallback direction logic.
        "macd_line": round(last_macd, 8),
        "macd_signal": round(last_macd_signal, 8),
        "macd_histogram": round(last_histogram, 8),

        "bollinger": {
            "upper": _rounded_or_none(bb_upper.iloc[-1]),
            "mid": _rounded_or_none(bb_mid.iloc[-1]),
            "lower": _rounded_or_none(bb_lower.iloc[-1]),
        },

        "bollinger_upper": _rounded_or_none(
            bb_upper.iloc[-1]
        ),
        "bollinger_lower": _rounded_or_none(
            bb_lower.iloc[-1]
        ),

        "stochastic": {
            "k": last_stoch_k,
            "d": last_stoch_d,
        },

        "stochastic_k": last_stoch_k,
        "stochastic_d": last_stoch_d,

        "atr14": _rounded_or_none(last_atr),
        "adx14": _rounded_or_none(last_adx),
        "adx": _rounded_or_none(last_adx),

        "obvTrend": obv_trend,
        "volume": round(float(volume.iloc[-1]), 8),
        "volume_change": (
            round(float(volume_change), 2)
            if volume_change is not None
            else None
        ),

        "support": (
            round(float(support), 8)
            if support is not None
            else None
        ),
        "resistance": (
            round(float(resistance), 8)
            if resistance is not None
            else None
        ),
    }


def _safe_last(series):
    if series is None or len(series) == 0:
        return None

    value = series.iloc[-1]

    if pd.isna(value):
        return None

    return round(float(value), 8)


def _rounded_or_none(value):
    if value is None or pd.isna(value):
        return None

    return round(float(value), 8)


def _rsi(series, period=14):
    delta = series.diff()

    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)

    average_gain = gains.ewm(
        alpha=1 / period,
        adjust=False,
    ).mean()

    average_loss = losses.ewm(
        alpha=1 / period,
        adjust=False,
    ).mean()

    relative_strength = (
        average_gain
        / average_loss.replace(0, 1e-9)
    )

    return 100 - (
        100 / (1 + relative_strength)
    )


def _stochastic(
    high,
    low,
    close,
    k_period=14,
    d_period=3,
):
    lowest = low.rolling(
        k_period,
        min_periods=k_period,
    ).min()

    highest = high.rolling(
        k_period,
        min_periods=k_period,
    ).max()

    spread = (highest - lowest).replace(
        0,
        1e-9,
    )

    k = 100 * (
        (close - lowest) / spread
    )

    d = k.rolling(
        d_period,
        min_periods=d_period,
    ).mean()

    return k, d


def _atr(
    high,
    low,
    close,
    period=14,
):
    previous_close = close.shift(1)

    true_range = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    return true_range.ewm(
        alpha=1 / period,
        adjust=False,
    ).mean()


def _adx(
    high,
    low,
    close,
    period=14,
):
    upward_move = high.diff()
    downward_move = -low.diff()

    plus_dm = np.where(
        (upward_move > downward_move)
        & (upward_move > 0),
        upward_move,
        0.0,
    )

    minus_dm = np.where(
        (downward_move > upward_move)
        & (downward_move > 0),
        downward_move,
        0.0,
    )

    atr = _atr(
        high,
        low,
        close,
        period,
    ).replace(0, 1e-9)

    plus_di = (
        100
        * pd.Series(
            plus_dm,
            index=high.index,
        ).ewm(
            alpha=1 / period,
            adjust=False,
        ).mean()
        / atr
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
        / atr
    )

    denominator = (
        plus_di + minus_di
    ).replace(0, 1e-9)

    dx = 100 * (
        (plus_di - minus_di).abs()
        / denominator
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
    window = min(
        lookback,
        len(close),
    )

    recent_high = high.tail(window)
    recent_low = low.tail(window)
    current_price = close.iloc[-1]

    highs_above = recent_high[
        recent_high > current_price
    ]

    lows_below = recent_low[
        recent_low < current_price
    ]

    if highs_above.empty:
        resistance = recent_high.max()
    else:
        resistance = highs_above.min()

    if lows_below.empty:
        support = recent_low.min()
    else:
        support = lows_below.max()

    return support, resistance
