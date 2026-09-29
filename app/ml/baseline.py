"""
Non-ML baseline delay propagation model (Section 12.3 of architecture doc).

Serves as the rigorous benchmark against which LightGBM lift is computed.
Uses simple persistence (rho=0.90 within-journey) minus scheduled recovery buffer.
"""

from typing import List, Dict, Any
from app.simulation.delay_model import RECOVERY_MARGIN_FRACTION


class DelayPropagationBaseline:
    """
    Standard operational baseline:
    Predicted arrival delay at station k =
        max(0, current_delay * (persistence ** k) - accumulated_recovery_buffer)
    """

    def __init__(self, persistence: float = 0.90):
        self.persistence = persistence

    def predict_journey(
        self,
        current_delay_minutes: float,
        remaining_sections: List[Dict[str, Any]],
    ) -> List[Dict[str, float]]:
        """
        remaining_sections: list of dicts with keys:
            - 'scheduled_minutes': float
            - 'distance_km': float
        Returns list of dicts with {'predicted_delay': float} for each remaining station.
        """
        predictions = []
        delay = max(0.0, float(current_delay_minutes))

        for k, sec in enumerate(remaining_sections, start=1):
            sched_min = float(sec.get("scheduled_minutes") or 0.0)
            # Recovery buffer available in this section
            recovery = sched_min * RECOVERY_MARGIN_FRACTION
            # Persistence decay + recovery
            delay = max(0.0, (delay * self.persistence) - recovery)
            predictions.append({"predicted_delay": round(delay, 1)})

        return predictions
