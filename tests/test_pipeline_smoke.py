"""
End-to-end smoke test for the data pipeline. Run this any time you change
one of the scripts in scripts/data/ to catch breakage immediately, instead
of finding out three steps later that something upstream is silently wrong.

This does NOT replace the diagnose_*.py scripts (those check DATA QUALITY
on real cloned data). This checks that the CODE runs correctly and produces
structurally sane output, using a small synthetic fixture so it's fast and
doesn't depend on datameet/railways being cloned.

IMPORTANT: this runs entirely inside a temporary directory (via `tempfile`)
and NEVER touches your real data/raw or data/processed folders. An earlier
version of this test deleted the real data/processed folder directly, which
both risked wiping real generated data and crashed on Windows/OneDrive with
a PermissionError (OneDrive can hold a lock on files it's syncing). Isolating
into a temp dir fixes both problems at once.

Usage:
    python tests/test_pipeline_smoke.py

Exits with code 0 and prints "ALL CHECKS PASSED" if everything's fine,
otherwise prints exactly which check failed and exits non-zero.
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]

FAILURES = []


def check(name: str, condition: bool, detail: str = ""):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail and not condition else ""))
    if not condition:
        FAILURES.append(name)


def write_fixture(raw_dir: Path):
    """A deliberately small, hand-crafted fixture — 3 stations, 1 train, 3 stops —
    covering the day-rollover case (KOTA is day 1, BCT is day 2) since that's
    the trickiest part of the parsing/simulation logic."""
    raw_dir.mkdir(parents=True, exist_ok=True)

    (raw_dir / "stations.json").write_text(json.dumps({
        "type": "FeatureCollection", "features": [
            {"geometry": {"type": "Point", "coordinates": [77.2, 28.6]}, "type": "Feature",
             "properties": {"state": "Delhi", "code": "NDLS", "name": "NEW DELHI", "zone": "NR", "address": "Delhi"}},
            {"geometry": {"type": "Point", "coordinates": [72.87, 19.07]}, "type": "Feature",
             "properties": {"state": "Maharashtra", "code": "BCT", "name": "MUMBAI CENTRAL", "zone": "WR", "address": "Mumbai"}},
            {"geometry": {"type": "Point", "coordinates": [75.8, 26.9]}, "type": "Feature",
             "properties": {"state": "Rajasthan", "code": "KOTA", "name": "KOTA JN", "zone": "WCR", "address": "Kota"}},
        ]
    }))

    (raw_dir / "trains.json").write_text(json.dumps({
        "type": "FeatureCollection", "features": [
            {"geometry": {"type": "LineString", "coordinates": [[77.2, 28.6], [72.87, 19.07]]}, "type": "Feature",
             "properties": {"number": "12951", "name": "MUMBAI RAJDHANI", "from_station_code": "NDLS",
                             "to_station_code": "BCT", "distance": 1384, "type": "Rajdhani"}},
        ]
    }))

    (raw_dir / "schedules.json").write_text(json.dumps([
        {"arrival": "None", "day": 1, "train_name": "MUMBAI RAJDHANI", "station_name": "NEW DELHI",
         "station_code": "NDLS", "id": 1, "train_number": "12951", "departure": "16:00:00"},
        {"arrival": "23:45:00", "day": 1, "train_name": "MUMBAI RAJDHANI", "station_name": "KOTA JN",
         "station_code": "KOTA", "id": 2, "train_number": "12951", "departure": "23:50:00"},
        {"arrival": "08:15:00", "day": 2, "train_name": "MUMBAI RAJDHANI", "station_name": "MUMBAI CENTRAL",
         "station_code": "BCT", "id": 3, "train_number": "12951", "departure": "None"},
    ]))


def run(cmd: list) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable] + cmd, cwd=REPO_ROOT, capture_output=True, text=True)


def main():
    # Everything runs inside a fresh OS temp directory — never touches the
    # real data/raw or data/processed folders, so this is safe to run anytime
    # regardless of what real data you currently have generated.
    with tempfile.TemporaryDirectory(prefix="sih26028_smoketest_") as tmpdir:
        tmp = Path(tmpdir)
        raw_dir = tmp / "raw"
        processed_dir = tmp / "processed"
        processed_dir.mkdir(parents=True)

        write_fixture(raw_dir)

        # --- Stage 1: parse_reference_data.py ---
        result = run(["scripts/data/parse_reference_data.py",
                      "--raw-dir", str(raw_dir), "--out-dir", str(processed_dir)])
        check("parse_reference_data.py exits successfully", result.returncode == 0, result.stderr[-500:])

        stations_path = processed_dir / "stations.csv"
        routes_path = processed_dir / "routes.csv"
        route_stations_path = processed_dir / "route_stations.csv"
        check("stations.csv was created", stations_path.exists())
        check("routes.csv was created", routes_path.exists())
        check("route_stations.csv was created", route_stations_path.exists())

        if route_stations_path.exists():
            rs = pd.read_csv(route_stations_path)
            check("route_stations.csv has exactly 3 stops for our 3-stop fixture train",
                  len(rs) == 3, f"got {len(rs)} rows")
            check("route_stations.csv sequence is 1,2,3 in order",
                  list(rs.sort_values("sequence")["sequence"]) == [1, 2, 3])

            # IMPORTANT: read the raw text here, not via pd.read_csv. pandas' default
            # read_csv treats the literal string "None" as a missing value and silently
            # converts it to NaN — which would mask exactly the bug this check exists to
            # catch (the parser writing literal text "None" instead of a real blank).
            raw_csv_text = route_stations_path.read_text()
            check("'None' string values were converted to actual blanks, not left as literal text 'None' in the CSV",
                  ",None," not in raw_csv_text,
                  "found literal 'None' text in the CSV — check_one_train.py/read_csv would silently hide this")

        # --- Stage 2: generate_synthetic_events.py ---
        synthetic_path = processed_dir / "synthetic_status_log.csv"
        result = run(["scripts/data/generate_synthetic_events.py",
                      "--num-journeys", "1", "--seed", "1",
                      "--routes-dir", str(processed_dir), "--out", str(synthetic_path)])
        check("generate_synthetic_events.py exits successfully", result.returncode == 0, result.stderr[-500:])
        check("synthetic_status_log.csv was created", synthetic_path.exists())

        if synthetic_path.exists():
            events = pd.read_csv(synthetic_path)
            check("synthetic events cover all 3 stops", len(events) == 3, f"got {len(events)} rows")
            check("delay_minutes is never negative", (events["delay_minutes"] >= 0).all())
            events_sorted = events.sort_values("event_time")
            check("event_time strictly increases across the journey (day rollover handled correctly)",
                  events_sorted["event_time"].is_monotonic_increasing)

        # --- Stage 3: build_section_observations.py ---
        section_obs_path = processed_dir / "section_observations_test.csv"
        result = run(["scripts/data/build_section_observations.py",
                      "--input", str(synthetic_path), "--out", str(section_obs_path)])
        check("build_section_observations.py exits successfully", result.returncode == 0, result.stderr[-500:])
        check("section_observations_test.csv was created", section_obs_path.exists())

        if section_obs_path.exists():
            sections = pd.read_csv(section_obs_path)
            check("exactly 2 sections derived from 3 stops (NDLS->KOTA, KOTA->BCT)",
                  len(sections) == 2, f"got {len(sections)} rows")
            check("actual_minutes is always positive", (sections["actual_minutes"] > 0).all())

        # tmpdir is cleaned up automatically on exit from the `with` block —
        # ignore_errors isn't even needed since OS temp dirs aren't subject to
        # the OneDrive-sync-lock problem that caused the original crash

    print()
    if FAILURES:
        print(f"{len(FAILURES)} CHECK(S) FAILED: {FAILURES}")
        sys.exit(1)
    else:
        print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
