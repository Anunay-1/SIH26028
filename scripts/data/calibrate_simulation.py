"""
Simulation Calibration Audit — Anchoring Synthetic Delays to Real Published Indian Railways Numbers.

Indian Railways Official Punctuality Definition:
- A train is classified as 'Punctual / On-Time' if terminating arrival delay is <= 15 minutes.

Published Benchmark Targets (Ministry of Railways FY 2022-23 / Rajya Sabha replies):
- Premium (Rajdhani, Shatabdi, Duronto, Vande Bharat): ~90.0%
- Mail / Express: ~84.1%
- Passenger / Ordinary: ~68.0%
"""

import json
from datetime import date, timedelta
from pathlib import Path
import pandas as pd
import numpy as np

from app.config import PROCESSED_DATA_DIR
from app.providers.replay import ReplayProvider


def run_calibration_audit(num_samples_per_class: int = 75) -> dict:
    data_dir = PROCESSED_DATA_DIR
    provider = ReplayProvider(data_dir)
    routes = pd.read_csv(data_dir / "routes.csv")
    route_stations = pd.read_csv(data_dir / "route_stations.csv")

    stop_counts = route_stations.groupby("route_id").size()
    valid_routes = routes[routes["route_id"].isin(stop_counts[(stop_counts >= 3) & (stop_counts <= 35)].index)]

    # Categorize routes into the 3 official classes
    premium_types = {"Rajdhani", "Raj", "Shatabdi", "Shtb", "Duronto", "Drnt", "Vande Bharat"}
    passenger_types = {"Passenger", "Pass", "MEMU", "DEMU", "Toy"}

    classes = {
        "Premium": valid_routes[valid_routes["train_type"].isin(premium_types)],
        "Mail_Express": valid_routes[~valid_routes["train_type"].isin(premium_types | passenger_types)],
        "Passenger": valid_routes[valid_routes["train_type"].isin(passenger_types)],
    }

    targets = {
        "Premium": 90.0,
        "Mail_Express": 84.1,
        "Passenger": 68.0,
    }

    start_date = date(2026, 4, 1)
    results = {}

    print("Running simulation calibration against Indian Railways official punctuality figures...\n")

    for c_name, c_routes in classes.items():
        if c_routes.empty:
            continue

        delays = []
        sampled = c_routes.head(num_samples_per_class)

        for i, (_, route) in enumerate(sampled.iterrows()):
            t_num = str(route["train_number"])
            j_date = start_date + timedelta(days=(i % 15))
            events = provider.get_journey_events(t_num, j_date)
            if events:
                final_delay = float(events[-1].delay_minutes or 0)
                delays.append(final_delay)

        delays_arr = np.array(delays) if delays else np.array([0.0])
        # Punctual if final delay <= 15 minutes
        on_time_pct = round(float(np.mean(delays_arr <= 15.0)) * 100.0, 1)
        target_pct = targets[c_name]
        gap = round(on_time_pct - target_pct, 1)

        results[c_name] = {
            "samples_evaluated": len(delays),
            "simulated_punctuality_pct": on_time_pct,
            "ir_target_pct": target_pct,
            "gap_points": gap,
            "mean_final_delay_minutes": round(float(np.mean(delays_arr)), 1),
            "median_final_delay_minutes": round(float(np.median(delays_arr)), 1),
            "p90_final_delay_minutes": round(float(np.percentile(delays_arr, 90)), 1),
        }

        print(f"[{c_name}] Simulated Punctuality: {on_time_pct}% (Target: {target_pct}%, Gap: {gap:+}%)")

    report = {
        "title": "Simulation Operational Realism Audit",
        "benchmark_source": "Ministry of Railways Published Operational Statistics (FY 2022-23 / Rajya Sabha PQ)",
        "punctuality_grace_minutes": 15,
        "classes": results,
        "notes": "Evaluation uses standard Indian Railways 15-minute terminating arrival threshold.",
    }

    out_file = PROCESSED_DATA_DIR / "simulation_calibration_report.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\nCalibration report saved to {out_file}")
    return report


if __name__ == "__main__":
    run_calibration_audit()
