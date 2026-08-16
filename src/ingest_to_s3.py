from pathlib import Path

import boto3


BUCKET_NAME = "nyc-mobility-pipeline-samtoussi"
LOCAL_RAW_DIR = Path("data/raw")

s3 = boto3.client("s3")


def upload_raw_data():
    parquet_files = sorted(
        LOCAL_RAW_DIR.glob("yellow_tripdata_2025-*.parquet")
    )

    if not parquet_files:
        raise FileNotFoundError(
            f"No 2025 parquet files found in {LOCAL_RAW_DIR}"
        )

    print(f"Found {len(parquet_files)} files.")

    for file_path in parquet_files:
        s3_key = (
            f"raw/yellow_tripdata/year=2025/{file_path.name}"
        )

        print(f"Uploading {file_path.name}...")

        s3.upload_file(
            str(file_path),
            BUCKET_NAME,
            s3_key,
        )

    print("\nUpload complete.")


if __name__ == "__main__":
    upload_raw_data()