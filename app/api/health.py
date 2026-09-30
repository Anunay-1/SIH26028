"""
Health and System Status API Endpoints.
"""

from fastapi import APIRouter
from app.config import PROJECT_NAME, PROJECT_VERSION, TEAM_NAME, PROBLEM_STATEMENT_ID
from app.services.status_service import status_service
from app.services.prediction_service import prediction_service
from app.storage.redis_store import store

router = APIRouter(tags=["Health"])


@router.api_route("/health", methods=["GET", "HEAD"], summary="Health Check")
def health_check():
    return {
        "status": "healthy",
        "project": PROJECT_NAME,
        "team": TEAM_NAME,
        "problem_statement": PROBLEM_STATEMENT_ID,
        "version": PROJECT_VERSION,
        "model_loaded": prediction_service.predictor.is_ready,
        "model_version": prediction_service.predictor.model_version,
        "redis_connected": store.is_redis(),
        "provider_health": status_service.health_check(),
    }
