import pyarrow.parquet as pq

file_path = "data/raw/yellow_tripdata_2025-01.parquet"

parquet_file = pq.ParquetFile(file_path)
metadata = parquet_file.metadata

print(f"Rows:       {metadata.num_rows:,}")
print(f"Columns:    {metadata.num_columns}")
print(f"Row groups: {metadata.num_row_groups}")

print("\nSchema:")
print(parquet_file.schema)