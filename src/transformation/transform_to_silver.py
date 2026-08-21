from io import BytesIO
import re
import sys

import boto3
import pandas as pd


BUCKET_NAME = "nyc-mobility-pipeline-samtoussi"

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


def list_silver_files(year: int) -> set[str]:
    silver_prefix = f"silver/yellow_tripdata/year={year}/"

    response = s3.list_objects_v2(
        Bucket=BUCKET_NAME,
        Prefix=silver_prefix,
    )

    objects = response.get("Contents", [])

    return {
        obj["Key"].split("/")[-1]
        for obj in objects
        if obj["Key"].endswith(".parquet")
    }


def read_parquet_from_s3(key):
    response = s3.get_object(
        Bucket=BUCKET_NAME,
        Key=key,
    )

    data = response["Body"].read()

    return pd.read_parquet(
        BytesIO(data)
    )


def normalize_source_schema(df):
    df = df.copy()

    if (
        "airport_fee" in df.columns
        and "Airport_fee" not in df.columns
    ):
        df = df.rename(
            columns={
                "airport_fee": "Airport_fee",
            }
        )

    return df


def extract_batch_month(
    file_name: str,
    expected_year: int,
) -> int:
    pattern = (
        rf"^yellow_tripdata_"
        rf"{expected_year}-(\d{{2}})\.parquet$"
    )

    match = re.match(
        pattern,
        file_name,
    )

    if not match:
        raise ValueError(
            f"Could not determine batch month "
            f"from filename: {file_name}"
        )

    month = int(match.group(1))

    if month < 1 or month > 12:
        raise ValueError(
            f"Invalid month in filename: "
            f"{file_name}"
        )

    return month


def apply_temporal_quality(df):
    df = df.copy()

    duration_min = (
        df["tpep_dropoff_datetime"]
        - df["tpep_pickup_datetime"]
    ).dt.total_seconds() / 60

    df["duration_min"] = duration_min
    df["duration_quality"] = "VALID"

    helix_unavailable = (
        (df["VendorID"] == 7)
        & (
            df["tpep_pickup_datetime"]
            == df["tpep_dropoff_datetime"]
        )
    )

    df.loc[
        helix_unavailable,
        "duration_min",
    ] = pd.NA

    df.loc[
        helix_unavailable,
        "duration_quality",
    ] = "UNAVAILABLE_SOURCE_SEMANTICS"

    invalid_negative = (
        duration_min < 0
    )

    df.loc[
        invalid_negative,
        "duration_min",
    ] = pd.NA

    df.loc[
        invalid_negative,
        "duration_quality",
    ] = "INVALID"

    return df


def apply_date_quality(
    df,
    year: int,
    month: int,
):
    df = df.copy()

    df["date_quality"] = "VALID"

    year_start = pd.Timestamp(
        year=year,
        month=1,
        day=1,
    )

    next_year_start = pd.Timestamp(
        year=year + 1,
        month=1,
        day=1,
    )

    month_start = pd.Timestamp(
        year=year,
        month=month,
        day=1,
    )

    if month == 12:
        next_month_start = pd.Timestamp(
            year=year + 1,
            month=1,
            day=1,
        )
    else:
        next_month_start = pd.Timestamp(
            year=year,
            month=month + 1,
            day=1,
        )

    pickup_datetime = (
        df["tpep_pickup_datetime"]
    )

    outside_expected_year = (
        (pickup_datetime < year_start)
        | (pickup_datetime >= next_year_start)
    )

    outside_expected_month = (
        ~outside_expected_year
        & (
            (pickup_datetime < month_start)
            | (
                pickup_datetime
                >= next_month_start
            )
        )
    )

    df.loc[
        outside_expected_month,
        "date_quality",
    ] = "OUTSIDE_EXPECTED_MONTH"

    df.loc[
        outside_expected_year,
        "date_quality",
    ] = "OUTSIDE_EXPECTED_YEAR"

    return df


def apply_distance_quality(df):
    df = df.copy()

    df["distance_quality"] = "VALID"

    negative_distance = (
        df["trip_distance"] < 0
    )

    df.loc[
        negative_distance,
        "distance_quality",
    ] = "INVALID"

    zero_distance = (
        df["trip_distance"] == 0
    )

    df.loc[
        zero_distance,
        "distance_quality",
    ] = "ZERO_REPORTED"

    suspicious_extreme = (
        df["trip_distance"] > 500
    )

    df.loc[
        suspicious_extreme,
        "distance_quality",
    ] = "SUSPICIOUS_EXTREME"

    return df


