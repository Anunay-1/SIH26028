"""
Feature engineering for LightGBM dynamic quantile ETA prediction (Section 12.2).
"""

from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
import pandas as pd

from app.simulation.calendar_context import get_operating_context
from app.simulation.delay_model import priority_multiplier, typical_average_speed_kmh

FEATURE_COLUMNS = [
    "current_delay",
    "distance_to_station",
    "scheduled_section_minutes",
    "accumulated_distance",
    "stop_sequence",
    "is_fog_season",
    "is_monsoon_season",
    "is_peak_hour",
    "is_high_traffic_zone",
    "priority_multiplier",
    "speed_kmh",
    "day_of_week",
    "hour_of_day",
    # --- Derived Section A Features ---
    "delay_momentum",
    "timetable_slack_density",
    "station_centrality",
    "section_pace_gap",
]

_CENTRALITY_CACHE: Optional[Dict[str, int]] = None


def get_station_centrality(station_code: str) -> int:
    """Returns number of unique routes passing through this station (junction complexity)."""
    global _CENTRALITY_CACHE
    if _CENTRALITY_CACHE is None:
        try:
            rs_path = Path(__file__).resolve().parents[2] / "data" / "processed" / "route_stations.csv"
            if rs_path.exists():
                df = pd.read_csv(rs_path, usecols=["station_code"])
                _CENTRALITY_CACHE = df["station_code"].value_counts().to_dict()
            else:
                _CENTRALITY_CACHE = {}
        except Exception:
            _CENTRALITY_CACHE = {}
    return _CENTRALITY_CACHE.get(str(station_code).strip().upper(), 10)


def extract_features(
    current_delay_minutes: float,
    train_type: str,
    when: datetime,
    zone: str,
    stop_sequence: int,
    distance_to_station: float,
    scheduled_section_minutes: float,
    accumulated_distance: float,
    delay_momentum: float = 0.0,
    station_centrality: int = 10,
) -> Dict[str, Any]:
    """
    Extract a single feature vector for a target station prediction including derived Section A features.
    """
    ctx = get_operating_context(zone, when)
    pm = priority_multiplier(train_type)
    speed = typical_average_speed_kmh(train_type)

    dist = max(0.0, float(distance_to_station))
    sched_min = max(0.1, float(scheduled_section_minutes))
    geo_min = (dist / max(1.0, speed)) * 60.0
    slack = max(0.0, sched_min - geo_min)
    slack_density = slack / (dist + 1.0)
    sched_speed = dist / (sched_min / 60.0)
    pace_gap = speed - sched_speed

    return {
        "current_delay": float(current_delay_minutes),
        "distance_to_station": dist,
        "scheduled_section_minutes": sched_min,
        "accumulated_distance": float(accumulated_distance),
        "stop_sequence": int(stop_sequence),
        "is_fog_season": int(ctx.is_fog_season),
        "is_monsoon_season": int(ctx.is_monsoon_season),
        "is_peak_hour": int(ctx.is_peak_hour),
        "is_high_traffic_zone": int(ctx.is_high_traffic_zone),
        "priority_multiplier": float(pm),
        "speed_kmh": float(speed),
        "day_of_week": int(when.weekday()),
        "hour_of_day": int(when.hour),
        "delay_momentum": float(delay_momentum),
        "timetable_slack_density": round(float(slack_density), 4),
        "station_centrality": int(station_centrality),
        "section_pace_gap": round(float(pace_gap), 2),
    }


def to_dataframe(feature_dicts: List[Dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(feature_dicts)
    for col in FEATURE_COLUMNS:
        if col not in df.columns:
            df[col] = 0
    return df[FEATURE_COLUMNS]
