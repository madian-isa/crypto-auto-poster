"""
screener.py

Pulls 24h ticker stats for every USDT-margined perpetual on Binance Futures
and ranks them by liquidity + momentum + a simple "volume spike" proxy.
No fixed coin list — the shortlist changes every run based on what's
actually moving right now.
"""

import math
import requests
import bot_config as cfg


def get_screener_shortlist(limit=None):
    limit = limit or cfg.SCREENER_SHORTLIST_SIZE
    tickers = _fetch_all_24hr_tickers()

    usdt_pairs = [
        t for t in tickers
        if t["symbol"].endswith("USDT") and t["symbol"] not in cfg.EXCLUDE_SYMBOLS
    ]

    scored = []
    for t in usdt_pairs:
        quote_volume = float(t["quoteVolume"])
        pct_change = abs(float(t["priceChangePercent"]))
        weighted_avg = float(t.get("weightedAvgPrice") or 1) or 1
        volume_spike = float(t["volume"]) / weighted_avg

        score = (
            _norm_log(quote_volume) * 0.5
            + _norm(pct_change, 20) * 0.35
            + _norm(volume_spike, 1e6) * 0.15
        )

        scored.append({
            "symbol": t["symbol"],
            "quote_volume": quote_volume,
            "pct_change": pct_change,
            "last_price": float(t["lastPrice"]),
            "score": score,
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:limit]


def _fetch_all_24hr_tickers():
    url = f"{cfg.BINANCE_FAPI_BASE}/fapi/v1/ticker/24hr"
    res = requests.get(url, timeout=15)
    res.raise_for_status()
    return res.json()


def _norm_log(value):
    return math.log10(value + 1) / 10


def _norm(value, cap):
    return min(value / cap, 1)


if __name__ == "__main__":
    for row in get_screener_shortlist():
        print(row)
