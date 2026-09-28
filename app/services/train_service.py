"""
Train Service — route, station, and schedule lookups (with NaN sanitization for JSON).
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np
import pandas as pd

from app.config import PROCESSED_DATA_DIR


def sanitize_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    cleaned = {}
    for k, v in d.items():
        if pd.isna(v) or (isinstance(v, float) and np.isnan(v)):
            cleaned[k] = None
        else:
            cleaned[k] = v
    return cleaned


def sanitize_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [sanitize_dict(r) for r in records]


class TrainService:
    def __init__(self, data_dir: Path = PROCESSED_DATA_DIR):
        self.data_dir = Path(data_dir)
        self._stations = pd.read_csv(self.data_dir / "stations.csv")
        self._routes = pd.read_csv(self.data_dir / "routes.csv")
        self._route_stations = pd.read_csv(self.data_dir / "route_stations.csv")

        # Keep plausible routes
        stop_counts = self._route_stations.groupby("route_id").size()
        self._plausible_route_ids = set(
            stop_counts[(stop_counts >= 2) & (stop_counts <= 40)].index
        )
        self._plausible_routes = self._routes[self._routes["route_id"].isin(self._plausible_route_ids)]

    def search_trains(self, query: str = "", limit: int = 20) -> List[Dict[str, Any]]:
        if not query:
            records = self._plausible_routes.head(limit).to_dict(orient="records")
            return sanitize_records(records)

        q = query.strip().lower()
        mask = (
            self._plausible_routes["train_number"].astype(str).str.lower().str.contains(q)
            | self._plausible_routes["train_name"].astype(str).str.lower().str.contains(q)
            | self._plausible_routes["source_station_code"].astype(str).str.lower().str.contains(q)
            | self._plausible_routes["destination_station_code"].astype(str).str.lower().str.contains(q)
        )
        records = self._plausible_routes[mask].head(limit).to_dict(orient="records")
        return sanitize_records(records)

    def get_train(self, train_number: str) -> Optional[Dict[str, Any]]:
        matches = self._plausible_routes[self._plausible_routes["train_number"].astype(str) == str(train_number)]
        if matches.empty:
            return None
        return sanitize_dict(matches.iloc[0].to_dict())

    def get_route_stations(self, train_number: str) -> List[Dict[str, Any]]:
        matches = self._plausible_routes[self._plausible_routes["train_number"].astype(str) == str(train_number)]
        if matches.empty:
            return []
        route_id = matches.iloc[0]["route_id"]

        stops = self._route_stations[self._route_stations["route_id"] == route_id].sort_values("sequence")
        merged = stops.merge(self._stations, on="station_code", how="left")
        records = merged.to_dict(orient="records")
        return sanitize_records(records)

    def get_station_lookup(self) -> Dict[str, Dict[str, Any]]:
        return self._stations.set_index("station_code").to_dict(orient="index")


train_service = TrainService()
