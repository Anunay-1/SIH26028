"""
Prediction API Endpoints.
"""

from datetime import date
from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from app.services.prediction_service import prediction_service

router = APIRouter(prefix="/predictions", tags=["Predictions"])


@router.get("/{train_number}", summary="Get Dynamic ETA Snapshot")
def get_prediction(
    train_number: str,
    journey_date: Optional[date] = None,
    as_of: Optional[str] = Query(None, description="ISO 8601 replay timestamp"),
):
    snapshot = prediction_service.get_dynamic_eta(train_number, journey_date=journey_date, as_of=as_of)
    if not snapshot:
        raise HTTPException(status_code=404, detail=f"Prediction unavailable for train {train_number}")
    return snapshot.to_dict()
