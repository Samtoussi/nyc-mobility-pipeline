import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import boto3
from botocore.exceptions import ClientError


BUCKET_NAME = "nyc-mobility-pipeline-samtoussi"
GLUE_CRAWLER_NAME = "nyc-mobility-silver-crawler"

SILVER_PREFIX = "silver/yellow_tripdata/"
CHECKPOINT_KEY = "pipeline-state/gold-checkpoint.json"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DBT_PROJECT_DIR = PROJECT_ROOT / "dbt" / "nyc_mobility"

TLC_INGESTION_SCRIPT = (
    PROJECT_ROOT
    / "src"
    / "ingestion"
    / "ingest_from_tlc.py"
)

RAW_VALIDATION_SCRIPT = (
    PROJECT_ROOT
    / "src"
    / "validation"
    / "validate_raw.py"
)

TRANSFORMATION_SCRIPT = (
    PROJECT_ROOT
    / "src"
    / "transformation"
    / "transform_to_silver.py"
)

SILVER_VALIDATION_SCRIPT = (
    PROJECT_ROOT
    / "src"
    / "validation"
    / "validate_silver.py"
)


s3 = boto3.client("s3")
glue = boto3.client("glue")


def list_parquet_files(prefix: str) -> set[str]:
    files = set()

    paginator = s3.get_paginator("list_objects_v2")

    for page in paginator.paginate(
        Bucket=BUCKET_NAME,
        Prefix=prefix,
    ):
        for obj in page.get("Contents", []):
            key = obj["Key"]

            if key.endswith(".parquet"):
                files.add(key.split("/")[-1])

    return files


def get_pending_batches(year: int) -> list[str]:
    raw_prefix = f"raw/yellow_tripdata/year={year}/"
    silver_prefix = f"silver/yellow_tripdata/year={year}/"

    raw_files = list_parquet_files(raw_prefix)
    silver_files = list_parquet_files(silver_prefix)

    pending_batches = sorted(
        raw_files - silver_files
    )

    print("\nBATCH DISCOVERY")
    print("-" * 80)
    print(f"Raw batches:       {len(raw_files)}")
    print(f"Silver batches:    {len(silver_files)}")
    print(f"Pending batches:   {len(pending_batches)}")

    if pending_batches:
        print("\nBatches to process:")

        for batch in pending_batches:
            print(f"- {batch}")

    return pending_batches


def run_step(
    name,
    script_path,
    year,
    file_name=None,
):
    print("\n" + "=" * 80)
    print(f"STARTING: {name}")

    if file_name:
        print(f"Batch: {file_name}")

    print("=" * 80)

    started_at = datetime.now()

    command = [
        sys.executable,
        str(script_path),
        str(year),
    ]

    if file_name:
        command.append(file_name)

    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
    )

    duration = datetime.now() - started_at

    if result.returncode != 0:
        print("\n" + "!" * 80)
        print(f"FAILED: {name}")

        if file_name:
            print(f"Batch: {file_name}")

        print(f"Exit code: {result.returncode}")
        print(f"Runtime: {duration}")
        print("!" * 80)

        raise RuntimeError(
            f"Pipeline stopped because {name} failed."
        )

    print("\n" + "-" * 80)
    print(f"SUCCESS: {name}")

    if file_name:
        print(f"Batch: {file_name}")

    print(f"Runtime: {duration}")
    print("-" * 80)


def get_silver_fingerprint() -> str:
    """
    Create a fingerprint of the current Silver dataset.

    Both object keys and ETags are included, so replacing
    an existing Silver file also changes the fingerprint.
    """

    objects = []

    paginator = s3.get_paginator("list_objects_v2")

    for page in paginator.paginate(
        Bucket=BUCKET_NAME,
        Prefix=SILVER_PREFIX,
    ):
        for obj in page.get("Contents", []):
            key = obj["Key"]

            if key.endswith(".parquet"):
                objects.append(
                    {
                        "key": key,
                        "etag": obj["ETag"],
                    }
                )

    objects.sort(key=lambda obj: obj["key"])

    payload = json.dumps(
        objects,
        sort_keys=True,
    )

    fingerprint = hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()

    print("\nSILVER FINGERPRINT")
    print("-" * 80)
    print(f"Parquet objects: {len(objects)}")
    print(f"Fingerprint: {fingerprint}")

    return fingerprint


