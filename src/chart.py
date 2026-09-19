    # ---------------------------------------------------------
    # ROBUST TIMESTAMP FIX
    # Handles Binance timestamps in seconds / milliseconds /
    # microseconds / nanoseconds and converts to Bangladesh time.
    # ---------------------------------------------------------

    if "Date" in df.columns:

        raw_dates = df["Date"]

        if pd.api.types.is_numeric_dtype(raw_dates):

            values = pd.to_numeric(
                raw_dates,
                errors="coerce",
            )

            # Detect timestamp unit automatically
            sample = values.dropna()

            if sample.empty:
                raise ValueError(
                    f"Invalid timestamp data for {symbol}"
                )

            magnitude = abs(float(sample.iloc[0]))

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

        # UTC -> Bangladesh Standard Time
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

        # Existing datetime index
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
