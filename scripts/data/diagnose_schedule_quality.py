"""
Diagnostic: how many routes in route_stations.csv have an implausible number
of stops or implausibly tight timing (suburban-local-style patterns) despite
being labeled as express/superfast/Rajdhani/Shatabdi/Duronto class trains?

This doesn't fix anything — it just tells us if what we saw for 12951 is a
one-off or a systemic problem with the datameet/railways schedules.json data.

Usage:
    python scripts/data/diagnose_schedule_quality.py
"""

import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = REPO_ROOT / "data" / "processed"


def main():
    routes = pd.read_csv(PROCESSED_DIR / "routes.csv")
    rs = pd.read_csv(PROCESSED_DIR / "route_stations.csv")

    stop_counts = rs.groupby("route_id").size().rename("stop_count")
    merged = routes.merge(stop_counts, on="route_id", how="left")

    print("=== Stop count distribution across ALL routes ===")
    print(merged["stop_count"].describe())
    print()

    # Focus on named "premium" classes that should have FEW stops
    premium_types = merged["train_type"].astype(str).str.contains(
        "Raj|Shatabdi|Duronto|Superfast", case=False, na=False
    )
    premium = merged[premium_types]
    print(f"=== {len(premium)} routes labeled Rajdhani/Shatabdi/Duronto/Superfast ===")
    print(premium[["train_number", "train_name", "train_type", "stop_count"]]
          .sort_values("stop_count", ascending=False)
          .head(20)
          .to_string(index=False))
    print()

    suspicious = premium[premium["stop_count"] > 30]
    print(f"=== {len(suspicious)} / {len(premium)} premium-class routes have >30 stops "
          f"(suspicious for this train class) ===")
    if len(suspicious):
        pct = 100 * len(suspicious) / len(premium)
        print(f"That's {pct:.1f}% of premium-class routes — "
              f"{'a systemic problem' if pct > 10 else 'a smaller number of outliers'}.")


if __name__ == "__main__":
    main()
