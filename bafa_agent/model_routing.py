from __future__ import annotations

from typing import Dict, List


def select_model(
    quality_flags: List[str],
    contradictions: bool,
    ambiguity: bool,
    default_model: str = "gpt-5-mini",
    escalation_model: str = "gpt-5.2",
) -> Dict[str, str]:
    reasons: List[str] = []
    chosen = default_model

    if contradictions:
        chosen = escalation_model
        reasons.append("contradictions_detected")
    if ambiguity:
        chosen = escalation_model
        reasons.append("ambiguous_mapping")
    if "ocr_required" in quality_flags:
        reasons.append("ocr_before_structured_output")

    return {
        "model": chosen,
        "default_model": default_model,
        "escalation_model": escalation_model,
        "reason": ", ".join(reasons) if reasons else "default_path",
    }
