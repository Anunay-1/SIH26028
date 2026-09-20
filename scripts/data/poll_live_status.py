"""
Polls pyinrail for live running status of a fixed list of trains and appends
normalized rows to data/processed/live_status_log.csv.

This IS the LiveStatusProvider from the architecture doc (Section 11.1),
implemented minimally for the data-collection phase — once app/ has a real
FastAPI service, this logic moves into app/providers/pyinrail.py behind the
LiveStatusProvider interface, unchanged in spirit.

*** ACTION NEEDED BEFORE TRUSTING THIS SCRIPT ***
I could not verify pyinrail's exact live-status method name/return shape
from outside a working install (its README clearly documents schedule/fare/
seat methods, but not the live-status call signature). Run with `--once`
first, inspect `_call_live_status()`'s raw output via the printed debug line,
and fix that one function to match reality before scheduling the loop.
pyinrail also requires tesseract-ocr installed on your system (it appears to
solve a CAPTCHA against the NTES enquiry system) — if `--once` fails outright,
start there.

Usage:
    python scripts/data/poll_live_status.py --trains 12951,12301 --once
    python scripts/data/poll_live_status.py --trains 12951,12301 --interval 300
"""

import argparse
import csv
import sys
import time
from datetime import datetime, date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_PATH = REPO_ROOT / "data" / "processed" / "live_status_log.csv"

sys.path.insert(0, str(REPO_ROOT))
from app.schemas.canonical import TrainStateEvent, csv_columns  # noqa: E402


def _call_live_status(train_number: str, journey_date: str) -> dict:
    """
    ADAPTER FUNCTION — this is the one place that talks to pyinrail directly.
    Everything else in this file only knows about TrainStateEvent.

    Replace the body below once you've confirmed pyinrail's real method.
    Expected shape to normalize into, at minimum:
        last_station_code, next_station_code, delay_minutes
    """
    from pyinrail import pyinrail  # imported here so --help works without pyinrail installed

    # PLACEHOLDER — confirm the real call. pyinrail's RailwayEnquiry is
    # constructed with src/dest/date for route-search use cases; the
    # live-status call may hang off a different method/class. Inspect
    # `dir(pyinrail)` and the package source after `pip install pyinrail`
    # and wire the real call in here.
    enq = pyinrail.RailwayEnquiry(train_number=train_number, date=journey_date)
    raw = enq.get_live_status(as_df=False)  # <- verify this method exists
    print(f"[debug] raw pyinrail response for {train_number}: {raw}")

    return {
        "last_station_code": raw.get("currentStationCode"),
        "next_station_code": raw.get("nextStationCode"),
        "delay_minutes": raw.get("delayMinutes"),
    }


def poll_once(train_numbers: list[str], journey_date: str) -> list[TrainStateEvent]:
    events = []
    now_iso = datetime.utcnow().isoformat()
    for train_number in train_numbers:
        try:
            parsed = _call_live_status(train_number, journey_date)
        except Exception as exc:
            print(f"[warn] live status failed for {train_number}: {exc}")
            continue

        events.append(
            TrainStateEvent(
                train_number=train_number,
                journey_date=journey_date,
                event_time=now_iso,       # provisional: pyinrail may return its own timestamp
                received_at=now_iso,
                last_station_code=parsed.get("last_station_code"),
                next_station_code=parsed.get("next_station_code"),
                delay_minutes=parsed.get("delay_minutes"),
                source="pyinrail",
            )
        )
    return events


def append_events(events: list[TrainStateEvent]):
    if not events:
        return
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_header = not OUT_PATH.exists()
    with open(OUT_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_columns(TrainStateEvent))
        if write_header:
            writer.writeheader()
        for e in events:
            writer.writerow(e.__dict__)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trains", required=True, help="comma-separated train numbers")
    parser.add_argument("--date", default=date.today().strftime("%d-%m-%Y"))
    parser.add_argument("--interval", type=int, default=300, help="seconds between polls")
    parser.add_argument("--once", action="store_true", help="poll a single time and exit")
    args = parser.parse_args()

    train_numbers = [t.strip() for t in args.trains.split(",") if t.strip()]

    if args.once:
        events = poll_once(train_numbers, args.date)
        append_events(events)
        print(f"Wrote {len(events)} events to {OUT_PATH}")
        return

    print(f"Polling {train_numbers} every {args.interval}s. Ctrl+C to stop.")
    while True:
        events = poll_once(train_numbers, args.date)
        append_events(events)
        print(f"[{datetime.utcnow().isoformat()}] wrote {len(events)} events")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
