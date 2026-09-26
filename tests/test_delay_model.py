"""
Statistical validation of delay_model.py's real-world claims.

WHY THIS MATTERS MORE THAN NORMAL UNIT TESTS: a docstring saying "premium
trains have less delay" is worthless if the code doesn't actually produce
that pattern. These tests run each component MANY times and check the
resulting distribution has the qualitative shape we designed it to have —
this is the evidence you'd want in hand if a judge asks "how do you know
your simulation actually reflects the real-world patterns you're claiming?"

These are statistical (not exact) tests — they use enough samples that
random noise won't flip the result, but they are inherently about
distributions, not single values. If one fails ONCE after a code change,
rerun before assuming it's a real regression; if it keeps failing, it's real.
"""

import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.simulation import delay_model as dm  # noqa: E402
from app.simulation import calendar_context as cal  # noqa: E402
from datetime import datetime  # noqa: E402

FAILURES = []
N = 5000  # sample size for statistical checks


def check(name: str, condition: bool, detail: str = ""):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail and not condition else ""))
    if not condition:
        FAILURES.append(name)


def test_premium_trains_less_delayed():
    """Rajdhani should show meaningfully less origin delay than Passenger class."""
    rng = random.Random(1)
    rajdhani_delays = [dm.origin_delay("Rajdhani", rng) for _ in range(N)]
    passenger_delays = [dm.origin_delay("Passenger", rng) for _ in range(N)]

    raj_mean = statistics.mean(rajdhani_delays)
    pax_mean = statistics.mean(passenger_delays)
    check("Rajdhani mean origin delay is lower than Passenger's",
          raj_mean < pax_mean,
          f"Rajdhani={raj_mean:.2f}, Passenger={pax_mean:.2f}")


def test_rake_cascading_increases_origin_delay():
    """A train whose previous service was very late should show higher
    mean origin delay today than one whose previous service was on time."""
    rng = random.Random(20)
    with_cascade = [dm.origin_delay("Express", rng, previous_service_delay=60.0) for _ in range(N)]
    without_cascade = [dm.origin_delay("Express", rng, previous_service_delay=0.0) for _ in range(N)]
    check("large previous-service delay increases mean origin delay (rake cascading)",
          statistics.mean(with_cascade) > statistics.mean(without_cascade),
          f"with_cascade={statistics.mean(with_cascade):.2f}, without={statistics.mean(without_cascade):.2f}")


def test_rake_cascading_partial_not_full():
    """Carryover should be a FRACTION of the previous delay, not the full amount
    (turnaround buffer should absorb most of it) — mean added origin delay from
    a 60-min previous delay should be well under 60 minutes."""
    rng = random.Random(21)
    with_cascade = [dm.origin_delay("Express", rng, previous_service_delay=60.0) for _ in range(N)]
    without_cascade = [dm.origin_delay("Express", rng, previous_service_delay=0.0) for _ in range(N)]
    added = statistics.mean(with_cascade) - statistics.mean(without_cascade)
    check("carryover from a 60-min previous delay is a partial fraction, not the full 60 minutes",
          added < 40, f"added={added:.2f} (expected well under 60)")


def test_rake_cascading_scales_with_priority():
    """Premium trains should carry over LESS of a previous delay than ordinary
    trains, same previous_service_delay (better rake turnaround discipline)."""
    rng = random.Random(22)
    raj_with = [dm.origin_delay("Rajdhani", rng, previous_service_delay=60.0) for _ in range(N)]
    raj_without = [dm.origin_delay("Rajdhani", rng, previous_service_delay=0.0) for _ in range(N)]
    pax_with = [dm.origin_delay("Passenger", rng, previous_service_delay=60.0) for _ in range(N)]
    pax_without = [dm.origin_delay("Passenger", rng, previous_service_delay=0.0) for _ in range(N)]

    raj_carryover = statistics.mean(raj_with) - statistics.mean(raj_without)
    pax_carryover = statistics.mean(pax_with) - statistics.mean(pax_without)
    check("Rajdhani carries over less of a previous delay than Passenger, same input delay",
          raj_carryover < pax_carryover,
          f"Rajdhani carryover={raj_carryover:.2f}, Passenger carryover={pax_carryover:.2f}")


