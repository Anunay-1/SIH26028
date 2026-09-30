"""
Prediction Service — Dynamic ETA forecasts with TreeSHAP explanations & as_of scrubbing.
"""

from datetime import date, datetime, timedelta
from typing import Optional, Dict, Any, List
import pandas as pd
import numpy as np

from app.ml.feature_builder import extract_features, get_station_centrality, to_dataframe
from app.ml.predictor import predictor
from app.schemas.canonical import PredictionSnapshot, StationETA
from app.services.status_service import status_service
from app.services.train_service import train_service
from app.storage.redis_store import store


def clean_str(val: Any) -> Optional[str]:
    if val is None or pd.isna(val) or (isinstance(val, float) and np.isnan(val)):
        return None
    s = str(val).strip()
    return s if s and s.lower() != "nan" else None


def clean_float(val: Any, default: float = 0.0) -> float:
    if val is None or pd.isna(val) or (isinstance(val, float) and np.isnan(val)):
        return default
    try:
        return float(val)
    except Exception:
        return default


class PredictionService:
    def __init__(self):
        self.predictor = predictor
        self.train_service = train_service
        self.status_service = status_service

    def get_dynamic_eta(
        self,
        train_number: str,
        journey_date: Optional[date] = None,
        as_of: Optional[str] = None,
    ) -> Optional[PredictionSnapshot]:
        j_date = journey_date or date.today()
        j_date_str = j_date.isoformat()
        as_of_str = as_of or datetime.now().isoformat()

        # Cache key includes as_of timestamp
        cache_key = f"eta:{train_number}:{j_date_str}:{as_of_str}"
        cached = store.get(cache_key)
        if cached:
            return PredictionSnapshot(
                train_number=cached["train_number"],
                train_name=cached["train_name"],
                train_type=cached["train_type"],
                journey_date=cached["journey_date"],
                as_of=cached["as_of"],
                current_station_code=cached["current_station_code"],
                current_delay_minutes=cached["current_delay_minutes"],
                forecasts=[StationETA(**f) for f in cached["forecasts"]],
                model_version=cached["model_version"],
                generated_at=cached["generated_at"],
            )

        train_info = self.train_service.get_train(train_number)
        if not train_info:
            return None

        route_stops = self.train_service.get_route_stations(train_number)
        if not route_stops:
            return None

        state = self.status_service.get_status(train_number, j_date, as_of=as_of)
        events = self.status_service.get_events(train_number, j_date, as_of=as_of)

        current_delay = state.current_delay_minutes if state else 0
        current_stn = state.last_station_code if state else None

        passed_stns = {e.last_station_code for e in events if e.last_station_code}

        delay_momentum = 0.0
        if len(events) >= 2:
            delay_momentum = float(events[-1].delay_minutes or 0.0) - float(events[-2].delay_minutes or 0.0)

        # Build feature list for upcoming stations
        feature_rows = []
        current_time_dt = (
            datetime.fromisoformat(as_of_str.replace("Z", "+00:00")).replace(tzinfo=None)
            if as_of
            else datetime.now()
        )

        last_known_dist = 0.0
        for stop in route_stops:
            if stop["station_code"] in passed_stns:
                last_known_dist = clean_float(stop.get("distance_from_origin_km"), 0.0)

        for stop in route_stops:
            stn_code = stop["station_code"]
            is_passed = stn_code in passed_stns
            dist_from_orig = clean_float(stop.get("distance_from_origin_km"), 0.0)
            dist_to_stn = max(0.0, dist_from_orig - last_known_dist)

            zone = clean_str(stop.get("zone")) or "NR"

            if not is_passed:
                centrality = get_station_centrality(stn_code)
                feat = extract_features(
                    current_delay_minutes=current_delay,
                    train_type=clean_str(train_info.get("train_type")) or "Exp",
                    when=current_time_dt,
                    zone=zone,
                    stop_sequence=int(stop["sequence"]),
                    distance_to_station=dist_to_stn,
                    scheduled_section_minutes=max(10.0, dist_to_stn / 0.8),
                    accumulated_distance=dist_from_orig,
                    delay_momentum=delay_momentum,
                    station_centrality=centrality,
                )
                feature_rows.append(feat)

        p10_preds = []
        p50_preds = []
        p90_preds = []
        shap_explanations = []

        if feature_rows:
            feat_df = to_dataframe(feature_rows)
            p10, p50, p90 = self.predictor.predict(feat_df)
            p10_preds = p10.tolist()
            p50_preds = p50.tolist()
            p90_preds = p90.tolist()
            shap_explanations = self.predictor.explain_prediction(feat_df)

        # Assemble full station forecasts
        forecasts: List[StationETA] = []
        upcoming_idx = 0

        for stop in route_stops:
            stn_code = stop["station_code"]
            stn_name = clean_str(stop.get("station_name")) or stn_code
            sched_arr = clean_str(stop.get("scheduled_arrival"))
            sched_dep = clean_str(stop.get("scheduled_departure"))
            seq = int(stop["sequence"])
            dist_km = clean_float(stop.get("distance_from_origin_km"), 0.0)

            if stn_code in passed_stns:
                # Find actual delay for passed station
                past_ev = [e for e in events if e.last_station_code == stn_code]
                actual_delay = float(past_ev[-1].delay_minutes or 0.0) if past_ev else 0.0

                eta = StationETA(
                    sequence=seq,
                    station_code=stn_code,
                    station_name=stn_name,
                    scheduled_arrival=sched_arr,
                    scheduled_departure=sched_dep,
                    predicted_delay_p10=actual_delay,
                    predicted_delay_p50=actual_delay,
                    predicted_delay_p90=actual_delay,
                    estimated_arrival_p10=self._calc_estimated_time(j_date_str, sched_arr, actual_delay),
                    estimated_arrival_p50=self._calc_estimated_time(j_date_str, sched_arr, actual_delay),
                    estimated_arrival_p90=self._calc_estimated_time(j_date_str, sched_arr, actual_delay),
                    status="PASSED",
                    distance_km=dist_km,
                    shap_explanations=[],
                )
            else:
                p10_d = round(p10_preds[upcoming_idx], 1) if upcoming_idx < len(p10_preds) else 0.0
                p50_d = round(p50_preds[upcoming_idx], 1) if upcoming_idx < len(p50_preds) else 0.0
                p90_d = round(p90_preds[upcoming_idx], 1) if upcoming_idx < len(p90_preds) else 0.0
                shap_reasons = shap_explanations[upcoming_idx] if upcoming_idx < len(shap_explanations) else []

                status = "CURRENT" if (state and state.next_station_code == stn_code) else "UPCOMING"

                eta = StationETA(
                    sequence=seq,
                    station_code=stn_code,
                    station_name=stn_name,
                    scheduled_arrival=sched_arr,
                    scheduled_departure=sched_dep,
                    predicted_delay_p10=p10_d,
                    predicted_delay_p50=p50_d,
                    predicted_delay_p90=p90_d,
                    estimated_arrival_p10=self._calc_estimated_time(j_date_str, sched_arr, p10_d),
                    estimated_arrival_p50=self._calc_estimated_time(j_date_str, sched_arr, p50_d),
                    estimated_arrival_p90=self._calc_estimated_time(j_date_str, sched_arr, p90_d),
                    status=status,
                    distance_km=dist_km,
                    shap_explanations=shap_reasons,
                )
                upcoming_idx += 1

            forecasts.append(eta)

        snapshot = PredictionSnapshot(
            train_number=str(train_number),
            train_name=clean_str(train_info.get("train_name")) or "",
            train_type=clean_str(train_info.get("train_type")),
            journey_date=j_date_str,
            as_of=as_of_str,
            current_station_code=current_stn,
            current_delay_minutes=current_delay,
            forecasts=forecasts,
            model_version=self.predictor.model_version,
            generated_at=datetime.now().isoformat(),
        )

        # Store in cache (60s TTL for dynamic queries)
        store.set(cache_key, snapshot.to_dict(), ttl_seconds=60)
        return snapshot

    def _calc_estimated_time(self, journey_date_str: str, sched_time_str: Optional[str], delay_minutes: float) -> Optional[str]:
        if not sched_time_str:
            return None
        try:
            time_parts = [int(p) for p in sched_time_str.split(":")]
            h, m = time_parts[0], time_parts[1]
            s = time_parts[2] if len(time_parts) > 2 else 0
            base_dt = datetime.fromisoformat(journey_date_str).replace(hour=h, minute=m, second=s)
            est_dt = base_dt + timedelta(minutes=float(delay_minutes))
            return est_dt.strftime("%H:%M:%S")
        except Exception:
            return sched_time_str


prediction_service = PredictionService()
