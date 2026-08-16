from pathlib import Path

import pandas as pd


PROFILE_FILE = Path("data/profiles/batch_profiles.parquet")


METRICS = [
    "negative_duration_rate",
    "zero_duration_rate",
    "zero_distance_rate",
    "negative_fare_rate",
    "negative_total_rate",
    "p50_distance",
    "p95_distance",
    "p99_distance",
    "p999_distance",
]


# Minimum practical change required before an anomaly is surfaced.
#
# Rates are expressed as absolute percentage-point changes.
# Example:
# 0.07 -> 0.01 = 0.06 = 6 percentage points.
RATE_EFFECT_THRESHOLDS = {
    "negative_duration_rate": 0.0001,
    "zero_duration_rate": 0.0025,
    "zero_distance_rate": 0.0050,
    "negative_fare_rate": 0.0100,
    "negative_total_rate": 0.0050,
}


# Distribution metrics use minimum relative change.
# Example:
# baseline 10 -> current 11 = 10% relative change.
DISTANCE_EFFECT_THRESHOLDS = {
    "p50_distance": 0.05,
    "p95_distance": 0.05,
    "p99_distance": 0.05,
    "p999_distance": 0.05,
}


def load_profiles() -> pd.DataFrame:
    if not PROFILE_FILE.exists():
        raise FileNotFoundError(
            f"Profile dataset not found: {PROFILE_FILE}"
        )

    df = pd.read_parquet(PROFILE_FILE)

    return df.sort_values("file").reset_index(drop=True)


def practical_change(metric: str, current: float, baseline: float):
    if metric in RATE_EFFECT_THRESHOLDS:
        effect = abs(current - baseline)
        threshold = RATE_EFFECT_THRESHOLDS[metric]

        return effect, threshold, effect >= threshold

    if metric in DISTANCE_EFFECT_THRESHOLDS:
        if baseline == 0:
            return 0.0, DISTANCE_EFFECT_THRESHOLDS[metric], False

        effect = abs(current - baseline) / abs(baseline)
        threshold = DISTANCE_EFFECT_THRESHOLDS[metric]

        return effect, threshold, effect >= threshold

    return 0.0, 0.0, True


def detect_anomalies(
    df: pd.DataFrame,
    history_window: int = 4,
    min_history: int = 3,
    statistical_threshold: float = 3.0,
) -> pd.DataFrame:

    anomalies = []

    for metric in METRICS:

        for i in range(min_history, len(df)):
            start = max(0, i - history_window)

            history = df.loc[start:i - 1, metric]
            current = df.loc[i, metric]

            baseline = history.median()

            deviations = (history - baseline).abs()
            mad = deviations.median()

            if mad == 0:
                continue

            anomaly_score = abs(current - baseline) / mad

            if anomaly_score < statistical_threshold:
                continue

            effect, effect_threshold, is_material = practical_change(
                metric,
                current,
                baseline,
            )

            if not is_material:
                continue

            direction = "HIGH" if current > baseline else "LOW"

            anomalies.append(
                {
                    "file": df.loc[i, "file"],
                    "metric": metric,
                    "value": current,
                    "baseline": baseline,
                    "mad": mad,
                    "anomaly_score": anomaly_score,
                    "effect_size": effect,
                    "effect_threshold": effect_threshold,
                    "direction": direction,
                }
            )

    return pd.DataFrame(anomalies)


def format_value(metric: str, value: float) -> str:
    if metric.endswith("_rate"):
        return f"{value:.4%}"

    return f"{value:,.2f}"


def format_effect(metric: str, effect: float) -> str:
    if metric.endswith("_rate"):
        return f"{effect:.2%}"

    return f"{effect:.2%}"


def main():
    profiles = load_profiles()

    print("=== BATCH ANOMALY DETECTION V3 ===\n")
    print(f"Profiles loaded: {len(profiles)}")
    print(f"Metrics monitored: {len(METRICS)}")

    anomalies = detect_anomalies(profiles)

    if anomalies.empty:
        print("\nNo material anomalies detected.")
        return

    anomalies = anomalies.sort_values(
        ["file", "anomaly_score"],
        ascending=[True, False],
    )

    print(f"Material anomalies detected: {len(anomalies)}\n")

    for file_name, group in anomalies.groupby(
        "file",
        sort=False,
    ):
        print("=" * 90)
        print(file_name)
        print("=" * 90)

        for _, row in group.iterrows():
            metric = row["metric"]

            value = format_value(
                metric,
                row["value"],
            )

            baseline = format_value(
                metric,
                row["baseline"],
            )

            effect = format_effect(
                metric,
                row["effect_size"],
            )

            print(
                f"{metric:<25} "
                f"value={value:>12} | "
                f"baseline={baseline:>12} | "
                f"score={row['anomaly_score']:>8.2f} | "
                f"effect={effect:>8} | "
                f"{row['direction']}"
            )

        print()


if __name__ == "__main__":
    main()