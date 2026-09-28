"""
Shared contextual lookups: given a station's zone and a specific date/time,
what's the real-world operating context? (fog season, peak traffic hours,
monsoon season, how busy is this zone generally.)

WHY THIS IS ITS OWN MODULE: both the synthetic delay simulator AND the
eventual ML feature engineering (Phase D) need to answer "is this a
high-fog-risk moment" or "is this peak hour" — using the SAME logic. If the
simulator's notion of "fog season" drifted from the feature engineering's
notion of "fog season," the model would be learning from data whose labels
don't match its own inference-time features. This file is the one place
that logic lives.

HONESTY ABOUT THESE ASSUMPTIONS: the zone tiers and fog-season windows below
are informed by well-documented, widely-reported patterns (North India's
winter fog disruption affecting NR/NCR/NWR/WCR every Nov-Feb; monsoon
flooding affecting coastal/eastern zones June-Sept; trunk routes being
busier than branch lines) but are NOT fitted to real measured data, because
we don't have real measured data yet. Treat every constant here as a
documented, defensible starting assumption for a simulation, not a
statistically fitted parameter. If real data becomes available, THIS is the
file to recalibrate.
"""

from dataclasses import dataclass
from datetime import date


# Zones where dense winter fog is a well-documented, major disruptor
# (Northern/North-Central/North-Western/West-Central India, roughly the
# Indo-Gangetic plain corridor). Source of the pattern: widely reported every
# winter (train delays of many hours during Dec-Jan fog are routine news).
FOG_PRONE_ZONES = {"NR", "NCR", "NWR", "WCR", "NER", "NFR"}
FOG_SEASON_MONTHS = {11, 12, 1, 2}  # Nov, Dec, Jan, Feb

# Zones more exposed to monsoon-related disruption (flooding, waterlogging).
# This is a broader, gentler effect than fog — less catastrophic per-event,
# but affects more of the network.
MONSOON_PRONE_ZONES = {"WR", "CR", "SR", "SER", "SECR", "ECoR", "KR"}
MONSOON_MONTHS = {6, 7, 8, 9}

# Rough trunk-route congestion tiers. Zones carrying the heaviest
# long-distance trunk traffic (Delhi-Mumbai, Delhi-Howrah, Delhi-Chennai
# corridors) get a higher baseline congestion probability than branch-line
# zones. This is a simplifying proxy for real traffic-density data, which
# we don't have — documented here so it's an explicit, adjustable constant.
HIGH_TRAFFIC_ZONES = {"NR", "NCR", "CR", "WR", "ER", "SER"}

PEAK_HOUR_WINDOWS = [(6, 10), (17, 21)]  # local 24h clock, (start_inclusive, end_exclusive)


@dataclass(frozen=True)
class OperatingContext:
    is_fog_season: bool
    is_monsoon_season: bool
    is_peak_hour: bool
    is_high_traffic_zone: bool
    month: int
    hour: int


def get_operating_context(zone: str, when: "date_or_datetime") -> OperatingContext:  # noqa: F821
    """
    zone: station zone code (e.g. "NR", "WR") — expects the value as it
          appears in stations.csv's `zone` column.
    when: a date or datetime — only .month, and .hour if present, are used.
    """
    zone = (zone or "").upper()
    month = when.month
    hour = getattr(when, "hour", 12)  # default to midday if only a date was given

    is_peak = any(start <= hour < end for start, end in PEAK_HOUR_WINDOWS)

    return OperatingContext(
        is_fog_season=(zone in FOG_PRONE_ZONES) and (month in FOG_SEASON_MONTHS),
        is_monsoon_season=(zone in MONSOON_PRONE_ZONES) and (month in MONSOON_MONTHS),
        is_peak_hour=is_peak,
        is_high_traffic_zone=zone in HIGH_TRAFFIC_ZONES,
        month=month,
        hour=hour,
    )
