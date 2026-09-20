"""
Canonical data model — mirrors Section 10.2 of the Team Mango architecture doc.

These dataclasses are the single source of truth for field names across:
  - the CSVs written/read during this data-only phase
  - the future PostgreSQL tables (Section 10.3)
  - the API response schemas (Section 14)

Keeping one definition here means a CSV column rename and a future DB column
rename are the same edit, not two places that can drift apart.
"""

from dataclasses import dataclass, field, fields
from typing import Optional


@dataclass
class Station:
    station_code: str
    station_name: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    zone: Optional[str] = None
    state: Optional[str] = None


@dataclass
class Route:
    route_id: str          # derived, e.g. f"{train_number}_{direction}"
    train_number: str
    train_name: str
    source_station_code: str
    destination_station_code: str
    distance_km: Optional[float] = None
    train_type: Optional[str] = None


@dataclass
class RouteStation:
    route_id: str
    sequence: int
    station_code: str
    scheduled_arrival: Optional[str] = None   # "HH:MM:SS" or None for origin
    scheduled_departure: Optional[str] = None  # "HH:MM:SS" or None for terminus
    distance_from_origin_km: Optional[float] = None
    stop_flag: bool = True


@dataclass
class TrainStateEvent:
    """One immutable observation from a live-status provider (Section 10.2)."""
    train_number: str
    journey_date: str          # "YYYY-MM-DD"
    event_time: str            # observed_at, ISO 8601
    received_at: str           # when WE received it, ISO 8601
    last_station_code: Optional[str]
    next_station_code: Optional[str]
    delay_minutes: Optional[int]
    source: str                # e.g. "pyinrail", "replay"
    source_event_id: Optional[str] = None


@dataclass
class SectionObservation:
    """Training-ready row: what actually happened on one section of one journey."""
    journey_id: str            # f"{train_number}_{journey_date}"
    from_station_code: str
    to_station_code: str
    scheduled_minutes: Optional[float]
    actual_minutes: Optional[float]
    day_of_week: int           # 0=Monday
    hour_bucket: int           # hour of day the section started, 0-23
    source_event_ids: str      # comma-joined ids of the two events this was derived from


def csv_columns(dataclass_type) -> list[str]:
    """Convenience: consistent column order for writing CSVs from these types."""
    return [f.name for f in fields(dataclass_type)]
