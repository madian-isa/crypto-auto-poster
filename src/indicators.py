"""
indicators.py

Fetches recent candles for a symbol from Binance Futures and computes
RSI(14), EMA(9/21), and MACD using plain pandas (no extra TA dependency
needed beyond pandas itself).
"""

import requests
import pandas as pd
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
    closes = df["close"]

    rsi14 = _rsi(closes, period=14)
    ema9 = closes.ewm(span=9, adjust=False).mean()
    ema21 = closes.ewm(span=21, adjust=False).mean()

    ema12 = closes.ewm(span=12, adjust=False).mean()
    ema26 = closes.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    histogram = macd_line - signal_line

    last_price = closes.iloc[-1]
    last_ema9 = ema9.iloc[-1]
    last_ema21 = ema21.iloc[-1]

    return {
        "price": round(last_price, 6),
        "high24Approx": round(df["high"].tail(24).max(), 6),
        "low24Approx": round(df["low"].tail(24).min(), 6),
        "rsi14": round(rsi14.iloc[-1], 2),
        "ema9": round(last_ema9, 6),
        "ema21": round(last_ema21, 6),
        "emaTrend": "bullish (EMA9 > EMA21)" if last_ema9 > last_ema21 else "bearish (EMA9 < EMA21)",
        "macd": {
            "MACD": round(macd_line.iloc[-1], 6),
            "signal": round(signal_line.iloc[-1], 6),
            "histogram": round(histogram.iloc[-1], 6),
        },
    }


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, 1e-9)
    return 100 - (100 / (1 + rs))
