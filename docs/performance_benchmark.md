# Processing Performance Benchmark

## Purpose

This benchmark evaluates whether the current Pandas-based Silver transformation remains suitable as the NYC Mobility Analytics dataset grows.

The goal is to identify an actual processing bottleneck before introducing distributed processing technologies.

## Dataset Scale

The pipeline currently contains NYC Yellow Taxi data for 2023–2025.

| Year | Trips |
|---|---:|
| 2023 | 38,310,226 |
| 2024 | 41,169,720 |
| 2025 | 48,722,602 |
| **Total** | **128,202,548** |

## Pandas Transformation Benchmark

The 2023 dataset was processed through the existing Pandas-based Silver transformation.

| Metric | Result |
|---|---:|
| Rows processed | 38,310,226 |
| Wall-clock runtime | 73.806 seconds |
| Approx. throughput | 519,000 rows/second |

The measured runtime includes reading monthly Parquet files from Amazon S3, applying Silver transformations and quality classifications, serializing the resulting Parquet files, and writing them back to S3.

## Result

At the current scale, the Pandas implementation does not represent a meaningful processing bottleneck.

A migration to distributed processing is therefore not currently justified by measured performance.

Distributed processing should be reconsidered if future data volume, transformation complexity, memory requirements, or execution-time requirements exceed what the current implementation can handle efficiently.

## Schema Evolution Finding

The 2023 backfill also exposed an upstream schema variation in the NYC TLC source data.

January 2023 used:

`airport_fee`

while later source files used:

`Airport_fee`

The difference is case-sensitive in the source Parquet schema but resulted in duplicate column metadata when AWS Glue normalized the schema for Athena.

The Silver transformation now normalizes this source variation to a canonical `Airport_fee` column before writing Parquet.

This keeps the Silver schema consistent across years and prevents the schema variation from propagating into the analytical layer.