from app.api.trains import router as trains_router
from app.api.predictions import router as predictions_router
from app.api.analytics import router as analytics_router
from app.api.health import router as health_router

__all__ = ["trains_router", "predictions_router", "analytics_router", "health_router"]
