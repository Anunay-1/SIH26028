"""
Generates a realistic SYNTHETIC live-status log by simulating trains running
their real schedules (from route_stations.csv) with randomized delay
behavior, instead of waiting on a live data source that keeps failing.

This is the ReplayProvider concept from the architecture doc (Section 4.4,
11.5), just generating the replay data ourselves instead of recording it
from a real feed. It unblocks Phase C (baseline ETA) and Phase D (ML model)
immediately, and produces output in EXACTLY the same schema as
poll_live_status.py would, so nothing downstream needs to change when a
real LiveStatusProvider is finally working — you just point the pipeline
at real data instead of this and everything else stays the same.

DELAY MODEL (intentionally simple, documented so you can defend it to
judges as "a synthetic baseline for development," not "pretending this is
real data"):
  - Each journey gets a random "delay personality" drawn once (some trains
    run early, some chronically late) via a base delay offset.
  - Each section adds a small random walk on top of that base delay,
    occasionally with a larger random "incident" delay (simulating
    congestion/signal holds), so delay evolves realistically across a
    journey rather than jumping around independently at each station.

Usage:
    python scripts/data/generate_synthetic_events.py --num-journeys 200
"""

import argparse
import csv
import random
import sys
from datetime import datetime, timedelta, date
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = REPO_ROOT / "data" / "processed"

sys.path.insert(0, str(REPO_ROOT))
from app.schemas.canonical import TrainStateEvent, csv_columns  # noqa: E402


def parse_time_str(t: str, base_date: date, day_offset: int = 0):
    """Combine a schedule's HH:MM:SS with a base date + day offset into a real datetime."""
    if pd.isna(t) or t in (None, "", "None"):
        return None
    h, m, s = [int(x) for x in str(t).split(":")]
    return datetime.combine(base_date, datetime.min.time()) + timedelta(
        days=day_offset, hours=h, minutes=m, seconds=s
    )


def simulate_journey(route_id: str, train_number: str, stops: pd.DataFrame,
                      journey_date: date, rng: random.Random):
    """
    Walks through one train's real stop sequence, generating a synthetic
    TrainStateEvent at each stop with realistic cumulative delay.
    Returns a list of TrainStateEvent.
    """
    events = []
    base_delay_minutes = rng.gauss(mu=5, sigma=8)  # this train's general "personality"
    cumulative_delay = max(0, base_delay_minutes)

    stops = stops.sort_values("sequence").reset_index(drop=True)
    day_counter = 0
    prev_sched_time = None

    for i, row in stops.iterrows():
        sched_time_raw = row["scheduled_arrival"] if pd.notna(row["scheduled_arrival"]) else row["scheduled_departure"]
        sched_dt = parse_time_str(sched_time_raw, journey_date, day_counter)
        if sched_dt is None:
            continue

        # detect day rollover (schedule time went backwards vs previous stop)
        if prev_sched_time is not None and sched_dt < prev_sched_time:
            day_counter += 1
            sched_dt = parse_time_str(sched_time_raw, journey_date, day_counter)
        prev_sched_time = sched_dt

        # random walk on delay, with occasional bigger "incident" jumps
        cumulative_delay += rng.gauss(mu=0, sigma=2)
        if rng.random() < 0.05:  # 5% chance of a bigger delay event at this section
            cumulative_delay += rng.uniform(10, 30)
        cumulative_delay = max(0, cumulative_delay)  # trains don't un-delay below 0 here

        actual_dt = sched_dt + timedelta(minutes=cumulative_delay)
        next_station = stops.iloc[i + 1]["station_code"] if i + 1 < len(stops) else None

        events.append(
            TrainStateEvent(
                train_number=train_number,
                journey_date=journey_date.strftime("%d-%m-%Y"),
                event_time=actual_dt.isoformat(),
                received_at=actual_dt.isoformat(),  # synthetic: no real ingestion lag
                last_station_code=row["station_code"],
                next_station_code=next_station,
                delay_minutes=round(cumulative_delay, 1),
                source="synthetic",
                source_event_id=f"{route_id}_{i}",
            )
        )
    return events


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--num-journeys", type=int, default=200,
                         help="how many (train, date) journeys to simulate")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default=str(PROCESSED_DIR / "synthetic_status_log.csv"))
    parser.add_argument("--routes-dir", default=str(PROCESSED_DIR),
                         help="folder containing routes.csv and route_stations.csv to simulate from")
    args = parser.parse_args()

    rng = random.Random(args.seed)

    routes_dir = Path(args.routes_dir)
    routes = pd.read_csv(routes_dir / "routes.csv")
    route_stations = pd.read_csv(routes_dir / "route_stations.csv")

    # only simulate routes that actually have a plausible stop count (2-40),
    # sidestepping the corrupted-schedule routes we found earlier rather than
    # baking that known bad data into our synthetic set
    stop_counts = route_stations.groupby("route_id").size()
    plausible_route_ids = stop_counts[(stop_counts >= 2) & (stop_counts <= 40)].index
    candidate_routes = routes[routes["route_id"].isin(plausible_route_ids)]

    if candidate_routes.empty:
        print("No routes with a plausible (2-40) stop count found — "
              "check route_stations.csv before proceeding.")
        return

    sampled_routes = candidate_routes.sample(
        n=min(args.num_journeys, len(candidate_routes)), random_state=args.seed
    )

    all_events = []
    today = date.today()
    for _, route in sampled_routes.iterrows():
        stops = route_stations[route_stations["route_id"] == route["route_id"]]
        # spread journeys across the past 14 days so we get day-of-week variety
        journey_date = today - timedelta(days=rng.randint(0, 14))
        events = simulate_journey(route["route_id"], route["train_number"], stops, journey_date, rng)
        all_events.extend(events)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_columns(TrainStateEvent))
        writer.writeheader()
        for e in all_events:
            writer.writerow(e.__dict__)

    print(f"Simulated {len(sampled_routes)} journeys -> {len(all_events)} events -> {out_path}")
    print(f"(excluded routes with implausible stop counts from the corrupted-schedule "
          f"issue found earlier — {len(routes) - len(candidate_routes)} routes skipped)")


if __name__ == "__main__":
    main()
