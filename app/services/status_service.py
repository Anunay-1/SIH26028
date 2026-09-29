"""
Status Service — live tracking and historical event retrieval with as_of support.
"""

from datetime import date, datetime
from typing import List, Optional, Dict, Any

from app.config import PROCESSED_DATA_DIR
from app.providers.replay import ReplayProvider
from app.schemas.canonical import TrainState, TrainStateEvent


class StatusService:
    def __init__(self):
        self.provider = ReplayProvider(data_dir=PROCESSED_DATA_DIR)

    def get_status(
        self,
        train_number: str,
        journey_date: Optional[date] = None,
        as_of: Optional[str] = None,
    ) -> Optional[TrainState]:
        j_date = journey_date or date.today()
        return self.provider.get_current_state(train_number, j_date, as_of=as_of)

    def get_events(
        self,
        train_number: str,
        journey_date: Optional[date] = None,
        as_of: Optional[str] = None,
    ) -> List[TrainStateEvent]:
        j_date = journey_date or date.today()
        return self.provider.get_journey_events(train_number, j_date, as_of=as_of)

    def health_check(self) -> Dict[str, Any]:
        return self.provider.health_check()


status_service = StatusService()
