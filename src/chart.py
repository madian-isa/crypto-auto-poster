"""
chart.py

Renders a dark-themed candlestick chart (mplfinance) for a symbol and saves
it as a PNG, matching the "boxed chart screenshot" style from the reference
post. Returns the file path so it can be handed straight to the image
upload step in square_post_ext.py.
"""

import os
import pandas as pd
import mplfinance as mpf
from src import bot_config as cfg

_DARK_STYLE = mpf.make_mpf_style(
    base_mpf_style="nightclouds",
    marketcolors=mpf.make_marketcolors(
        up="#0ecb81", down="#f6465d",
        edge={"up": "#0ecb81", "down": "#f6465d"},
        wick={"up": "#0ecb81", "down": "#f6465d"},
        volume={"up": "#0ecb81", "down": "#f6465d"},
    ),
    facecolor="#0b0e11",
    figcolor="#0b0e11",
    gridcolor="#1e2329",
    gridstyle="-",
    rc={"axes.edgecolor": "#2b3139", "text.color": "#eaecef", "axes.labelcolor": "#848e9c",
        "xtick.color": "#848e9c", "ytick.color": "#848e9c"},
)


def render_chart_image(symbol: str, klines_df: pd.DataFrame, direction: str) -> str:
    os.makedirs(cfg.CHART_OUTPUT_DIR, exist_ok=True)

    df = klines_df.copy()
    df.index = pd.to_datetime(df["open_time"], unit="ms")
    df = df.rename(columns={
        "open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume",
    })

    out_path = os.path.join(cfg.CHART_OUTPUT_DIR, f"{symbol}_{direction}.png")

    mpf.plot(
        df,
        type="candle",
        style=_DARK_STYLE,
        title=f"\n{symbol} · {direction}",
        volume=False,
        savefig=dict(fname=out_path, dpi=150, bbox_inches="tight", facecolor="#0b0e11"),
        figsize=(7, 4.2),
        tight_layout=True,
    )

    return out_path
