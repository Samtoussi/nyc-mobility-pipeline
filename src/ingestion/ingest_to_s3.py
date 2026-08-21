from pathlib import Path
import sys

import boto3


BUCKET_NAME = "nyc-mobility-pipeline-samtoussi"
LOCAL_RAW_DIR = Path("data/raw")

s3 = boto3.client("s3")


def list_existing_s3_files(year: int) -> set[str]:
    prefix = f"raw/yellow_tripdata/year={year}/"

    response = s3.list_objects_v2(
        Bucket=BUCKET_NAME,
        Prefix=prefix,
    )

    objects = response.get("Contents", [])

    return {
        obj["Key"].split("/")[-1]
        for obj in objects
        if obj["Key"].endswith(".parquet")
    }


def upload_raw_data(year: int):
    year_dir = LOCAL_RAW_DIR / str(year)

    parquet_files = sorted(
        year_dir.glob(f"yellow_tripdata_{year}-*.parquet")
    )

    if not parquet_files:
        raise FileNotFoundError(
            f"No {year} parquet files found in {year_dir}"
        )

    print(
        f"Found {len(parquet_files)} local files for {year}."
    )

    existing_files = list_existing_s3_files(year)

    files_to_upload = [
        file_path
        for file_path in parquet_files
        if file_path.name not in existing_files
    ]

    print(
        f"Already in S3: {len(existing_files)}"
    )

    print(
        f"New files to upload: {len(files_to_upload)}"
    )

    if not files_to_upload:
        print("\nNo new files to upload.")
        return

    for file_path in files_to_upload:
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