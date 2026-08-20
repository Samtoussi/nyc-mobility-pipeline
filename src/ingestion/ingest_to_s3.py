from pathlib import Path
import sys

import boto3


BUCKET_NAME = "nyc-mobility-pipeline-samtoussi"
LOCAL_RAW_DIR = Path("data/raw")

s3 = boto3.client("s3")


def upload_raw_data(year: int):
    year_dir = LOCAL_RAW_DIR / str(year)

    parquet_files = sorted(
        year_dir.glob(f"yellow_tripdata_{year}-*.parquet")
    )

    if not parquet_files:
        raise FileNotFoundError(
            f"No {year} parquet files found in {year_dir}"
        )

    print(f"Found {len(parquet_files)} files for {year}.")

    for file_path in parquet_files:
        s3_key = (
            f"raw/yellow_tripdata/year={year}/{file_path.name}"
        )

        print(f"Uploading {file_path.name}...")

        s3.upload_file(
            str(file_path),
            BUCKET_NAME,
            s3_key,
        )

    print("\nUpload complete.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: python src/ingestion/ingest_to_s3.py <year>"
        )

    try:
        year = int(sys.argv[1])
    except ValueError:
        raise SystemExit("Year must be a number.")

    upload_raw_data(year)