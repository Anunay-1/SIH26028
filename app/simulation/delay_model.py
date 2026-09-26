"""
The mathematical model of WHY a train is delayed, broken into independent,
individually-testable components that mirror real-world causes. See
README.md's "Synthetic Data Methodology" section for the full writeup of
these assumptions (worth quoting directly if asked to justify the model
during judging).

Each function below models exactly ONE real-world cause. journey_simulator.py
composes them together while walking a route. Keeping them separate means:
  - each is unit-testable in isolation (e.g. "is congestion probability
    actually higher at peak hours")
  - any one can be recalibrated later against real data without touching
    the others
  - it's easy to explain to a judge which function represents which
    real-world phenomenon

TRAIN PRIORITY TIERS: higher-priority trains (Rajdhani/Shatabdi/Duronto) get
operational precedence in real operations, so they should show LESS
congestion-driven delay and tighter running-time variance than ordinary
Mail/Express/Passenger trains. `priority_multiplier` below encodes this.
"""

import math
import random
from dataclasses import dataclass


# Lower multiplier = less exposed to delay-inducing events. Values are
# documented assumptions (premium trains get real operational precedence in
# India), not fitted data.
PRIORITY_MULTIPLIERS = {
    "Rajdhani": 0.4,
    "Shatabdi": 0.4,
    "Duronto": 0.5,
    "Superfast": 0.7,
    "Mail": 1.0,
    "Express": 1.0,
    "Passenger": 1.3,  # ordinary passenger trains get the least precedence
}
DEFAULT_PRIORITY_MULTIPLIER = 1.0


def priority_multiplier(train_type: str) -> float:
    return PRIORITY_MULTIPLIERS.get((train_type or "").strip(), DEFAULT_PRIORITY_MULTIPLIER)


# Real, officially-cited average speeds by train class (km/h, including halts) —
# replaces an earlier flat "80 km/h for every train" assumption used to estimate
# schedule padding. Sourced from Ministry of Railways answers in Rajya Sabha:
#   - Mail/Express: 51.1 km/h (2023-24), consistently ~50-51 km/h over 2017-2024
#     (PQ 262/784, 08.12.2023; PQ 263/908, 09.02.2024)
#   - Ordinary/Passenger: 35.1 km/h (2023-24), ~33-35 km/h over the same period
#   - Superfast: officially DEFINED as averaging >=55 km/h end-to-end on Broad
#     Gauge (criterion set in 1993, unchanged since) — used as a floor estimate
#   - Premium (Rajdhani/Shatabdi/Duronto/Vande Bharat): "above 70 kmph" in
#     FY2019-20 per a Ministry statement; individual flagship trains report
#     75-90 km/h in practice
# These are national averages ACROSS ALL SECTIONS (flat, hilly, single-line,
# electrified or not) — using one number per class is itself a simplification
# (a single train's actual achievable speed still varies by section), but it
# is a real, sourced simplification rather than an arbitrary constant.
TYPICAL_AVERAGE_SPEED_KMH = {
    "Rajdhani": 78.0,
    "Shatabdi": 78.0,
    "Duronto": 76.0,
    "Vande Bharat": 80.0,
    "Superfast": 58.0,
    "Mail": 51.0,
    "Express": 51.0,
    "Passenger": 35.0,
}
DEFAULT_AVERAGE_SPEED_KMH = 45.0  # fallback for unrecognized/unlabeled train types


def typical_average_speed_kmh(train_type: str) -> float:
    return TYPICAL_AVERAGE_SPEED_KMH.get((train_type or "").strip(), DEFAULT_AVERAGE_SPEED_KMH)


@dataclass
class SectionDelayComponents:
    """Every contributing piece for one section, kept separate so
    journey_simulator can log/inspect them individually (useful later for
    the explanation-layer feature: Section 12.7 of the architecture doc)."""
    running_noise: float
    congestion: float
    weather: float
    recovery: float
    disruption: float

    @property
    def total(self) -> float:
        return self.running_noise + self.congestion + self.weather - self.recovery + self.disruption


RAKE_CASCADE_RHO = 0.35
"""
Fraction of a rake's PREVIOUS service's final delay that survives scheduled
turnaround buffer and carries into the NEXT service's origin delay.

WHY 0.35, NOT HIGHER OR LOWER: real terminals schedule a turnaround buffer
specifically to absorb a moderately late arrival before the next departure.
That buffer usually absorbs MOST of a typical delay — but if the buffer is
insufficient (a very late arrival, or a short scheduled turnaround), some
lateness survives into the next trip. 0.35 encodes "most ordinary delay gets
absorbed by turnaround buffer, but a meaningful minority carries through" —
a documented assumption, not a fitted value. Recalibrate here if real
turnaround-time data ever becomes available.
"""


def origin_delay(train_type: str, rng: random.Random, previous_service_delay: float = 0.0) -> float:
    """
    How late does this train START its journey? Two independent contributors:

    1. Base origin variance: rake turnaround, crew, platform congestion at
       origin, modeled as a half-normal-ish draw (can't leave early), scaled
       by priority — premium trains have tighter origin discipline.

    2. RAKE CASCADING: if this same physical rake's previous service (e.g.
       train 12952 arriving before today's 12951 departs) was itself running
       late, some of that lateness can survive the scheduled turnaround
       buffer and carry into today's departure. See RAKE_CASCADE_RHO's
       docstring for why this is a partial, not full, carryover.

    previous_service_delay: the FINAL delay (minutes) of this train's most
        recent prior service, or 0.0 if unknown/not applicable (e.g. this is
        the first simulated day, or the caller doesn't track this).
    """
    mult = priority_multiplier(train_type)
    base = abs(rng.gauss(mu=0, sigma=6)) * mult
    carryover = max(0.0, previous_service_delay) * RAKE_CASCADE_RHO * mult
    return round(base + carryover, 2)


