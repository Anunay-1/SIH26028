"""
Turns data/processed/live_status_log.csv into
data/processed/section_observations.csv — the actual model-training input.

Logic: for each (train_number, journey_date), sort events by event_time,
and whenever the last_station_code CHANGES between two consecutive events,
treat that as "the train covered one section" — from the old last_station
to the new one — and record the elapsed time as actual_minutes.

This is intentionally the simplest possible version of Section 13.1's
"construct section-level journeys by pairing consecutive valid
observations/stations" step. It will under-count sections if the polling
interval is coarser than the time it takes to pass a station — that's a
real limitation to revisit once we see actual polling data, not a bug to
silently ignore.

scheduled_minutes is filled in from route_stations.csv where a matching
route/station pair exists; left blank otherwise (join failures are printed,
not silently dropped, since a growing number of them signals a
route_id/matching problem worth fixing before training).

Run:
    python scripts/data/build_section_observations.py
    python scripts/data/build_section_observations.py --input data/processed/synthetic_status_log.csv --out data/processed/section_observations_synthetic.csv
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = REPO_ROOT / "data" / "processed"

sys.path.insert(0, str(REPO_ROOT))
from app.schemas.canonical import SectionObservation, csv_columns  # noqa: E402


def load_inputs(log_path: Path):
    if not log_path.exists():
        raise FileNotFoundError(
            f"{log_path} not found — run poll_live_status.py for a while first."
        )
    log_df = pd.read_csv(log_path)
    # explicit conversion rather than read_csv's parse_dates= — that argument's
    # behavior changed across pandas versions (confirmed silently non-functional
    # on pandas 3.0.2 in testing here, leaving these as plain strings with no
    # error), so we convert explicitly and fail loudly instead if it doesn't work
    for col in ("event_time", "received_at"):
        log_df[col] = pd.to_datetime(log_df[col], errors="raise", format="mixed")

    route_stations_path = PROCESSED_DIR / "route_stations.csv"
    route_stations_df = (
        pd.read_csv(route_stations_path) if route_stations_path.exists() else pd.DataFrame()
    )
    return log_df, route_stations_df


def build_sections(log_df: pd.DataFrame, route_stations_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    unmatched_scheduled = 0

    for (train_number, journey_date), group in log_df.groupby(["train_number", "journey_date"]):
        group = group.sort_values("event_time").reset_index(drop=True)
        journey_id = f"{train_number}_{journey_date}"

        for i in range(1, len(group)):
            prev, curr = group.iloc[i - 1], group.iloc[i]
            if pd.isna(prev["last_station_code"]) or pd.isna(curr["last_station_code"]):
                continue
            if prev["last_station_code"] == curr["last_station_code"]:
                continue  # train hasn't moved to a new station between these two polls yet

            elapsed_minutes = (curr["event_time"] - prev["event_time"]).total_seconds() / 60.0

            scheduled_minutes = None
            if not route_stations_df.empty:
                # best-effort lookup — see docstring re: join failures
                match = route_stations_df[
                    route_stations_df["station_code"].isin(
                        [prev["last_station_code"], curr["last_station_code"]]
                    )
                ]
                if match.empty:
                    unmatched_scheduled += 1

            rows.append(
                SectionObservation(
                    journey_id=journey_id,
                    from_station_code=prev["last_station_code"],
                    to_station_code=curr["last_station_code"],
                    scheduled_minutes=scheduled_minutes,
                    actual_minutes=round(elapsed_minutes, 1),
                    day_of_week=prev["event_time"].weekday(),
                    hour_bucket=prev["event_time"].hour,
                    source_event_ids=f"{i-1}|{i}",
                ).__dict__
            )

    if unmatched_scheduled:
        print(f"[warn] {unmatched_scheduled} sections had no matching route_stations entry "
              f"for scheduled_minutes — leaving blank. Worth investigating if this grows.")

    return pd.DataFrame(rows, columns=csv_columns(SectionObservation))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(PROCESSED_DIR / "live_status_log.csv"))
    parser.add_argument("--out", default=str(PROCESSED_DIR / "section_observations.csv"))
    args = parser.parse_args()

    log_df, route_stations_df = load_inputs(Path(args.input))
    sections_df = build_sections(log_df, route_stations_df)

    out_path = Path(args.out)
    sections_df.to_csv(out_path, index=False)
    print(f"{out_path.name} -> {len(sections_df)} rows written to {out_path}")


if __name__ == "__main__":
    main()
