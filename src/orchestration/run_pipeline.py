import subprocess
import sys
from pathlib import Path
from datetime import datetime


PROJECT_ROOT = Path(__file__).resolve().parents[2]

STEPS = [
    (
        "RAW VALIDATION",
        PROJECT_ROOT / "src" / "validation" / "validate_raw.py",
    ),
    (
        "SILVER TRANSFORMATION",
        PROJECT_ROOT / "src" / "transformation" / "transform_to_silver.py",
    ),
    (
        "SILVER VALIDATION",
        PROJECT_ROOT / "src" / "validation" / "validate_silver.py",
    ),
]


def run_step(name, script_path, year):
    print("\n" + "=" * 80)
    print(f"STARTING: {name}")
    print("=" * 80)

    started_at = datetime.now()

    result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            str(year),
        ],
        cwd=PROJECT_ROOT,
    )

    duration = datetime.now() - started_at

    if result.returncode != 0:
        print("\n" + "!" * 80)
        print(f"FAILED: {name}")
        print(f"Exit code: {result.returncode}")
        print(f"Runtime: {duration}")
        print("!" * 80)

        raise RuntimeError(
            f"Pipeline stopped because {name} failed."
        )

    print("\n" + "-" * 80)
    print(f"SUCCESS: {name}")
    print(f"Runtime: {duration}")
    print("-" * 80)


def main():
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: python src/orchestration/run_pipeline.py <year>"
        )

    try:
        year = int(sys.argv[1])
    except ValueError:
        raise SystemExit("Year must be a number.")

    pipeline_started_at = datetime.now()

    print("\n" + "=" * 80)
    print("NYC MOBILITY PIPELINE")
    print("=" * 80)
    print(f"Year: {year}")
    print(f"Started: {pipeline_started_at}")

    for name, script_path in STEPS:
        run_step(
            name,
            script_path,
            year,
        )

    pipeline_finished_at = datetime.now()
    total_runtime = pipeline_finished_at - pipeline_started_at

    print("\n" + "=" * 80)
    print("PIPELINE COMPLETE")
    print("=" * 80)
    print("Status: SUCCESS")
    print(f"Year:     {year}")
    print(f"Started:  {pipeline_started_at}")
    print(f"Finished: {pipeline_finished_at}")
    print(f"Runtime:  {total_runtime}")


if __name__ == "__main__":
    main()