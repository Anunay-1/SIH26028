"""
CLI wrapper around app.providers.replay.ReplayProvider. This file is now
intentionally thin — ALL the delay modeling logic lives in
app/simulation/delay_model.py and app/simulation/journey_simulator.py, and
ALL the orchestration (including rake-cascading lookback) lives in
ReplayProvider. This script's only job is: sample some (train, date) pairs,
call the provider, write the results to a CSV.

WHY VIA ReplayProvider RATHER THAN CALLING simulate_journey() DIRECTLY: using
the same provider the rest of the app will eventually use means this batch
dataset is generated with EXACTLY the same logic (including rake-cascading
lookback to the previous day) as any other caller would get — no risk of two
slightly-different copies of the orchestration drifting apart.

REPRODUCIBILITY NOTE: --seed controls which (train, date) pairs get SAMPLED.
The actual delay simulation for a given (train, date) pair is independently
deterministic (see ReplayProvider/_deterministic_seed) — so the same train on
the same date always simulates identically regardless of --seed, only which
trains/dates get chosen for this particular batch changes.

WHY A FULL YEAR: seasonal effects (fog Nov-Feb, monsoon Jun-Sep) are core to
the delay model's realism. Sampling only the last 14 days (the original
version of this script) could never actually exercise those seasonal
branches. Spreading simulated journeys across a full year is what makes the
fog/monsoon components in delay_model.py actually show up in the data,
rather than sitting unused.

Usage:
    python scripts/data/generate_synthetic_events.py --num-journeys 500
"""

import argparse
import csv
import random
import sys
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = REPO_ROOT / "data" / "processed"

sys.path.insert(0, str(REPO_ROOT))
from app.schemas.canonical import TrainStateEvent, csv_columns  # noqa: E402
from app.providers.replay import ReplayProvider  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--num-journeys", type=int, default=500,
                         help="how many (train, date) journeys to simulate")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default=str(PROCESSED_DIR / "synthetic_status_log.csv"))
    parser.add_argument("--routes-dir", default=str(PROCESSED_DIR),
                         help="folder containing stations.csv/routes.csv/route_stations.csv to simulate from")
    parser.add_argument("--days-back", type=int, default=365,
                         help="spread simulated journeys across this many past days, "
                              "so seasonal effects (fog/monsoon) actually appear in the data")
    args = parser.parse_args()

    routes_dir = Path(args.routes_dir)
    provider = ReplayProvider(routes_dir)

    usable_routes = provider._routes[provider._routes["route_id"].isin(provider._plausible_route_ids)]
    if usable_routes.empty:
        print("No routes with a plausible (2-40) stop count found — "
              "check route_stations.csv before proceeding.")
        return

    sample_rng = random.Random(args.seed)
    sampled_routes = usable_routes.sample(
        n=min(args.num_journeys, len(usable_routes)), random_state=args.seed,
        replace=args.num_journeys > len(usable_routes),
    )
    if args.num_journeys > len(usable_routes):
        print(f"[note] requested {args.num_journeys} journeys but only "
              f"{len(usable_routes)} plausible routes exist — sampling with "
              f"replacement (same routes simulated on different dates, which is "
              f"realistic anyway since real trains run repeatedly)")

    all_events = []
    today = date.today()
    for _, route in sampled_routes.iterrows():
        journey_date = today - timedelta(days=sample_rng.randint(0, args.days_back))
        events = provider.get_journey_events(route["train_number"], journey_date)
        all_events.extend(events)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_columns(TrainStateEvent))
        writer.writeheader()
        for e in all_events:
            writer.writerow(e.__dict__)

    print(f"Simulated {len(sampled_routes)} journeys -> {len(all_events)} events -> {out_path}")
    print(f"(spread across the last {args.days_back} days; "
          f"excluded {len(provider._routes) - len(usable_routes)} routes with implausible stop counts)")


if __name__ == "__main__":
    main()