def apply_financial_quality(df):
    df = df.copy()

    df["financial_quality"] = "STANDARD"

    zero_reported = (
        (df["fare_amount"] == 0)
        | (df["total_amount"] == 0)
    )

    df.loc[
        zero_reported,
        "financial_quality",
    ] = "ZERO_REPORTED"

    negative_reported = (
        (df["fare_amount"] < 0)
        | (df["total_amount"] < 0)
    )

    df.loc[
        negative_reported,
        "financial_quality",
    ] = "NEGATIVE_REPORTED"

    source_specific = (
        df["payment_type"] == 0
    )

    df.loc[
        source_specific,
        "financial_quality",
    ] = "SOURCE_SPECIFIC"

    return df


def write_parquet_to_s3(df, key):
    buffer = BytesIO()

    df.to_parquet(
        buffer,
        index=False,
    )

    buffer.seek(0)

    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=key,
        Body=buffer.getvalue(),
    )


def transform_file(
    raw_key,
    year: int,
):
    print(f"Reading {raw_key}...")

    df = read_parquet_from_s3(
        raw_key
    )

    print(
        f"Rows loaded: {len(df):,}"
    )

    file_name = (
        raw_key.split("/")[-1]
    )

    month = extract_batch_month(
        file_name,
        year,
    )

    print(
        f"Expected batch period: "
        f"{year}-{month:02d}"
    )

    df = normalize_source_schema(df)
    df = apply_temporal_quality(df)

    df = apply_date_quality(
        df,
        year,
        month,
    )

    df = apply_distance_quality(df)
    df = apply_financial_quality(df)

    silver_prefix = (
        f"silver/yellow_tripdata/"
        f"year={year}/"
    )

    silver_key = (
        f"{silver_prefix}{file_name}"
    )

    print(
        f"Writing {silver_key}..."
    )

    write_parquet_to_s3(
        df,
        silver_key,
    )

    print("Done.\n")


def main():
    if len(sys.argv) not in (2, 3):
        raise SystemExit(
            "Usage: python "
            "src/transformation/"
            "transform_to_silver.py "
            "<year> [file_name]"
        )

    try:
        year = int(sys.argv[1])
    except ValueError:
        raise SystemExit(
            "Year must be a number."
        )

    raw_prefix = (
        f"raw/yellow_tripdata/"
        f"year={year}/"
    )

    raw_files = list_raw_files(
        year
    )

    if not raw_files:
        raise FileNotFoundError(
            f"No parquet files found "
            f"under {raw_prefix}"
        )

    # ---------------------------------------------------------
    # Explicit single-batch reprocessing
    # ---------------------------------------------------------

    if len(sys.argv) == 3:
        file_name = sys.argv[2]

        expected_prefix = (
            f"yellow_tripdata_{year}-"
        )

        if (
            not file_name.startswith(
                expected_prefix
            )
            or not file_name.endswith(
                ".parquet"
            )
        ):
            raise SystemExit(
                f"Invalid batch filename "
                f"for {year}: {file_name}"
            )

        raw_key = (
            f"{raw_prefix}{file_name}"
        )

        if raw_key not in raw_files:
            raise FileNotFoundError(
                f"Raw batch not found: "
                f"{raw_key}"
            )

        print(
            "Explicit reprocess mode"
        )

        print(
            f"Batch: {file_name}\n"
        )

        transform_file(
            raw_key,
            year,
        )

        return

    # ---------------------------------------------------------
    # Normal incremental mode
    # ---------------------------------------------------------

    silver_files = list_silver_files(
        year
    )

    raw_files_to_process = [
        raw_key
        for raw_key in raw_files
        if (
            raw_key.split("/")[-1]
            not in silver_files
        )
    ]

    print(
        f"Raw files found: "
        f"{len(raw_files)}"
    )

    print(
        f"Already in Silver: "
        f"{len(silver_files)}"
    )

    print(
        f"New files to transform: "
        f"{len(raw_files_to_process)}\n"
    )

    if not raw_files_to_process:
        print(
            "No new Raw files to transform."
        )

        return

    for raw_key in raw_files_to_process:
        transform_file(
            raw_key,
            year,
        )


if __name__ == "__main__":
    main()