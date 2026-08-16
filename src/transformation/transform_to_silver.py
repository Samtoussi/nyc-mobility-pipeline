from io import BytesIO

import boto3
import pandas as pd


BUCKET_NAME = "nyc-mobility-pipeline-samtoussi"

RAW_PREFIX = "raw/yellow_tripdata/year=2025/"
SILVER_PREFIX = "silver/yellow_tripdata/year=2025/"

s3 = boto3.client("s3")


def list_raw_files():
    response = s3.list_objects_v2(
        Bucket=BUCKET_NAME,
        Prefix=RAW_PREFIX,
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


def transform_file(raw_key):
    print(f"Reading {raw_key}...")

    df = read_parquet_from_s3(raw_key)

    print(f"Rows loaded: {len(df):,}")

    df = apply_temporal_quality(df)

    file_name = raw_key.split("/")[-1]

    silver_key = (
        f"{SILVER_PREFIX}{file_name}"
    )

    print(f"Writing {silver_key}...")

    write_parquet_to_s3(
        df,
        silver_key,
    )

    print("Done.\n")


def main():
    raw_files = list_raw_files()

    if not raw_files:
        raise FileNotFoundError(
            f"No parquet files found under {RAW_PREFIX}"
        )

    print(
        f"Found {len(raw_files)} raw files.\n"
    )

    for raw_key in raw_files:
        transform_file(raw_key)


if __name__ == "__main__":
    main()