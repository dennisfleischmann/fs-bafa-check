from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List


@dataclass
class ValidationResult:
    ok: bool
    errors: List[str] = field(default_factory=list)


REQUIRED_TOP_LEVEL_OFFER_FACTS = ["case_id", "building", "applicant", "offer", "docs"]
REQUIRED_TOP_LEVEL_EVALUATION = ["case_id", "generated_at", "ruleset_version", "results"]


def _assert_keys(payload: Dict[str, Any], keys: Iterable[str], prefix: str = "") -> List[str]:
    errors: List[str] = []
    for key in keys:
        if key not in payload:
            pfx = f"{prefix}." if prefix else ""
            errors.append(f"missing key: {pfx}{key}")
    return errors


def validate_offer_facts(payload: Dict[str, Any]) -> ValidationResult:
    errors = _assert_keys(payload, REQUIRED_TOP_LEVEL_OFFER_FACTS)
    offer = payload.get("offer", {})
    if not isinstance(offer, dict):
        errors.append("offer must be object")
        return ValidationResult(ok=False, errors=errors)
    if "measures" not in offer:
        errors.append("missing key: offer.measures")
    elif not isinstance(offer["measures"], list):
        errors.append("offer.measures must be array")
    else:
        for idx, measure in enumerate(offer["measures"]):
            if not isinstance(measure, dict):
                errors.append(f"offer.measures[{idx}] must be object")
                continue
            for key in ["component_type", "input_mode"]:
                if key not in measure:
                    errors.append(f"missing key: offer.measures[{idx}].{key}")
            if "evidence" in measure and not isinstance(measure["evidence"], list):
                errors.append(f"offer.measures[{idx}].evidence must be array")
    return ValidationResult(ok=not errors, errors=errors)


def validate_evaluation(payload: Dict[str, Any]) -> ValidationResult:
    errors = _assert_keys(payload, REQUIRED_TOP_LEVEL_EVALUATION)
    results = payload.get("results", [])
    if not isinstance(results, list):
        errors.append("results must be array")
        return ValidationResult(ok=False, errors=errors)
    valid_statuses = {"PASS", "FAIL", "CLARIFY", "ABORT"}
    for idx, result in enumerate(results):
        if not isinstance(result, dict):
            errors.append(f"results[{idx}] must be object")
            continue
        for key in ["measure_id", "status", "reason"]:
            if key not in result:
                errors.append(f"missing key: results[{idx}].{key}")
        status = result.get("status")
        if status is not None and status not in valid_statuses:
            errors.append(f"invalid status at results[{idx}]: {status}")
    return ValidationResult(ok=not errors, errors=errors)


def ensure_valid(result: ValidationResult) -> None:
    if not result.ok:
        raise ValueError("; ".join(result.errors))