def test_congestion_never_negative():
    rng = random.Random(2)
    values = [dm.congestion_event(True, True, "Express", rng) for _ in range(N)]
    check("congestion_event never returns negative delay", min(values) >= 0)


def test_peak_hour_increases_congestion_probability():
    """Peak-hour congestion should fire more often than off-peak, same conditions otherwise."""
    rng = random.Random(3)
    peak_hits = sum(1 for _ in range(N) if dm.congestion_event(True, True, "Express", rng) > 0)
    offpeak_hits = sum(1 for _ in range(N) if dm.congestion_event(True, False, "Express", rng) > 0)
    check("peak-hour congestion fires more often than off-peak",
          peak_hits > offpeak_hits,
          f"peak_hits={peak_hits}, offpeak_hits={offpeak_hits} (out of {N})")


def test_high_traffic_zone_increases_congestion_probability():
    rng = random.Random(4)
    high_hits = sum(1 for _ in range(N) if dm.congestion_event(True, False, "Express", rng) > 0)
    low_hits = sum(1 for _ in range(N) if dm.congestion_event(False, False, "Express", rng) > 0)
    check("high-traffic-zone congestion fires more often than low-traffic",
          high_hits > low_hits,
          f"high_hits={high_hits}, low_hits={low_hits} (out of {N})")


def test_fog_season_increases_weather_delay():
    """Fog season + fog hours should produce meaningfully more weather delay
    than non-fog-season, same hour."""
    rng = random.Random(5)
    fog_season_delays = [dm.weather_event(True, False, hour=2, rng=rng) for _ in range(N)]
    no_fog_delays = [dm.weather_event(False, False, hour=2, rng=rng) for _ in range(N)]

    fog_mean = statistics.mean(fog_season_delays)
    no_fog_mean = statistics.mean(no_fog_delays)
    check("fog season produces higher mean weather delay than non-fog season",
          fog_mean > no_fog_mean,
          f"fog_season={fog_mean:.2f}, non_fog={no_fog_mean:.2f}")


def test_fog_worse_overnight_than_midday():
    """Fog risk should be higher at 3am than at 2pm, same fog season."""
    rng = random.Random(6)
    overnight_delays = [dm.weather_event(True, False, hour=3, rng=rng) for _ in range(N)]
    midday_delays = [dm.weather_event(True, False, hour=14, rng=rng) for _ in range(N)]

    overnight_mean = statistics.mean(overnight_delays)
    midday_mean = statistics.mean(midday_delays)
    check("fog delay is higher overnight than midday, same fog season",
          overnight_mean > midday_mean,
          f"overnight={overnight_mean:.2f}, midday={midday_mean:.2f}")


def test_disruption_jump_is_rare():
    """Disruption events should fire on a small minority of sections, not constantly."""
    rng = random.Random(7)
    hits = sum(1 for _ in range(N) if dm.disruption_jump(rng) > 0)
    rate = hits / N
    check("disruption events fire on a small minority of sections (<5%)",
          rate < 0.05,
          f"observed rate={rate:.3f}")


def test_disruption_jump_capped():
    rng = random.Random(8)
    values = [dm.disruption_jump(rng) for _ in range(N)]
    check("disruption jump never exceeds its documented 180-minute cap", max(values) <= 180)


def test_recovery_only_when_delay_exists():
    rng = random.Random(9)
    recovery = dm.recovery_margin(scheduled_minutes=60, geographic_minimum_minutes=40,
                                   current_delay=0, rng=rng)
    check("no recovery is applied when there's no current delay to recover from",
          recovery == 0.0)


