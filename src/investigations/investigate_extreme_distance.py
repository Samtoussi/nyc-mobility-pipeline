from pathlib import Path

import pandas as pd


RAW_DIR = Path("data/raw")


COLUMNS = [
    "VendorID",
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime",
    "trip_distance",
    "PULocationID",
    "DOLocationID",
    "payment_type",
    "RatecodeID",
    "fare_amount",
    "total_amount",
]


DISTANCE_BINS = [
    0,
    50,
    100,
    500,
    1_000,
    10_000,
    float("inf"),
]

DISTANCE_LABELS = [
    "0-50",
    "50-100",
    "100-500",
    "500-1,000",
    "1,000-10,000",
    "10,000+",
]


def load_extreme_trips():
    files = sorted(
        RAW_DIR.glob("yellow_tripdata_2025-*.parquet")
    )

    frames = []
    total_rows = 0

    for file_path in files:
        print(f"Reading {file_path.name}...")

        df = pd.read_parquet(
            file_path,
            columns=COLUMNS,
        )

        total_rows += len(df)

        # Keep only trips above 50 miles for detailed investigation.
        extreme = df[df["trip_distance"] > 50].copy()

        extreme["source_file"] = file_path.name

        frames.append(extreme)

    if not frames:
        return pd.DataFrame(), total_rows

    return pd.concat(frames, ignore_index=True), total_rows


def main():
    print(
        "=== INC-004: EXTREME TRIP DISTANCE INVESTIGATION ===\n"
    )

    extreme, total_rows = load_extreme_trips()

    print("\n" + "=" * 70)
    print("POPULATION")
    print("=" * 70)

    print(f"\nTotal 2025 rows:       {total_rows:,}")
    print(f"Trips above 50 miles:  {len(extreme):,}")

    if total_rows > 0:
        print(
            f"Rate:                  "
            f"{len(extreme) / total_rows:.6%}"
        )

    if extreme.empty:
        print("\nNo trips above 50 miles found.")
        return

    # ---------------------------------------------------------
    # Distance buckets
    # ---------------------------------------------------------

    extreme["distance_bucket"] = pd.cut(
        extreme["trip_distance"],
        bins=DISTANCE_BINS,
        labels=DISTANCE_LABELS,
        right=False,
    )

    print("\n" + "=" * 70)
    print("DISTANCE BUCKETS")
    print("=" * 70)

    print(
        extreme["distance_bucket"]
        .value_counts(sort=False)
    )

    # ---------------------------------------------------------
    # Vendors
    # ---------------------------------------------------------

    print("\n" + "=" * 70)
    print("VENDOR DISTRIBUTION")
    print("=" * 70)

    print(
        extreme["VendorID"]
        .value_counts(dropna=False)
        .sort_index()
    )

    # ---------------------------------------------------------
    # Duration
    # ---------------------------------------------------------

    extreme["duration_min"] = (
        extreme["tpep_dropoff_datetime"]
        - extreme["tpep_pickup_datetime"]
    ).dt.total_seconds() / 60

    print("\n" + "=" * 70)
    print("DURATION BEHAVIOUR")
    print("=" * 70)

    print(
        f"\nNegative duration: "
        f"{(extreme['duration_min'] < 0).sum():,}"
    )

    print(
        f"Zero duration:     "
        f"{(extreme['duration_min'] == 0).sum():,}"
    )

    print(
        f"Positive duration: "
        f"{(extreme['duration_min'] > 0).sum():,}"
    )

    print("\nDuration statistics:")
    print(extreme["duration_min"].describe())

    # ---------------------------------------------------------
    # Fare
    # ---------------------------------------------------------

    print("\n" + "=" * 70)
    print("FARE BEHAVIOUR")
    print("=" * 70)

    print(
        f"\nNegative fare: "
        f"{(extreme['fare_amount'] < 0).sum():,}"
    )

    print(
        f"Zero fare:     "
        f"{(extreme['fare_amount'] == 0).sum():,}"
    )

    print(
        f"Positive fare: "
        f"{(extreme['fare_amount'] > 0).sum():,}"
    )

    print("\nFare statistics:")
    print(extreme["fare_amount"].describe())

    # ---------------------------------------------------------
    # Relationship between distance and fare
    # ---------------------------------------------------------

    valid_ratio = (
        (extreme["trip_distance"] > 0)
        & (extreme["fare_amount"] > 0)
    )

    extreme.loc[valid_ratio, "fare_per_mile"] = (
        extreme.loc[valid_ratio, "fare_amount"]
        / extreme.loc[valid_ratio, "trip_distance"]
    )

    print("\n" + "=" * 70)
    print("FARE PER MILE")
    print("=" * 70)

    print(extreme["fare_per_mile"].describe())

    # ---------------------------------------------------------
    # Largest trips
    # ---------------------------------------------------------

    print("\n" + "=" * 70)
    print("TOP 30 LONGEST TRIPS")
    print("=" * 70)

    longest = (
        extreme.sort_values(
            "trip_distance",
            ascending=False,
        )
        .head(30)
    )

    print(
        longest[
            [
                "source_file",
                "VendorID",
                "tpep_pickup_datetime",
                "tpep_dropoff_datetime",
                "duration_min",
                "trip_distance",
                "PULocationID",
                "DOLocationID",
                "payment_type",
                "RatecodeID",
                "fare_amount",
                "total_amount",
                "fare_per_mile",
            ]
        ].to_string(index=False)
    )

    # ---------------------------------------------------------
    # Monthly distribution
    # ---------------------------------------------------------

    print("\n" + "=" * 70)
    print("MONTHLY EXTREME DISTANCE COUNTS")
    print("=" * 70)

    monthly = (
        extreme.groupby("source_file")
        .size()
        .rename("trips_above_50")
    )

    print(monthly)


if __name__ == "__main__":
    main()