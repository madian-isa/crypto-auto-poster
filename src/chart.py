from __future__ import annotations

import os
from datetime import timezone
from zoneinfo import ZoneInfo

import matplotlib.pyplot as plt
import mplfinance as mpf
import pandas as pd
from matplotlib.patches import Rectangle


CHART_OUTPUT_DIR = os.environ.get(
    "CHART_OUTPUT_DIR",
    "/tmp/trade_setup_charts",
)

DHAKA_TZ = ZoneInfo("Asia/Dhaka")


_CHART_STYLE = mpf.make_mpf_style(
    base_mpf_style="nightclouds",
    marketcolors=mpf.make_marketcolors(
        up="#0ecb81",
        down="#f6465d",
        edge={"up": "#0ecb81", "down": "#f6465d"},
        wick={"up": "#0ecb81", "down": "#f6465d"},
        volume={"up": "#0ecb81", "down": "#f6465d"},
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


def _detect_timestamp_unit(series: pd.Series) -> str:
    """Detect Binance timestamp unit."""
    values = pd.to_numeric(series, errors="coerce").dropna()

    if values.empty:
        return "ms"

    value = abs(float(values.iloc[-1]))

    if value > 1e17:
        return "ns"
    if value > 1e14:
        return "us"
    if value > 1e11:
        return "ms"

    return "s"


def _prepare_dataframe(klines_df: pd.DataFrame) -> pd.DataFrame:
    """Prepare OHLC dataframe and convert timestamps to Asia/Dhaka."""

    df = klines_df.copy()

    # ---------------------------------------------------------
    # Detect timestamp column
    # ---------------------------------------------------------
    timestamp_candidates = [
        "timestamp",
        "time",
        "open_time",
        "openTime",
        "date",
    ]

    timestamp_col = None

    for col in timestamp_candidates:
        if col in df.columns:
            timestamp_col = col
            break

    if timestamp_col is None:
        if isinstance(df.index, pd.DatetimeIndex):
            index = df.index

            if index.tz is None:
                index = index.tz_localize("UTC")

            df.index = index.tz_convert(DHAKA_TZ)
        else:
            raise ValueError(
                "No timestamp column found and index is not DatetimeIndex."
            )
    else:
        unit = _detect_timestamp_unit(df[timestamp_col])

        print(f"[chart] detected timestamp unit: {unit}")

        dt = pd.to_datetime(
            df[timestamp_col],
            unit=unit,
            utc=True,
            errors="coerce",
        )

        df.index = dt.dt.tz_convert(DHAKA_TZ)

        df = df.drop(columns=[timestamp_col])

    # ---------------------------------------------------------
    # Remove invalid timestamps
    # ---------------------------------------------------------
    df = df[~df.index.isna()]

    # ---------------------------------------------------------
    # Normalize OHLC column names
    # ---------------------------------------------------------
    rename_map = {}

    for col in df.columns:
        lower = str(col).lower()

        if lower == "open":
            rename_map[col] = "Open"
        elif lower == "high":
            rename_map[col] = "High"
        elif lower == "low":
            rename_map[col] = "Low"
        elif lower == "close":
            rename_map[col] = "Close"
        elif lower == "volume":
            rename_map[col] = "Volume"

    df = df.rename(columns=rename_map)

    required = ["Open", "High", "Low", "Close"]

    missing = [col for col in required if col not in df.columns]

    if missing:
        raise ValueError(
            f"Missing OHLC columns: {missing}"
        )

    # ---------------------------------------------------------
    # Numeric conversion
    # ---------------------------------------------------------
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col],
                errors="coerce",
            )

    df = df.dropna(
        subset=["Open", "High", "Low", "Close"]
    )

    df = df.sort_index()

    return df


