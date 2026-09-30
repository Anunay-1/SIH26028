"""
Train and Route API Endpoints.
"""

from datetime import date
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query

from app.services.train_service import train_service
from app.services.status_service import status_service
from app.services.prediction_service import prediction_service

router = APIRouter(prefix="/trains", tags=["Trains"])


@router.get("", summary="Search Trains")
def search_trains(q: str = Query("", description="Train number, name, or station code"), limit: int = 20):
    return train_service.search_trains(query=q, limit=limit)


@router.get("/{train_number}", summary="Get Train Details")
def get_train_details(train_number: str):
    train = train_service.get_train(train_number)
    if not train:
        raise HTTPException(status_code=404, detail=f"Train {train_number} not found.")
    return train


@router.get("/{train_number}/route", summary="Get Route Stations")
def get_route(train_number: str):
    route_stops = train_service.get_route_stations(train_number)
    if not route_stops:
        raise HTTPException(status_code=404, detail=f"Route for train {train_number} not found.")
    return route_stops


@router.get("/{train_number}/status", summary="Get Live Running Status (with as_of support)")
def get_train_status(
    train_number: str,
    journey_date: Optional[date] = None,
    as_of: Optional[str] = Query(None, description="ISO 8601 timestamp to reconstruct state at that moment"),
):
    state = status_service.get_status(train_number, journey_date=journey_date, as_of=as_of)
    if not state:
        raise HTTPException(status_code=404, detail=f"No status found for train {train_number}.")
    return state.to_dict()


@router.get("/{train_number}/history", summary="Get Journey Event History")
def get_train_history(
    train_number: str,
    journey_date: Optional[date] = None,
    as_of: Optional[str] = Query(None, description="ISO 8601 timestamp cutoff"),
):
    events = status_service.get_events(train_number, journey_date=journey_date, as_of=as_of)
    return [e.to_dict() for e in events]


@router.get("/{train_number}/eta", summary="Get Dynamic Quantile ETA Forecast")
def get_train_eta(
    train_number: str,
    journey_date: Optional[date] = None,
    as_of: Optional[str] = Query(None, description="ISO 8601 replay timestamp for time-travel scrubbing"),
):
    forecast = prediction_service.get_dynamic_eta(train_number, journey_date=journey_date, as_of=as_of)
    if not forecast:
        raise HTTPException(status_code=404, detail=f"Cannot generate ETA for train {train_number}.")
    return forecast.to_dict()
