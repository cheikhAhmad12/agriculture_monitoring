from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class AIResult:
    risk_score: float
    zone_label: str
    recommended_action: str
    reasons: list[str]


class CropStressInference:
    """
    Lightweight baseline inference for crop stress.
    Uses NDVI summary + telemetry to produce actionable labels.
    """

    def __init__(self, cfg: Dict[str, Any]):
        self.enabled = bool(cfg.get("enabled", True))
        self.weights = cfg.get(
            "weights",
            {
                "stress_ratio": 0.55,
                "low_ndvi": 0.25,
                "battery_penalty": 0.20,
            },
        )
        self.thresholds = cfg.get(
            "thresholds",
            {
                "watch": 0.45,
                "critical": 0.70,
                "low_ndvi_mean": 0.30,
                "low_battery": 25.0,
            },
        )
        self.actions = cfg.get(
            "actions",
            {
                "healthy": "continue_mission",
                "watch": "revisit_waypoint",
                "critical": "prioritize_irrigation_alert",
            },
        )

    def predict(self, ndvi: Dict[str, Any], telemetry: Dict[str, Any]) -> Dict[str, Any]:
        if not self.enabled:
            return {
                "enabled": False,
                "risk_score": 0.0,
                "zone_label": "disabled",
                "recommended_action": "none",
                "reasons": ["ai_disabled"],
            }

        stress_ratio = float(ndvi.get("stress_ratio", 0.0))
        mean_ndvi = float(ndvi.get("mean", 0.0))
        battery = telemetry.get("battery")
        battery_penalty = 0.0
        reasons: list[str] = []

        if stress_ratio > 0.0:
            reasons.append("stressed_pixels_detected")
        if mean_ndvi < float(self.thresholds["low_ndvi_mean"]):
            reasons.append("low_ndvi_mean")
        if battery is not None:
            try:
                battery_value = float(battery)
                if battery_value < float(self.thresholds["low_battery"]):
                    battery_penalty = 1.0
                    reasons.append("low_battery")
            except (TypeError, ValueError):
                pass

        low_ndvi_factor = 1.0 if mean_ndvi < float(self.thresholds["low_ndvi_mean"]) else 0.0
        risk_score = (
            float(self.weights["stress_ratio"]) * min(max(stress_ratio, 0.0), 1.0)
            + float(self.weights["low_ndvi"]) * low_ndvi_factor
            + float(self.weights["battery_penalty"]) * battery_penalty
        )
        risk_score = min(max(risk_score, 0.0), 1.0)

        if risk_score >= float(self.thresholds["critical"]):
            zone_label = "critical"
        elif risk_score >= float(self.thresholds["watch"]):
            zone_label = "watch"
        else:
            zone_label = "healthy"

        result = AIResult(
            risk_score=risk_score,
            zone_label=zone_label,
            recommended_action=str(self.actions.get(zone_label, "continue_mission")),
            reasons=reasons or ["nominal_ndvi_and_telemetry"],
        )
        return {
            "enabled": True,
            "risk_score": result.risk_score,
            "zone_label": result.zone_label,
            "recommended_action": result.recommended_action,
            "reasons": result.reasons,
        }
