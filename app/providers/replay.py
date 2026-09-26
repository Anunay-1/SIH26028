"""
ReplayProvider — the only currently-working LiveStatusProvider implementation.

DESIGN CHOICE: simulates ON DEMAND rather than only replaying a pre-generated
CSV, using a seed DERIVED from (train_number, journey_date) so the same
query always produces the same answer — call get_journey_events() for the
same train/date twice, get identical events both times. This matters for:
  - reproducibility (architecture doc Section 7: "same input snapshot should
    reproduce same inference")
  - a future backend/demo being able to query ANY train/date and get a
    plausible, consistent answer, not just whatever happened to be in a
    pre-generated batch file

The batch CLI script (generate_synthetic_events.py) still exists separately
for producing a large training dataset in one go — this class is for
serving individual queries the way a real provider eventually would.
"""

import hashlib
import random
from datetime import date, timedelta
from pathlib import Path
from typing import List, Optional

import pandas as pd

from app.providers.base import LiveStatusProvider
from app.schemas.canonical import TrainStateEvent
from app.simulation.journey_simulator import simulate_journey


def _deterministic_seed(train_number: str, journey_date: date) -> int:
    """Same (train_number, journey_date) always maps to the same seed."""
    key = f"{train_number}_{journey_date.isoformat()}"
    return int(hashlib.sha256(key.encode()).hexdigest(), 16) % (2**32)


class ReplayProvider(LiveStatusProvider):
    def __init__(self, data_dir: Path):
        """
        data_dir: folder containing stations.csv, routes.csv, route_stations.csv
        (i.e. data/processed/ in this repo).
        """
        self.data_dir = Path(data_dir)
        self._stations = pd.read_csv(self.data_dir / "stations.csv")
        self._routes = pd.read_csv(self.data_dir / "routes.csv")
        self._route_stations = pd.read_csv(self.data_dir / "route_stations.csv")

        # precompute plausible-route filter once (same corrupted-schedule
        # exclusion used by generate_synthetic_events.py), so a query for a
        # known-corrupted train fails clearly instead of returning garbage
        stop_counts = self._route_stations.groupby("route_id").size()
        self._plausible_route_ids = set(
            stop_counts[(stop_counts >= 2) & (stop_counts <= 40)].index
        )

    def get_journey_events(self, train_number: str, journey_date: date,
                            _allow_lookback: bool = True) -> List[TrainStateEvent]:
        """
        _allow_lookback: internal use only. When True (the normal case), this
        method looks back exactly ONE day to find this train's previous
        service's final delay, for rake-cascading (delay_model.RAKE_CASCADE_RHO).
        That lookback call passes _allow_lookback=False so the recursion is
        capped at depth 1 — we deliberately do NOT chain further back (e.g.
        having yesterday's lookback trigger the day before that, and so on).
        See delay_model.RAKE_CASCADE_RHO's docstring for why one day of memory
        is the documented scope, not an arbitrary implementation shortcut.
        """
        route_rows = self._routes[self._routes["train_number"].astype(str) == str(train_number)]
        if route_rows.empty:
            return []  # unknown train — normal outcome, not an error

        route = route_rows.iloc[0]
        route_id = route["route_id"]

        if route_id not in self._plausible_route_ids:
            return []  # known-corrupted schedule data for this train — see README

        stops = self._route_stations[self._route_stations["route_id"] == route_id]
        if stops.empty:
            return []

        previous_service_delay = 0.0
        if _allow_lookback:
            previous_events = self.get_journey_events(
                train_number, journey_date - timedelta(days=1), _allow_lookback=False
            )
            if previous_events:
                previous_service_delay = previous_events[-1].delay_minutes

        seed = _deterministic_seed(str(train_number), journey_date)
        rng = random.Random(seed)

        return simulate_journey(
            route_id=route_id,
            train_number=str(train_number),
            train_type=route.get("train_type"),
            stops=stops,
            stations_lookup=self._stations,
            journey_date=journey_date,
            rng=rng,
            previous_service_delay=previous_service_delay,
        )

    def health_check(self) -> dict:
        return {
            "provider": "ReplayProvider",
            "status": "ok",
            "known_trains": len(self._routes),
            "usable_routes": len(self._plausible_route_ids),
            "note": "synthetic data — see README.md 'Status as of last session'",
        }
