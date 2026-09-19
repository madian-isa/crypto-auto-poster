import os

import pandas as pd
import mplfinance as mpf

from src import bot_config


_CHART_STYLE = mpf.make_mpf_style(
    base_mpf_style="nightclouds",
    gridstyle="-",
    gridcolor="#333333",
    facecolor="#0b0f14",
    edgecolor="#555555",
    figcolor="#0b0f14",
    rc={
        "font.size": 9,
        "axes.labelcolor": "white",
        "xtick.color": "white",
        "ytick.color": "white",
        "text.color": "white",
    },
)


def render_chart_image(
    symbol: str,
    klines_df: pd.DataFrame,
    setup: dict | None = None,
) -> str:
    """
    Create a neutral 1H market-analysis chart.

    Includes:
      - Candlesticks
      - EMA 21
      - SMA 50

    Time shown on chart:
      - Bangladesh time (UTC+6)

    Does not include:
      - Entry / SL / TP overlays
      - Volume panel
    """

    if klines_df is None or klines_df.empty:
        raise ValueError(
            f"No kline data available for {symbol}"
        )

    df = klines_df.copy()

    rename_map = {
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "volume": "Volume",
        "Open time": "Date",
        "open_time": "Date",
        "timestamp": "Date",
    }

    df = df.rename(
        columns={
            old: new
            for old, new in rename_map.items()
            if old in df.columns
        }
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
            f"Missing OHLC columns for {symbol}: {missing}"
        )

    for col in required:
        df[col] = pd.to_numeric(
            df[col],
            errors="coerce",
        )

    df = df.dropna(
        subset=required
    )

    if df.empty:
        raise ValueError(
            f"No valid OHLC data available for {symbol}"
        )

    # ---------------------------------------------------------
    # FIX TIMEZONE
    # Binance timestamps are normally UTC.
    # Convert them explicitly to Bangladesh time (UTC+6).
    # ---------------------------------------------------------

    if "Date" in df.columns:

        raw_dates = df["Date"]

        # Numeric timestamps from Binance are usually
        # milliseconds since Unix epoch.
        if pd.api.types.is_numeric_dtype(raw_dates):

            df["Date"] = pd.to_datetime(
                raw_dates,
                unit="ms",
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

        # Convert UTC -> Bangladesh Standard Time
        df["Date"] = (
            df["Date"]
            .dt.tz_convert("Asia/Dhaka")
            .dt.tz_localize(None)
        )

        df = df.set_index("Date")

    elif not isinstance(
        df.index,
        pd.DatetimeIndex,
    ):

        raise ValueError(
            f"Datetime index required for {symbol}"
        )

    else:

        # If the index already exists as datetime,
        # make sure it is interpreted as UTC first.
        if df.index.tz is None:

            df.index = (
                pd.to_datetime(
                    df.index,
                    errors="coerce",
                    utc=True,
                )
                .tz_convert("Asia/Dhaka")
                .tz_localize(None)
            )

        else:

            df.index = (
                df.index
                .tz_convert("Asia/Dhaka")
                .tz_localize(None)
            )

    df = df.sort_index()

    # Latest 80 candles
    df = df.tail(80).copy()

    if len(df) < 10:
        raise ValueError(
            f"Not enough candles available for {symbol}"
        )

    # ---------------------------------------------------------
    # INDICATORS
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

    addplots = [
        mpf.make_addplot(
            df["EMA21"],
            width=1.2,
        ),
        mpf.make_addplot(
            df["SMA50"],
            width=1.0,
        ),
    ]

    # ---------------------------------------------------------
    # OUTPUT
    # ---------------------------------------------------------

    output_dir = getattr(
        bot_config,
        "CHART_OUTPUT_DIR",
        "/tmp/trade_setup_charts",
    )

    os.makedirs(
        output_dir,
        exist_ok=True,
    )

    safe_symbol = (
        symbol
        .replace("/", "_")
        .replace(":", "_")
    )

    chart_path = os.path.join(
        output_dir,
        f"{safe_symbol}_market_chart.png",
    )

    title = (
        f"{symbol} — 1H Market Analysis"
    )

    plot_kwargs = {
        "type": "candle",
        "style": _CHART_STYLE,
        "title": title,
        "figsize": (10, 6),
        "tight_layout": True,
        "returnfig": True,

        # Bangladesh local time
        "datetime_format": "%d %b %H:%M",

        "xrotation": 0,
        "addplot": addplots,
    }

    fig, axes = mpf.plot(
        df,
        **plot_kwargs,
    )

    fig.savefig(
        chart_path,
        dpi=160,
        bbox_inches="tight",
    )

    try:
        import matplotlib.pyplot as plt

        plt.close(fig)

    except Exception:
        pass

    print(
        f"[chart] generated: {chart_path}"
    )

    print(
        "[chart] timezone: "
        "Asia/Dhaka (UTC+6)"
    )

    return chart_path
