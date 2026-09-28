"""
Canonical data model — mirrors Section 10.2 of the Team Mango architecture doc.
"""

from dataclasses import dataclass, field, fields, asdict
from typing import Optional, List, Dict, Any


@dataclass
class Station:
    station_code: str
    station_name: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    zone: Optional[str] = None
    state: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Route:
    route_id: str
    train_number: str
    train_name: str
    source_station_code: str
    destination_station_code: str
    distance_km: Optional[float] = None
    train_type: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RouteStation:
    route_id: str
    sequence: int
    station_code: str
    scheduled_arrival: Optional[str] = None
    scheduled_departure: Optional[str] = None
    distance_from_origin_km: Optional[float] = None
    stop_flag: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TrainStateEvent:
    """One immutable observation from a live-status provider (Section 10.2)."""
    train_number: str
    journey_date: str
    event_time: str
    received_at: str
    last_station_code: Optional[str]
    next_station_code: Optional[str]
    delay_minutes: Optional[int]
    source: str
    source_event_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SectionObservation:
    """Training-ready row: what actually happened on one section of one journey."""
    journey_id: str
    from_station_code: str
    to_station_code: str
    scheduled_minutes: Optional[float]
    actual_minutes: Optional[float]
    day_of_week: int
    hour_bucket: int
    source_event_ids: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TrainJourney:
    train_number: str
    journey_date: str
    route_id: str
    train_name: str
    train_type: Optional[str]
    events: List[TrainStateEvent] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "train_number": self.train_number,
            "journey_date": self.journey_date,
            "route_id": self.route_id,
            "train_name": self.train_name,
            "train_type": self.train_type,
            "events": [e.to_dict() for e in self.events],
        }


@dataclass
class TrainState:
    """Current live operational snapshot of a train journey."""
    train_number: str
    journey_date: str
    last_station_code: Optional[str]
    next_station_code: Optional[str]
    current_delay_minutes: int
    status: str
    last_updated: str
    as_of: Optional[str] = None
    progress_percentage: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StationETA:
    """Quantile ETA forecast for a single station along the route."""
    sequence: int
    station_code: str
    station_name: str
    scheduled_arrival: Optional[str]
    scheduled_departure: Optional[str]
    predicted_delay_p10: float
    predicted_delay_p50: float
    predicted_delay_p90: float
    estimated_arrival_p10: Optional[str]
    estimated_arrival_p50: Optional[str]
    estimated_arrival_p90: Optional[str]
    status: str
    distance_km: Optional[float] = None
    shap_explanations: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PredictionSnapshot:
    """Full journey dynamic ETA forecast snapshot."""
    train_number: str
    train_name: str
    train_type: Optional[str]
    journey_date: str
    as_of: str
    current_station_code: Optional[str]
    current_delay_minutes: int
    forecasts: List[StationETA]
    model_version: str
    generated_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "train_number": self.train_number,
            "train_name": self.train_name,
            "train_type": self.train_type,
            "journey_date": self.journey_date,
            "as_of": self.as_of,
            "current_station_code": self.current_station_code,
            "current_delay_minutes": self.current_delay_minutes,
            "forecasts": [f.to_dict() for f in self.forecasts],
            "model_version": self.model_version,
            "generated_at": self.generated_at,
        }


@dataclass
class SourceHealth:
    provider: str
    status: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def csv_columns(dataclass_type) -> list[str]:
    return [f.name for f in fields(dataclass_type)]