def test_recovery_requires_padding():
    """If the schedule has NO slack (scheduled == geographic minimum), no recovery should occur."""
    rng = random.Random(10)
    recovery = dm.recovery_margin(scheduled_minutes=40, geographic_minimum_minutes=40,
                                   current_delay=20, rng=rng)
    check("no recovery is applied when the schedule has no padding to recover from",
          recovery == 0.0)


def test_recovery_never_exceeds_available_delay_or_padding():
    rng = random.Random(11)
    for _ in range(N):
        recovery = dm.recovery_margin(scheduled_minutes=90, geographic_minimum_minutes=50,
                                       current_delay=15, rng=rng)
        if recovery > min(40, 15):  # padding=40, current_delay=15
            check("recovery never exceeds min(padding, current_delay)", False,
                  f"got {recovery}, expected <= 15")
            return
    check("recovery never exceeds min(padding, current_delay)", True)


def test_autocorrelation_persists_delay():
    """A previously-large delay should pull the next delay upward on average,
    versus starting from zero — this is the 'delay tends to persist' claim."""
    high_start = [dm.apply_autocorrelation(previous_delay=30, new_component_total=0, rho=0.9)
                  for _ in range(10)]
    low_start = [dm.apply_autocorrelation(previous_delay=0, new_component_total=0, rho=0.9)
                 for _ in range(10)]
    check("high previous delay produces high next delay (persistence, not independent reset)",
          statistics.mean(high_start) > statistics.mean(low_start),
          f"high_start_result={statistics.mean(high_start):.2f}, low_start_result={statistics.mean(low_start):.2f}")


def test_autocorrelation_never_negative():
    result = dm.apply_autocorrelation(previous_delay=0, new_component_total=-50, rho=0.9)
    check("autocorrelation result is floored at 0 even with a large negative component",
          result == 0.0)


def test_calendar_context_fog_season_correct_months():
    ctx_dec = cal.get_operating_context("NR", datetime(2026, 12, 15, 3, 0))
    ctx_july = cal.get_operating_context("NR", datetime(2026, 7, 15, 3, 0))
    check("December + fog-prone zone (NR) is flagged as fog season", ctx_dec.is_fog_season)
    check("July + fog-prone zone (NR) is NOT flagged as fog season", not ctx_july.is_fog_season)


def test_calendar_context_zone_matters_for_fog():
    """A zone NOT in the fog-prone list shouldn't be flagged even in December."""
    ctx = cal.get_operating_context("SR", datetime(2026, 12, 15, 3, 0))  # Southern Railway
    check("December + non-fog-prone zone (SR) is NOT flagged as fog season", not ctx.is_fog_season)


def test_calendar_context_peak_hours():
    morning_peak = cal.get_operating_context("NR", datetime(2026, 6, 1, 8, 0))
    midday = cal.get_operating_context("NR", datetime(2026, 6, 1, 13, 0))
    check("8am is flagged as peak hour", morning_peak.is_peak_hour)
    check("1pm is NOT flagged as peak hour", not midday.is_peak_hour)


def main():
    test_premium_trains_less_delayed()
    test_rake_cascading_increases_origin_delay()
    test_rake_cascading_partial_not_full()
    test_rake_cascading_scales_with_priority()
    test_congestion_never_negative()
    test_peak_hour_increases_congestion_probability()
    test_high_traffic_zone_increases_congestion_probability()
    test_fog_season_increases_weather_delay()
    test_fog_worse_overnight_than_midday()
    test_disruption_jump_is_rare()
    test_disruption_jump_capped()
    test_recovery_only_when_delay_exists()
    test_recovery_requires_padding()
    test_recovery_never_exceeds_available_delay_or_padding()
    test_autocorrelation_persists_delay()
    test_autocorrelation_never_negative()
    test_calendar_context_fog_season_correct_months()
    test_calendar_context_zone_matters_for_fog()
    test_calendar_context_peak_hours()

    print()
    if FAILURES:
        print(f"{len(FAILURES)} CHECK(S) FAILED: {FAILURES}")
        sys.exit(1)
    else:
        print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
