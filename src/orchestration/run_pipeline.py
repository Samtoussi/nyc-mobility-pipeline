import subprocess
import sys
from pathlib import Path
from datetime import datetime

import boto3


BUCKET_NAME = "nyc-mobility-pipeline-samtoussi"

PROJECT_ROOT = Path(__file__).resolve().parents[2]

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


def list_parquet_files(prefix: str) -> set[str]:
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


def get_pending_batches(year: int) -> list[str]:
    raw_prefix = (
        f"raw/yellow_tripdata/year={year}/"
    )

    silver_prefix = (
        f"silver/yellow_tripdata/year={year}/"
    )

    raw_files = list_parquet_files(
        raw_prefix
    )

    silver_files = list_parquet_files(
        silver_prefix
    )

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
            f"Pipeline stopped because "
            f"{name} failed."
        )

    print("\n" + "-" * 80)
    print(f"SUCCESS: {name}")

    if file_name:
        print(f"Batch: {file_name}")

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

    pending_batches = get_pending_batches(
        year
    )

    if not pending_batches:
        print("\n" + "=" * 80)
        print("PIPELINE COMPLETE")
        print("=" * 80)
        print("Status: SUCCESS")
        print("No new batches to process.")
        return

    # ---------------------------------------------------------
    # 1. Validate every pending Raw batch
    # ---------------------------------------------------------

    for file_name in pending_batches:
        run_step(
            "RAW VALIDATION",
            RAW_VALIDATION_SCRIPT,
            year,
            file_name,
        )

    # ---------------------------------------------------------
    # 2. Transform missing Raw batches
    # ---------------------------------------------------------

    run_step(
        "SILVER TRANSFORMATION",
        TRANSFORMATION_SCRIPT,
        year,
    )

    # ---------------------------------------------------------
    # 3. Validate every newly created Silver batch
    # ---------------------------------------------------------

    for file_name in pending_batches:
        run_step(
            "SILVER VALIDATION",
            SILVER_VALIDATION_SCRIPT,
            year,
            file_name,
        )

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

    print(f"Started:  {pipeline_started_at}")
    print(f"Finished: {pipeline_finished_at}")
    print(f"Runtime:  {total_runtime}")


if __name__ == "__main__":
    main()