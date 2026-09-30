"""
Application Configuration — Team Mango SIH 26028.
"""

from pathlib import Path
import os

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
RAW_DATA_DIR = DATA_DIR / "raw"
MODELS_DIR = REPO_ROOT / "models"

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

API_V1_PREFIX = "/api/v1"
PROJECT_NAME = "Dynamic ETA Forecasting for Coaching Trains"
PROJECT_VERSION = "1.1.0"
TEAM_NAME = "Team Mango"
PROBLEM_STATEMENT_ID = "26028"
