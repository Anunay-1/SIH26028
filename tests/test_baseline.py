"""
Unit tests for DelayPropagationBaseline.
"""

from app.ml.baseline import DelayPropagationBaseline


def test_delay_propagation_decay():
    baseline = DelayPropagationBaseline(persistence=0.90)
    sections = [
        {"scheduled_minutes": 60.0},
        {"scheduled_minutes": 60.0},
        {"scheduled_minutes": 60.0},
    ]
    preds = baseline.predict_journey(current_delay_minutes=50.0, remaining_sections=sections)

    assert len(preds) == 3
    # Delays should decrease as distance/recovery advances
    assert preds[0]["predicted_delay"] < 50.0
    assert preds[1]["predicted_delay"] < preds[0]["predicted_delay"]
    assert preds[2]["predicted_delay"] < preds[1]["predicted_delay"]


def test_delay_propagation_zero_delay():
    baseline = DelayPropagationBaseline(persistence=0.90)
    sections = [{"scheduled_minutes": 45.0}]
    preds = baseline.predict_journey(current_delay_minutes=0.0, remaining_sections=sections)
    assert preds[0]["predicted_delay"] == 0.0


if __name__ == "__main__":
    test_delay_propagation_decay()
    test_delay_propagation_zero_delay()
    print("Baseline tests passed.")
