from pathlib import Path

import pandas as pd


RAW_DIR = Path("data/raw")

FILES = [
    "yellow_tripdata_2025-01.parquet",
    "yellow_tripdata_2025-03.parquet",
    "yellow_tripdata_2025-05.parquet",
    "yellow_tripdata_2025-08.parquet",
]

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


def investigate(file_name: str) -> None:
    file_path = RAW_DIR / file_name

    df = pd.read_parquet(
        file_path,
        columns=COLUMNS,
    )

    duration_seconds = (
        df["tpep_dropoff_datetime"]
        - df["tpep_pickup_datetime"]
    ).dt.total_seconds()

    zero = df[duration_seconds == 0].copy()

    print("\n" + "=" * 75)
    print(file_name)
    print("=" * 75)

    print(f"\nTotal rows:          {len(df):,}")
    print(f"Zero-duration rows:  {len(zero):,}")
    print(f"Rate:                {len(zero) / len(df):.4%}")

    print("\n--- Vendor ---")
    print(
        zero["VendorID"]
        .value_counts(dropna=False)
        .sort_index()
    )

    print("\n--- Payment type ---")
    print(
        zero["payment_type"]
        .value_counts(dropna=False)
        .sort_index()
    )

    print("\n--- Rate code ---")
    print(
        zero["RatecodeID"]
        .value_counts(dropna=False)
        .sort_index()
    )

    print("\n--- Distance behaviour ---")
    print(f"Zero distance:     {(zero['trip_distance'] == 0).sum():,}")
    print(f"Positive distance: {(zero['trip_distance'] > 0).sum():,}")
    print(f"Negative distance: {(zero['trip_distance'] < 0).sum():,}")

    print("\nDistance statistics:")
    print(zero["trip_distance"].describe())

    print("\n--- Fare behaviour ---")
    print(f"Negative fare: {(zero['fare_amount'] < 0).sum():,}")
    print(f"Zero fare:     {(zero['fare_amount'] == 0).sum():,}")
    print(f"Positive fare: {(zero['fare_amount'] > 0).sum():,}")

    print("\n--- Pickup hour ---")
    print(
        zero["tpep_pickup_datetime"]
        .dt.hour
        .value_counts()
        .sort_index()
    )

    print("\n--- Sample rows ---")
    print(
        zero[
            [
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
        ]
        .head(15)
        .to_string(index=False)
    )


def main():
    print("=== INC-003: ZERO-DURATION REGIME CHANGE ===")

    for file_name in FILES:
        investigate(file_name)


if __name__ == "__main__":
    main()