def running_time_noise(section_distance_km: float, train_type: str, rng: random.Random) -> float:
    """
    Ordinary variance in how long a section takes to traverse — track
    conditions, minor signal holds, driver behavior. Scales mildly with
    section length (more distance = more opportunity for small variance to
    accumulate) and is tighter for premium trains.
    """
    mult = priority_multiplier(train_type)
    distance = section_distance_km if section_distance_km and section_distance_km > 0 else 30
    sigma = (0.15 + 0.01 * min(distance, 100)) * mult  # cap the distance effect's growth
    return round(rng.gauss(mu=0, sigma=sigma), 2)


def congestion_event(is_high_traffic_zone: bool, is_peak_hour: bool, train_type: str,
                      rng: random.Random) -> float:
    """
    Congestion/precedence delay: the single most common real-world cause —
    a train waits for a crossing, loses its slot behind a slower train, or
    queues for platform access at a busy junction. Modeled as a Bernoulli
    trigger (does congestion happen on this section) with a right-skewed
    Gamma magnitude when it does (most congestion delays are small, a few
    are large — a Gamma shape captures that better than a Normal would).
    """
    mult = priority_multiplier(train_type)
    base_prob = 0.06
    if is_high_traffic_zone:
        base_prob *= 2.2
    if is_peak_hour:
        base_prob *= 1.8
    prob = min(base_prob * mult, 0.6)  # cap so it never becomes near-certain

    if rng.random() >= prob:
        return 0.0
    # Gamma(shape=2, scale=4) has mean 8, right-skewed — a few big delays,
    # mostly small ones. This shape is a deliberate, documented choice, not
    # a fitted one.
    magnitude = rng.gammavariate(alpha=2.0, beta=4.0) * mult
    return round(magnitude, 2)


def weather_event(is_fog_season: bool, is_monsoon_season: bool, hour: int,
                   rng: random.Random) -> float:
    """
    Weather-driven delay. Fog is modeled as a severe, higher-probability
    event during early-morning hours in fog season for fog-prone zones
    (matches the well-documented real pattern of dense fog forming overnight
    and clearing by mid-morning). Monsoon is modeled as a gentler, more
    probable-but-less-severe effect (waterlogging/slow sections) without the
    strong time-of-day dependency fog has.
    """
    delay = 0.0

    if is_fog_season:
        is_fog_hours = hour < 9 or hour >= 22  # fog is worst overnight/early morning
        fog_prob = 0.35 if is_fog_hours else 0.05
        if rng.random() < fog_prob:
            # log-normal: heavy tail — fog delays are notorious for being
            # severe outliers (multi-hour), not just "a bit slow"
            delay += rng.lognormvariate(mu=2.5, sigma=0.8)  # median ~e^2.5 ≈ 12 min

    if is_monsoon_season:
        if rng.random() < 0.10:
            delay += rng.gammavariate(alpha=1.5, beta=5.0)  # gentler than fog

    return round(delay, 2)


def disruption_jump(rng: random.Random) -> float:
    """
    Rare, high-impact, low-probability disruptions: signal failures,
    accidents, VIP-movement holds. Modeled as a low-rate trigger with a
    heavy-tailed magnitude (Pareto) when it fires — most of the time this
    contributes nothing, occasionally it dominates everything else.
    """
    if rng.random() >= 0.01:  # ~1% chance per section
        return 0.0
    # Pareto(alpha=1.5) scaled — heavy right tail, occasional huge values
    magnitude = (rng.paretovariate(1.5) - 1) * 15
    return round(min(magnitude, 180), 2)  # cap at 3 hours so it stays plausible


def recovery_margin(scheduled_minutes: float, geographic_minimum_minutes: float,
                     current_delay: float, rng: random.Random) -> float:
    """
    Real timetables build in slack ("padding") on certain sections so trains
    CAN recover lost time. Without this, delay could only ever grow across
    a journey, which is unrealistic — real trains frequently claw back a few
    minutes on generously-padded sections.

    scheduled_minutes: timetabled running time for this section.
    geographic_minimum_minutes: our best estimate of the fastest plausible
        running time (rough proxy — see journey_simulator's usage). If the
        schedule allows meaningfully more time than this minimum, we treat
        the difference as recoverable padding.
    current_delay: only recover if there's actually delay to recover from.
    """
    if current_delay <= 0 or scheduled_minutes is None or geographic_minimum_minutes is None:
        return 0.0
    padding = max(0.0, scheduled_minutes - geographic_minimum_minutes)
    if padding <= 0:
        return 0.0
    # recover a random fraction of the smaller of (available padding, current delay)
    recoverable_cap = min(padding, current_delay)
    fraction = rng.uniform(0.0, 0.6)  # never guaranteed full recovery in one section
    return round(recoverable_cap * fraction, 2)


def apply_autocorrelation(previous_delay: float, new_component_total: float,
                           rho: float = 0.9) -> float:
    """
    Delay persists rather than resetting independently at each station — a
    train that's already delayed is more likely to STAY delayed (it lost its
    crossing slot, its crew's duty clock is running, etc.), not
    independently re-randomized. rho close to 1 = strong persistence.
    """
    return max(0.0, rho * previous_delay + new_component_total)
