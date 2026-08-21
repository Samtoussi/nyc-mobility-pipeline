import os
import sys
import tempfile

import boto3
import requests



BUCKET_NAME = "nyc-mobility-pipeline-samtoussi"

TLC_BASE_URL = (
    "https://d37ci6vzurychx.cloudfront.net/"
    "trip-data"
)

s3 = boto3.client("s3")


def build_file_name(year: int, month: int) -> str:
    return (
        f"yellow_tripdata_"
        f"{year}-{month:02d}.parquet"
    )


def build_tlc_url(file_name: str) -> str:
    return f"{TLC_BASE_URL}/{file_name}"


def list_existing_raw_files(year: int) -> set[str]:
    prefix = (
        f"raw/yellow_tripdata/year={year}/"
    )

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


def source_file_exists(url: str) -> bool:
    response = requests.head(
        url,
        timeout=30,
    )

    return response.status_code == 200


def discover_available_files(
    year: int,
) -> list[str]:
    available_files = []

    print("\nChecking TLC source...")

    for month in range(1, 13):
        file_name = build_file_name(
            year,
            month,
        )

        url = build_tlc_url(file_name)

        if source_file_exists(url):
            print(
                f"{year}-{month:02d}: available"
            )

            available_files.append(
                file_name
            )
        else:
            print(
                f"{year}-{month:02d}: "
                f"not available"
            )

    return available_files


def download_and_upload(
    year: int,
    file_name: str,
):
    url = build_tlc_url(file_name)

    s3_key = (
        f"raw/yellow_tripdata/"
        f"year={year}/{file_name}"
    )

    print(f"\nDownloading {file_name}...")

    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            suffix=".parquet",
            delete=False,
        ) as temp_file:
            temp_path = temp_file.name

            with requests.get(
                url,
                stream=True,
                timeout=120,
            ) as response:
                response.raise_for_status()

                for chunk in response.iter_content(
                    chunk_size=1024 * 1024
                ):
                    if chunk:
                        temp_file.write(chunk)

        print(
            f"Uploading {file_name} to S3..."
        )

        s3.upload_file(
            temp_path,
            BUCKET_NAME,
            s3_key,
        )

    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)

    print(f"Complete: {file_name}")


def main():
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: python "
            "src/ingestion/ingest_from_tlc.py "
            "<year>"
        )

    try:
        year = int(sys.argv[1])
    except ValueError:
        raise SystemExit(
            "Year must be a number."
        )

    print("\n" + "=" * 80)
    print("NYC TLC SOURCE INGESTION")
    print("=" * 80)
    print(f"Year: {year}")

    available_files = (
        discover_available_files(year)
    )

    existing_files = (
        list_existing_raw_files(year)
    )

    files_to_ingest = sorted(
        set(available_files)
        - existing_files
    )

    print("\n" + "-" * 80)
    print("INGESTION SUMMARY")
    print("-" * 80)

    print(
        f"Available from TLC: "
        f"{len(available_files)}"
    )

    print(
        f"Already in Raw:     "
        f"{len(existing_files)}"
    )

    print(
        f"New files:          "
        f"{len(files_to_ingest)}"
    )

    if not files_to_ingest:
        print("\nNo new files to ingest.")
        return

    print("\nFiles to ingest:")

    for file_name in files_to_ingest:
        print(f"- {file_name}")

    for file_name in files_to_ingest:
        download_and_upload(
            year,
            file_name,
        )

    print("\n" + "=" * 80)
    print("INGESTION COMPLETE")
    print("=" * 80)

    print(
        f"Files ingested: "
        f"{len(files_to_ingest)}"
    )


if __name__ == "__main__":
    main()