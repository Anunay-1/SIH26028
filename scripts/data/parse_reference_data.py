"""
Parses the datameet/railways JSON dump into the three master CSVs.

Input (expected at data/raw/datameet_railways/, from:
    git clone https://github.com/datameet/railways.git data/raw/datameet_railways
):
    stations.json  -> GeoJSON FeatureCollection of stations
    trains.json    -> GeoJSON FeatureCollection of trains (LineString per train)
    schedules.json -> flat array, one object per train-stop

Output (data/processed/):
    stations.csv
    routes.csv
    route_stations.csv

Run:
    python scripts/data/parse_reference_data.py
"""

import argparse
import json
import sys
from pathlib import Path
from collections import defaultdict

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RAW_DIR = REPO_ROOT / "data" / "raw" / "datameet_railways"
DEFAULT_OUT_DIR = REPO_ROOT / "data" / "processed"

sys.path.insert(0, str(REPO_ROOT))
from app.schemas.canonical import Station, Route, RouteStation, csv_columns  # noqa: E402


def load_json(path: Path, raw_dir: Path):
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path}. Did you run:\n"
            f"  git clone https://github.com/datameet/railways.git {raw_dir}\n"
            f"first? See README.md."
        )
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_stations(raw: dict) -> pd.DataFrame:
    rows = []
    for feature in raw.get("features", []):
        props = feature.get("properties", {})
        geom = feature.get("geometry", {}) or {}
        coords = geom.get("coordinates", [None, None])
        lon, lat = (coords + [None, None])[:2]
        rows.append(
            Station(
                station_code=props.get("code"),
                station_name=props.get("name"),
                latitude=lat,
                longitude=lon,
                zone=props.get("zone"),
                state=props.get("state"),
            ).__dict__
        )
    df = pd.DataFrame(rows, columns=csv_columns(Station))
    before = len(df)
    df = df.dropna(subset=["station_code"]).drop_duplicates(subset=["station_code"])
    if len(df) != before:
        print(f"[stations] dropped {before - len(df)} rows with no/duplicate station_code")
    return df


def parse_trains(raw: dict) -> pd.DataFrame:
    rows = []
    for feature in raw.get("features", []):
        props = feature.get("properties", {})
        train_number = props.get("number")
        if not train_number:
            continue
        route_id = f"{train_number}_{props.get('from_station_code')}_{props.get('to_station_code')}"
        rows.append(
            Route(
                route_id=route_id,
                train_number=train_number,
                train_name=props.get("name"),
                source_station_code=props.get("from_station_code"),
                destination_station_code=props.get("to_station_code"),
                distance_km=props.get("distance"),
                train_type=props.get("type"),
            ).__dict__
        )
    df = pd.DataFrame(rows, columns=csv_columns(Route))
    before = len(df)
    df = df.drop_duplicates(subset=["route_id"])
    if len(df) != before:
        print(f"[routes] dropped {before - len(df)} duplicate route_id rows")
    return df


def parse_schedules(raw: list, routes_df: pd.DataFrame) -> pd.DataFrame:
    """
    schedules.json has one row per (train, station) stop but no explicit
    route_id and no explicit sequence number — we derive sequence from the
    'day' field plus stop order as it appears in the source array, since
    that reflects the order the stops were recorded in.

    NOTE: verify this ordering assumption against a couple of known routes
    once you have the real file open — 'day' alone is not always a reliable
    sort key for multi-day trains with same-day repeats. Flag this for
    Phase A step 5 ("build a small verified dataset") rather than trusting
    it blindly.
    """
    train_to_route = {}
    for _, r in routes_df.iterrows():
        train_to_route.setdefault(str(r["train_number"]), r["route_id"])

    grouped = defaultdict(list)
    for stop in raw:
        train_number = str(stop.get("train_number"))
        grouped[train_number].append(stop)

    rows = []
    skipped_no_route = 0
    for train_number, stops in grouped.items():
        route_id = train_to_route.get(train_number)
        if route_id is None:
            skipped_no_route += 1
            continue
        # preserve source order as the sequence proxy — see note above
        for seq, stop in enumerate(stops, start=1):
            arrival = stop.get("arrival")
            departure = stop.get("departure")
            rows.append(
                RouteStation(
                    route_id=route_id,
                    sequence=seq,
                    station_code=stop.get("station_code"),
                    scheduled_arrival=None if arrival in (None, "None") else arrival,
                    scheduled_departure=None if departure in (None, "None") else departure,
                    distance_from_origin_km=None,
                    stop_flag=True,
                ).__dict__
            )
    if skipped_no_route:
        print(f"[route_stations] skipped {skipped_no_route} trains with no matching route_id "
              f"(present in schedules.json but not in trains.json)")
    return pd.DataFrame(rows, columns=csv_columns(RouteStation))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", default=str(DEFAULT_RAW_DIR),
                         help="folder containing stations.json/trains.json/schedules.json")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR),
                         help="folder to write stations.csv/routes.csv/route_stations.csv into")
    args = parser.parse_args()

    raw_dir = Path(args.raw_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    stations_raw = load_json(raw_dir / "stations.json", raw_dir)
    trains_raw = load_json(raw_dir / "trains.json", raw_dir)
    schedules_raw = load_json(raw_dir / "schedules.json", raw_dir)

    stations_df = parse_stations(stations_raw)
    routes_df = parse_trains(trains_raw)
    route_stations_df = parse_schedules(schedules_raw, routes_df)

    stations_df.to_csv(out_dir / "stations.csv", index=False)
    routes_df.to_csv(out_dir / "routes.csv", index=False)
    route_stations_df.to_csv(out_dir / "route_stations.csv", index=False)

    print(f"stations.csv        -> {len(stations_df)} rows")
    print(f"routes.csv          -> {len(routes_df)} rows")
    print(f"route_stations.csv  -> {len(route_stations_df)} rows")


if __name__ == "__main__":
    main()
