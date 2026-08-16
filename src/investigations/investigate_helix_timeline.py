from pathlib import Path

import pandas as pd


RAW_DIR = Path("data/raw")

# Start with H1 because that is where the regime change develops.
FILES = [
    "yellow_tripdata_2025-01.parquet",
    "yellow_tripdata_2025-02.parquet",
    "yellow_tripdata_2025-03.parquet",
    "yellow_tripdata_2025-04.parquet",
    "yellow_tripdata_2025-05.parquet",
    "yellow_tripdata_2025-06.parquet",
]

HELIX_VENDOR_ID = 7


def load_helix_data() -> pd.DataFrame:
    frames = []

    for file_name in FILES:
        file_path = RAW_DIR / file_name

        print(f"Reading {file_name}...")

        df = pd.read_parquet(
            file_path,
            columns=[
                "VendorID",
                "tpep_pickup_datetime",
                "tpep_dropoff_datetime",
                "trip_distance",
                "fare_amount",
            ],
        )

        # We only need Helix records for this investigation.
        helix = df[df["VendorID"] == HELIX_VENDOR_ID].copy()

        frames.append(helix)

    return pd.concat(frames, ignore_index=True)


def build_daily_timeline(df: pd.DataFrame) -> pd.DataFrame:
    df["duration_seconds"] = (
        df["tpep_dropoff_datetime"]
        - df["tpep_pickup_datetime"]
    ).dt.total_seconds()

    df["pickup_date"] = (
        df["tpep_pickup_datetime"]
        .dt.normalize()
    )

    df["is_zero_duration"] = (
        df["duration_seconds"] == 0
    )

    daily = (
        df.groupby("pickup_date")
        .agg(
            helix_trips=("VendorID", "size"),
            zero_duration=("is_zero_duration", "sum"),
        )
        .reset_index()
    )

    daily["zero_duration_rate"] = (
        daily["zero_duration"]
        / daily["helix_trips"]
    )

    return daily


def main():
    print(
        "=== INC-003: HELIX ZERO-DURATION TIMELINE ===\n"
    )

    helix = load_helix_data()

    print(f"\nTotal Helix trips loaded: {len(helix):,}")

    daily = build_daily_timeline(helix)

    print("\n=== DAILY TIMELINE ===\n")

    print(
        daily.to_string(
            index=False,
            formatters={
                "zero_duration_rate": lambda x: f"{x:.2%}"
            },
        )
    )

    print("\n=== HIGHEST ZERO-DURATION DAYS ===\n")

    highest = daily.sort_values(
        "zero_duration_rate",
        ascending=False,
    ).head(20)

    print(
        highest.to_string(
            index=False,
            formatters={
                "zero_duration_rate": lambda x: f"{x:.2%}"
            },
        )
    )

    print("\n=== FIRST DAYS ABOVE THRESHOLDS ===\n")

    thresholds = [
        0.01,
        0.05,
        0.10,
        0.25,
        0.50,
    ]

    for threshold in thresholds:
        matches = daily[
            daily["zero_duration_rate"] >= threshold
        ]

        if matches.empty:
            print(
                f"{threshold:.0%}: never reached"
            )
        else:
            first = matches.iloc[0]

            print(
                f"{threshold:.0%}: "
                f"{first['pickup_date'].date()} | "
                f"{int(first['zero_duration']):,} / "
                f"{int(first['helix_trips']):,} "
                f"({first['zero_duration_rate']:.2%})"
            )

    print("\n=== MONTHLY HELIX SUMMARY ===\n")

    daily["month"] = (
        daily["pickup_date"]
        .dt.to_period("M")
        .astype(str)
    )

    monthly = (
        daily.groupby("month")
        .agg(
            helix_trips=("helix_trips", "sum"),
            zero_duration=("zero_duration", "sum"),
        )
    )

    monthly["zero_duration_rate"] = (
        monthly["zero_duration"]
        / monthly["helix_trips"]
    )

    print(
        monthly.to_string(
            formatters={
                "zero_duration_rate": lambda x: f"{x:.2%}"
            },
        )
    )


if __name__ == "__main__":
    main()