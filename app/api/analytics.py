"""
Analytics and Calibration API Endpoints.
"""

from fastapi import APIRouter
from app.services.analytics_service import analytics_service

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/accuracy", summary="Get Model Accuracy & Baseline Lift")
def get_accuracy_metrics():
    return analytics_service.get_accuracy_metrics()


@router.get("/calibration", summary="Get Simulation Calibration Audit")
def get_calibration_report():
    return analytics_service.get_calibration_report()
