"""
Quick manual sanity check: prints one train's parsed route_stations rows in
sequence order, so you can visually confirm stations are in the right
geographic order and times increase sensibly.

Usage:
    python scripts/data/check_one_train.py 12951
"""

import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = REPO_ROOT / "data" / "processed"


def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/data/check_one_train.py <train_number>")
        sys.exit(1)

    train_number = sys.argv[1]

    routes = pd.read_csv(PROCESSED_DIR / "routes.csv")
    rs = pd.read_csv(PROCESSED_DIR / "route_stations.csv")

    matches = routes[routes["train_number"].astype(str) == train_number]
    if matches.empty:
        print(f"No train {train_number} found in routes.csv. "
              f"Try one of these instead:\n{routes['train_number'].sample(10).tolist()}")
        return

    print(matches.to_string())
    print()

    for rid in matches["route_id"]:
        stops = rs[rs["route_id"] == rid].sort_values("sequence")
        print(f"--- route_id: {rid} ({len(stops)} stops) ---")
        print(stops[["sequence", "station_code", "scheduled_arrival", "scheduled_departure"]].to_string(index=False))
        print()


if __name__ == "__main__":
    main()
