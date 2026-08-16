import glob
import pandas as pd

FILES = sorted(glob.glob("data/raw/yellow_tripdata_2025-*.parquet"))

total_rows = 0

distance_zero_or_less = 0
fare_zero_or_less = 0
duration_zero_or_less = 0

any_invalid = 0
all_three_invalid = 0

negative_distance = 0
zero_distance = 0

negative_fare = 0
zero_fare = 0

negative_duration = 0
zero_duration = 0


for file in FILES:
    df = pd.read_parquet(
        file,
        columns=[
            "tpep_pickup_datetime",
            "tpep_dropoff_datetime",
            "trip_distance",
            "fare_amount",
            "total_amount",
            "payment_type",
            "PULocationID",
            "DOLocationID",
        ],
    )

    duration_min = (
        df["tpep_dropoff_datetime"] - df["tpep_pickup_datetime"]
    ).dt.total_seconds() / 60

    bad_distance = df["trip_distance"] <= 0
    bad_fare = df["fare_amount"] <= 0
    bad_duration = duration_min <= 0

    total_rows += len(df)

    distance_zero_or_less += bad_distance.sum()
    fare_zero_or_less += bad_fare.sum()
    duration_zero_or_less += bad_duration.sum()

    any_invalid += (
        bad_distance | bad_fare | bad_duration
    ).sum()

    all_three_invalid += (
        bad_distance & bad_fare & bad_duration
    ).sum()

    negative_distance += (df["trip_distance"] < 0).sum()
    zero_distance += (df["trip_distance"] == 0).sum()

    negative_fare += (df["fare_amount"] < 0).sum()
    zero_fare += (df["fare_amount"] == 0).sum()

    negative_duration += (duration_min < 0).sum()
    zero_duration += (duration_min == 0).sum()


def pct(value):
    return (value / total_rows) * 100


print("=== NYC TAXI DATA QUALITY INVESTIGATION ===\n")

print(f"Total rows: {total_rows:,}\n")

print("--- Benchmark rule failures ---")
print(
    f"Distance <= 0: {distance_zero_or_less:,} "
    f"({pct(distance_zero_or_less):.2f}%)"
)
print(
    f"Fare <= 0:     {fare_zero_or_less:,} "
    f"({pct(fare_zero_or_less):.2f}%)"
)
print(
    f"Duration <= 0: {duration_zero_or_less:,} "
    f"({pct(duration_zero_or_less):.2f}%)"
)

print("\n--- Breakdown ---")
print(f"Negative distance: {negative_distance:,}")
print(f"Zero distance:     {zero_distance:,}")

print(f"Negative fare:     {negative_fare:,}")
print(f"Zero fare:         {zero_fare:,}")

print(f"Negative duration: {negative_duration:,}")
print(f"Zero duration:     {zero_duration:,}")

print("\n--- Combined ---")
print(
    f"At least one benchmark rule failed: "
    f"{any_invalid:,} ({pct(any_invalid):.2f}%)"
)
print(
    f"All three rules failed: "
    f"{all_three_invalid:,} ({pct(all_three_invalid):.2f}%)"
)