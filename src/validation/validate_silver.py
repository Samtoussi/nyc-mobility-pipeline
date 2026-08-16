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


EXPECTED_DISTANCE_QUALITY = {
    "VALID",
    "INVALID",
    "ZERO_REPORTED",
    "SUSPICIOUS_EXTREME",
}


REQUIRED_SILVER_COLUMNS = {
    "VendorID",
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime",
    "trip_distance",
    "fare_amount",
    "duration_min",
    "duration_quality",
    "distance_quality",
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

        return failures

    # ---------------------------------------------------------
    # 3. duration_quality domain
    # ---------------------------------------------------------

    observed_duration_quality = set(
        silver_df["duration_quality"]
        .dropna()
        .unique()
    )

    unexpected_duration_quality = (
        observed_duration_quality
        - EXPECTED_DURATION_QUALITY
    )

    print(
        f"duration_quality values: "
        f"{sorted(observed_duration_quality)}"
    )

    if unexpected_duration_quality:
        failures.append(
            f"Unexpected duration_quality values: "
            f"{sorted(unexpected_duration_quality)}"
        )

    # ---------------------------------------------------------
    # 4. VALID durations must not be negative
    # ---------------------------------------------------------

    valid_duration_rows = (
        silver_df["duration_quality"] == "VALID"
    )

    valid_with_negative_duration = (
        valid_duration_rows
        & (silver_df["duration_min"] < 0)
    )

    count = int(
        valid_with_negative_duration.sum()
    )

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

    invalid_duration_rows = (
        silver_df["duration_quality"] == "INVALID"
    )

    invalid_duration_with_value = (
        invalid_duration_rows
        & silver_df["duration_min"].notna()
    )

    count = int(
        invalid_duration_with_value.sum()
    )

    print(
        f"INVALID rows with duration value: "
        f"{count:,}"
    )

    if count > 0:
        failures.append(
            f"{count} INVALID rows still contain duration"
        )

    # ---------------------------------------------------------
    # 6. UNAVAILABLE duration must be NULL
    # ---------------------------------------------------------

    unavailable_duration_rows = (
        silver_df["duration_quality"]
        == "UNAVAILABLE_SOURCE_SEMANTICS"
    )

    unavailable_duration_with_value = (
        unavailable_duration_rows
        & silver_df["duration_min"].notna()
    )

    count = int(
        unavailable_duration_with_value.sum()
    )

    print(
        f"UNAVAILABLE rows with duration value: "
        f"{count:,}"
    )

    if count > 0:
        failures.append(
            f"{count} UNAVAILABLE rows still contain duration"
        )

    # ---------------------------------------------------------
    # 7. distance_quality domain
    # ---------------------------------------------------------

    observed_distance_quality = set(
        silver_df["distance_quality"]
        .dropna()
        .unique()
    )

    unexpected_distance_quality = (
        observed_distance_quality
        - EXPECTED_DISTANCE_QUALITY
    )

    print(
        f"distance_quality values: "
        f"{sorted(observed_distance_quality)}"
    )

    if unexpected_distance_quality:
        failures.append(
            f"Unexpected distance_quality values: "
            f"{sorted(unexpected_distance_quality)}"
        )

    # ---------------------------------------------------------
    # 8. Negative distance must be INVALID
    # ---------------------------------------------------------

    negative_distance_wrong = (
        (silver_df["trip_distance"] < 0)
        & (
            silver_df["distance_quality"]
            != "INVALID"
        )
    )

    count = int(
        negative_distance_wrong.sum()
    )

    print(
        f"Negative distances not INVALID: "
        f"{count:,}"
    )

    if count > 0:
        failures.append(
            f"{count} negative distances are not INVALID"
        )

    # ---------------------------------------------------------
    # 9. Zero distance must be ZERO_REPORTED
    # ---------------------------------------------------------

    zero_distance_wrong = (
        (silver_df["trip_distance"] == 0)
        & (
            silver_df["distance_quality"]
            != "ZERO_REPORTED"
        )
    )

    count = int(
        zero_distance_wrong.sum()
    )

    print(
        f"Zero distances not ZERO_REPORTED: "
        f"{count:,}"
    )

    if count > 0:
        failures.append(
            f"{count} zero distances are not ZERO_REPORTED"
        )

    # ---------------------------------------------------------
    # 10. Distances > 500 must be SUSPICIOUS_EXTREME
    # ---------------------------------------------------------

    extreme_distance_wrong = (
        (silver_df["trip_distance"] > 500)
        & (
            silver_df["distance_quality"]
            != "SUSPICIOUS_EXTREME"
        )
    )

    count = int(
        extreme_distance_wrong.sum()
    )

    print(
        f"Distances >500 not SUSPICIOUS_EXTREME: "
        f"{count:,}"
    )

    if count > 0:
        failures.append(
            f"{count} extreme distances are incorrectly classified"
        )

    # ---------------------------------------------------------
    # 11. VALID distance must be > 0 and <= 500
    # ---------------------------------------------------------

    valid_distance_wrong = (
        (silver_df["distance_quality"] == "VALID")
        & (
            (silver_df["trip_distance"] <= 0)
            | (silver_df["trip_distance"] > 500)
        )
    )

    count = int(
        valid_distance_wrong.sum()
    )

    print(
        f"VALID distances outside expected range: "
        f"{count:,}"
    )

    if count > 0:
        failures.append(
            f"{count} VALID distance rows are outside expected range"
        )

    # ---------------------------------------------------------
    # Distribution summary
    # ---------------------------------------------------------

    print("\nDuration quality distribution:")

    print(
        silver_df["duration_quality"]
        .value_counts(dropna=False)
    )

    print("\nDistance quality distribution:")

    print(
        silver_df["distance_quality"]
        .value_counts(dropna=False)
    )

    return failures


def main():
    raw_files = list_parquet_files(
        RAW_PREFIX
    )

    silver_files = list_parquet_files(
        SILVER_PREFIX
    )

    print("=== SILVER VALIDATION V2 ===\n")

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
        "the current V2 validation rules."
    )


if __name__ == "__main__":
    main()