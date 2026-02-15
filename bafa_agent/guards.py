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


def coverage_manifest_report(
    requirements: Iterable[Dict[str, Any]],
    manifest: Dict[str, Any],
    source_doc_id: str = "infoblatt_sanieren",
) -> Dict[str, Any]:
    sections = manifest.get("sections", [])
    required_sections = sorted(
        {
            str(item.get("section_id"))
            for item in sections
            if item.get("required", True) and item.get("section_id")
        }
    )
    represented_sections: Set[str] = set()
    for req in requirements:
        scope = req.get("scope", {})
        if scope.get("source_doc_id") != source_doc_id:
            continue
        section_id = scope.get("section_id")
        if section_id:
            represented_sections.add(str(section_id))

    missing = sorted(set(required_sections) - represented_sections)
    return {
        "source_doc_id": source_doc_id,
        "required_count": len(required_sections),
        "represented_count": len(represented_sections),
        "missing_count": len(missing),
        "required_sections": required_sections,
        "represented_sections": sorted(represented_sections),
        "missing_sections": missing,
    }


def coverage_manifest_guard(
    requirements: Iterable[Dict[str, Any]],
    manifest: Dict[str, Any],
    source_doc_id: str = "infoblatt_sanieren",
) -> GuardResult:
    report = coverage_manifest_report(requirements, manifest, source_doc_id=source_doc_id)
    if report["missing_count"] > 0:
        return GuardResult(
            ok=False,
            errors=[
                (
                    f"coverage_manifest_missing_sections:{source_doc_id}:"
                    + ",".join(report["missing_sections"])
                )
            ],
        )
    return GuardResult(ok=True)
