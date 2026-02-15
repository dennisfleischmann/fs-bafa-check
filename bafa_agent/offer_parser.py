from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .normalization import normalize_measure_values
from .taxonomy import map_component, map_cost_category
from .utils import parse_float, read_text

U_PATTERN = re.compile(r"\bU\w*\s*[=:]?\s*([0-9]+[.,]?[0-9]*)\s*W", flags=re.IGNORECASE)
UW_PATTERN = re.compile(r"\bUw\s*[=:]?\s*([0-9]+[.,]?[0-9]*)\s*W", flags=re.IGNORECASE)
LAMBDA_PATTERN = re.compile(r"(?:lambda|wls)\s*([0-9]+[.,]?[0-9]*)", flags=re.IGNORECASE)
THICKNESS_PATTERN = re.compile(r"([0-9]+[.,]?[0-9]*)\s*(mm|cm|m)\b", flags=re.IGNORECASE)
AMOUNT_PATTERN = re.compile(r"([0-9]+[.,]?[0-9]*)\s*EUR", flags=re.IGNORECASE)


def _to_meters(value: float, unit: str) -> Optional[float]:
    if unit == "m":
        return value
    if unit == "cm":
        return value / 100.0
    if unit == "mm":
        return value / 1000.0
    return None


def _extract_values(line: str) -> Dict[str, Any]:
    values: Dict[str, Any] = {}
    uw_match = UW_PATTERN.search(line)
    if uw_match:
        values["uw"] = {
            "value": parse_float(uw_match.group(1)),
            "unit": "W/(m2K)",
            "evidence": line,
        }
    else:
        u_match = U_PATTERN.search(line)
        if u_match:
            values["u_value_target"] = {
                "value": parse_float(u_match.group(1)),
                "unit": "W/(m2K)",
                "evidence": line,
            }

    lamb_match = LAMBDA_PATTERN.search(line)
    thick_match = THICKNESS_PATTERN.search(line)
    if lamb_match and thick_match:
        lamb = parse_float(lamb_match.group(1))
        thickness = parse_float(thick_match.group(1))
        unit = thick_match.group(2).lower()
        d_m = _to_meters(thickness or 0.0, unit)
        if d_m is not None:
            values.setdefault("layers", []).append(
                {
                    "name": "layer",
                    "d_m": d_m,
                    "lambda": lamb,
                    "evidence": line,
                }
            )
    return values


def parse_offer_text(path: str | Path) -> Dict[str, Any]:
    content = read_text(path)
    measures: Dict[str, Dict[str, Any]] = {}

    for raw in content.splitlines():
        line = raw.strip()
        if not line:
            continue
        component = map_component(line)
        amount_match = AMOUNT_PATTERN.search(line)
        amount = parse_float(amount_match.group(1)) if amount_match else None
        category = map_cost_category(line) or "material"

        if component is None:
            continue

        bucket = measures.setdefault(
            component,
            {
                "measure_id": f"envelope_{component}",
                "component_type": component,
                "input_mode": "direct_u",
                "values": {},
                "layers": [],
                "geometry": {},
                "costs": {"total": 0.0, "currency": "EUR"},
                "line_items": [],
                "evidence": [],
            },
        )

        extracted = _extract_values(line)
        if "uw" in extracted:
            bucket["values"]["uw"] = extracted["uw"]
        if "u_value_target" in extracted:
            bucket["values"]["u_value_target"] = extracted["u_value_target"]
        layers = extracted.get("layers", [])
        if layers:
            bucket["input_mode"] = "layers"
            bucket["layers"].extend(layers)

        if amount is not None:
            bucket["costs"]["total"] += amount
            bucket["line_items"].append(
                {
                    "description": line,
                    "amount": amount,
                    "currency": "EUR",
                    "category": category,
                }
            )
        bucket["evidence"].append({"quote": line})

    normalized_measures: List[Dict[str, Any]] = []
    for measure in measures.values():
        normalized_measures.append(normalize_measure_values(measure))

    return {
        "building": {"is_existing": True, "type": "WG", "monument": False},
        "applicant": {"income_bonus_requested": False},
        "offer": {
            "input_mode": "mixed",
            "measures": normalized_measures,
        },
        "docs": {
            "fachunternehmererklaerung_present": False,
            "tauwassernachweis_present": None,
        },
    }
