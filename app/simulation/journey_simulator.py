"""
Walks ONE train's real route (from route_stations.csv, joined with stations.csv
for zone info) section by section, calling delay_model + calendar_context at
each step, and produces the resulting sequence of TrainStateEvent.

WHY THIS IS SEPARATE FROM delay_model.py: this file only knows about
"walking a route and accumulating state." It has zero domain logic about
WHY delay happens — that all lives in delay_model.py. This separation is
what makes multi-train interaction (planned for later) a clean addition:
when trains need to affect each other's congestion, that logic extends
THIS file's orchestration, while delay_model.py's individual functions
stay untouched.

Also deliberately separate from the CLI (generate_synthetic_events.py),
so this same simulate_journey() function can later be called from
somewhere other than a batch script — e.g. a live "digital twin" demo mode,
or directly from tests, without needing a subprocess.
"""

import random
from dataclasses import dataclass
from datetime import datetime, timedelta, date
from typing import Optional

import pandas as pd

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.schemas.canonical import TrainStateEvent  # noqa: E402
from app.simulation import calendar_context as cal  # noqa: E402
from app.simulation import delay_model as dm  # noqa: E402


def _parse_time_str(t, base_date: date, day_offset: int = 0) -> Optional[datetime]:
    if pd.isna(t) or t in (None, "", "None"):
        return None
    h, m, s = [int(x) for x in str(t).split(":")]
    return datetime.combine(base_date, datetime.min.time()) + timedelta(
        days=day_offset, hours=h, minutes=m, seconds=s
    )


def _estimate_geographic_minimum(distance_km: Optional[float], train_type: str) -> Optional[float]:
    """
    Proxy for "fastest plausible running time" for a section, used to estimate
    how much schedule padding exists (see delay_model.recovery_margin).

    Uses delay_model.TYPICAL_AVERAGE_SPEED_KMH — real, officially-cited average
    speeds by train class (Ministry of Railways Rajya Sabha replies), rather
    than one flat speed for every train regardless of class. This directly
    affects which sections get credited with "padding" a train could recover
    time from: e.g. a Passenger train's genuinely-achievable pace (35 km/h) is
    much lower than a Rajdhani's (78 km/h), so the SAME scheduled time on the
    same section implies very different amounts of real slack for each.

    Still a national-average simplification (doesn't vary by section terrain/
    track type), not a real engineering calculation — refine if real
    per-section speed data ever becomes available.
    """
    if not distance_km or distance_km <= 0:
        return None
    speed = dm.typical_average_speed_kmh(train_type)
    return (distance_km / speed) * 60.0  # minutes


def simulate_journey(route_id: str, train_number: str, train_type: str,
                      stops: pd.DataFrame, stations_lookup: pd.DataFrame,
                      journey_date: date, rng: random.Random,
                      previous_service_delay: float = 0.0) -> list:
    """
    stops: route_stations.csv rows for this route_id, any order (will be sorted
           by 'sequence' here).
    stations_lookup: stations.csv, used to look up each stop's zone for
           calendar_context.
    previous_service_delay: this same train's final delay on its most recent
           prior service, for rake-cascading (see delay_model.origin_delay).
           Pass 0.0 if unknown or not applicable — this parameter is what lets
           a CALLER (e.g. ReplayProvider) decide how far to look back, without
           this function itself needing to know about dates/lookups/recursion.
    Returns: list[TrainStateEvent], one per stop, with realistic evolving delay.
    """
    stops = stops.sort_values("sequence").reset_index(drop=True)
    zone_by_code = stations_lookup.set_index("station_code")["zone"].to_dict()

    events = []
    cumulative_delay = dm.origin_delay(train_type, rng, previous_service_delay)
    day_counter = 0
    prev_sched_time = None
    prev_distance = None

    for i, row in stops.iterrows():
        sched_time_raw = row["scheduled_arrival"] if pd.notna(row["scheduled_arrival"]) else row["scheduled_departure"]
        sched_dt = _parse_time_str(sched_time_raw, journey_date, day_counter)
        if sched_dt is None:
            continue

        if prev_sched_time is not None and sched_dt < prev_sched_time:
            day_counter += 1
            sched_dt = _parse_time_str(sched_time_raw, journey_date, day_counter)
        prev_sched_time = sched_dt

        zone = zone_by_code.get(row["station_code"], "")
        ctx = cal.get_operating_context(zone, sched_dt)

        if i == 0:
            # origin delay already set before the loop; no section to traverse yet
            pass
        else:
            distance = row.get("distance_from_origin_km")
            section_km = None
            if pd.notna(distance) and prev_distance is not None and pd.notna(prev_distance):
                section_km = distance - prev_distance

            running_noise = dm.running_time_noise(section_km, train_type, rng)
            congestion = dm.congestion_event(ctx.is_high_traffic_zone, ctx.is_peak_hour, train_type, rng)
            weather = dm.weather_event(ctx.is_fog_season, ctx.is_monsoon_season, ctx.hour, rng)
            disruption = dm.disruption_jump(rng)

            geo_min = _estimate_geographic_minimum(section_km, train_type)
            sched_minutes = None
            if prev_sched_time is not None:
                sched_minutes = (sched_dt - prev_sched_time).total_seconds() / 60.0
            recovery = dm.recovery_margin(sched_minutes, geo_min, cumulative_delay, rng)

            component_total = running_noise + congestion + weather + disruption - recovery
            cumulative_delay = dm.apply_autocorrelation(cumulative_delay, component_total)

        prev_distance = row.get("distance_from_origin_km")
        actual_dt = sched_dt + timedelta(minutes=cumulative_delay)
        next_station = stops.iloc[i + 1]["station_code"] if i + 1 < len(stops) else None

        events.append(
            TrainStateEvent(
                train_number=train_number,
                journey_date=journey_date.strftime("%d-%m-%Y"),
                event_time=actual_dt.isoformat(),
                received_at=actual_dt.isoformat(),
                last_station_code=row["station_code"],
                next_station_code=next_station,
                delay_minutes=round(cumulative_delay, 1),
                source="synthetic",
                source_event_id=f"{route_id}_{i}",
            )
        )

    return events
