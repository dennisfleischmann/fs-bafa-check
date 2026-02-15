from __future__ import annotations

from typing import Any, Dict, List, Optional

from .utils import normalize_unit, parse_float


PLAUSIBILITY_RANGES = {
    "thickness_cm": (2.0, 40.0),
    "u_value": (0.10, 2.0),
}


def normalize_value_unit(value: Any, unit: Optional[str]) -> Dict[str, Any]:
    parsed = parse_float(value)
    return {
        "value": parsed,
        "unit": normalize_unit(unit),
    }


def check_plausibility(metric: str, value: Optional[float]) -> bool:
    if value is None:
        return False
    if metric not in PLAUSIBILITY_RANGES:
        return True
    low, high = PLAUSIBILITY_RANGES[metric]
    return low <= value <= high


def normalize_measure_values(measure: Dict[str, Any]) -> Dict[str, Any]:
    values = dict(measure.get("values", {}))
    normalized: Dict[str, Any] = {}
    for key, payload in values.items():
        if not isinstance(payload, dict):
            continue
        norm = normalize_value_unit(payload.get("value"), payload.get("unit"))
        if key in {"u_value", "uw", "u_value_target"}:
            norm["plausible"] = check_plausibility("u_value", norm.get("value"))
        elif key in {"thickness", "thickness_cm"}:
            norm["plausible"] = check_plausibility("thickness_cm", norm.get("value"))
        normalized[key] = norm
    measure["values"] = normalized

    layers: List[Dict[str, Any]] = []
    for layer in measure.get("layers", []):
        d_m = parse_float(layer.get("d_m"))
        lamb = parse_float(layer.get("lambda"))
        layers.append({
            **layer,
            "d_m": d_m,
            "lambda": lamb,
            "plausible": d_m is not None and lamb is not None and d_m > 0 and lamb > 0,
        })
    if layers:
        measure["layers"] = layers
    return measure
