import pandas as pd

FILE = "data/raw/yellow_tripdata_2025-11.parquet"

df = pd.read_parquet(
    FILE,
    columns=[
        "VendorID",
        "tpep_pickup_datetime",
        "tpep_dropoff_datetime",
        "trip_distance",
        "PULocationID",
        "DOLocationID",
        "payment_type",
        "fare_amount",
        "total_amount",
    ],
)

df["duration_min"] = (
    df["tpep_dropoff_datetime"]
    - df["tpep_pickup_datetime"]
).dt.total_seconds() / 60

negative = df[df["duration_min"] < 0].copy()

print("=== NOVEMBER NEGATIVE DURATION INCIDENT ===\n")

print(f"Total November rows:     {len(df):,}")
print(f"Negative duration rows:  {len(negative):,}")
print(
    f"Percentage:              "
    f"{len(negative) / len(df) * 100:.4f}%"
)

print("\n--- Duration statistics ---")
print(negative["duration_min"].describe())

print("\n--- Vendor ---")
print(
    negative["VendorID"]
    .value_counts(dropna=False)
    .sort_index()
)

print("\n--- Payment type ---")
print(
    negative["payment_type"]
    .value_counts(dropna=False)
    .sort_index()
)

print("\n--- Pickup dates ---")
print(
    negative["tpep_pickup_datetime"]
    .dt.date
    .value_counts()
    .sort_index()
)

print("\n--- Pickup hours ---")
print(
    negative["tpep_pickup_datetime"]
    .dt.hour
    .value_counts()
    .sort_index()
)

print("\n--- Most common exact durations ---")
print(
    negative["duration_min"]
    .round(4)
    .value_counts()
    .head(20)
)

print("\n--- Sample rows ---")
print(
    negative[
        [
            "VendorID",
            "tpep_pickup_datetime",
            "tpep_dropoff_datetime",
            "duration_min",
            "trip_distance",
            "PULocationID",
            "DOLocationID",
            "payment_type",
            "fare_amount",
            "total_amount",
        ]
    ]
    .head(30)
    .to_string(index=False)
)

# --------------------------------------------------
# NEGATIVE DURATIONS OUTSIDE DST FALL-BACK WINDOW
# --------------------------------------------------

dst_window = (
    (negative["tpep_pickup_datetime"].dt.date == pd.Timestamp("2025-11-02").date())
    & (negative["tpep_pickup_datetime"].dt.hour == 1)
)

non_dst = negative[~dst_window]

print("\n--- NEGATIVE DURATIONS OUTSIDE DST WINDOW ---")
print(f"Rows: {len(non_dst):,}\n")

print(
    non_dst[
        [
            "VendorID",
            "tpep_pickup_datetime",
            "tpep_dropoff_datetime",
            "duration_min",
            "trip_distance",
            "PULocationID",
            "DOLocationID",
            "payment_type",
            "fare_amount",
            "total_amount",
        ]
    ].to_string(index=False)
)