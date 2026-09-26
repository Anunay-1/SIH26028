"""
Human-readable demo: shows one simulated train journey, station by station,
with scheduled vs. actual time and evolving delay. This is the "does the
model actually look right" sanity check to run visually, complementing the
automated statistical tests in tests/test_delay_model.py.

Usage:
    python scripts/demo/show_journey.py --train 12951 --date 2026-12-15
    python scripts/demo/show_journey.py --train 12951 --list-trains   # see what's available
    python scripts/demo/show_journey.py --train 12951 --compare-seasons
    python scripts/demo/show_journey.py --compare-priority --date 2026-12-15
"""

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data" / "processed"

sys.path.insert(0, str(REPO_ROOT))
from app.providers.replay import ReplayProvider  # noqa: E402


def fmt_dt(iso_str: str) -> str:
    dt = datetime.fromisoformat(iso_str)
    return dt.strftime("%d-%b %H:%M")


def print_journey(provider: ReplayProvider, train_number: str, journey_date: date, routes_df: pd.DataFrame):
    events = provider.get_journey_events(train_number, journey_date)
    if not events:
        print(f"No data for train {train_number} on {journey_date} "
              f"(unknown train, or excluded for corrupted schedule data — see README)")
        return

    route_row = routes_df[routes_df["train_number"].astype(str) == str(train_number)].iloc[0]
    print(f"\n=== Train {train_number} — {route_row['train_name']} ({route_row['train_type']}) ===")
    print(f"Journey date: {journey_date}    Route: {route_row['source_station_code']} -> {route_row['destination_station_code']}")
    print()
    print(f"{'Seq':<4} {'Station':<8} {'Actual Time':<16} {'Delay (min)':<12} {'Δ vs prev':<10}")
    print("-" * 55)

    prev_delay = None
    for i, e in enumerate(events, start=1):
        delta = "" if prev_delay is None else f"{e.delay_minutes - prev_delay:+.1f}"
        print(f"{i:<4} {e.last_station_code:<8} {fmt_dt(e.event_time):<16} "
              f"{e.delay_minutes:<12} {delta:<10}")
        prev_delay = e.delay_minutes

    print()
    print(f"Net delay by final station: {events[-1].delay_minutes:.1f} min")


def compare_seasons(provider: ReplayProvider, train_number: str, routes_df: pd.DataFrame):
    """Same train, winter (fog season) vs summer — should show winter running later on average."""
    print(f"\n{'='*60}\nSEASONAL COMPARISON — same train, two dates\n{'='*60}")
    print_journey(provider, train_number, date(2026, 12, 20), routes_df)  # deep fog season
    print_journey(provider, train_number, date(2026, 7, 20), routes_df)   # no fog season


def compare_priority(provider: ReplayProvider, routes_df: pd.DataFrame, journey_date: date):
    """Different priority classes, same date — premium trains should show less delay."""
    print(f"\n{'='*60}\nPRIORITY-CLASS COMPARISON — different train types, same date\n{'='*60}")
    for train_type in ["Rajdhani", "Passenger", "Express"]:
        candidates = routes_df[routes_df["train_type"].astype(str).str.contains(train_type, case=False, na=False)]
        if candidates.empty:
            print(f"\n(no {train_type}-class train found in this dataset)")
            continue
        train_number = str(candidates.iloc[0]["train_number"])
        print_journey(provider, train_number, journey_date, routes_df)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", help="train number to show")
    parser.add_argument("--date", help="journey date, YYYY-MM-DD (default: 2026-12-15)")
    parser.add_argument("--data-dir", default=str(DATA_DIR))
    parser.add_argument("--list-trains", action="store_true", help="list available train numbers and exit")
    parser.add_argument("--compare-seasons", action="store_true",
                         help="show the same train in winter vs summer (fog effect demo)")
    parser.add_argument("--compare-priority", action="store_true",
                         help="show Rajdhani vs Express vs Passenger on the same date (priority effect demo)")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    routes_df = pd.read_csv(data_dir / "routes.csv")
    provider = ReplayProvider(data_dir)

    if args.list_trains:
        usable = routes_df[routes_df["route_id"].isin(provider._plausible_route_ids)]
        print(usable[["train_number", "train_name", "train_type"]].to_string(index=False))
        return

    journey_date = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else date(2026, 12, 15)

    if args.compare_seasons:
        if not args.train:
            print("--compare-seasons requires --train <number>")
            return
        compare_seasons(provider, args.train, routes_df)
        return

    if args.compare_priority:
        compare_priority(provider, routes_df, journey_date)
        return

    if not args.train:
        print("Specify --train <number>, or use --list-trains to see options, "
              "or --compare-seasons / --compare-priority for a demonstration.")
        return

    print_journey(provider, args.train, journey_date, routes_df)


if __name__ == "__main__":
    main()
