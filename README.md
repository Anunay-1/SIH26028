# Dynamic ETA Forecasting System — Team Mango (SIH 26028)

## Current phase: Phase A — Data Foundation (CSV-first, pre-DB)

We are deliberately operating on flat CSVs under `data/` before wiring up
PostgreSQL/Redis. The canonical schemas in `app/schemas/` are written now so
that moving each CSV into a real table later is a mechanical step, not a
redesign.

## Repo structure

```
.
├── data/
│   ├── raw/            # untouched dumps from external sources (gitignored)
│   ├── interim/         # cleaned but not yet joined/finalized
│   └── processed/       # final master CSVs — these are what everything else reads
├── scripts/
│   └── data/
│       ├── parse_reference_data.py         # datameet/railways JSON -> master CSVs
│       ├── generate_synthetic_events.py    # thin CLI wrapper around app/simulation (batch dataset generation)
│       ├── build_section_observations.py   # turns an event log into training-ready rows
│       ├── poll_live_status.py             # NOT CURRENTLY FUNCTIONAL — see status notes above
│       ├── check_one_train.py              # manual diagnostic: eyeball one train's parsed schedule
│       ├── diagnose_schedule_quality.py    # manual diagnostic: scan for implausible stop counts
│       └── diagnose_duplicate_stops.py     # manual diagnostic: duplication vs genuinely-wrong data
├── app/
│   ├── schemas/
│   │   └── canonical.py                  # dataclasses mirroring the doc's Section 10.2 model — single source of truth for field names
│   ├── simulation/                       # THE MATH — why a train is delayed, real-world-grounded
│   │   ├── calendar_context.py           # zone/season/time-of-day lookups (fog, monsoon, peak hours, traffic tiers)
│   │   ├── delay_model.py                # individual, independently-testable delay causes (see "Synthetic Data Methodology" below)
│   │   └── journey_simulator.py          # orchestrates delay_model across one full route -> list of TrainStateEvent
│   └── providers/                        # THE INTERFACE — Section 11.1 of the architecture doc
│       ├── base.py                       # LiveStatusProvider abstract interface — everything else in the app talks to THIS, never a concrete source directly
│       └── replay.py                     # ReplayProvider — the only currently-working implementation, wraps journey_simulator with deterministic per-(train,date) seeding
├── tests/
│   ├── test_pipeline_smoke.py            # end-to-end pipeline test (parse -> simulate -> section observations), isolated in a temp dir
│   └── test_delay_model.py               # statistical validation that delay_model's real-world claims actually hold in the code
└── requirements.txt
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

# get the reference data
git clone https://github.com/datameet/railways.git data/raw/datameet_railways
```

## Status as of last session — READ THIS FIRST

Three real findings changed the plan since this repo was first scaffolded:

1. **`datameet/railways`'s `schedules.json` is corrupted for at least premium-class
   trains** (Rajdhani/Shatabdi/Duronto). Verified: e.g. train 12431 has 414
   "stops," all genuinely unique station codes — not a dedup-able bug, the
   source data is just wrong for these. `stations.csv` (station master) is
   still fine and safe to use. Do NOT trust `route_stations.csv` for any
   route without first checking its stop count is plausible (use
   `check_one_train.py` / `diagnose_schedule_quality.py` below).

2. **`pyinrail` is effectively dead.** It depends on `demjson`, whose build
   process requires `use_2to3`, a `setuptools` feature removed years ago.
   It fails to install on any current Python. `poll_live_status.py` is kept
   in this repo for reference/future revival but should NOT be relied on
   right now.

3. **Third-party live-status APIs (`railwayapi.com`, `indianrailapi.com`)
   were both unreachable/under maintenance when checked.** This may change —
   worth re-checking periodically — but don't block work on them.

**Current path forward: build against synthetic data.** This matches the
architecture doc's own `ReplayProvider` design (Sections 4.4, 11.5) — the
rest of the pipeline (baseline ETA, ML model) doesn't care whether events
came from a real feed or a realistic simulation, and everything is written
against the same `TrainStateEvent` schema either way. When a real live
source is finally working, it slots in without changing anything downstream.

## Workflow order (current, synthetic-data-based)

1. `python scripts/data/parse_reference_data.py`
   Reads `data/raw/datameet_railways/*.json`, writes
   `data/processed/stations.csv`, `routes.csv`, `route_stations.csv`.
   (Get the source: `git clone https://github.com/datameet/railways.git data/raw/datameet_railways`)

2. **Validate before trusting `route_stations.csv`:**
   ```
   python scripts/data/diagnose_schedule_quality.py
   python scripts/data/check_one_train.py <some_train_number>
   ```
   If a route's stop count looks implausible for its train class, don't use
   it — `generate_synthetic_events.py` already filters routes to a plausible
   2–40 stop range automatically, but keep this in mind if you use
   `route_stations.csv` anywhere else.

3. `python scripts/data/generate_synthetic_events.py --num-journeys 200`
   Simulates trains running their real schedules with realistic randomized
   delay (a "delay personality" per journey + a random walk + occasional
   bigger delay events per section). Writes
   `data/processed/synthetic_status_log.csv` in the exact same schema a real
   `LiveStatusProvider` would produce.

4. `python scripts/data/build_section_observations.py --input data/processed/synthetic_status_log.csv --out data/processed/section_observations.csv`
   Turns the event log into training-ready section-level rows.

## Synthetic Data Methodology

Since no reliable public live-status source was available during development
(see "Status as of last session" above), the training/demo dataset is
generated by a **statistically-grounded delay simulation**, not random noise.
Real station/route/schedule data (`datameet/railways`) is used as-is; only
the *delay behavior* — how late a train runs at each point in its journey —
is simulated. This section documents that model so it can be defended
directly to evaluators, not hidden as an implementation detail.

