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


def load_insane_trips() -> pd.DataFrame:
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

        insane = df[
            df["trip_distance"] >= 10_000
        ].copy()

        insane["source_file"] = file_path.name

        frames.append(insane)

    return pd.concat(
        frames,
        ignore_index=True,
    )


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    df["duration_min"] = (
        df["tpep_dropoff_datetime"]
        - df["tpep_pickup_datetime"]
    ).dt.total_seconds() / 60

    return df


def classify_population(df: pd.DataFrame) -> pd.DataFrame:
    population_a = (
        (df["VendorID"] == 2)
        & (df["payment_type"] == 0)
        & (df["RatecodeID"].isna())
    )

    population_b = (
        (df["VendorID"] == 1)
        & (df["RatecodeID"] == 99)
    )

    df["population"] = "C_REMAINDER"

    df.loc[
        population_a,
        "population",
    ] = "A_VENDOR2_PAYMENT0_NULL_RATECODE"

    df.loc[
        population_b,
        "population",
    ] = "B_VENDOR1_RATECODE99"

    return df


def print_population_summary(
    df: pd.DataFrame,
    population_name: str,
) -> None:

    subset = df[
        df["population"] == population_name
    ]

    print("\n" + "=" * 90)
    print(population_name)
    print("=" * 90)

    print(f"\nRows: {len(subset):,}")

    if subset.empty:
        return

    print("\n--- Distance ---")
    print(subset["trip_distance"].describe())

    print("\n--- Duration ---")
    print(subset["duration_min"].describe())

    print("\n--- Fare ---")
    print(subset["fare_amount"].describe())

    print("\n--- Vendor ---")
    print(
        subset["VendorID"]
        .value_counts(dropna=False)
        .sort_index()
    )

    print("\n--- Payment type ---")
    print(
        subset["payment_type"]
        .value_counts(dropna=False)
        .sort_index()
    )

    print("\n--- Ratecode ---")
    print(
        subset["RatecodeID"]
        .value_counts(dropna=False)
        .sort_index()
    )

    print("\n--- Monthly distribution ---")
    print(
        subset["source_file"]
        .value_counts()
        .sort_index()
    )

    print("\n--- Sample rows ---")

    sample_columns = [
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
    ]

    print(
        subset[
            sample_columns
        ]
        .head(20)
        .to_string(index=False)
    )


def main():
    print(
        "=== INC-004: EXTREME DISTANCE POPULATIONS ===\n"
    )

    df = load_insane_trips()

    df = add_features(df)
    df = classify_population(df)

    print(f"\n10,000+ trips loaded: {len(df):,}")

    print("\n" + "=" * 90)
    print("POPULATION COUNTS")
    print("=" * 90)

    print(
        df["population"]
        .value_counts()
    )

    for population_name in [
        "A_VENDOR2_PAYMENT0_NULL_RATECODE",
        "B_VENDOR1_RATECODE99",
        "C_REMAINDER",
    ]:
        print_population_summary(
            df,
            population_name,
        )


if __name__ == "__main__":
    main()