def render_chart_image(
    symbol: str,
    klines_df: pd.DataFrame,
    setup: dict | None = None,
) -> str:
    """
    Generate Binance-style 1H market chart.

    Includes the signal levels supplied in ``setup`` and leaves a
    right-side gap for a TradingView-style risk/reward box.
    """

    os.makedirs(
        CHART_OUTPUT_DIR,
        exist_ok=True,
    )

    # ---------------------------------------------------------
    # Prepare data
    # ---------------------------------------------------------
    df = _prepare_dataframe(klines_df)

    # Latest 80 candles
    df = df.tail(80).copy()

    # ---------------------------------------------------------
    # Indicators
    # ---------------------------------------------------------
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

    df["EMA200"] = (
        df["Close"]
        .ewm(
            span=200,
            adjust=False,
        )
        .mean()
    )

    # ---------------------------------------------------------
    # Current price
    # ---------------------------------------------------------
    current_price = float(df["Close"].iloc[-1])

    # ---------------------------------------------------------
    # Add plots
    # ---------------------------------------------------------
    add_plots = [
        mpf.make_addplot(
            df["EMA21"],
            color="#f0b90b",
            width=1.2,
            label="EMA 21",
        ),
        mpf.make_addplot(
            df["SMA50"],
            color="#5b8def",
            width=1.2,
            label="SMA 50",
        ),
        mpf.make_addplot(
            df["EMA200"],
            color="#c084fc",
            width=1.2,
            label="EMA 200",
        ),
    ]

    # ---------------------------------------------------------
    # Create chart
    # ---------------------------------------------------------
    fig, axes = mpf.plot(
        df[
            [
                "Open",
                "High",
                "Low",
                "Close",
            ]
        ],
        type="candle",
        style=_CHART_STYLE,
        addplot=add_plots,
        figsize=(16, 8),
        volume=False,
        returnfig=True,
        tight_layout=True,
        datetime_format="%d %b %H:%M",
        xrotation=0,
        show_nontrading=False,
        title=f"{symbol} • 1H",
    )

    # ---------------------------------------------------------
    # Main price axis
    # ---------------------------------------------------------
    ax = axes[0]

    direction = str((setup or {}).get("direction", "")).upper()
    entry_low = (setup or {}).get("entry_low")
    entry_high = (setup or {}).get("entry_high")
    stop_loss = (setup or {}).get("stop_loss")
    take_profit = (setup or {}).get("take_profit")

    def _number(value):
        try:
            value = float(value)
            return value if value > 0 else None
        except (TypeError, ValueError):
            return None

    entry_low = _number(entry_low)
    entry_high = _number(entry_high)
    stop_loss = _number(stop_loss)
    take_profit = _number(take_profit)

    if entry_low is not None and entry_high is not None:
        entry_low, entry_high = sorted((entry_low, entry_high))
        entry_mid = (entry_low + entry_high) / 2
        levels = [entry_low, entry_high]
        if stop_loss is not None:
            levels.append(stop_loss)
        if take_profit is not None:
            levels.append(take_profit)
        pad = max((max(levels) - min(levels)) * 0.12, entry_mid * 0.01)
        ax.set_ylim(min(levels) - pad, max(levels) + pad)

        last_x = len(df) - 1
        box_x = last_x + 4
        box_width = 10
        ax.set_xlim(-1, box_x + box_width + 3)

        if direction == "LONG":
            reward_color = "#0ecb81"
            risk_color = "#f6465d"
        else:
            reward_color = "#f6465d"
            risk_color = "#0ecb81"

        if take_profit is not None:
            reward_low = min(entry_mid, take_profit)
            reward_high = max(entry_mid, take_profit)
            ax.add_patch(
                Rectangle(
                    (box_x, reward_low),
                    box_width,
                    reward_high - reward_low,
                    facecolor=reward_color,
                    edgecolor=reward_color,
                    alpha=0.28,
                    linewidth=1.0,
                )
            )

        if stop_loss is not None:
            risk_low = min(entry_mid, stop_loss)
            risk_high = max(entry_mid, stop_loss)
            ax.add_patch(
                Rectangle(
                    (box_x, risk_low),
                    box_width,
                    max(risk_high - risk_low, 1e-12),
                    facecolor=risk_color,
                    edgecolor=risk_color,
                    alpha=0.28,
                    linewidth=1.0,
                )
            )

        ax.axhspan(
            entry_low,
            entry_high,
            xmin=0.0,
            xmax=1.0,
            facecolor="#5b8def",
            alpha=0.08,
        )

        for label, value, color in (
            ("ENTRY", entry_mid, "#5b8def"),
            ("SL", stop_loss, "#f6465d"),
            ("TP", take_profit, "#0ecb81"),
        ):
            if value is None:
                continue
            ax.axhline(
                value,
                color=color,
                linewidth=1.0,
                linestyle="--",
                alpha=0.9,
            )
            ax.text(
                box_x + box_width + 0.5,
                value,
                f"{label} {value:g}",
                va="center",
                ha="left",
                fontsize=8,
                color=color,
                bbox=dict(
                    boxstyle="round,pad=0.2",
                    facecolor="#0b0f14",
                    edgecolor=color,
                ),
            )

        ax.text(
            box_x + box_width / 2,
            max(levels) + pad * 0.35,
            f"{direction or 'SETUP'}  1:2 RR",
            ha="center",
            va="bottom",
            fontsize=9,
            color="#eaecef",
            fontweight="bold",
        )

    # Current price line
    ax.axhline(
        current_price,
        color="#848e9c",
        linewidth=0.8,
        linestyle="--",
        alpha=0.7,
    )

    # Current price label
    ax.text(
        1.005,
        current_price,
        f"{current_price:g}",
        transform=ax.get_yaxis_transform(),
        va="center",
        ha="left",
        fontsize=9,
        color="#eaecef",
        fontweight="normal",
        bbox=dict(
            boxstyle="round,pad=0.25",
            facecolor="#1e2329",
            edgecolor="#2b3139",
        ),
    )

    # ---------------------------------------------------------
    # Chart title
    # ---------------------------------------------------------
    ax.set_title(
        f"{symbol} • 1H Market Chart",
        color="#eaecef",
        fontsize=13,
        fontweight="normal",
        pad=12,
    )

    # ---------------------------------------------------------
    # Footer
    # ---------------------------------------------------------
    latest_time = df.index[-1]

    if latest_time.tzinfo is None:
        latest_time = latest_time.replace(
            tzinfo=timezone.utc
        )

    latest_time = latest_time.astimezone(
        DHAKA_TZ
    )

    fig.text(
        0.5,
        0.015,
        (
            f"Time: {latest_time.strftime('%d %b %Y, %I:%M %p')} "
            f"• Asia/Dhaka (UTC+6)"
        ),
        ha="center",
        color="#848e9c",
        fontsize=8,
    )

    # ---------------------------------------------------------
    # Legend
    # ---------------------------------------------------------
    ax.legend(
        loc="upper left",
        fontsize=8,
        frameon=False,
    )

    # ---------------------------------------------------------
    # Save
    # ---------------------------------------------------------
    chart_path = os.path.join(
        CHART_OUTPUT_DIR,
        f"{symbol}_market_chart.png",
    )

    fig.savefig(
        chart_path,
        dpi=150,
        bbox_inches="tight",
        facecolor="#0b0f14",
    )

    plt.close(fig)

    # ---------------------------------------------------------
    # Logs
    # ---------------------------------------------------------
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
        f"[chart] current price: {current_price:g}"
    )

    return chart_path
