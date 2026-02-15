from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .utils import parse_float

R_SI = 0.13
R_SE = 0.04


def u_value_from_layers(layers: List[Dict[str, Any]], rsi: float = R_SI, rse: float = R_SE) -> Optional[float]:
    if not layers:
        return None
    resistance = rsi + rse
    for layer in layers:
        d_m = parse_float(layer.get("d_m"))
        lamb = parse_float(layer.get("lambda"))
        if d_m is None or lamb is None or d_m <= 0 or lamb <= 0:
            return None
        resistance += d_m / lamb
    if resistance <= 0:
        return None
    return 1.0 / resistance


def roof_bandwidth_u(
    layers_ins: List[Dict[str, Any]],
    layers_wood: List[Dict[str, Any]],
    f_values: Tuple[float, ...] = (0.07, 0.10, 0.15),
) -> Dict[str, Any]:
    u_ins = u_value_from_layers(layers_ins)
    u_wood = u_value_from_layers(layers_wood)
    if u_ins is None or u_wood is None:
        return {"status": "CLARIFY", "reason": "invalid_layers", "values": []}
    values = []
    for f in f_values:
        values.append({"f": f, "u": f * u_wood + (1.0 - f) * u_ins})
    return {"status": "OK", "reason": "bandwidth", "values": values}


def roof_decision_from_bandwidth(u_threshold: float, bandwidth: Dict[str, Any]) -> Dict[str, Any]:
    if bandwidth.get("status") != "OK":
        return {
            "status": "CLARIFY",
            "reason": "missing_or_invalid_wood_fraction_data",
            "questions": [
                "Bitte Sparrenbreite und Sparrenabstand angeben.",
                "Alternativ U-Wert-Nachweis nach Sanierung senden.",
            ],
        }
    values = [item["u"] for item in bandwidth.get("values", [])]
    if not values:
        return {"status": "CLARIFY", "reason": "missing_bandwidth_values", "questions": []}
    if max(values) <= u_threshold:
        return {"status": "PASS", "reason": "roof_bandwidth_pass"}
    if min(values) > u_threshold:
        return {"status": "FAIL", "reason": "roof_bandwidth_fail"}
    return {
        "status": "CLARIFY",
        "reason": "roof_bandwidth_uncertain",
        "questions": [
            "Bitte Sparrenbreite und Sparrenabstand angeben.",
            "Ist zusaetzliche Aufsparrendaemmung vorhanden?",
        ],
    }


def wall_worst_case_u(new_layers: List[Dict[str, Any]], rsi: float = R_SI, rse: float = R_SE) -> Optional[float]:
    if not new_layers:
        return None
    resistance = rsi + rse
    for layer in new_layers:
        d_m = parse_float(layer.get("d_m"))
        lamb = parse_float(layer.get("lambda"))
        if d_m is None or lamb is None or d_m <= 0 or lamb <= 0:
            return None
        resistance += d_m / lamb
    if resistance <= 0:
        return None
    return 1.0 / resistance


def wall_decision(u_threshold: float, direct_u: Optional[float], new_layers: List[Dict[str, Any]]) -> Dict[str, Any]:
    if direct_u is not None:
        return {
            "status": "PASS" if direct_u <= u_threshold else "FAIL",
            "reason": "wall_direct_u",
        }

    worst_case = wall_worst_case_u(new_layers)
    if worst_case is None:
        return {
            "status": "CLARIFY",
            "reason": "missing_wall_layers",
            "questions": [
                "Bitte U-Wert nach Sanierung ODER Daemmstaerke + Material (lambda) + Wandaufbau nachreichen."
            ],
        }

    if worst_case <= u_threshold:
        return {"status": "PASS", "reason": "wall_worst_case_pass", "u_upper": worst_case}

    return {
        "status": "CLARIFY",
        "reason": "wall_worst_case_uncertain",
        "u_upper": worst_case,
        "questions": [
            "Bitte Bestandswandaufbau (Material + Dicke) nachreichen.",
            "Oder Daemmstaerke erhoehen und neue Berechnung senden.",
        ],
    }


def derive_measure(measure: Dict[str, Any], threshold: Optional[float] = None) -> Dict[str, Any]:
    derived: Dict[str, Any] = {"calculated": False}
    component = measure.get("component_type", "")
    values = measure.get("values", {})

    if component == "fenster":
        uw = values.get("uw", {}).get("value")
        derived["uw"] = uw
        derived["u_value_target"] = uw
        derived["calculated"] = uw is not None
        return derived

    if measure.get("input_mode") == "layers":
        u_calc = u_value_from_layers(measure.get("layers", []))
        derived["u_value_target"] = u_calc
        derived["calculated"] = u_calc is not None
    else:
        direct = values.get("u_value_target", {}).get("value")
        derived["u_value_target"] = direct
        derived["calculated"] = direct is not None

    if component == "aussenwand" and threshold is not None:
        direct_u = values.get("u_value_target", {}).get("value")
        derived["wall_decision"] = wall_decision(threshold, direct_u, measure.get("layers", []))

    return derived
