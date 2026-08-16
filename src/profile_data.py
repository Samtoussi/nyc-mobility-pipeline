from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq


RAW_DIR = Path("data/raw")
PROFILE_DIR = Path("data/profiles")
PROFILE_OUTPUT = PROFILE_DIR / "batch_profiles.parquet"


EXPECTED_COLUMNS = {
    "VendorID",
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime",
    "passenger_count",
    "trip_distance",
    "RatecodeID",
    "store_and_fwd_flag",
    "PULocationID",
    "DOLocationID",
    "payment_type",
    "fare_amount",
    "extra",
    "mta_tax",
    "tip_amount",
    "tolls_amount",
    "improvement_surcharge",
    "total_amount",
    "congestion_surcharge",
    "Airport_fee",
    "cbd_congestion_fee",
}


def rate(count: int, total: int) -> float:
    if total == 0:
        return 0.0

    return count / total


def profile_file(file_path: Path) -> dict:
    parquet_file = pq.ParquetFile(file_path)

    actual_columns = set(parquet_file.schema.names)

    missing_columns = EXPECTED_COLUMNS - actual_columns
    unexpected_columns = actual_columns - EXPECTED_COLUMNS

    df = pd.read_parquet(
        file_path,
        columns=[
            "VendorID",
            "tpep_pickup_datetime",
            "tpep_dropoff_datetime",
            "trip_distance",
            "PULocationID",
            "DOLocationID",
            "payment_type",
            "fare_amount",
            "total_amount",
        ],
    )

    rows = len(df)

    duration_min = (
        df["tpep_dropoff_datetime"]
        - df["tpep_pickup_datetime"]
    ).dt.total_seconds() / 60

    negative_duration = int((duration_min < 0).sum())
    zero_duration = int((duration_min == 0).sum())

    negative_distance = int((df["trip_distance"] < 0).sum())
    zero_distance = int((df["trip_distance"] == 0).sum())

    negative_fare = int((df["fare_amount"] < 0).sum())
    zero_fare = int((df["fare_amount"] == 0).sum())

    negative_total = int((df["total_amount"] < 0).sum())
    zero_total = int((df["total_amount"] == 0).sum())

    distance_quantiles = df["trip_distance"].quantile(
        [0.50, 0.95, 0.99, 0.999]
    )

    profile = {
        "file": file_path.name,
        "rows": rows,

        # Schema
        "missing_columns": sorted(missing_columns),
        "unexpected_columns": sorted(unexpected_columns),

        # Temporal
        "negative_duration": negative_duration,
        "negative_duration_rate": rate(
            negative_duration,
            rows,
        ),
        "zero_duration": zero_duration,
        "zero_duration_rate": rate(
            zero_duration,
            rows,
        ),

        # Distance
        "negative_distance": negative_distance,
        "negative_distance_rate": rate(
            negative_distance,
            rows,
        ),
        "zero_distance": zero_distance,
        "zero_distance_rate": rate(
            zero_distance,
            rows,
        ),
        "p50_distance": float(distance_quantiles.loc[0.50]),
        "p95_distance": float(distance_quantiles.loc[0.95]),
        "p99_distance": float(distance_quantiles.loc[0.99]),
        "p999_distance": float(distance_quantiles.loc[0.999]),
        "max_distance": float(df["trip_distance"].max()),

        # Financial
        "negative_fare": negative_fare,
        "negative_fare_rate": rate(
            negative_fare,
            rows,
        ),
        "zero_fare": zero_fare,
        "zero_fare_rate": rate(
            zero_fare,
            rows,
        ),
        "negative_total": negative_total,
        "negative_total_rate": rate(
            negative_total,
            rows,
        ),
        "zero_total": zero_total,
        "zero_total_rate": rate(
            zero_total,
            rows,
        ),

        # Structural / categorical
        "null_pickup_location": int(
            df["PULocationID"].isna().sum()
        ),
        "null_dropoff_location": int(
            df["DOLocationID"].isna().sum()
        ),
        "vendor_ids": sorted(
            df["VendorID"].dropna().unique().tolist()
        ),
        "payment_types": sorted(
            df["payment_type"].dropna().unique().tolist()
        ),
    }

    return profile


