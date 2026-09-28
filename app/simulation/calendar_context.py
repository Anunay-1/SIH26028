"""
Shared contextual lookups: zone, date/time operating context.
"""

from dataclasses import dataclass
from datetime import date
from typing import Any
import pandas as pd

FOG_PRONE_ZONES = {"NR", "NCR", "NWR", "WCR", "NER", "NFR"}
FOG_SEASON_MONTHS = {11, 12, 1, 2}  # Nov, Dec, Jan, Feb

MONSOON_PRONE_ZONES = {"WR", "CR", "SR", "SER", "SECR", "ECoR", "KR"}
MONSOON_MONTHS = {6, 7, 8, 9}

HIGH_TRAFFIC_ZONES = {"NR", "NCR", "CR", "WR", "ER", "SER"}
PEAK_HOUR_WINDOWS = [(6, 10), (17, 21)]

TRAFFIC_TIERS = {
    "HIGH": HIGH_TRAFFIC_ZONES,
    "FOG_PRONE": FOG_PRONE_ZONES,
    "MONSOON_PRONE": MONSOON_PRONE_ZONES,
}


@dataclass(frozen=True)
class OperatingContext:
    is_fog_season: bool
    is_monsoon_season: bool
    is_peak_hour: bool
    is_high_traffic_zone: bool
    month: int
    hour: int


def is_fog_season(zone: Any, when: Any) -> bool:
    if pd.isna(zone) or zone is None:
        z = ""
    else:
        z = str(zone).strip().upper()
    m = when.month
    return (z in FOG_PRONE_ZONES) and (m in FOG_SEASON_MONTHS)


def is_monsoon_season(zone: Any, when: Any) -> bool:
    if pd.isna(zone) or zone is None:
        z = ""
    else:
        z = str(zone).strip().upper()
    m = when.month
    return (z in MONSOON_PRONE_ZONES) and (m in MONSOON_MONTHS)


def is_peak_hour(when: Any) -> bool:
    h = getattr(when, "hour", 12)
    return any(start <= h < end for start, end in PEAK_HOUR_WINDOWS)


def get_operating_context(zone: Any, when: Any) -> OperatingContext:
    if pd.isna(zone) or zone is None:
        z = ""
    else:
        z = str(zone).strip().upper()
    m = when.month
    h = getattr(when, "hour", 12)

    is_peak = any(start <= h < end for start, end in PEAK_HOUR_WINDOWS)

    return OperatingContext(
        is_fog_season=(z in FOG_PRONE_ZONES) and (m in FOG_SEASON_MONTHS),
        is_monsoon_season=(z in MONSOON_PRONE_ZONES) and (m in MONSOON_MONTHS),
        is_peak_hour=is_peak,
        is_high_traffic_zone=z in HIGH_TRAFFIC_ZONES,
        month=m,
        hour=h,
    )