### Real-world causes modeled, and why

| Real-world cause | Why it matters | Where it lives |
|---|---|---|
| Origin delay | Trains often depart late due to rake turnaround, crew, platform congestion | `delay_model.origin_delay()` |
| Running-time noise | Ordinary variance from track conditions, minor holds, driver behavior | `delay_model.running_time_noise()` |
| Congestion/precedence | **The dominant real-world delay cause** — waiting for a crossing, losing a slot behind a slower train, queuing at a busy junction | `delay_model.congestion_event()` |
| Weather (fog/monsoon) | Fog is the single biggest seasonal disruptor in North India (Nov-Feb); monsoon flooding affects other zones Jun-Sep | `delay_model.weather_event()` |
| Train priority class | Rajdhani/Shatabdi/Duronto get real operational precedence over Mail/Express/Passenger | `PRIORITY_MULTIPLIERS` in `delay_model.py` |
| Schedule padding/recovery | Real timetables build in slack so trains CAN claw back lost time — without this, delay could only ever grow, which is unrealistic | `delay_model.recovery_margin()` |
| Rare high-impact disruptions | Signal failures, accidents, VIP holds — low probability, high impact, long-tailed | `delay_model.disruption_jump()` |
| Delay persistence | A delayed train tends to STAY delayed (lost its crossing slot) rather than resetting independently at each station | `delay_model.apply_autocorrelation()` |

### Mathematical formulation

At each section (station *i* to *i+1*):

```
component_total = running_noise + congestion + weather + disruption - recovery
D_i = max(0, ρ · D_{i-1} + component_total)
```

Where `ρ` (~0.9) controls how strongly delay persists from one section to
the next, and each component is drawn from a distribution shape chosen to
match the real phenomenon it represents:
- **Congestion**: Bernoulli trigger (probability boosted by peak hours and
  high-traffic zones) × **Gamma** magnitude when triggered — right-skewed,
  since most congestion delays are small and a few are large
- **Fog**: Bernoulli trigger (much higher overnight, in-season, in fog-prone
  zones) × **log-normal** magnitude — heavy-tailed, matching fog's
  well-documented tendency to cause severe, multi-hour outliers
- **Disruption**: very-low-probability trigger × **Pareto** magnitude,
  capped at 180 minutes — rare but occasionally dominant
- **Recovery**: only fires when there's both current delay AND real schedule
  padding (estimated as `scheduled_time - distance/80km/h`) to recover from

### Honesty about parameterization

Every constant (fog-prone zone list, season date ranges, priority
multipliers, distribution shapes/scales) is a **domain-informed simulation
prior**, sourced from widely-documented real-world patterns (e.g., North
Indian winter fog disruption is routine annual news; premium trains'
operational precedence is a matter of Railway Board policy) — NOT fitted to
real measured data, because that's exactly the data this pivot exists to
work around. If asked: this is a literature/domain-informed simulation,
clearly documented as a development stand-in, not a claim of measured
accuracy. `calendar_context.py` and `delay_model.py` are the two files to
recalibrate first if real data ever becomes available.

### Validated, not just asserted

`tests/test_delay_model.py` statistically verifies every claim in the table
above actually holds in the code (e.g., "Rajdhani's mean delay is lower than
Passenger's," "fog season produces more weather delay than non-fog season,"
"recovery never fires without real padding to recover from"). Run it after
any change to `delay_model.py` or `calendar_context.py`:
```
python tests/test_delay_model.py
```

### Realistic per-class speeds (not one flat number)

`recovery_margin()` needs to know how much "padding" a schedule has, which
requires estimating the fastest plausible running time for a section. This
used to assume a flat 80 km/h for every train — now it uses real,
officially-cited average speeds by train class (Ministry of Railways Rajya
Sabha replies): Mail/Express 51.1 km/h and Ordinary/Passenger 35.1 km/h
(2023-24 figures), Superfast's official 55 km/h minimum-average definition,
and premium trains (Rajdhani/Shatabdi/Duronto/Vande Bharat) reported "above
70 kmph." See `TYPICAL_AVERAGE_SPEED_KMH` in `delay_model.py`.

### Rake cascading (cross-day memory)

Most Indian long-distance trains are the same physical rake running back and
forth (e.g. 12951 down / 12952 up). If a rake's previous service arrived very
late, scheduled turnaround buffer may not fully absorb it before the next
departure — some lateness carries over. `delay_model.origin_delay()` now
accepts the previous service's final delay and applies a partial (35%,
priority-scaled) carryover — see `RAKE_CASCADE_RHO`'s docstring for why it's
partial, not full. `ReplayProvider` looks back exactly ONE day to supply this
(capped, not an infinite chain — see `get_journey_events`'s docstring).

### Known simplification: no multi-train interaction (yet)

The congestion model uses a *probability proxy* (zone traffic tier + peak
hour) rather than simulating actual queuing/precedence between multiple
trains sharing a section. Modeling real multi-train interaction (a genuine
discrete-event simulation where trains can actually block each other) is a
planned extension — the architecture is deliberately structured so this
extends `journey_simulator.py`'s orchestration layer without needing to
touch `delay_model.py`'s individual causal functions.

## Reviving the live-data path later (don't block on this now)

- Re-check `railwayapi.com` / `indianrailapi.com` periodically — they may
  come back online.
- `poll_live_status.py` is ready to be fixed once ANY working live source is
  confirmed — only `_call_live_status()` needs rewriting to match whatever
  source ends up working; everything else (the `TrainStateEvent` schema, the
  CSV writer) stays the same.
- If you do get a live source working, the transition is: run
  `poll_live_status.py` for real instead of (or alongside)
  `generate_synthetic_events.py`, feeding the same
  `build_section_observations.py` step unchanged.
