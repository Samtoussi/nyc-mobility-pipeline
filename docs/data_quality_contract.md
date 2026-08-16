# Data Quality Contract V1

## Purpose

This document defines the initial data quality expectations for the NYC Yellow Taxi pipeline.

The rules are based on profiling and investigation of the 2025 Yellow Taxi trip dataset.

The goal of the Silver layer is not to remove every unusual record.

Instead, Silver should:

- preserve valid information whenever possible
- prevent unreliable values from being presented as trustworthy
- expose data quality explicitly to downstream consumers
- distinguish record-level problems from column-level problems
- detect upstream changes instead of silently accepting them

Raw data must remain unchanged.

---

# 1. Schema Contract

## Required columns

The pipeline expects the required Yellow Taxi fields used by downstream transformations to exist.

Examples include:

- VendorID
- tpep_pickup_datetime
- tpep_dropoff_datetime
- trip_distance
- PULocationID
- DOLocationID
- payment_type
- RatecodeID
- fare_amount
- total_amount

### Missing required column

Severity:

CRITICAL

Action:

FAIL BATCH

Reason:

A missing required field can make downstream transformations unreliable or impossible.

---

## Unexpected columns

Severity:

WARNING

Action:

ALLOW BATCH  
LOG SCHEMA CHANGE

Reason:

New upstream columns do not necessarily invalidate existing data.

They should be recorded and investigated before being incorporated downstream.

---

# 2. Temporal Quality

Silver derives:

duration_min

from:

tpep_dropoff_datetime - tpep_pickup_datetime

However, raw timestamps cannot always be interpreted literally.

---

## Valid duration

Condition:

dropoff_datetime > pickup_datetime

Action:

Calculate duration normally.

Quality:

duration_quality = VALID

---

## Zero duration

Zero-duration records must not automatically be removed.

Source-specific behavior may cause pickup and dropoff timestamps to be identical even when other attributes indicate a meaningful trip.

### Known Helix pattern

For VendorID = 7, profiling showed that Helix records can contain:

pickup_datetime == dropoff_datetime

while still containing meaningful:

- trip distance
- fare
- pickup location
- dropoff location

Therefore these records must not be interpreted as genuine zero-minute trips.

Action:

duration_min = NULL

Quality:

duration_quality = UNAVAILABLE_SOURCE_SEMANTICS

The trip itself remains available for analyses that do not depend on duration.

---

## Negative duration

Negative durations are not automatically grounds for deleting the entire record.

Known timezone / DST ambiguity must be considered.

If the duration cannot be interpreted reliably:

Action:

duration_min = NULL

Quality:

duration_quality = INVALID

The remaining trip attributes may still be retained.

---

# 3. Distance Quality

Extreme trip_distance values were identified during profiling.

Investigation showed that some extreme values are inconsistent with other trip attributes.

Examples included records with:

- tens or hundreds of thousands of miles
- durations measured in minutes
- ordinary NYC fares
- valid-looking pickup and dropoff zones

This indicates that trip_distance may be unreliable while the rest of the record remains useful.

Therefore:

Extreme distance must NOT automatically cause the entire trip to be deleted.

Silver should distinguish between:

distance_quality = VALID

distance_quality = SUSPICIOUS

distance_quality = INVALID

When distance is considered unreliable:

trip_distance should not be exposed downstream as a trustworthy measurement.

The exact automated classification rules will be defined separately from this contract and may evolve as additional source behavior is understood.

---

# 4. Financial Quality

Negative financial values must not automatically be treated as invalid data.

Profiling showed systematic negative fare behavior associated with specific source patterns and possible correction/reversal behavior.

Therefore:

fare_amount < 0

does NOT imply:

INVALID RECORD

Negative values must remain available unless stronger evidence indicates corruption.

Silver must preserve the original financial information.

Future derived fields may classify financial semantics such as corrections or reversal candidates when sufficient evidence exists.

---

# 5. Record Preservation Principle

A quality problem in one attribute does not automatically invalidate the entire trip.

Example:

A record may have:

duration_quality = INVALID

while:

distance_quality = VALID

financial_quality = VALID

The record should therefore remain usable for analyses that do not depend on duration.

This principle applies throughout the Silver transformation layer.

---

# 6. Quality Metadata

Silver should expose quality information explicitly.

Planned derived fields include:

- duration_min
- duration_quality
- distance_quality
- financial_quality
- record_quality

Possible record-level classifications:

VALID

PARTIAL

INVALID

A PARTIAL record contains useful information but has one or more attributes that should not be trusted for specific downstream analyses.

---

# 7. Raw Data Immutability

Raw source files must never be modified by cleaning or transformation logic.

The pipeline follows:

RAW
↓
VALIDATE
↓
TRANSFORM
↓
SILVER

Raw represents the source exactly as received.

Silver represents the pipeline's interpreted and quality-controlled version of that data.

---

# 8. Observability

Data quality rules must be monitored over time.

The pipeline should detect changes in metrics such as:

- row counts
- schema
- zero-duration rate
- negative-duration rate
- zero-distance rate
- negative-fare rate
- negative-total rate
- distance distribution

A statistical anomaly is not automatically a data quality failure.

An anomaly is a signal that upstream behavior may have changed and should be investigated.

---

# 9. Contract Evolution

This contract is versioned.

Rules may change when:

- upstream systems change
- new vendors or record types appear
- field semantics change
- new evidence invalidates an existing assumption
- additional profiling reveals previously unknown behavior

Changes to validation or cleaning rules must be intentional and documented.

The pipeline should never silently reinterpret historical assumptions.

---

# Contract Version

Version: 1.0

Status: Initial contract based on 2025 discovery and profiling.