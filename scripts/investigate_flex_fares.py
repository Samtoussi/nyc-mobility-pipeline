import glob
import pandas as pd

FILES = sorted(glob.glob("data/raw/yellow_tripdata_2025-*.parquet"))

frames = []

for file in FILES:
    df = pd.read_parquet(
        file,
        columns=[
            "VendorID",
            "payment_type",
            "RatecodeID",
            "fare_amount",
            "total_amount",
            "trip_distance",
            "tip_amount",
            "extra",
            "mta_tax",
            "tolls_amount",
            "improvement_surcharge",
            "congestion_surcharge",
            "Airport_fee",
            "cbd_congestion_fee",
            "tpep_pickup_datetime",
            "tpep_dropoff_datetime",
        ],
    )

    flex = df[
        (df["VendorID"] == 2)
        & (df["payment_type"] == 0)
    ].copy()

    flex["duration_min"] = (
        flex["tpep_dropoff_datetime"]
        - flex["tpep_pickup_datetime"]
    ).dt.total_seconds() / 60

    frames.append(flex)

flex = pd.concat(frames, ignore_index=True)

negative = flex[flex["fare_amount"] < 0]
positive = flex[flex["fare_amount"] > 0]
zero = flex[flex["fare_amount"] == 0]

print("=== FLEX FARE INVESTIGATION ===\n")

print(f"All Flex Fare rows:       {len(flex):,}")
print(f"Negative fare:            {len(negative):,}")
print(f"Positive fare:            {len(positive):,}")
print(f"Zero fare:                {len(zero):,}")

print("\n--- RatecodeID ---")
print(flex["RatecodeID"].value_counts(dropna=False).sort_index())

print("\n--- NEGATIVE FLEX FARE ---")
print(negative[
    [
        "fare_amount",
        "total_amount",
        "trip_distance",
        "duration_min",
        "tip_amount",
        "extra",
        "congestion_surcharge",
        "Airport_fee",
        "cbd_congestion_fee",
    ]
].describe())

print("\nNegative fare with positive total:")
print((negative["total_amount"] > 0).sum())

print("\nNegative fare with negative total:")
print((negative["total_amount"] < 0).sum())

print("\n--- POSITIVE FLEX FARE ---")
print(positive[
    [
        "fare_amount",
        "total_amount",
        "trip_distance",
        "duration_min",
        "tip_amount",
        "extra",
        "congestion_surcharge",
        "Airport_fee",
        "cbd_congestion_fee",
    ]
].describe())

print("\n--- SAMPLE NEGATIVE FLEX FARES ---")
print(
    negative[
        [
            "fare_amount",
            "total_amount",
            "trip_distance",
            "duration_min",
            "tip_amount",
            "extra",
            "mta_tax",
            "tolls_amount",
            "improvement_surcharge",
            "congestion_surcharge",
            "Airport_fee",
            "cbd_congestion_fee",
        ]
    ].head(20).to_string(index=False)
)

print("\n--- SAMPLE POSITIVE FLEX FARES ---")
print(
    positive[
        [
            "fare_amount",
            "total_amount",
            "trip_distance",
            "duration_min",
            "tip_amount",
            "extra",
            "mta_tax",
            "tolls_amount",
            "improvement_surcharge",
            "congestion_surcharge",
            "Airport_fee",
            "cbd_congestion_fee",
        ]
    ].head(20).to_string(index=False)
)