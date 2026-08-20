from io import BytesIO
import sys

import boto3
import pandas as pd


BUCKET_NAME = "nyc-mobility-pipeline-samtoussi"


# Columns expected from the 2025 Yellow Taxi source schema.
EXPECTED_RAW_COLUMNS = {
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


# These columns are required by our current Silver transformation.
# If one is missing, transformation cannot safely continue.
REQUIRED_RAW_COLUMNS = {
    "VendorID",
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime",
    "trip_distance",
    "payment_type",
    "fare_amount",
    "total_amount",
}


s3 = boto3.client("s3")


def list_raw_files(year: int):
    raw_prefix = f"raw/yellow_tripdata/year={year}/"

    response = s3.list_objects_v2(
        Bucket=BUCKET_NAME,
        Prefix=raw_prefix,
    )

    objects = response.get("Contents", [])

    return sorted(
        obj["Key"]
        for obj in objects
        if obj["Key"].endswith(".parquet")
    )


def read_parquet_from_s3(key):
    response = s3.get_object(
        Bucket=BUCKET_NAME,
        Key=key,
    )

    data = response["Body"].read()

    return pd.read_parquet(
        BytesIO(data)
    )


def validate_file(raw_key):
    print("\n" + "=" * 80)
    print(raw_key)
    print("=" * 80)

    df = read_parquet_from_s3(raw_key)

    failures = []
    warnings = []

    print(f"\nRows: {len(df):,}")

    actual_columns = set(df.columns)

    # ---------------------------------------------------------
    # 1. Required columns
    # ---------------------------------------------------------

    missing_required = (
        REQUIRED_RAW_COLUMNS
        - actual_columns
    )

    print(
        f"Missing required columns: "
        f"{sorted(missing_required)}"
    )

    if missing_required:
        failures.append(
            f"Missing required columns: "
            f"{sorted(missing_required)}"
        )

    # ---------------------------------------------------------
    # 2. Expected schema
    # ---------------------------------------------------------

    missing_expected = (
        EXPECTED_RAW_COLUMNS
        - actual_columns
    )

    unexpected_columns = (
        actual_columns
        - EXPECTED_RAW_COLUMNS
    )

    print(
        f"Missing expected columns: "
        f"{sorted(missing_expected)}"
    )

    print(
        f"Unexpected columns: "
        f"{sorted(unexpected_columns)}"
    )

    # Missing expected-but-not-required columns are warnings.
    optional_missing = (
        missing_expected
        - REQUIRED_RAW_COLUMNS
    )

    if optional_missing:
        warnings.append(
            f"Expected columns missing but not currently "
            f"required downstream: {sorted(optional_missing)}"
        )

    # New columns do not automatically make the batch invalid.
    if unexpected_columns:
        warnings.append(
            f"Unexpected upstream columns detected: "
            f"{sorted(unexpected_columns)}"
        )

    # ---------------------------------------------------------
    # 3. Critical timestamp nulls
    # ---------------------------------------------------------

    pickup_nulls = int(
        df["tpep_pickup_datetime"].isna().sum()
    ) if "tpep_pickup_datetime" in df.columns else None

    dropoff_nulls = int(
        df["tpep_dropoff_datetime"].isna().sum()
    ) if "tpep_dropoff_datetime" in df.columns else None

    if pickup_nulls is not None:
        print(
            f"NULL pickup timestamps: "
            f"{pickup_nulls:,}"
        )

    if dropoff_nulls is not None:
        print(
            f"NULL dropoff timestamps: "
            f"{dropoff_nulls:,}"
        )

    # For V1 we report timestamp nulls as warnings.
    # We have not yet established enough evidence
    # to fail an entire batch because of isolated null rows.
    if pickup_nulls:
        warnings.append(
            f"{pickup_nulls} NULL pickup timestamps"
        )

    if dropoff_nulls:
        warnings.append(
            f"{dropoff_nulls} NULL dropoff timestamps"
        )

    return failures, warnings


def main():
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: python src/validation/validate_raw.py <year>"
        )

    try:
        year = int(sys.argv[1])
    except ValueError:
        raise SystemExit("Year must be a number.")

    raw_prefix = f"raw/yellow_tripdata/year={year}/"
    raw_files = list_raw_files(year)

    print(f"=== RAW VALIDATION: {year} ===\n")
    print(f"Raw files found: {len(raw_files)}")

    if not raw_files:
        raise FileNotFoundError(
            f"No parquet files found under {raw_prefix}"
        )

    all_failures = []
    all_warnings = []

    for raw_key in raw_files:
        failures, warnings = validate_file(
            raw_key
        )

        for failure in failures:
            all_failures.append(
                f"{raw_key}: {failure}"
            )

        for warning in warnings:
            all_warnings.append(
                f"{raw_key}: {warning}"
            )

    print("\n" + "=" * 80)
    print("RAW VALIDATION SUMMARY")
    print("=" * 80)

    if all_warnings:
        print(
            f"\nWARNINGS: "
            f"{len(all_warnings)}\n"
        )

        for warning in all_warnings:
            print(f"- {warning}")

    if all_failures:
        print(
            f"\nFAILED with "
            f"{len(all_failures)} critical issue(s):\n"
        )

        for failure in all_failures:
            print(f"- {failure}")

        raise ValueError(
            "Raw validation failed. "
            "Downstream transformation must not run."
        )

    print("\nPASS ✅")

    print(
        f"All {year} Raw batches satisfy "
        "the current schema contract."
    )


if __name__ == "__main__":
    main()