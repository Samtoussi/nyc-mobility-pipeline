import time
import os
import glob
import psutil
import pandas as pd

FILES = sorted(glob.glob("data/raw/yellow_tripdata_2025-*.parquet"))

process = psutil.Process(os.getpid())

def ram_mb():
    return process.memory_info().rss / 1024 / 1024


print("=== NYC TAXI 2025 PANDAS BENCHMARK ===\n")
print(f"Files found: {len(FILES)}\n")

total_start = time.perf_counter()
total_rows = 0
total_valid_rows = 0

monthly_results = []

for file in FILES:
    start = time.perf_counter()

    df = pd.read_parquet(file)
    rows = len(df)
    total_rows += rows

    df["trip_duration_min"] = (
        df["tpep_dropoff_datetime"] - df["tpep_pickup_datetime"]
    ).dt.total_seconds() / 60

    valid = df[
        (df["trip_distance"] > 0)
        & (df["fare_amount"] > 0)
        & (df["trip_duration_min"] > 0)
    ].copy()

    valid["pickup_hour"] = valid["tpep_pickup_datetime"].dt.hour

    valid_rows = len(valid)
    total_valid_rows += valid_rows

    summary = (
        valid.groupby("PULocationID")
        .agg(
            trips=("VendorID", "count"),
            avg_distance=("trip_distance", "mean"),
            avg_fare=("fare_amount", "mean"),
            total_revenue=("total_amount", "sum"),
        )
        .reset_index()
    )

    elapsed = time.perf_counter() - start

    monthly_results.append(summary)

    print(
        f"{os.path.basename(file)} | "
        f"{rows:,} rows | "
        f"{elapsed:.2f} sec | "
        f"RAM: {ram_mb():.0f} MB"
    )

    del df
    del valid


total_time = time.perf_counter() - total_start

print("\n=== RESULTS ===")
print(f"Files processed:      {len(FILES)}")
print(f"Total rows:           {total_rows:,}")
print(f"Valid rows:           {total_valid_rows:,}")
print(f"Total processing:     {total_time:.2f} sec")
print(f"Final RAM usage:      {ram_mb():.1f} MB")