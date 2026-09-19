"""
chart.py

1H dark Binance-style market analysis chart.

Includes:
- 1H candlesticks
- Asia/Dhaka timezone
- Correct timestamp handling
- EMA21
- SMA50
- Current Price
- Support
- Resistance
- Market-structure zones
- PNG output for Binance Square upload
"""

import os

import pandas as pd
import mplfinance as mpf
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from src import bot_config


# =========================================================
# DARK BINANCE-STYLE
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

    facecolor="#0b0f14",
    figcolor="#0b0f14",

    gridcolor="#1e2329",
    gridstyle="-",

    rc={
        "axes.edgecolor": "#2b3139",
        "axes.labelcolor": "#848e9c",
        "xtick.color": "#848e9c",
        "ytick.color": "#848e9c",
        "text.color": "#eaecef",
        "font.size": 9,
        "font.weight": "normal",
    },
)


# =========================================================
# MAIN CHART FUNCTION
# =========================================================

def render_chart_image(
    symbol: str,
    klines_df: pd.DataFrame,
    setup: dict | None = None,
) -> str:

    if klines_df is None or klines_df.empty:
        raise ValueError(
            f"No kline data available for {symbol}"
        )

    # -----------------------------------------------------
    # Output directory
    # -----------------------------------------------------

    output_dir = getattr(
        bot_config,
        "CHART_OUTPUT_DIR",
        "/tmp/trade_setup_charts",
    )

    os.makedirs(
        output_dir,
        exist_ok=True,
    )

    # -----------------------------------------------------
    # Copy dataframe
    # -----------------------------------------------------

    df = klines_df.copy()

    # -----------------------------------------------------
    # Rename columns
    # -----------------------------------------------------

    rename_map = {
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "volume": "Volume",

        "open_time": "Date",
        "Open time": "Date",
        "timestamp": "Date",
    }

    df = df.rename(
        columns={
            old: new
            for old, new in rename_map.items()
            if old in df.columns
        }
    )

    # -----------------------------------------------------
    # Validate OHLC
    # -----------------------------------------------------

    required_columns = [
        "Open",
        "High",
        "Low",
        "Close",
    ]

    missing = [
        col
        for col in required_columns
        if col not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing OHLC columns for {symbol}: {missing}"
        )

    for col in required_columns:

        df[col] = pd.to_numeric(
            df[col],
            errors="coerce",
        )

    df = df.dropna(
        subset=required_columns
    )

    if df.empty:
        raise ValueError(
            f"No valid OHLC data available for {symbol}"
        )

    # =====================================================
    # TIMESTAMP
    # UTC -> ASIA/DHAKA
    # =====================================================

    if "Date" in df.columns:

        raw_dates = df["Date"]

        if pd.api.types.is_numeric_dtype(raw_dates):

            values = pd.to_numeric(
                raw_dates,
                errors="coerce",
            )

            sample = values.dropna()

            if sample.empty:
                raise ValueError(
                    f"Invalid timestamp data for {symbol}"
                )

            magnitude = abs(
                float(sample.iloc[0])
            )

            # Automatically detect Binance timestamp unit
            if magnitude >= 1e18:
                unit = "ns"

            elif magnitude >= 1e15:
                unit = "us"

            elif magnitude >= 1e12:
                unit = "ms"

            else:
                unit = "s"

            print(
                f"[chart] detected timestamp unit: {unit}"
            )

            df["Date"] = pd.to_datetime(
                values,
                unit=unit,
                utc=True,
                errors="coerce",
            )

        else:

            df["Date"] = pd.to_datetime(
                raw_dates,
                utc=True,
                errors="coerce",
            )

        df = df.dropna(
            subset=["Date"]
        )

        # Bangladesh UTC+6
        df["Date"] = (
            df["Date"]
            .dt.tz_convert("Asia/Dhaka")
            .dt.tz_localize(None)
        )

        df = df.set_index("Date")

    elif isinstance(
        df.index,
        pd.DatetimeIndex,
    ):

        if df.index.tz is None:

            df.index = (
                pd.DatetimeIndex(df.index)
                .tz_localize("UTC")
                .tz_convert("Asia/Dhaka")
                .tz_localize(None)
            )

        else:

            df.index = (
                df.index
                .tz_convert("Asia/Dhaka")
                .tz_localize(None)
            )

    else:

        raise ValueError(
            f"Datetime index required for {symbol}"
        )

    # -----------------------------------------------------
    # Sort
    # -----------------------------------------------------

    df = df.sort_index()

    # -----------------------------------------------------
    # Latest 80 candles
    # -----------------------------------------------------

    df = df.tail(80).copy()

    if len(df) < 10:
        raise ValueError(
            f"Not enough candles available for {symbol}"
        )

    # =====================================================
    # INDICATORS
    # =====================================================

    df["EMA21"] = (
        df["Close"]
        .ewm(
            span=21,
            adjust=False,
        )
        .mean()
    )

    df["SMA50"] = (
        df["Close"]
        .rolling(
            window=50,
            min_periods=1,
        )
        .mean()
    )

    # -----------------------------------------------------
    # Indicator plots
    # -----------------------------------------------------

    addplots = [

        mpf.make_addplot(
            df["EMA21"],
            color="#f0b90b",
            width=1.2,
        ),

        mpf.make_addplot(
            df["SMA50"],
            color="#8b5cf6",
            width=1.0,
        ),
    ]

    # =====================================================
    # CURRENT PRICE
    # =====================================================

    current_price = float(
        df["Close"].iloc[-1]
    )

    # =====================================================
    # SUPPORT / RESISTANCE
    # =====================================================

    support = None
    resistance = None

    if setup:

        try:

            value = setup.get("support")

            if value is not None:
                support = float(value)

        except (
            TypeError,
            ValueError,
        ):

            support = None

        try:

            value = setup.get("resistance")

            if value is not None:
                resistance = float(value)

        except (
            TypeError,
            ValueError,
        ):

            resistance = None

    # =====================================================
    # TITLE
    # =====================================================

    title = (
        f"\n{symbol} — 1H Market Analysis"
    )

    # =====================================================
    # PLOT
    # =====================================================

    plot_kwargs = {

        "type": "candle",

        "style": _CHART_STYLE,

        "title": title,

        "figsize": (10, 6),

        "tight_layout": True,

        "returnfig": True,

        "datetime_format": "%d %b %H:%M",

        "xrotation": 0,

        "addplot": addplots,

        "volume": False,
    }

    fig, axes = mpf.plot(
        df,
        **plot_kwargs,
    )

    ax = axes[0]

    # =====================================================
    # COLORS
    # =====================================================

    GREEN = "#0ecb81"
    RED = "#f6465d"
    WHITE = "#eaecef"
    YELLOW = "#f0b90b"
    PURPLE = "#8b5cf6"

    # =====================================================
    # MARKET STRUCTURE ZONES
    # =====================================================

    data_low = float(
        df["Low"].min()
    )

    data_high = float(
        df["High"].max()
    )

    # -----------------------------------------------------
    # Support zone
    # -----------------------------------------------------

    if support is not None:

        support_width = (
            data_high - data_low
        ) * 0.012

        support_low = (
            support - support_width
        )

        support_high = (
            support + support_width
        )

        ax.add_patch(
            Rectangle(
                (
                    -0.5,
                    support_low,
                ),

                len(df) + 8,

                support_high - support_low,

                facecolor=GREEN,

                edgecolor="none",

                alpha=0.08,

                zorder=0,
            )
        )

        ax.axhline(
            support,

            color=GREEN,

            linestyle="--",

            linewidth=1,

            alpha=0.75,

            zorder=1,
        )

        ax.text(
            0.995,
            support,

            f" Support {support:.6g} ",

            transform=ax.get_yaxis_transform(),

            ha="right",

            va="bottom",

            fontsize=8,

            color="#0b0f14",

            fontweight="bold",

            bbox=dict(
                boxstyle="round,pad=0.25",

                facecolor=GREEN,

                edgecolor="none",

                alpha=0.95,
            ),

            zorder=6,
        )

    # -----------------------------------------------------
    # Resistance zone
    # -----------------------------------------------------

    if resistance is not None:

        resistance_width = (
            data_high - data_low
        ) * 0.012

        resistance_low = (
            resistance - resistance_width
        )

        resistance_high = (
            resistance + resistance_width
        )

        ax.add_patch(
            Rectangle(
                (
                    -0.5,
                    resistance_low,
                ),

                len(df) + 8,

                resistance_high - resistance_low,

                facecolor=RED,

                edgecolor="none",

                alpha=0.08,

                zorder=0,
            )
        )

        ax.axhline(
            resistance,

            color=RED,

            linestyle="--",

            linewidth=1,

            alpha=0.75,

            zorder=1,
        )

        ax.text(
            0.995,
            resistance,

            f" Resistance {resistance:.6g} ",

            transform=ax.get_yaxis_transform(),

            ha="right",

            va="bottom",

            fontsize=8,

            color="#0b0f14",

            fontweight="bold",

            bbox=dict(
                boxstyle="round,pad=0.25",

                facecolor=RED,

                edgecolor="none",

                alpha=0.95,
            ),

            zorder=6,
        )

    # =====================================================
    # CURRENT PRICE
    # =====================================================

    ax.axhline(
        current_price,

        color=WHITE,

        linestyle=":",

        linewidth=1,

        alpha=0.85,

        zorder=1,
    )

    ax.text(
        0.995,
        current_price,

        f" Current {current_price:.6g} ",

        transform=ax.get_yaxis_transform(),

        ha="right",

        va="bottom",

        fontsize=8,

        color="#0b0f14",

        fontweight="bold",

        bbox=dict(
            boxstyle="round,pad=0.25",

            facecolor=WHITE,

            edgecolor="none",

            alpha=0.95,
        ),

        zorder=6,
    )

    # =====================================================
    # INDICATOR LABELS
    # =====================================================

    ax.text(
        0.015,
        0.96,

        "EMA21",

        transform=ax.transAxes,

        fontsize=8,

        color=YELLOW,

        fontweight="bold",

        va="top",
    )

    ax.text(
        0.075,
        0.96,

        "SMA50",

        transform=ax.transAxes,

        fontsize=8,

        color=PURPLE,

        fontweight="bold",

        va="top",
    )

    # =====================================================
    # Y-AXIS PADDING
    # =====================================================

    levels = [
        data_low,
        data_high,
        current_price,
    ]

    if support is not None:
        levels.append(support)

    if resistance is not None:
        levels.append(resistance)

    y_low = min(levels)
    y_high = max(levels)

    price_range = y_high - y_low

    if price_range > 0:

        padding = (
            price_range * 0.08
        )

        ax.set_ylim(
            y_low - padding,
            y_high + padding,
        )

    # =====================================================
    # SAVE
    # =====================================================

    safe_symbol = (
        symbol
        .replace("/", "_")
        .replace(":", "_")
    )

    chart_path = os.path.join(
        output_dir,
        f"{safe_symbol}_market_chart.png",
    )

    fig.savefig(
        chart_path,

        dpi=160,

        bbox_inches="tight",

        facecolor="#0b0f14",
    )

    # -----------------------------------------------------
    # Close matplotlib figure
    # -----------------------------------------------------

    try:

        plt.close(fig)

    except Exception:
        pass

    print(
        f"[chart] generated: {chart_path}"
    )

    print(
        "[chart] timeframe: 1H"
    )

    print(
        "[chart] timezone: Asia/Dhaka (UTC+6)"
    )

    print(
        f"[chart] current price: {current_price}"
    )

    if support is not None:

        print(
            f"[chart] support: {support}"
        )

    if resistance is not None:

        print(
            f"[chart] resistance: {resistance}"
        )

    # =====================================================
    # RETURN
    # =====================================================

    return chart_path
