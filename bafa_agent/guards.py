from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Set

from .compiler import detect_conflicts
from .utils import parse_float


@dataclass
class GuardResult:
    ok: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def evidence_binding_guard(requirements: Iterable[Dict[str, Any]]) -> GuardResult:
    errors: List[str] = []
    warnings: List[str] = []
    for req in requirements:
        req_id = req.get("req_id", "unknown")
        rule = req.get("rule", {})
        evidence = req.get("evidence", [])
        if req.get("req_type") == "TECH_THRESHOLD":
            value = rule.get("value")
            if value is None:
                warnings.append(f"{req_id}: threshold without numeric value")
                continue
            numeric = parse_float(value)
            if numeric is None:
                errors.append(f"{req_id}: threshold value is not numeric")
                continue
            if not evidence:
                errors.append(f"{req_id}: missing evidence")
                continue
            token = str(numeric).rstrip("0").rstrip(".")
            found = False
            for ev in evidence:
                quote = str(ev.get("quote", ""))
                quote_norm = quote.replace(",", ".")
                if token in quote_norm:
                    found = True
                    break
            if not found:
                errors.append(f"{req_id}: threshold token {token} missing in evidence quote")
    return GuardResult(ok=not errors, errors=errors, warnings=warnings)


def coverage_guard(measures: Dict[str, Dict[str, Any]], required_components: Iterable[str]) -> GuardResult:
    required = set(required_components)
    present: Set[str] = set()
    for _, spec in measures.items():
        component = spec.get("scope", {}).get("component")
        if isinstance(component, str):
            present.add(component)
    missing = sorted(required - present)
    if missing:
        return GuardResult(ok=False, errors=[f"missing coverage components: {', '.join(missing)}"])
    return GuardResult(ok=True)


def conflict_guard(requirements: List[Dict[str, Any]]) -> GuardResult:
    conflicts = detect_conflicts(requirements)
    if not conflicts:
        return GuardResult(ok=True)
    errors = []
    for old_req, new_req in conflicts:
        errors.append(
            "conflict: "
            f"{old_req.get('req_id')} value={old_req.get('rule', {}).get('value')} "
            f"vs {new_req.get('req_id')} value={new_req.get('rule', {}).get('value')}"
        )
    return GuardResult(ok=False, errors=errors)


def activation_guard(guard_results: Iterable[GuardResult]) -> GuardResult:
    all_errors: List[str] = []
    all_warnings: List[str] = []
    for result in guard_results:
        all_errors.extend(result.errors)
        all_warnings.extend(result.warnings)
    return GuardResult(ok=not all_errors, errors=all_errors, warnings=all_warnings)
