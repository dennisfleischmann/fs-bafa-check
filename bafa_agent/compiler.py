from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Tuple

from .utils import write_json


def _req_to_condition(req: Dict[str, Any]) -> Dict[str, Any]:
    rule = req.get("rule", {})
    if not isinstance(rule, dict):
        return {}
    if "field" in rule and "op" in rule:
        return {
            "field": rule.get("field"),
            "op": rule.get("op"),
            "value": rule.get("value"),
            "unit": rule.get("unit"),
            "severity_if_missing": req.get("severity_if_missing", "CLARIFY"),
            "evidence_required": True,
        }
    return {}


def compile_measure_specs(requirements: List[Dict[str, Any]], version: str) -> Dict[str, Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for req in requirements:
        measure = req.get("scope", {}).get("measure")
        if not measure:
            continue
        grouped[measure].append(req)

    compiled: Dict[str, Dict[str, Any]] = {}
    for measure_id, reqs in grouped.items():
        conditions: List[Dict[str, Any]] = []
        exclusions: List[Dict[str, Any]] = []
        documentation: List[Dict[str, Any]] = []
        component = reqs[0].get("scope", {}).get("component", "unknown")
        required_fields = [
            {"path": "offer.component_type", "severity_if_missing": "ABORT"},
            {"path": "offer.input_mode", "severity_if_missing": "CLARIFY"},
        ]

        for req in reqs:
            req_type = req.get("req_type")
            if req_type == "TECH_THRESHOLD":
                condition = _req_to_condition(req)
                if condition:
                    conditions.append(condition)
            elif req_type == "EXCLUSION":
                exclusions.append(
                    {
                        "when_all_of": [{"field": "derived.exclusion_hit", "op": "==", "value": True}],
                        "result": "CLARIFY",
                        "message_key": "clarify_exclusion",
                    }
                )
            elif req_type == "DOC_REQUIREMENT":
                documentation.append(
                    {
                        "doc": "supporting_document",
                        "severity_if_missing": req.get("severity_if_missing", "CLARIFY"),
                    }
                )

        compiled[measure_id] = {
            "measure_id": measure_id,
            "module": "envelope",
            "title": measure_id.replace("_", " ").title(),
            "version": version,
            "legal_basis": [{"doc_id": "compiled", "section": "auto", "priority": 100}],
            "scope": {
                "component": component,
                "requires_existing_building": True,
                "building_types": ["WG", "NWG"],
                "excludes_new_build": True,
            },
            "required_fields": required_fields,
            "eligibility": {
                "all_of": [{"field": "building.is_existing", "op": "==", "value": True}],
                "any_of": [],
                "exclusions": exclusions,
            },
            "technical_requirements": {
                "thresholds": [{"name": "threshold", "condition": c} for c in conditions],
                "calculation_methods": [],
            },
            "cost_rules": {
                "eligible_cost_categories": ["material", "montage"],
                "ineligible_cost_categories": ["finanzierung", "wartung", "eigenleistung"],
                "split_rules": [
                    {
                        "when": {"field": "line_item.category", "op": "==", "value": "geruest"},
                        "result": "ELIGIBLE_IF_NECESSARY",
                    }
                ],
            },
            "documentation": {"must_have": documentation, "nice_to_have": []},
            "outputs": {
                "messages": {
                    "pass_summary_key": "pass_default",
                    "clarify_questions_keys": ["ask_missing_documents"],
                }
            },
            "examples": {
                "eligible": [],
                "not_eligible": [],
                "clarify": [],
            },
        }
    return compiled


def compile_tables(requirements: List[Dict[str, Any]]) -> Dict[str, Any]:
    rows = []
    for req in requirements:
        if req.get("req_type") != "TECH_THRESHOLD":
            continue
        rule = req.get("rule", {})
        if not rule:
            continue
        rows.append(
            {
                "component": req.get("scope", {}).get("component", "unknown"),
                "case": req.get("scope", {}).get("case", "default"),
                "field": rule.get("field"),
                "op": rule.get("op"),
                "value": rule.get("value"),
                "unit": rule.get("unit"),
                "evidence": req.get("evidence", []),
            }
        )
    return {"tma": {"thresholds": rows}}


def compile_bundle(
    manifest: Dict[str, Any],
    measures: Dict[str, Dict[str, Any]],
    tables: Dict[str, Any],
    taxonomy: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "bundle_meta": {
            "manifest_generated_at": manifest.get("generated_at"),
            "doc_count": len(manifest.get("docs", [])),
        },
        "measures": measures,
        "tables": tables,
        "taxonomy": taxonomy,
    }


def save_compiled_outputs(
    manifest_path: str,
    measures: Dict[str, Dict[str, Any]],
    tables: Dict[str, Any],
    taxonomy: Dict[str, Any],
    measures_dir: str,
    tables_path: str,
    bundle_path: str,
) -> Dict[str, Any]:
    manifest = {"generated_at": "", "docs": []}
    try:
        from .utils import read_json

        loaded = read_json(manifest_path, default={})
        if isinstance(loaded, dict):
            manifest = loaded
    except Exception:
        pass

    for measure_id, spec in measures.items():
        write_json(f"{measures_dir}/{measure_id}.json", spec)
    write_json(tables_path, tables)
    bundle = compile_bundle(manifest, measures, tables, taxonomy)
    write_json(bundle_path, bundle)
    return bundle


def detect_conflicts(requirements: List[Dict[str, Any]]) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
    index: Dict[tuple, Dict[str, Any]] = {}
    conflicts: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    for req in requirements:
        if req.get("req_type") != "TECH_THRESHOLD":
            continue
        scope = req.get("scope", {})
        rule = req.get("rule", {})
        key = (scope.get("measure"), scope.get("component"), rule.get("field"), rule.get("op"))
        existing = index.get(key)
        if existing is None:
            index[key] = req
            continue
        old_value = existing.get("rule", {}).get("value")
        new_value = rule.get("value")
        if old_value != new_value:
            conflicts.append((existing, req))
            if req.get("priority", 0) >= existing.get("priority", 0):
                index[key] = req
    return conflicts
