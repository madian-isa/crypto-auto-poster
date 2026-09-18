"""
indicators.py

Fetches recent candles for a symbol from Binance and computes a broad set
of indicators (RSI, EMA9/21, SMA50, MACD, Bollinger Bands, Stochastic,
ADX, ATR, OBV) plus simple support/resistance levels from recent swing
highs/lows — using plain pandas, no extra TA dependency.
"""

import requests
import pandas as pd
import numpy as np
from src import bot_config as cfg


def fetch_klines(symbol, interval=None, limit=None):
    interval = interval or cfg.KLINE_INTERVAL
    limit = limit or cfg.KLINE_LIMIT

    url = f"{cfg.BINANCE_FAPI_BASE}/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    res = requests.get(url, params=params, timeout=15)
    res.raise_for_status()
    raw = res.json()

    df = pd.DataFrame(raw, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades", "taker_base", "taker_quote", "ignore",
    ])
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    return df


def compute_indicators(df: pd.DataFrame) -> dict:
    closes, highs, lows, volumes = df["close"], df["high"], df["low"], df["volume"]

    rsi14 = _rsi(closes, period=14)
    ema9 = closes.ewm(span=9, adjust=False).mean()
    ema21 = closes.ewm(span=21, adjust=False).mean()
    sma50 = closes.rolling(50).mean()

    ema12 = closes.ewm(span=12, adjust=False).mean()
    ema26 = closes.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    histogram = macd_line - signal_line

    bb_mid = closes.rolling(20).mean()
    bb_std = closes.rolling(20).std()
    bb_upper = bb_mid + 2 * bb_std
    bb_lower = bb_mid - 2 * bb_std

    stoch_k, stoch_d = _stochastic(highs, lows, closes)
    atr14 = _atr(highs, lows, closes, period=14)
    adx14 = _adx(highs, lows, closes, period=14)
    obv = _obv(closes, volumes)

    support, resistance = _support_resistance(highs, lows, closes)

    last = lambda s: s.iloc[-1]
    last_price = last(closes)
    last_ema9, last_ema21 = last(ema9), last(ema21)
    last_atr = last(atr14)

    return {
        "price": round(last_price, 6),
        "high24Approx": round(highs.tail(24).max(), 6),
        "low24Approx": round(lows.tail(24).min(), 6),
        "rsi14": round(last(rsi14), 2),
        "ema9": round(last_ema9, 6),
        "ema21": round(last_ema21, 6),
        "sma50": round(last(sma50), 6) if not pd.isna(last(sma50)) else None,
        "emaTrend": "bullish (EMA9 > EMA21)" if last_ema9 > last_ema21 else "bearish (EMA9 < EMA21)",
        "macd": {
            "MACD": round(last(macd_line), 6),
            "signal": round(last(signal_line), 6),
            "histogram": round(last(histogram), 6),
        },
        "bollinger": {
            "upper": round(last(bb_upper), 6),
            "mid": round(last(bb_mid), 6),
            "lower": round(last(bb_lower), 6),
        },
        "stochastic": {"k": round(last(stoch_k), 2), "d": round(last(stoch_d), 2)},
        "atr14": round(last_atr, 6),
        "adx14": round(last(adx14), 2),
        "obvTrend": "rising" if obv.iloc[-1] > obv.iloc[-6] else "falling",
        "support": round(support, 6) if support else None,
        "resistance": round(resistance, 6) if resistance else None,
    }


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-9)
    return 100 - (100 / (1 + rs))


def _stochastic(high, low, close, k_period=14, d_period=3):
    lowest_low = low.rolling(k_period).min()
    highest_high = high.rolling(k_period).max()
    k = 100 * (close - lowest_low) / (highest_high - lowest_low).replace(0, 1e-9)
    d = k.rolling(d_period).mean()
    return k, d


def _atr(high, low, close, period=14):
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def _adx(high, low, close, period=14):
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    atr = _atr(high, low, close, period)
    plus_di = 100 * pd.Series(plus_dm, index=high.index).ewm(alpha=1 / period, adjust=False).mean() / atr.replace(0, 1e-9)
    minus_di = 100 * pd.Series(minus_dm, index=high.index).ewm(alpha=1 / period, adjust=False).mean() / atr.replace(0, 1e-9)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, 1e-9)
    return dx.ewm(alpha=1 / period, adjust=False).mean()


def _obv(close, volume):
    direction = np.sign(close.diff().fillna(0))
    return (direction * volume).cumsum()


def _support_resistance(high, low, close, lookback=40):
    """Simple swing-based support/resistance: recent local highs/lows near
    (but not equal to) the current price, over the given lookback window."""
    window = min(lookback, len(close))
    recent_high = high.tail(window)
    recent_low = low.tail(window)
    current = close.iloc[-1]

    highs_above = recent_high[recent_high > current]
    lows_below = recent_low[recent_low < current]

    resistance = highs_above.min() if not highs_above.empty else recent_high.max()
    support = lows_below.max() if not lows_below.empty else recent_low.min()
    return support, resistance
