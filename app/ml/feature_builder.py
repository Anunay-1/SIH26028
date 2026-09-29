"""
Feature engineering for LightGBM dynamic quantile ETA prediction (Section 12.2).
"""

from datetime import datetime
from typing import Dict, Any, List
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
]


def extract_features(
    current_delay_minutes: float,
    train_type: str,
    when: datetime,
    zone: str,
    stop_sequence: int,
    distance_to_station: float,
    scheduled_section_minutes: float,
    accumulated_distance: float,
) -> Dict[str, Any]:
    """
    Extract a single feature vector for a target station prediction.
    """
    ctx = get_operating_context(zone, when)
    pm = priority_multiplier(train_type)
    speed = typical_average_speed_kmh(train_type)

    return {
        "current_delay": float(current_delay_minutes),
        "distance_to_station": float(distance_to_station),
        "scheduled_section_minutes": float(scheduled_section_minutes),
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
    }


def to_dataframe(feature_dicts: List[Dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(feature_dicts)
    for col in FEATURE_COLUMNS:
        if col not in df.columns:
            df[col] = 0
    return df[FEATURE_COLUMNS]
