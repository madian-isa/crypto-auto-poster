"""
chart.py

Creates a clean market-data candlestick chart for Binance Square.

This chart is for educational market visualization only.
It uses the existing kline dataframe and does not generate
or calculate trade-entry, stop-loss, or take-profit signals.
"""

import os

import pandas as pd
import mplfinance as mpf

from src import bot_config as cfg


# =========================================================
# CHART STYLE
# =========================================================

_CHART_STYLE = mpf.make_mpf_style(
    base_mpf_style="nightclouds",
    marketcolors=mpf.make_marketcolors(
        up="#0ecb81",
        down="#f6465d",
        edge={
            "up": "#0ecb81",
            "down": "#f6465d",
        },
        wick={
            "up": "#0ecb81",
            "down": "#f6465d",
        },
        volume={
            "up": "#0ecb81",
            "down": "#f6465d",
        },
    ),
    facecolor="#0b0e11",
    figcolor="#0b0e11",
    gridcolor="#1e2329",
    gridstyle="-",
    rc={
        "axes.edgecolor": "#2b3139",
        "text.color": "#eaecef",
        "axes.labelcolor": "#848e9c",
        "xtick.color": "#848e9c",
        "ytick.color": "#848e9c",
    },
)


# =========================================================
# RENDER CHART
# =========================================================

def render_chart_image(
    symbol: str,
    klines_df: pd.DataFrame,
    setup: dict | None = None,
) -> str:

    os.makedirs(
        cfg.CHART_OUTPUT_DIR,
        exist_ok=True,
    )

    if klines_df is None or klines_df.empty:
        raise ValueError(
            f"No kline data available for {symbol}"
        )

    df = klines_df.copy()

    # -----------------------------------------------------
    # DATETIME INDEX
    # -----------------------------------------------------

    if "open_time" in df.columns:

        df.index = pd.to_datetime(
            df["open_time"],
            unit="ms",
        )

    elif not isinstance(
        df.index,
        pd.DatetimeIndex,
    ):

        raise ValueError(
            "Kline dataframe must contain "
            "'open_time' or a DatetimeIndex."
        )

    # -----------------------------------------------------
    # RENAME OHLCV
    # -----------------------------------------------------

    rename_map = {
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "volume": "Volume",
    }

    df = df.rename(
        columns=rename_map
    )

    required = [
        "Open",
        "High",
        "Low",
        "Close",
    ]

    missing = [
        col
        for col in required
        if col not in df.columns
    ]

    if missing:

        raise ValueError(
            "Missing OHLC columns: "
            + ", ".join(missing)
        )

    # -----------------------------------------------------
    # NUMERIC CLEANUP
    # -----------------------------------------------------

    for column in required:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    if "Volume" in df.columns:

        df["Volume"] = pd.to_numeric(
            df["Volume"],
            errors="coerce",
        )

    df = df.dropna(
        subset=required
    )

    if df.empty:

        raise ValueError(
            f"No valid OHLC data for {symbol}"
        )

    # -----------------------------------------------------
    # LIMIT CHART DATA
    # -----------------------------------------------------

    # Keep the latest candles so the image remains readable.
    df = df.tail(80)

    # -----------------------------------------------------
    # OUTPUT PATH
    # -----------------------------------------------------

    safe_symbol = (
        str(symbol)
        .upper()
        .replace("/", "_")
        .replace(":", "_")
    )

    out_path = os.path.join(
        cfg.CHART_OUTPUT_DIR,
        f"{safe_symbol}_market_chart.png",
    )

    # -----------------------------------------------------
    # TITLE
    # -----------------------------------------------------

    timeframe = str(
        getattr(
            cfg,
            "KLINE_INTERVAL",
            "1h",
        )
    ).upper()

    title = (
        f"{safe_symbol}  |  "
        f"{timeframe} Market Chart"
    )

    # -----------------------------------------------------
    # VOLUME
    # -----------------------------------------------------

    show_volume = (
        "Volume" in df.columns
        and df["Volume"].notna().any()
    )

    # -----------------------------------------------------
    # MOVING AVERAGES
    # -----------------------------------------------------

    addplots = []

    if len(df) >= 21:

        ema21 = (
            df["Close"]
            .ewm(
                span=21,
                adjust=False,
            )
            .mean()
        )

        addplots.append(
            mpf.make_addplot(
                ema21,
                panel=0,
                width=1.0,
                color="#f0b90b",
            )
        )

    if len(df) >= 50:

        sma50 = (
            df["Close"]
            .rolling(50)
            .mean()
        )

        addplots.append(
            mpf.make_addplot(
                sma50,
                panel=0,
                width=1.0,
                color="#8b5cf6",
            )
        )

    # -----------------------------------------------------
    # CREATE CHART
    # -----------------------------------------------------

    fig, axes = mpf.plot(
        df,
        type="candle",
        style=_CHART_STYLE,
        title=title,
        volume=show_volume,
        addplot=addplots or None,
        figsize=(10, 6),
        tight_layout=True,
        returnfig=True,
        datetime_format="%d %b %H:%M",
        xrotation=0,
    )

    # -----------------------------------------------------
    # SAVE
    # -----------------------------------------------------

    fig.savefig(
        out_path,
        dpi=150,
        bbox_inches="tight",
        facecolor="#0b0e11",
    )

    # -----------------------------------------------------
    # CLOSE FIGURE
    # -----------------------------------------------------

    try:

        import matplotlib.pyplot as plt

        plt.close(fig)

    except Exception:
        pass

    print(
        f"[chart] saved market chart: {out_path}"
    )

    return out_path
