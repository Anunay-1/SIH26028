"""
Integration tests for FastAPI endpoints, including as_of dynamic scrubbing.
"""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


def test_train_search_endpoint():
    response = client.get("/api/v1/trains?q=11047")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert str(data[0]["train_number"]) == "11047"


def test_train_route_endpoint():
    response = client.get("/api/v1/trains/11047/route")
    assert response.status_code == 200
    stops = response.json()
    assert isinstance(stops, list)
    assert len(stops) > 0
    assert "station_code" in stops[0]


def test_train_eta_endpoint():
    response = client.get("/api/v1/trains/11047/eta?journey_date=2026-06-15")
    assert response.status_code == 200
    eta = response.json()
    assert eta["train_number"] == "11047"
    assert len(eta["forecasts"]) > 0
    first_forecast = eta["forecasts"][0]
    assert "predicted_delay_p10" in first_forecast
    assert "predicted_delay_p50" in first_forecast
    assert "predicted_delay_p90" in first_forecast
    # Monotonicity
    assert first_forecast["predicted_delay_p10"] <= first_forecast["predicted_delay_p50"]
    assert first_forecast["predicted_delay_p50"] <= first_forecast["predicted_delay_p90"]


def test_dynamic_eta_with_as_of_time_travel():
    # Early snapshot: early morning (e.g. 01:00)
    res_early = client.get("/api/v1/trains/11047/eta?journey_date=2026-06-15&as_of=2026-06-15T01:00:00")
    assert res_early.status_code == 200
    data_early = res_early.json()

    # Late snapshot: later in the journey (e.g. 05:00)
    res_late = client.get("/api/v1/trains/11047/eta?journey_date=2026-06-15&as_of=2026-06-15T05:00:00")
    assert res_late.status_code == 200
    data_late = res_late.json()

    # Count passed stations: late snapshot must have >= early snapshot passed stations
    passed_early = sum(1 for f in data_early["forecasts"] if f["status"] == "PASSED")
    passed_late = sum(1 for f in data_late["forecasts"] if f["status"] == "PASSED")
    assert passed_late >= passed_early


def test_analytics_endpoints():
    res_acc = client.get("/api/v1/analytics/accuracy")
    assert res_acc.status_code == 200
    acc_data = res_acc.json()
    assert "data_provenance" in acc_data
    assert "ml_metrics" in acc_data
    assert "lift" in acc_data

    res_cal = client.get("/api/v1/analytics/calibration")
    assert res_cal.status_code == 200
    cal_data = res_cal.json()
    assert "classes" in cal_data
