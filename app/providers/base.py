"""
Abstract base class for all live-status data providers.
"""

from abc import ABC, abstractmethod
from datetime import date
from typing import List, Optional

from app.schemas.canonical import TrainStateEvent, TrainState


class LiveStatusProvider(ABC):
    """Abstract interface for any source of train running status."""

    @abstractmethod
    def get_journey_events(
        self,
        train_number: str,
        journey_date: date,
        as_of: Optional[str] = None,
    ) -> List[TrainStateEvent]:
        """
        Return the list of state events observed for this journey.
        If as_of is provided (ISO 8601 string or timestamp), returns ONLY events
        observed on or before that point in time.
        """
        pass

    @abstractmethod
    def get_current_state(
        self,
        train_number: str,
        journey_date: date,
        as_of: Optional[str] = None,
    ) -> Optional[TrainState]:
        """
        Return the reconstructed operational status of the train at as_of time.
        """
        pass

    @abstractmethod
    def health_check(self) -> dict:
        """Return operational health details of this provider."""
        pass
