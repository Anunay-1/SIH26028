"""
The LiveStatusProvider interface — Section 11.1 of the architecture doc.

WHY THIS EXISTS: nothing else in the system (baseline ETA logic, the ML
model, eventually the FastAPI backend) should ever import a specific data
source directly. Everything talks to THIS interface. Today the only working
implementation is ReplayProvider (synthetic data); when a real live source
is eventually found, it becomes a new class implementing this same
interface, and nothing else in the codebase changes.

DESIGN DECISION (per your instruction): get_journey_events() returns the
FULL sequence of events for a journey, not just the latest one. Rationale:
a provider that can only give "the latest event" can't retroactively give
you "the full event," but a provider that gives you the full event list can
trivially also give you just the latest one (call .get_current_state() which
is implemented here ONCE, in terms of get_journey_events(), so no subclass
needs to reimplement that logic separately).
"""

from abc import ABC, abstractmethod
from datetime import date
from typing import List, Optional

from app.schemas.canonical import TrainStateEvent


class LiveStatusProvider(ABC):
    """
    Abstract base for anything that can report a train's running state,
    real or simulated. Subclass this, don't call CSV/scraper/API code
    directly from anywhere else in the app.
    """

    @abstractmethod
    def get_journey_events(self, train_number: str, journey_date: date) -> List[TrainStateEvent]:
        """
        Return every known TrainStateEvent for this (train, date) journey,
        in chronological order. Empty list if the journey isn't found/hasn't
        started/has no data — never raise for "not found," that's a normal
        outcome the caller should be able to handle without a try/except.
        """
        raise NotImplementedError

    def get_current_state(self, train_number: str, journey_date: date) -> Optional[TrainStateEvent]:
        """
        Convenience method built ON TOP of get_journey_events() — the latest
        known event for this journey, or None if there's no data yet.
        Implemented once here so no subclass needs to duplicate this logic.
        """
        events = self.get_journey_events(train_number, journey_date)
        if not events:
            return None
        return max(events, key=lambda e: e.event_time)

    def health_check(self) -> dict:
        """
        Basic health/status reporting (Section 11.1's "provider health can be
        measured independently of model health"). Subclasses should override
        with something meaningful once there's a real network call involved
        (latency, last successful fetch, etc). Default: assume healthy,
        since ReplayProvider reading local files has no real failure mode
        worth reporting yet.
        """
        return {"provider": self.__class__.__name__, "status": "ok"}
