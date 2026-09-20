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
│       ├── parse_reference_data.py       # datameet/railways JSON -> master CSVs
│       ├── poll_live_status.py           # pyinrail polling loop -> live_status_log.csv
│       └── build_section_observations.py # turns the log into training-ready rows
├── app/
│   └── schemas/
│       └── canonical.py                  # dataclasses mirroring the doc's Section 10.2 model
├── tests/
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
