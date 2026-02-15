from __future__ import annotations

from typing import Any, Dict, List

from .models import EscalationTicket


def risk_score(evaluation: Dict[str, Any], quality_flags: List[str]) -> float:
    score = 0.0
    for result in evaluation.get("results", []):
        status = result.get("status")
        if status == "CLARIFY":
            score += 0.20
        elif status == "ABORT":
            score += 0.40
        elif status == "FAIL":
            score += 0.10
    if "ocr_required" in quality_flags:
        score += 0.15
    if "unknown_doc_type" in quality_flags:
        score += 0.20
    return min(1.0, round(score, 2))


def should_escalate(
    evaluation: Dict[str, Any],
    quality_flags: List[str],
    threshold: float = 0.30,
) -> bool:
    return risk_score(evaluation, quality_flags) >= threshold


def build_escalation_ticket(
    case_id: str,
    evaluation: Dict[str, Any],
    quality_flags: List[str],
) -> EscalationTicket:
    reasons: List[str] = []
    for result in evaluation.get("results", []):
        if result.get("status") in {"CLARIFY", "ABORT"}:
            reasons.append(f"{result.get('measure_id')}: {result.get('reason')}")
    for flag in quality_flags:
        reasons.append(f"quality:{flag}")
    score = risk_score(evaluation, quality_flags)
    severity = "high" if score >= 0.5 else "medium"
    return EscalationTicket(
        case_id=case_id,
        reasons=reasons,
        severity=severity,
        payload={"risk_score": score, "evaluation": evaluation},
    )
