"""
ReplayProvider — deterministic simulation-backed LiveStatusProvider.
"""

import hashlib
import random
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Optional

import pandas as pd

from app.providers.base import LiveStatusProvider
from app.schemas.canonical import TrainStateEvent, TrainState
from app.simulation.journey_simulator import simulate_journey


def _deterministic_seed(train_number: str, journey_date: date) -> int:
    """Same (train_number, journey_date) always maps to the same seed."""
    key = f"{train_number}_{journey_date.isoformat()}"
    return int(hashlib.sha256(key.encode()).hexdigest(), 16) % (2**32)


class ReplayProvider(LiveStatusProvider):
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self._stations = pd.read_csv(self.data_dir / "stations.csv")
        self._routes = pd.read_csv(self.data_dir / "routes.csv")
        self._route_stations = pd.read_csv(self.data_dir / "route_stations.csv")

        # Keep plausible routes (2 to 40 stops)
        stop_counts = self._route_stations.groupby("route_id").size()
        self._plausible_route_ids = set(
            stop_counts[(stop_counts >= 2) & (stop_counts <= 40)].index
        )

    def get_journey_events(
        self,
        train_number: str,
        journey_date: date,
        as_of: Optional[str] = None,
        _allow_lookback: bool = True,
    ) -> List[TrainStateEvent]:
        route_rows = self._routes[self._routes["train_number"].astype(str) == str(train_number)]
        if route_rows.empty:
            return []

        route = route_rows.iloc[0]
        route_id = route["route_id"]

        if route_id not in self._plausible_route_ids:
            return []

        stops = self._route_stations[self._route_stations["route_id"] == route_id]
        if stops.empty:
            return []

        previous_service_delay = 0.0
        if _allow_lookback:
            previous_events = self.get_journey_events(
                train_number, journey_date - timedelta(days=1), _allow_lookback=False
            )
            if previous_events:
                previous_service_delay = float(previous_events[-1].delay_minutes or 0)

        seed = _deterministic_seed(str(train_number), journey_date)
        rng = random.Random(seed)

        all_events = simulate_journey(
            route_id=route_id,
            train_number=str(train_number),
            train_type=route.get("train_type"),
            stops=stops,
            stations_lookup=self._stations,
            journey_date=journey_date,
            rng=rng,
            previous_service_delay=previous_service_delay,
        )

        if not as_of:
            return all_events

        # Strict cutoff filtering for as_of to prevent time-travel leakage
        as_of_dt = datetime.fromisoformat(as_of.replace("Z", "+00:00")).replace(tzinfo=None)
        filtered = []
        for e in all_events:
            ev_dt = datetime.fromisoformat(e.event_time.replace("Z", "+00:00")).replace(tzinfo=None)
            if ev_dt <= as_of_dt:
                filtered.append(e)

        return filtered

    def get_current_state(
        self,
        train_number: str,
        journey_date: date,
        as_of: Optional[str] = None,
    ) -> Optional[TrainState]:
        route_rows = self._routes[self._routes["train_number"].astype(str) == str(train_number)]
        if route_rows.empty:
            return None

        route = route_rows.iloc[0]
        route_id = route["route_id"]
        stops = self._route_stations[self._route_stations["route_id"] == route_id].sort_values("sequence")
        total_stops = len(stops)

        events = self.get_journey_events(train_number, journey_date, as_of=as_of)
        
        if not events:
            first_stop = stops.iloc[0]["station_code"]
            return TrainState(
                train_number=str(train_number),
                journey_date=journey_date.isoformat(),
                last_station_code=None,
                next_station_code=first_stop,
                current_delay_minutes=0,
                status="SCHEDULED",
                last_updated=datetime.now().isoformat(),
                as_of=as_of,
                progress_percentage=0.0,
            )

        last_ev = events[-1]
        passed_stations = {e.last_station_code for e in events if e.last_station_code}
        progress = min(100.0, round((len(passed_stations) / max(1, total_stops)) * 100, 1))

        status = "IN_TRANSIT"
        if len(passed_stations) >= total_stops or last_ev.next_station_code is None:
            status = "COMPLETED"

        return TrainState(
            train_number=str(train_number),
            journey_date=journey_date.isoformat(),
            last_station_code=last_ev.last_station_code,
            next_station_code=last_ev.next_station_code,
            current_delay_minutes=int(last_ev.delay_minutes or 0),
            status=status,
            last_updated=last_ev.event_time,
            as_of=as_of,
            progress_percentage=progress,
        )

    def health_check(self) -> dict:
        return {
            "provider": "ReplayProvider",
            "status": "ok",
            "known_trains": int(len(self._routes)),
            "usable_routes": int(len(self._plausible_route_ids)),
            "note": "synthetic data — evaluated with chronological split and anchored to published IR stats",
        }
