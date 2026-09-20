"""
For one train, check: are the ~400 "stops" mostly the SAME station code
repeated many times (duplication bug — dedup would fix it), or genuinely
~400 DIFFERENT station codes (the source file itself is wrong/unusable)?

Usage:
    python scripts/data/diagnose_duplicate_stops.py 12431
"""

import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = REPO_ROOT / "data" / "processed"


def main():
    train_number = sys.argv[1] if len(sys.argv) > 1 else "12431"

    routes = pd.read_csv(PROCESSED_DIR / "routes.csv")
    rs = pd.read_csv(PROCESSED_DIR / "route_stations.csv")

    matches = routes[routes["train_number"].astype(str) == train_number]
    if matches.empty:
        print(f"train {train_number} not found")
        return

    rid = matches.iloc[0]["route_id"]
    stops = rs[rs["route_id"] == rid]

    total_rows = len(stops)
    unique_stations = stops["station_code"].nunique()

    print(f"Route {rid}: {total_rows} total stop-rows, {unique_stations} UNIQUE station codes")
    print()

    dupe_counts = stops["station_code"].value_counts()
    print("Top 15 most-repeated station codes on this 'route':")
    print(dupe_counts.head(15).to_string())


if __name__ == "__main__":
    main()
