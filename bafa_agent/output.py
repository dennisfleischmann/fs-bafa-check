from __future__ import annotations

from typing import Any, Dict

from .models import EvaluationReport
from .utils import write_json
from .validation import validate_evaluation


def build_evaluation_payload(report: EvaluationReport) -> Dict[str, Any]:
    return report.to_dict()


def save_evaluation(path: str, report: EvaluationReport) -> Dict[str, Any]:
    payload = build_evaluation_payload(report)
    validation = validate_evaluation(payload)
    if not validation.ok:
        raise ValueError("evaluation invalid: " + "; ".join(validation.errors))
    write_json(path, payload)
    return payload
