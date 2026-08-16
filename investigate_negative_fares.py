import glob
import pandas as pd

FILES = sorted(glob.glob("data/raw/yellow_tripdata_2025-*.parquet"))

results = []

for file in FILES:
    df = pd.read_parquet(
        file,
        columns=[
            "VendorID",
            "fare_amount",
            "total_amount",
            "payment_type",
            "RatecodeID",
            "trip_distance",
            "tpep_pickup_datetime",
            "tpep_dropoff_datetime",
        ],
    )

    negative = df[df["fare_amount"] < 0].copy()

    negative["duration_min"] = (
        negative["tpep_dropoff_datetime"]
        - negative["tpep_pickup_datetime"]
    ).dt.total_seconds() / 60

    results.append(negative)

neg = pd.concat(results, ignore_index=True)

print("=== NEGATIVE FARE INVESTIGATION ===\n")

print(f"Negative fare rows: {len(neg):,}")

print("\n--- Payment type ---")
print(
    neg["payment_type"]
    .value_counts(dropna=False)
    .sort_index()
)

print("\n--- Rate code ---")
print(
    neg["RatecodeID"]
    .value_counts(dropna=False)
    .sort_index()
)

print("\n--- Vendor ---")
print(
    neg["VendorID"]
    .value_counts(dropna=False)
    .sort_index()
)

print("\n--- Amount behaviour ---")
print(f"Negative total_amount: {(neg['total_amount'] < 0).sum():,}")
print(f"Zero total_amount:     {(neg['total_amount'] == 0).sum():,}")
print(f"Positive total_amount: {(neg['total_amount'] > 0).sum():,}")

print("\n--- Distance ---")
print(f"Zero distance:     {(neg['trip_distance'] == 0).sum():,}")
print(f"Positive distance: {(neg['trip_distance'] > 0).sum():,}")

print("\n--- Fare statistics ---")
print(neg["fare_amount"].describe())

print("\n--- Sample rows ---")
print(
    neg[
        [
            "VendorID",
            "payment_type",
            "RatecodeID",
            "fare_amount",
            "total_amount",
            "trip_distance",
            "duration_min",
        ]
    ].head(20).to_string(index=False)
)