def get_dbt_fingerprint() -> str:
    """
    Create a fingerprint of the dbt project.

    Changes to models, seeds or project configuration
    will trigger a new Gold build.
    """

    files = [
        path
        for path in DBT_PROJECT_DIR.rglob("*")
        if path.is_file()
        and path.suffix in {".sql", ".csv", ".yml", ".yaml"}
        and path.name not in {"profiles.yml", ".user.yml"}
        and not any(
            directory in path.parts
            for directory in {"target", "logs", "dbt_packages"}
        )
    ]

    digest = hashlib.sha256()

    for path in sorted(files):
        relative_path = path.relative_to(DBT_PROJECT_DIR)

        digest.update(
            relative_path.as_posix().encode("utf-8")
        )

        digest.update(
            path.read_bytes()
        )

    fingerprint = digest.hexdigest()

    print("\nDBT FINGERPRINT")
    print("-" * 80)
    print(f"Project files: {len(files)}")
    print(f"Fingerprint: {fingerprint}")

    return fingerprint


def get_gold_checkpoint() -> str | None:
    """
    Read the fingerprint from the last successful
    Glue + dbt run.
    """

    try:
        response = s3.get_object(
            Bucket=BUCKET_NAME,
            Key=CHECKPOINT_KEY,
        )

    except ClientError as error:
        error_code = error.response["Error"]["Code"]

        if error_code in ("NoSuchKey", "404"):
            print("\nNo Gold checkpoint found.")
            return None

        raise

    checkpoint = json.loads(
        response["Body"].read()
    )

    return checkpoint.get("silver_fingerprint")


def save_gold_checkpoint(
    fingerprint: str,
):
    """
    Save the checkpoint only after both Glue
    and dbt have completed successfully.
    """

    checkpoint = {
        "silver_fingerprint": fingerprint,
        "completed_at": datetime.now().isoformat(),
    }

    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=CHECKPOINT_KEY,
        Body=json.dumps(
            checkpoint,
            indent=2,
        ).encode("utf-8"),
        ContentType="application/json",
    )

    print("\nGold checkpoint saved.")
    print(f"S3 key: {CHECKPOINT_KEY}")


def run_glue_crawler():
    print("\n" + "=" * 80)
    print("STARTING: GLUE CRAWLER")
    print(f"Crawler: {GLUE_CRAWLER_NAME}")
    print("=" * 80)

    started_at = datetime.now()

    glue.start_crawler(
        Name=GLUE_CRAWLER_NAME
    )

    print("Crawler started.")
    print("Waiting for crawler to finish...")

    timeout_seconds = 1800

    while True:
        crawler = glue.get_crawler(
            Name=GLUE_CRAWLER_NAME
        )["Crawler"]

        state = crawler["State"]

        print(f"Crawler state: {state}")

        if state == "READY":
            break

        elapsed = (
            datetime.now() - started_at
        ).total_seconds()

        if elapsed >= timeout_seconds:
            raise TimeoutError(
                "Glue crawler did not finish "
                "within 30 minutes."
            )

        time.sleep(10)

    crawler = glue.get_crawler(
        Name=GLUE_CRAWLER_NAME
    )["Crawler"]

    last_crawl = crawler.get("LastCrawl")

    if not last_crawl:
        raise RuntimeError(
            "Glue crawler finished without "
            "LastCrawl information."
        )

    status = last_crawl.get("Status")
    duration = datetime.now() - started_at

    if status != "SUCCEEDED":
        error_message = last_crawl.get(
            "ErrorMessage",
            "No error message returned.",
        )

        print("\n" + "!" * 80)
        print("FAILED: GLUE CRAWLER")
        print(f"Status: {status}")
        print(f"Error: {error_message}")
        print(f"Runtime: {duration}")
        print("!" * 80)

        raise RuntimeError(
            f"Glue crawler failed with status {status}."
        )

    print("\n" + "-" * 80)
    print("SUCCESS: GLUE CRAWLER")
    print(f"Status: {status}")
    print(f"Runtime: {duration}")
    print("-" * 80)


