import pandas as pd

NOV_FILE = "data/raw/yellow_tripdata_2025-11.parquet"
DEC_FILE = "data/raw/yellow_tripdata_2025-12.parquet"

COLUMNS = [
    "VendorID",
    "payment_type",
    "RatecodeID",
    "fare_amount",
    "total_amount",
]

def summarize(file_path, label):
    df = pd.read_parquet(file_path, columns=COLUMNS)

    total = len(df)
    negative_fares = (df["fare_amount"] < 0).sum()

    flex = df[df["payment_type"] == 0]
    flex_negative = (flex["fare_amount"] < 0).sum()
    flex_positive = (flex["fare_amount"] > 0).sum()
    flex_zero = (flex["fare_amount"] == 0).sum()

    print(f"\n=== {label} ===")
    print(f"Total rows:               {total:,}")
    print(f"Negative fare rows:       {negative_fares:,}")
    print(f"Flex Fare rows:           {len(flex):,}")
    print(f"Flex negative fare:       {flex_negative:,}")
    print(f"Flex positive fare:       {flex_positive:,}")
    print(f"Flex zero fare:           {flex_zero:,}")

    print("\nPayment type distribution:")
    print(
        df["payment_type"]
        .value_counts(dropna=False)
        .sort_index()
    )

    print("\nNegative fares by payment type:")
    print(
        df.loc[df["fare_amount"] < 0, "payment_type"]
        .value_counts(dropna=False)
        .sort_index()
    )

    print("\nNegative fares by vendor:")
    print(
        df.loc[df["fare_amount"] < 0, "VendorID"]
        .value_counts(dropna=False)
        .sort_index()
    )

    return {
        "total": total,
        "negative_fares": negative_fares,
        "flex_rows": len(flex),
        "flex_negative": flex_negative,
    }


nov = summarize(NOV_FILE, "NOVEMBER 2025")
dec = summarize(DEC_FILE, "DECEMBER 2025")

print("\n=== CHANGE NOV -> DEC ===")

def pct_change(old, new):
    if old == 0:
        return None
    return ((new - old) / old) * 100

print(
    f"Total rows:         "
    f"{pct_change(nov['total'], dec['total']):.2f}%"
)
print(
    f"Negative fares:     "
    f"{pct_change(nov['negative_fares'], dec['negative_fares']):.2f}%"
)
print(
    f"Flex Fare rows:     "
    f"{pct_change(nov['flex_rows'], dec['flex_rows']):.2f}%"
)
print(
    f"Flex negative fare: "
    f"{pct_change(nov['flex_negative'], dec['flex_negative']):.2f}%"
)