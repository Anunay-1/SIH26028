"""
Multi-quantile LightGBM Predictor with TreeSHAP Explanations (Section 12.4 & 12.7).
"""

from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
import pandas as pd
try:
    import lightgbm as lgb
except ImportError:
    lgb = None

from app.config import MODELS_DIR
from app.ml.feature_builder import FEATURE_COLUMNS


class DynamicETAPredictor:
    def __init__(self, models_dir: Path = MODELS_DIR):
        self.models_dir = Path(models_dir)
        self.model_p10 = None
        self.model_p50 = None
        self.model_p90 = None
        self.model_version = "v1.1-lightgbm-quantile-shap"
        self._load_models()

    def _load_models(self):
        if lgb is None:
            return
        p10_path = self.models_dir / "model_p10.txt"
        p50_path = self.models_dir / "model_p50.txt"
        p90_path = self.models_dir / "model_p90.txt"

        if p10_path.exists() and p50_path.exists() and p90_path.exists():
            self.model_p10 = lgb.Booster(model_file=str(p10_path))
            self.model_p50 = lgb.Booster(model_file=str(p50_path))
            self.model_p90 = lgb.Booster(model_file=str(p90_path))

    @property
    def is_ready(self) -> bool:
        return (
            self.model_p10 is not None
            and self.model_p50 is not None
            and self.model_p90 is not None
        )

    def predict(self, features_df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Predict P10, P50, P90 delays (in minutes).
        Ensures monotonic ordering: P10 <= P50 <= P90.
        """
        if not self.is_ready:
            # Fallback heuristic if models missing
            delays = features_df["current_delay"].to_numpy()
            p50 = np.maximum(0.0, delays * 0.9)
            p10 = np.maximum(0.0, p50 * 0.7)
            p90 = np.maximum(p50, p50 * 1.4 + 5.0)
            return p10, p50, p90

        X = features_df[FEATURE_COLUMNS]
        p10 = np.maximum(0.0, self.model_p10.predict(X))
        p50 = np.maximum(0.0, self.model_p50.predict(X))
        p90 = np.maximum(0.0, self.model_p90.predict(X))

        # Enforce quantile monotonicity
        p50 = np.maximum(p10, p50)
        p90 = np.maximum(p50, p90)

        return p10, p50, p90

    def explain_prediction(self, features_df: pd.DataFrame) -> List[List[Dict[str, Any]]]:
        """
        Extract TreeSHAP per-prediction attributions using LightGBM pred_contrib=True.
        Returns top influential factors with human-readable rationale per observation.
        """
        if not self.is_ready or self.model_p50 is None or features_df.empty:
            return [[] for _ in range(len(features_df))]

        X = features_df[FEATURE_COLUMNS]
        # pred_contrib returns matrix of shape (N, num_features + 1), last column is bias
        contribs = self.model_p50.predict(X, pred_contrib=True)
        feature_contribs = contribs[:, :-1]  # Exclude expected value

        explanations_per_row = []

        feature_display_names = {
            "current_delay": "Current Upstream Delay",
            "distance_to_station": "Remaining Route Distance",
            "scheduled_section_minutes": "Scheduled Run Time",
            "accumulated_distance": "Journey Progress",
            "stop_sequence": "Station Stop Order",
            "is_fog_season": "Winter Fog Conditions",
            "is_monsoon_season": "Monsoon Season Alert",
            "is_peak_hour": "Peak Traffic Hours",
            "is_high_traffic_zone": "High-Density Trunk Corridor",
            "priority_multiplier": "Train Priority Precedence",
            "speed_kmh": "Section Speed Capability",
            "day_of_week": "Day-of-Week Congestion",
            "hour_of_day": "Time-of-Day Traffic",
        }

        for i in range(len(features_df)):
            row_contribs = feature_contribs[i]
            row_feats = features_df.iloc[i]

            # Rank features by absolute SHAP impact
            ranked_indices = np.argsort(-np.abs(row_contribs))
            reasons = []
            seen_categories = set()

            for idx in ranked_indices:
                feat_name = FEATURE_COLUMNS[idx]
                val = row_contribs[idx]
                feat_val = row_feats[feat_name]

                # Only include features with notable impact (|SHAP| >= 0.15 min)
                if abs(val) < 0.15:
                    continue

                direction = "adds_delay" if val > 0 else "absorbs_delay"
                sign_str = f"+{val:.1f}" if val > 0 else f"{val:.1f}"

                # Provide rich contextual description
                if feat_name == "current_delay" and feat_val > 0:
                    category = "momentum"
                    desc = f"Carrying forward {int(feat_val)} min upstream delay ({sign_str} min impact)"
                elif feat_name == "is_fog_season" and feat_val == 1:
                    category = "weather"
                    desc = f"Winter fog risk in northern corridor ({sign_str} min impact)"
                elif feat_name == "is_peak_hour" and feat_val == 1:
                    category = "peak"
                    desc = f"Navigating peak network rush window ({sign_str} min impact)"
                elif feat_name == "is_high_traffic_zone" and feat_val == 1:
                    category = "corridor"
                    desc = f"High-density trunk route traffic ({sign_str} min impact)"
                elif feat_name == "priority_multiplier":
                    category = "priority"
                    desc = f"Train priority class buffer adjustment ({sign_str} min impact)"
                else:
                    category = feat_name
                    desc = f"{feature_display_names.get(feat_name, feat_name)} ({sign_str} min impact)"

                if category not in seen_categories:
                    seen_categories.add(category)
                    reasons.append({
                        "feature": feat_name,
                        "display_name": feature_display_names.get(feat_name, feat_name),
                        "shap_value": round(float(val), 2),
                        "impact_minutes": round(float(val), 1),
                        "direction": direction,
                        "description": desc,
                    })

                if len(reasons) >= 3:
                    break

            explanations_per_row.append(reasons)

        return explanations_per_row


# Global singleton instance
predictor = DynamicETAPredictor()