def run_dbt_build():
    print("\n" + "=" * 80)
    print("STARTING: DBT GOLD BUILD")
    print("=" * 80)

    started_at = datetime.now()

    command = [
        "dbt",
        "build",
        "--profiles-dir",
        str(DBT_PROJECT_DIR),
    ]

    result = subprocess.run(
        command,
        cwd=DBT_PROJECT_DIR,
    )

    duration = datetime.now() - started_at

    if result.returncode != 0:
        print("\n" + "!" * 80)
        print("FAILED: DBT GOLD BUILD")
        print(f"Exit code: {result.returncode}")
        print(f"Runtime: {duration}")
        print("!" * 80)

        raise RuntimeError(
            "Pipeline stopped because dbt build failed."
        )

    print("\n" + "-" * 80)
    print("SUCCESS: DBT GOLD BUILD")
    print(f"Runtime: {duration}")
    print("-" * 80)


def main():
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: python "
            "src/orchestration/run_pipeline.py "
            "<year>"
        )

    try:
        year = int(sys.argv[1])

    except ValueError:
        raise SystemExit(
            "Year must be a number."
        )

    pipeline_started_at = datetime.now()

    print("\n" + "=" * 80)
    print("NYC MOBILITY INCREMENTAL PIPELINE")
    print("=" * 80)
    print(f"Year: {year}")
    print(f"Started: {pipeline_started_at}")

    # ---------------------------------------------------------
    # 1. Discover and ingest newly published TLC batches
    # ---------------------------------------------------------

    run_step(
        "TLC INGESTION",
        TLC_INGESTION_SCRIPT,
        year,
    )

    # ---------------------------------------------------------
    # 2. Discover Raw batches missing from Silver
    # ---------------------------------------------------------

    pending_batches = get_pending_batches(year)

    # ---------------------------------------------------------
    # 3. Process new batches, if any
    # ---------------------------------------------------------

    if pending_batches:
        for file_name in pending_batches:
            run_step(
                "RAW VALIDATION",
                RAW_VALIDATION_SCRIPT,
                year,
                file_name,
            )

        run_step(
            "SILVER TRANSFORMATION",
            TRANSFORMATION_SCRIPT,
            year,
        )

        for file_name in pending_batches:
            run_step(
                "SILVER VALIDATION",
                SILVER_VALIDATION_SCRIPT,
                year,
                file_name,
            )

    else:
        print("\nNo new Raw batches to process.")

    # ---------------------------------------------------------
    # 4. Check whether Gold needs to be refreshed
    # ---------------------------------------------------------

    silver_fingerprint = get_silver_fingerprint()
    dbt_fingerprint = get_dbt_fingerprint()

    current_fingerprint = hashlib.sha256(
        f"{silver_fingerprint}:{dbt_fingerprint}".encode("utf-8")
    ).hexdigest()

    previous_fingerprint = get_gold_checkpoint()

    gold_needs_refresh = (
        current_fingerprint != previous_fingerprint
    )

    # ---------------------------------------------------------
    # 5. Refresh Glue and build Gold when necessary
    # ---------------------------------------------------------

    if gold_needs_refresh:
        print("\nGold refresh required.")

        run_glue_crawler()
        run_dbt_build()

        # Save the checkpoint only after both
        # operations have succeeded.
        save_gold_checkpoint(
            current_fingerprint
        )

    else:
        print("\nGold is already up to date.")
        print("Skipping Glue Crawler and dbt build.")

    # ---------------------------------------------------------
    # 6. Pipeline summary
    # ---------------------------------------------------------

    pipeline_finished_at = datetime.now()

    total_runtime = (
        pipeline_finished_at
        - pipeline_started_at
    )

    print("\n" + "=" * 80)
    print("PIPELINE COMPLETE")
    print("=" * 80)

    print("Status: SUCCESS")
    print(f"Year: {year}")
    print(
        f"Batches processed: "
        f"{len(pending_batches)}"
    )
    print(
        f"Gold refreshed: "
        f"{gold_needs_refresh}"
    )

    print(f"Started:  {pipeline_started_at}")
    print(f"Finished: {pipeline_finished_at}")
    print(f"Runtime:  {total_runtime}")


if __name__ == "__main__":
    main()