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


def render_chart_image(symbol: str, klines_df: pd.DataFrame, direction: str, setup: dict) -> str:
    os.makedirs(cfg.CHART_OUTPUT_DIR, exist_ok=True)

    df = klines_df.copy()
    df.index = pd.to_datetime(df["open_time"], unit="ms")
    df = df.rename(columns={
        "open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume",
    })

    out_path = os.path.join(cfg.CHART_OUTPUT_DIR, f"{symbol}_{direction}.png")

    entry = (float(setup["entry_low"]) + float(setup["entry_high"])) / 2
    sl = float(setup["sl"])
    tp = (float(setup["tp_low"]) + float(setup["tp_high"])) / 2

    profit_color = "#0ecb81"
    loss_color = "#f6465d"
    # Long: profit zone is above entry (toward TP), loss zone below (toward SL).
    # Short: it's flipped.
    if direction == "Short":
        profit_lo, profit_hi = tp, entry
        loss_lo, loss_hi = entry, sl
    else:
        profit_lo, profit_hi = entry, tp
        loss_lo, loss_hi = sl, entry

    fig, axlist = mpf.plot(
        df,
        type="candle",
        style=_DARK_STYLE,
        title=f"\n{symbol} · {direction}",
        volume=False,
        figsize=(7, 4.2),
        tight_layout=True,
        returnfig=True,
    )
    ax = axlist[0]

    ax.axhspan(profit_lo, profit_hi, color=profit_color, alpha=0.15, zorder=0)
    ax.axhspan(loss_lo, loss_hi, color=loss_color, alpha=0.15, zorder=0)

    for level, label, color in [
        (entry, f"Entry {entry:.6g}", "#eaecef"),
        (tp, f"TP {tp:.6g}", profit_color),
        (sl, f"SL {sl:.6g}", loss_color),
    ]:
        ax.axhline(level, color=color, linestyle="--", linewidth=1, alpha=0.8, zorder=1)
        ax.text(
            0.995, level, label, transform=ax.get_yaxis_transform(),
            ha="right", va="bottom", fontsize=8, color=color,
        )

    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor="#0b0e11")

    return out_path
