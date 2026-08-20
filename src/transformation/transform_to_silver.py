from io import BytesIO
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

    if "airport_fee" in df.columns and "Airport_fee" not in df.columns:
        df = df.rename(
            columns={
                "airport_fee": "Airport_fee",
            }
        )

    return df


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


def apply_date_quality(df, year: int):
    df = df.copy()

    df["date_quality"] = "VALID"

    year_start = pd.Timestamp(f"{year}-01-01")
    next_year_start = pd.Timestamp(f"{year + 1}-01-01")

    outside_expected_year = (
        (df["tpep_pickup_datetime"] < year_start)
        | (df["tpep_pickup_datetime"] >= next_year_start)
    )

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

    # Default classification
    df["financial_quality"] = "STANDARD"

    # Zero values are preserved but explicitly classified.
    zero_reported = (
        (df["fare_amount"] == 0)
        | (df["total_amount"] == 0)
    )

    df.loc[
        zero_reported,
        "financial_quality",
    ] = "ZERO_REPORTED"

    # Negative values are preserved rather than assumed corrupt.
    negative_reported = (
        (df["fare_amount"] < 0)
        | (df["total_amount"] < 0)
    )

    df.loc[
        negative_reported,
        "financial_quality",
    ] = "NEGATIVE_REPORTED"

    # payment_type=0 represents source-specific Flex Fare
    # semantics and therefore takes highest classification priority.
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


def transform_file(raw_key, year: int):
    print(f"Reading {raw_key}...")

    df = read_parquet_from_s3(raw_key)

    print(f"Rows loaded: {len(df):,}")

    df = normalize_source_schema(df)
    df = apply_temporal_quality(df)
    df = apply_date_quality(df, year)
    df = apply_distance_quality(df)
    df = apply_financial_quality(df)

    file_name = raw_key.split("/")[-1]

    silver_prefix = f"silver/yellow_tripdata/year={year}/"

    silver_key = (
        f"{silver_prefix}{file_name}"
    )

    print(f"Writing {silver_key}...")

    write_parquet_to_s3(
        df,
        silver_key,
    )

    print("Done.\n")


def main():
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: python src/transformation/transform_to_silver.py <year>"
        )

    try:
        year = int(sys.argv[1])
    except ValueError:
        raise SystemExit("Year must be a number.")

    raw_prefix = f"raw/yellow_tripdata/year={year}/"
    raw_files = list_raw_files(year)

    if not raw_files:
        raise FileNotFoundError(
            f"No parquet files found under {raw_prefix}"
        )

    print(
        f"Found {len(raw_files)} raw files for {year}.\n"
    )

    for raw_key in raw_files:
        transform_file(
            raw_key,
            year,
        )


if __name__ == "__main__":
    main()