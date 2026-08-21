from io import BytesIO
import sys

import boto3
import pandas as pd


BUCKET_NAME = "nyc-mobility-pipeline-samtoussi"


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

EXPECTED_FINANCIAL_QUALITY = {
    "STANDARD",
    "ZERO_REPORTED",
    "NEGATIVE_REPORTED",
    "SOURCE_SPECIFIC",
}


REQUIRED_SILVER_COLUMNS = {
    "VendorID",
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime",
    "trip_distance",
    "fare_amount",
    "total_amount",
    "payment_type",
    "duration_min",
    "duration_quality",
    "distance_quality",
    "financial_quality",
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

    valid_with_negative_duration = (
        (silver_df["duration_quality"] == "VALID")
        & (silver_df["duration_min"] < 0)
    )

    count = int(valid_with_negative_duration.sum())

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

    invalid_duration_with_value = (
        (silver_df["duration_quality"] == "INVALID")
        & silver_df["duration_min"].notna()
    )

    count = int(invalid_duration_with_value.sum())

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

    unavailable_duration_with_value = (
        (
            silver_df["duration_quality"]
            == "UNAVAILABLE_SOURCE_SEMANTICS"
        )
        & silver_df["duration_min"].notna()
    )

    count = int(unavailable_duration_with_value.sum())

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

    count = int(negative_distance_wrong.sum())

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

    count = int(zero_distance_wrong.sum())

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

    count = int(extreme_distance_wrong.sum())

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

    count = int(valid_distance_wrong.sum())

    print(
        f"VALID distances outside expected range: "
        f"{count:,}"
    )

    if count > 0:
        failures.append(
            f"{count} VALID distance rows are outside expected range"
        )

    # ---------------------------------------------------------
    # 12. financial_quality domain
    # ---------------------------------------------------------

    observed_financial_quality = set(
        silver_df["financial_quality"]
        .dropna()
        .unique()
    )

    unexpected_financial_quality = (
        observed_financial_quality
        - EXPECTED_FINANCIAL_QUALITY
    )

    print(
        f"financial_quality values: "
        f"{sorted(observed_financial_quality)}"
    )

    if unexpected_financial_quality:
        failures.append(
            f"Unexpected financial_quality values: "
            f"{sorted(unexpected_financial_quality)}"
        )

    # ---------------------------------------------------------
    # 13. payment_type=0 must be SOURCE_SPECIFIC
    # ---------------------------------------------------------

    source_specific_wrong = (
        (silver_df["payment_type"] == 0)
        & (
            silver_df["financial_quality"]
            != "SOURCE_SPECIFIC"
        )
    )

    count = int(source_specific_wrong.sum())

    print(
        f"payment_type=0 not SOURCE_SPECIFIC: "
        f"{count:,}"
    )

    if count > 0:
        failures.append(
            f"{count} payment_type=0 rows are not SOURCE_SPECIFIC"
        )

    # ---------------------------------------------------------
    # 14. Non-Flex negative values must be NEGATIVE_REPORTED
    # ---------------------------------------------------------

    negative_financial_wrong = (
        (silver_df["payment_type"] != 0)
        & (
            (silver_df["fare_amount"] < 0)
            | (silver_df["total_amount"] < 0)
        )
        & (
            silver_df["financial_quality"]
            != "NEGATIVE_REPORTED"
        )
    )

    count = int(negative_financial_wrong.sum())

    print(
        f"Non-Flex negative financial rows misclassified: "
        f"{count:,}"
    )

    if count > 0:
        failures.append(
            f"{count} non-Flex negative financial rows "
            f"are incorrectly classified"
        )

    # ---------------------------------------------------------
    # 15. Non-Flex zero values must be ZERO_REPORTED
    #     unless a negative condition takes priority
    # ---------------------------------------------------------

    zero_financial_wrong = (
        (silver_df["payment_type"] != 0)
        & (silver_df["fare_amount"] >= 0)
        & (silver_df["total_amount"] >= 0)
        & (
            (silver_df["fare_amount"] == 0)
            | (silver_df["total_amount"] == 0)
        )
        & (
            silver_df["financial_quality"]
            != "ZERO_REPORTED"
        )
    )

    count = int(zero_financial_wrong.sum())

    print(
        f"Non-Flex zero financial rows misclassified: "
        f"{count:,}"
    )

    if count > 0:
        failures.append(
            f"{count} non-Flex zero financial rows "
            f"are incorrectly classified"
        )

    # ---------------------------------------------------------
    # 16. STANDARD must contain ordinary positive values
    # ---------------------------------------------------------

    standard_wrong = (
        (silver_df["financial_quality"] == "STANDARD")
        & (
            (silver_df["payment_type"] == 0)
            | (silver_df["fare_amount"] <= 0)
            | (silver_df["total_amount"] <= 0)
        )
    )

    count = int(standard_wrong.sum())

    print(
        f"STANDARD financial rows violating contract: "
        f"{count:,}"
    )

    if count > 0:
        failures.append(
            f"{count} STANDARD financial rows violate the contract"
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

    print("\nFinancial quality distribution:")

    print(
        silver_df["financial_quality"]
        .value_counts(dropna=False)
    )

    return failures


def main():
    if len(sys.argv) not in (2, 3):
        raise SystemExit(
            "Usage: python src/validation/validate_silver.py "
            "<year> [file_name]"
        )

    try:
        year = int(sys.argv[1])
    except ValueError:
        raise SystemExit("Year must be a number.")

    raw_prefix = f"raw/yellow_tripdata/year={year}/"
    silver_prefix = f"silver/yellow_tripdata/year={year}/"

    # ---------------------------------------------------------
    # Single-batch mode
    # ---------------------------------------------------------

    if len(sys.argv) == 3:
        file_name = sys.argv[2]

        expected_prefix = f"yellow_tripdata_{year}-"

        if (
            not file_name.startswith(expected_prefix)
            or not file_name.endswith(".parquet")
        ):
            raise SystemExit(
                f"Invalid batch filename for {year}: "
                f"{file_name}"
            )

        raw_key = f"{raw_prefix}{file_name}"
        silver_key = f"{silver_prefix}{file_name}"

        print(
            f"=== SILVER VALIDATION: "
            f"{file_name} ==="
        )

        failures = validate_file(
            raw_key,
            silver_key,
        )

        print("\n" + "=" * 80)
        print("VALIDATION SUMMARY")
        print("=" * 80)

        if failures:
            print(
                f"\nFAILED with "
                f"{len(failures)} issue(s):\n"
            )

            for failure in failures:
                print(f"- {silver_key}: {failure}")

            raise ValueError(
                "Silver validation failed."
            )

        print("\nPASS ✅")
        print(
            "Silver batch satisfies "
            "the current validation rules."
        )

        return

    # ---------------------------------------------------------
    # Full-year mode
    # ---------------------------------------------------------

    raw_files = list_parquet_files(
        raw_prefix
    )

    silver_files = list_parquet_files(
        silver_prefix
    )

    print(f"=== SILVER VALIDATION: {year} ===\n")

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
        f"All {year} Silver batches satisfy "
        "the current validation rules."
    )


if __name__ == "__main__":
    main()