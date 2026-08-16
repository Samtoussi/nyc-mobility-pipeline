from pathlib import Path

import pandas as pd


RAW_DIR = Path("data/raw")

COLUMNS = [
    "VendorID",
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime",
    "trip_distance",
    "payment_type",
    "RatecodeID",
    "fare_amount",
    "total_amount",
]

DISTANCE_BINS = [
    50,
    100,
    500,
    1_000,
    10_000,
    float("inf"),
]

DISTANCE_LABELS = [
    "50-100",
    "100-500",
    "500-1,000",
    "1,000-10,000",
    "10,000+",
]


def load_extreme_trips() -> pd.DataFrame:
    frames = []

    files = sorted(
        RAW_DIR.glob("yellow_tripdata_2025-*.parquet")
    )

    for file_path in files:
        print(f"Reading {file_path.name}...")

        df = pd.read_parquet(
            file_path,
            columns=COLUMNS,
        )

        extreme = df[
            df["trip_distance"] >= 50
        ].copy()

        extreme["source_file"] = file_path.name

        frames.append(extreme)

    return pd.concat(
        frames,
        ignore_index=True,
    )


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    df["distance_bucket"] = pd.cut(
        df["trip_distance"],
        bins=DISTANCE_BINS,
        labels=DISTANCE_LABELS,
        right=False,
    )

    df["duration_min"] = (
        df["tpep_dropoff_datetime"]
        - df["tpep_pickup_datetime"]
    ).dt.total_seconds() / 60

    df["ratecode_is_null"] = df["RatecodeID"].isna()

    return df


def print_distribution(
    df: pd.DataFrame,
    column: str,
) -> None:

    table = pd.crosstab(
        df["distance_bucket"],
        df[column],
        dropna=False,
    )

    print(table)


def main():
    print(
        "=== INC-004: DISTANCE BUCKET PROFILING ===\n"
    )

    df = load_extreme_trips()
    df = add_features(df)

    print(f"\nExtreme trips loaded: {len(df):,}")

    print("\n" + "=" * 70)
    print("BUCKET SIZE")
    print("=" * 70)

    print(
        df["distance_bucket"]
        .value_counts(sort=False)
    )

    print("\n" + "=" * 70)
    print("VENDOR BY DISTANCE BUCKET")
    print("=" * 70)

    print_distribution(
        df,
        "VendorID",
    )

    print("\n" + "=" * 70)
    print("PAYMENT TYPE BY DISTANCE BUCKET")
    print("=" * 70)

    print_distribution(
        df,
        "payment_type",
    )

    print("\n" + "=" * 70)
    print("NULL RATECODE BY DISTANCE BUCKET")
    print("=" * 70)

    ratecode_table = (
        df.groupby(
            "distance_bucket",
            observed=True,
        )
        .agg(
            trips=("trip_distance", "size"),
            null_ratecode=("ratecode_is_null", "sum"),
        )
    )

    ratecode_table["null_ratecode_rate"] = (
        ratecode_table["null_ratecode"]
        / ratecode_table["trips"]
    )

    print(
        ratecode_table.to_string(
            formatters={
                "null_ratecode_rate":
                    lambda x: f"{x:.2%}"
            }
        )
    )

    print("\n" + "=" * 70)
    print("DURATION BY DISTANCE BUCKET")
    print("=" * 70)

    duration_stats = (
        df.groupby(
            "distance_bucket",
            observed=True,
        )["duration_min"]
        .agg(
            [
                "count",
                "median",
                "mean",
                "min",
                "max",
            ]
        )
    )

    print(duration_stats)

    print("\n" + "=" * 70)
    print("FARE BY DISTANCE BUCKET")
    print("=" * 70)

    fare_stats = (
        df.groupby(
            "distance_bucket",
            observed=True,
        )["fare_amount"]
        .agg(
            [
                "count",
                "median",
                "mean",
                "min",
                "max",
            ]
        )
    )

    print(fare_stats)

    # ---------------------------------------------------------
    # Test our strongest current hypothesis
    # ---------------------------------------------------------

    print("\n" + "=" * 70)
    print("10,000+ SOURCE PATTERN")
    print("=" * 70)

    insane = df[
        df["distance_bucket"] == "10,000+"
    ].copy()

    print(f"\n10,000+ trips: {len(insane):,}")

    if not insane.empty:
        vendor2 = insane["VendorID"] == 2
        payment0 = insane["payment_type"] == 0
        null_ratecode = insane["RatecodeID"].isna()

        exact_pattern = (
            vendor2
            & payment0
            & null_ratecode
        )

        print(
            f"VendorID = 2:       "
            f"{vendor2.sum():,} "
            f"({vendor2.mean():.2%})"
        )

        print(
            f"payment_type = 0:   "
            f"{payment0.sum():,} "
            f"({payment0.mean():.2%})"
        )

        print(
            f"RatecodeID is NULL: "
            f"{null_ratecode.sum():,} "
            f"({null_ratecode.mean():.2%})"
        )

        print(
            f"\nALL THREE:          "
            f"{exact_pattern.sum():,} "
            f"({exact_pattern.mean():.2%})"
        )

        print("\nVendor distribution:")
        print(
            insane["VendorID"]
            .value_counts(dropna=False)
            .sort_index()
        )

        print("\nPayment distribution:")
        print(
            insane["payment_type"]
            .value_counts(dropna=False)
            .sort_index()
        )

        print("\nRatecode distribution:")
        print(
            insane["RatecodeID"]
            .value_counts(dropna=False)
            .sort_index()
        )


if __name__ == "__main__":
    main()