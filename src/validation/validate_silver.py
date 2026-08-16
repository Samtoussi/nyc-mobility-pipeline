from io import BytesIO

import boto3
import pandas as pd


BUCKET_NAME = "nyc-mobility-pipeline-samtoussi"

RAW_PREFIX = "raw/yellow_tripdata/year=2025/"
SILVER_PREFIX = "silver/yellow_tripdata/year=2025/"

EXPECTED_DURATION_QUALITY = {
    "VALID",
    "INVALID",
    "UNAVAILABLE_SOURCE_SEMANTICS",
}

REQUIRED_SILVER_COLUMNS = {
    "VendorID",
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime",
    "trip_distance",
    "fare_amount",
    "duration_min",
    "duration_quality",
}

s3 = boto3.client("s3")


def list_parquet_files(prefix):
    response = s3.list_objects_v2(
        Bucket=BUCKET_NAME,
        Prefix=prefix,
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


def validate_file(raw_key, silver_key):
    print("\n" + "=" * 80)
    print(silver_key)
    print("=" * 80)

    raw_df = read_parquet_from_s3(raw_key)
    silver_df = read_parquet_from_s3(silver_key)

    failures = []

    # ---------------------------------------------------------
    # 1. Row count
    # ---------------------------------------------------------

    raw_rows = len(raw_df)
    silver_rows = len(silver_df)

    print(f"\nRaw rows:    {raw_rows:,}")
    print(f"Silver rows: {silver_rows:,}")

    if raw_rows != silver_rows:
        failures.append(
            f"Row count mismatch: raw={raw_rows}, silver={silver_rows}"
        )

    # ---------------------------------------------------------
    # 2. Required columns
    # ---------------------------------------------------------

    missing_columns = (
        REQUIRED_SILVER_COLUMNS
        - set(silver_df.columns)
    )

    print(
        f"Missing required Silver columns: "
        f"{sorted(missing_columns)}"
    )

    if missing_columns:
        failures.append(
            f"Missing columns: {sorted(missing_columns)}"
        )

    # If quality columns are missing, remaining checks
    # cannot be performed safely.
    if missing_columns:
        return failures

    # ---------------------------------------------------------
    # 3. duration_quality domain
    # ---------------------------------------------------------

    observed_quality = set(
        silver_df["duration_quality"]
        .dropna()
        .unique()
    )

    unexpected_quality = (
        observed_quality
        - EXPECTED_DURATION_QUALITY
    )

    print(
        f"duration_quality values: "
        f"{sorted(observed_quality)}"
    )

    if unexpected_quality:
        failures.append(
            f"Unexpected duration_quality values: "
            f"{sorted(unexpected_quality)}"
        )

    # ---------------------------------------------------------
    # 4. VALID durations must be positive or zero
    # ---------------------------------------------------------

    valid_rows = (
        silver_df["duration_quality"] == "VALID"
    )

    invalid_valid_duration = (
        valid_rows
        & (silver_df["duration_min"] < 0)
    )

    count = int(invalid_valid_duration.sum())

    print(
        f"VALID rows with negative duration: "
        f"{count:,}"
    )

    if count > 0:
        failures.append(
            f"{count} VALID rows have negative duration"
        )

    # ---------------------------------------------------------
    # 5. INVALID duration must be NULL
    # ---------------------------------------------------------

    invalid_rows = (
        silver_df["duration_quality"] == "INVALID"
    )

    invalid_with_value = (
        invalid_rows
        & silver_df["duration_min"].notna()
    )

    count = int(invalid_with_value.sum())

    print(
        f"INVALID rows with duration value: "
        f"{count:,}"
    )

    if count > 0:
        failures.append(
            f"{count} INVALID rows still contain duration"
        )

    # ---------------------------------------------------------
    # 6. Helix unavailable duration must be NULL
    # ---------------------------------------------------------

    unavailable_rows = (
        silver_df["duration_quality"]
        == "UNAVAILABLE_SOURCE_SEMANTICS"
    )

    unavailable_with_value = (
        unavailable_rows
        & silver_df["duration_min"].notna()
    )

    count = int(unavailable_with_value.sum())

    print(
        f"UNAVAILABLE rows with duration value: "
        f"{count:,}"
    )

    if count > 0:
        failures.append(
            f"{count} UNAVAILABLE rows still contain duration"
        )

    # ---------------------------------------------------------
    # Summary
    # ---------------------------------------------------------

    print("\nDuration quality distribution:")

    print(
        silver_df["duration_quality"]
        .value_counts(dropna=False)
    )

    return failures


def main():
    raw_files = list_parquet_files(RAW_PREFIX)
    silver_files = list_parquet_files(SILVER_PREFIX)

    print("=== SILVER VALIDATION V1 ===\n")

    print(f"Raw files:    {len(raw_files)}")
    print(f"Silver files: {len(silver_files)}")

    if len(raw_files) != len(silver_files):
        raise ValueError(
            "Raw and Silver file counts do not match."
        )

    all_failures = []

    for raw_key, silver_key in zip(
        raw_files,
        silver_files,
    ):
        failures = validate_file(
            raw_key,
            silver_key,
        )

        for failure in failures:
            all_failures.append(
                f"{silver_key}: {failure}"
            )

    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)

    if all_failures:
        print(
            f"\nFAILED with "
            f"{len(all_failures)} issue(s):\n"
        )

        for failure in all_failures:
            print(f"- {failure}")

        raise ValueError(
            "Silver validation failed."
        )

    print("\nPASS ✅")
    print(
        "All Silver batches satisfy "
        "the current V1 validation rules."
    )


if __name__ == "__main__":
    main()