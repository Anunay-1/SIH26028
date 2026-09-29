"""
FastAPI Application Entry Point — SIH 26028 Dynamic ETA System.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import PROJECT_NAME, PROJECT_VERSION, API_V1_PREFIX
from app.api import trains_router, predictions_router, analytics_router, health_router

app = FastAPI(
    title=PROJECT_NAME,
    version=PROJECT_VERSION,
    description="Dynamic ETA Forecasting for Coaching Trains (SIH 26028) - Multi-Quantile LightGBM with TreeSHAP Explanations and Dynamic Replay Scrubbing",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware to support frontend Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API Routers
app.include_router(health_router, prefix=API_V1_PREFIX)
app.include_router(trains_router, prefix=API_V1_PREFIX)
app.include_router(predictions_router, prefix=API_V1_PREFIX)
app.include_router(analytics_router, prefix=API_V1_PREFIX)


from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

# Mount Static Files (Frontend assets: styles.css, app.js)
STATIC_DIR = Path(__file__).resolve().parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", summary="Dashboard UI")
def root():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {
        "message": "Dynamic ETA Forecasting API is active.",
        "docs": "/docs",
        "api_v1": API_V1_PREFIX,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