def print_profile(profile: dict) -> None:
    print("\n" + "=" * 60)
    print(profile["file"])
    print("=" * 60)

    print(f"\nRows: {profile['rows']:,}")

    print("\nSCHEMA")
    print(f"Missing columns:    {profile['missing_columns']}")
    print(f"Unexpected columns: {profile['unexpected_columns']}")

    print("\nTEMPORAL")
    print(
        f"Negative duration: "
        f"{profile['negative_duration']:,} "
        f"({profile['negative_duration_rate']:.4%})"
    )
    print(
        f"Zero duration:     "
        f"{profile['zero_duration']:,} "
        f"({profile['zero_duration_rate']:.4%})"
    )

    print("\nDISTANCE")
    print(
        f"Negative distance: "
        f"{profile['negative_distance']:,} "
        f"({profile['negative_distance_rate']:.4%})"
    )
    print(
        f"Zero distance:     "
        f"{profile['zero_distance']:,} "
        f"({profile['zero_distance_rate']:.4%})"
    )

    print(f"P50 distance:      {profile['p50_distance']:,.2f}")
    print(f"P95 distance:      {profile['p95_distance']:,.2f}")
    print(f"P99 distance:      {profile['p99_distance']:,.2f}")
    print(f"P99.9 distance:    {profile['p999_distance']:,.2f}")
    print(f"Maximum distance:  {profile['max_distance']:,.2f}")

    print("\nFINANCIAL")
    print(
        f"Negative fare:  "
        f"{profile['negative_fare']:,} "
        f"({profile['negative_fare_rate']:.4%})"
    )
    print(
        f"Zero fare:      "
        f"{profile['zero_fare']:,} "
        f"({profile['zero_fare_rate']:.4%})"
    )
    print(
        f"Negative total: "
        f"{profile['negative_total']:,} "
        f"({profile['negative_total_rate']:.4%})"
    )
    print(
        f"Zero total:     "
        f"{profile['zero_total']:,} "
        f"({profile['zero_total_rate']:.4%})"
    )

    print("\nSTRUCTURAL")
    print(
        f"NULL pickup location:  "
        f"{profile['null_pickup_location']:,}"
    )
    print(
        f"NULL dropoff location: "
        f"{profile['null_dropoff_location']:,}"
    )

    print(f"Vendor IDs:    {profile['vendor_ids']}")
    print(f"Payment types: {profile['payment_types']}")


def main():
    files = sorted(
        RAW_DIR.glob("yellow_tripdata_2025-*.parquet")
    )

    if not files:
        raise FileNotFoundError(
            f"No Yellow Taxi Parquet files found in {RAW_DIR}"
        )

    print(f"Found {len(files)} files.")

    profiles = []

    for file_path in files:
        profile = profile_file(file_path)

        print_profile(profile)

        profiles.append(
            {
                "file": profile["file"],
                "rows": profile["rows"],

                "missing_column_count": len(
                    profile["missing_columns"]
                ),
                "unexpected_column_count": len(
                    profile["unexpected_columns"]
                ),

                "negative_duration": profile[
                    "negative_duration"
                ],
                "negative_duration_rate": profile[
                    "negative_duration_rate"
                ],

                "zero_duration": profile[
                    "zero_duration"
                ],
                "zero_duration_rate": profile[
                    "zero_duration_rate"
                ],

                "negative_distance": profile[
                    "negative_distance"
                ],
                "negative_distance_rate": profile[
                    "negative_distance_rate"
                ],

                "zero_distance": profile[
                    "zero_distance"
                ],
                "zero_distance_rate": profile[
                    "zero_distance_rate"
                ],

                "p50_distance": profile["p50_distance"],
                "p95_distance": profile["p95_distance"],
                "p99_distance": profile["p99_distance"],
                "p999_distance": profile["p999_distance"],
                "max_distance": profile["max_distance"],

                "negative_fare": profile[
                    "negative_fare"
                ],
                "negative_fare_rate": profile[
                    "negative_fare_rate"
                ],

                "zero_fare": profile[
                    "zero_fare"
                ],
                "zero_fare_rate": profile[
                    "zero_fare_rate"
                ],

                "negative_total": profile[
                    "negative_total"
                ],
                "negative_total_rate": profile[
                    "negative_total_rate"
                ],

                "zero_total": profile[
                    "zero_total"
                ],
                "zero_total_rate": profile[
                    "zero_total_rate"
                ],

                "null_pickup_location": profile[
                    "null_pickup_location"
                ],
                "null_dropoff_location": profile[
                    "null_dropoff_location"
                ],
            }
        )

    profile_df = pd.DataFrame(profiles)

    PROFILE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    profile_df.to_parquet(
        PROFILE_OUTPUT,
        index=False,
    )

    print("\n" + "=" * 60)
    print("PROFILING COMPLETE")
    print("=" * 60)

    print(f"\nBatches profiled: {len(profile_df)}")
    print(f"Output: {PROFILE_OUTPUT}")

    print("\nBatch summary:")
    print(profile_df.to_string(index=False))


if __name__ == "__main__":
    main()