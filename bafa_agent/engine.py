from __future__ import annotations

from typing import Any, Dict, List, Optional

from .costs import evaluate_costs
from .derived import derive_measure
from .models import DecisionStatus, EvaluationReport, EvaluationResult, Evidence, MeasureSpec, Severity
from .utils import dotted_get, utc_now_iso


def _compare(left: Any, op: str, right: Any) -> bool:
    if op == "==":
        return left == right
    if op == "!=":
        return left != right
    if op == "<=":
        return left is not None and right is not None and left <= right
    if op == "<":
        return left is not None and right is not None and left < right
    if op == ">=":
        return left is not None and right is not None and left >= right
    if op == ">":
        return left is not None and right is not None and left > right
    return False


def _severity_to_status(severity: Severity) -> DecisionStatus:
    if severity == Severity.ABORT:
        return DecisionStatus.ABORT
    if severity == Severity.FAIL:
        return DecisionStatus.FAIL
    if severity == Severity.PASS:
        return DecisionStatus.PASS
    return DecisionStatus.CLARIFY


def _extract_evidence(measure: Dict[str, Any]) -> List[Evidence]:
    evidence: List[Evidence] = []
    for idx, ev in enumerate(measure.get("evidence", []), start=1):
        quote = ev.get("quote") or ""
        evidence.append(
            Evidence(
                doc_id=ev.get("doc_id", "offer"),
                page=int(ev.get("page", 1)),
                quote=quote,
                bbox=ev.get("bbox"),
                source_path=ev.get("source_path"),
            )
        )
    return evidence


def evaluate_measure(
    case_context: Dict[str, Any],
    measure: Dict[str, Any],
    spec: Optional[MeasureSpec],
    threshold_defaults: Optional[Dict[str, float]] = None,
) -> EvaluationResult:
    measure_id = measure.get("measure_id", "unknown_measure")
    evidence = _extract_evidence(measure)

    if spec is None:
        return EvaluationResult(
            measure_id=measure_id,
            status=DecisionStatus.CLARIFY,
            reason="missing_measure_spec",
            used_evidence=evidence,
            questions=["Massnahme konnte keinem Regelpaket zugeordnet werden."],
        )

    merged_context = dict(case_context)
    merged_context["offer"] = measure

    for req in spec.required_fields:
        value = dotted_get(merged_context, req.path)
        if value in (None, "", [], {}):
            status = _severity_to_status(req.severity_if_missing)
            return EvaluationResult(
                measure_id=measure_id,
                status=status,
                reason=f"missing_required_field:{req.path}",
                used_evidence=evidence,
                questions=[f"Bitte Feld nachreichen: {req.path}"],
            )

    for rule in spec.eligibility.get("all_of", []):
        left = dotted_get(merged_context, rule.get("field", ""))
        if not _compare(left, rule.get("op", "=="), rule.get("value")):
            return EvaluationResult(
                measure_id=measure_id,
                status=DecisionStatus.FAIL,
                reason=f"eligibility_failed:{rule.get('field')}",
                used_evidence=evidence,
                questions=[],
            )

    thresholds = spec.technical_requirements.thresholds
    derived = derive_measure(measure, threshold=(threshold_defaults or {}).get("wall", 0.2))
    merged_context["derived"] = derived

    for threshold in thresholds:
        condition = threshold.get("condition", {})
        field = condition.get("field")
        op = condition.get("op")
        expected = condition.get("value")
        current = dotted_get(merged_context, field)

        if current is None:
            severity = Severity(condition.get("severity_if_missing", "CLARIFY"))
            return EvaluationResult(
                measure_id=measure_id,
                status=_severity_to_status(severity),
                reason=f"missing_threshold_value:{field}",
                used_evidence=evidence,
                questions=[f"Bitte Nachweis fuer {field} nachreichen."],
            )

        if not _compare(current, op, expected):
            return EvaluationResult(
                measure_id=measure_id,
                status=DecisionStatus.FAIL,
                reason=f"threshold_failed:{field}",
                used_evidence=evidence,
                questions=[],
            )

    cost_summary = evaluate_costs(measure, spec.cost_rules.__dict__)

    return EvaluationResult(
        measure_id=measure_id,
        status=DecisionStatus.PASS,
        reason="all_checks_passed",
        used_evidence=evidence,
        questions=[],
        cost_summary=cost_summary,
    )


def evaluate_case(
    offer_facts: Dict[str, Any],
    measure_specs: Dict[str, MeasureSpec],
    ruleset_version: str,
) -> EvaluationReport:
    case_id = offer_facts.get("case_id", "unknown_case")
    context = {
        "building": offer_facts.get("building", {}),
        "applicant": offer_facts.get("applicant", {}),
        "docs": offer_facts.get("docs", {}),
    }

    results: List[EvaluationResult] = []
    for measure in offer_facts.get("offer", {}).get("measures", []):
        measure_id = measure.get("measure_id")
        spec = measure_specs.get(measure_id)
        result = evaluate_measure(context, measure, spec)
        results.append(result)

    return EvaluationReport(
        case_id=case_id,
        results=results,
        generated_at=utc_now_iso(),
        ruleset_version=ruleset_version,
    )
