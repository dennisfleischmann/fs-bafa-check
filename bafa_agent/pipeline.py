from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from .audit import persist_pipeline_artifacts
from .compiler import compile_measure_specs, compile_tables, save_compiled_outputs
from .communications import render_secretary_memo
from .engine import evaluate_case
from .escalation import build_escalation_ticket, should_escalate
from .extraction import extract_document
from .guards import (
    activation_guard,
    conflict_guard,
    coverage_guard,
    coverage_manifest_guard,
    coverage_manifest_report,
    evidence_binding_guard,
    threshold_guard,
)
from .intake import preflight
from .model_routing import select_model
from .offer_parser import parse_offer_text
from .requirements import snippets_to_requirements, write_requirements_jsonl, load_requirements_jsonl
from .snippets import detect_requirement_snippets
from .source import (
    BAFA_OVERVIEW_URL,
    build_manifest,
    bafa_source_registry,
    default_source_registry,
    load_manifest,
    load_source_registry,
    save_source_registry,
)
from .taxonomy import default_component_taxonomy, default_cost_taxonomy
from .utils import ensure_dir, read_json, utc_now_iso, write_json
from .validation import ensure_valid, validate_offer_facts
from .models import MeasureSpec

DEFAULT_MEASURE_THRESHOLDS: Dict[str, float] = {
    "envelope_aussenwand": 0.20,
    "envelope_dach": 0.14,
    "envelope_fenster": 0.95,
    "envelope_kellerdecke": 0.25,
}


def init_workspace(base_dir: str | Path) -> None:
    base = Path(base_dir)
    dirs = [
        base / "rules" / "tables",
        base / "rules" / "measures",
        base / "rules" / "taxonomy",
        base / "rules" / "evidence_store",
        base / "rules" / "bundles",
        base / "schemas",
        base / "data" / "cases",
        base / "data" / "logs",
    ]
    for item in dirs:
        ensure_dir(item)

    registry_path = base / "rules" / "source_registry.json"
    if not registry_path.exists():
        save_source_registry(registry_path, default_source_registry())

    write_json(base / "rules" / "taxonomy" / "components.json", default_component_taxonomy())
    write_json(base / "rules" / "taxonomy" / "cost_categories.json", default_cost_taxonomy())

    _write_default_measure_specs(base)
    _write_default_coverage_manifest(base)
    _write_schema_files(base)


def _write_default_measure_specs(base: Path) -> None:
    templates = {
        "envelope_aussenwand": 0.20,
        "envelope_dach": 0.14,
        "envelope_fenster": 0.95,
        "envelope_kellerdecke": 0.25,
    }
    for measure_id, threshold in templates.items():
        target = base / "rules" / "measures" / f"{measure_id}.json"
        if target.exists():
            continue
        spec = {
            "measure_id": measure_id,
            "module": "envelope",
            "title": measure_id.replace("_", " "),
            "version": "bootstrap",
            "legal_basis": [{"doc_id": "bootstrap", "section": "seed", "priority": 1}],
            "scope": {
                "component": measure_id.split("_", 1)[1],
                "requires_existing_building": True,
                "building_types": ["WG", "NWG"],
                "excludes_new_build": True,
            },
            "required_fields": [
                {"path": "offer.component_type", "severity_if_missing": "ABORT"},
                {"path": "building.is_existing", "severity_if_missing": "CLARIFY"},
            ],
            "eligibility": {
                "all_of": [{"field": "building.is_existing", "op": "==", "value": True}],
                "any_of": [],
                "exclusions": [],
            },
            "technical_requirements": {
                "thresholds": [
                    {
                        "name": "u_or_uw_max",
                        "condition": {
                            "field": "derived.u_value_target",
                            "op": "<=",
                            "value": threshold,
                            "unit": "W/(m2K)",
                            "severity_if_missing": "CLARIFY",
                            "evidence_required": True,
                        },
                    }
                ],
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
            "documentation": {
                "must_have": [{"doc": "Uwert_Nachweis_or_Layers", "severity_if_missing": "CLARIFY"}],
                "nice_to_have": [],
            },
            "outputs": {
                "messages": {
                    "pass_summary_key": "pass_generic",
                    "clarify_questions_keys": ["ask_u_value_or_layers"],
                }
            },
            "examples": {"eligible": [], "not_eligible": [], "clarify": []},
        }
        write_json(target, spec)


def _write_default_coverage_manifest(base: Path) -> None:
    coverage_manifest_path = base / "rules" / "coverage_manifest.json"
    if coverage_manifest_path.exists():
        return

    # Coverage targets derived from the Infoblatt TOC supplied in requirements.
    sections = [
        "1", "1.1", "1.2", "1.3", "1.3.1", "1.3.2", "1.3.3", "1.4", "1.5", "1.5.1", "1.5.2", "1.6", "1.7",
        "2", "2.1", "2.2", "2.3", "2.4", "2.5",
        "3", "3.1", "3.2", "3.3", "3.4", "3.5", "3.5.1", "3.5.2", "3.5.3", "3.5.4", "3.5.5", "3.6", "3.7", "3.8",
        "4", "4.1", "4.1.1", "4.1.2", "4.1.3", "4.1.4", "4.1.5", "4.1.6", "4.1.7", "4.1.8",
        "4.2", "4.2.1", "4.2.2", "4.2.3", "4.2.4", "4.2.5", "4.2.6", "4.2.7", "4.2.8", "4.2.9", "4.3",
        "5", "5.1", "5.2",
        "6", "6.1", "6.1.1", "6.1.2", "6.1.3", "6.1.4", "6.1.5", "6.1.6", "6.2", "6.3", "6.3.1", "6.3.2", "6.3.3", "6.3.4", "6.3.5",
        "7",
        "8",
        "9", "9.1", "9.2", "9.3", "9.4", "9.5", "9.6", "9.7",
    ]
    payload = {
        "source_doc_id": "infoblatt_sanieren",
        "sections": [{"section_id": section_id, "required": True} for section_id in sections],
    }
    write_json(coverage_manifest_path, payload)


def _write_schema_files(base: Path) -> None:
    offer_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "OfferFacts",
        "type": "object",
        "required": ["case_id", "building", "applicant", "offer", "docs"],
        "properties": {
            "case_id": {"type": "string"},
            "building": {"type": "object"},
            "applicant": {"type": "object"},
            "offer": {
                "type": "object",
                "required": ["measures"],
                "properties": {
                    "measures": {"type": "array"},
                },
            },
            "docs": {"type": "object"},
        },
    }
    evaluation_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Evaluation",
        "type": "object",
        "required": ["case_id", "generated_at", "ruleset_version", "results"],
        "properties": {
            "case_id": {"type": "string"},
            "generated_at": {"type": "string"},
            "ruleset_version": {"type": "string"},
            "results": {"type": "array"},
        },
    }
    write_json(base / "schemas" / "offer_facts.schema.json", offer_schema)
    write_json(base / "schemas" / "evaluation.schema.json", evaluation_schema)


def compile_rules(
    base_dir: str | Path,
    fetch: bool = False,
    source: str = "local",
    source_url: str = BAFA_OVERVIEW_URL,
) -> Dict[str, Any]:
    base = Path(base_dir)
    init_workspace(base)

    registry_path = base / "rules" / "source_registry.json"
    if source == "bafa":
        registry = bafa_source_registry(source_url=source_url)
        save_source_registry(registry_path, registry)
        fetch = True
    elif source == "local-default":
        registry = default_source_registry()
        save_source_registry(registry_path, registry)
    else:
        registry = load_source_registry(registry_path)

    manifest = build_manifest(
        registry=registry,
        download_dir=base / "rules" / "source_docs",
        manifest_path=base / "rules" / "manifest.json",
        fetch=fetch,
    )

    requirements_path = base / "rules" / "requirements.jsonl"
    if requirements_path.exists():
        requirements_path.unlink()

    all_requirements: List[Dict[str, Any]] = []
    for doc in manifest.docs:
        extracted = extract_document(doc.local_path, doc.doc_id)
        snippets = detect_requirement_snippets(extracted)
        component = "aussenwand"
        measure = "envelope_aussenwand"
        if "fenster" in doc.doc_id:
            component, measure = "fenster", "envelope_fenster"
        elif "dach" in doc.doc_id:
            component, measure = "dach", "envelope_dach"
        records = snippets_to_requirements(
            snippets,
            measure_id=measure,
            component=component,
            priority=doc.priority,
        )
        all_requirements.extend(records)

    write_requirements_jsonl(str(requirements_path), all_requirements)
    loaded_requirements = load_requirements_jsonl(str(requirements_path))
    coverage_manifest = read_json(base / "rules" / "coverage_manifest.json", default={"sections": []})
    coverage_report = coverage_manifest_report(
        loaded_requirements,
        coverage_manifest,
        source_doc_id=coverage_manifest.get("source_doc_id", "infoblatt_sanieren"),
    )

    measures = compile_measure_specs(loaded_requirements, version=utc_now_iso())
    existing_measures: Dict[str, Dict[str, Any]] = {}
    for path in (base / "rules" / "measures").glob("*.json"):
        payload = read_json(path, default={})
        if isinstance(payload, dict) and payload.get("measure_id"):
            existing_measures[payload["measure_id"]] = payload

    # Merge compiled specs into existing specs while preserving bootstrap thresholds
    # when extraction produced no TECH_THRESHOLD records for a measure.
    for measure_id, compiled_spec in measures.items():
        existing = existing_measures.get(measure_id, {})
        compiled_technical = compiled_spec.get("technical_requirements", {})
        compiled_thresholds = (
            compiled_technical.get("thresholds", [])
            if isinstance(compiled_technical, dict)
            else []
        )
        if not compiled_thresholds and isinstance(existing, dict):
            existing_technical = existing.get("technical_requirements", {})
            existing_thresholds = (
                existing_technical.get("thresholds", [])
                if isinstance(existing_technical, dict)
                else []
            )
            if existing_thresholds:
                compiled_spec.setdefault("technical_requirements", {})
                if isinstance(compiled_spec["technical_requirements"], dict):
                    compiled_spec["technical_requirements"]["thresholds"] = existing_thresholds
                    if not compiled_spec["technical_requirements"].get("calculation_methods"):
                        compiled_spec["technical_requirements"]["calculation_methods"] = (
                            existing_technical.get("calculation_methods", [])
                            if isinstance(existing_technical, dict)
                            else []
                        )
            else:
                default_threshold = DEFAULT_MEASURE_THRESHOLDS.get(measure_id)
                if default_threshold is not None:
                    compiled_spec.setdefault("technical_requirements", {})
                    if isinstance(compiled_spec["technical_requirements"], dict):
                        compiled_spec["technical_requirements"]["thresholds"] = [
                            {
                                "name": "u_or_uw_max",
                                "condition": {
                                    "field": "derived.u_value_target",
                                    "op": "<=",
                                    "value": default_threshold,
                                    "unit": "W/(m2K)",
                                    "severity_if_missing": "CLARIFY",
                                    "evidence_required": True,
                                },
                            }
                        ]
                        if not compiled_spec["technical_requirements"].get("calculation_methods"):
                            compiled_spec["technical_requirements"]["calculation_methods"] = []

        existing_measures[measure_id] = compiled_spec

    # Ensure all core envelope measures have at least one numeric threshold.
    for measure_id, default_threshold in DEFAULT_MEASURE_THRESHOLDS.items():
        spec = existing_measures.get(measure_id)
        if not isinstance(spec, dict):
            continue
        technical = spec.get("technical_requirements", {})
        if not isinstance(technical, dict):
            technical = {}
            spec["technical_requirements"] = technical
        thresholds = technical.get("thresholds", [])
        if not isinstance(thresholds, list) or not thresholds:
            technical["thresholds"] = [
                {
                    "name": "u_or_uw_max",
                    "condition": {
                        "field": "derived.u_value_target",
                        "op": "<=",
                        "value": default_threshold,
                        "unit": "W/(m2K)",
                        "severity_if_missing": "CLARIFY",
                        "evidence_required": True,
                    },
                }
            ]
            if not isinstance(technical.get("calculation_methods"), list):
                technical["calculation_methods"] = []

    measures = existing_measures
    tables = compile_tables(loaded_requirements)
    taxonomy = {
        "components": default_component_taxonomy(),
        "cost_categories": default_cost_taxonomy(),
    }

    bundle = save_compiled_outputs(
        manifest_path=str(base / "rules" / "manifest.json"),
        measures=measures,
        tables=tables,
        taxonomy=taxonomy,
        measures_dir=str(base / "rules" / "measures"),
        tables_path=str(base / "rules" / "tables" / "tma_thresholds.json"),
        bundle_path=str(base / "rules" / "bundles" / "ruleset.bundle.json"),
    )

    guard_results = [
        evidence_binding_guard(loaded_requirements),
        conflict_guard(loaded_requirements),
        coverage_manifest_guard(
            loaded_requirements,
            coverage_manifest,
            source_doc_id=coverage_manifest.get("source_doc_id", "infoblatt_sanieren"),
        ),
        coverage_guard(
            measures,
            required_components={"aussenwand", "dach", "fenster", "kellerdecke"},
        ),
        threshold_guard(
            measures,
            required_measure_ids={
                "envelope_aussenwand",
                "envelope_dach",
                "envelope_fenster",
                "envelope_kellerdecke",
            },
        ),
    ]
    activation = activation_guard(guard_results)

    build_report = {
        "validation_passed": activation.ok,
        "errors": activation.errors,
        "warnings": activation.warnings,
        "bundle_path": str(base / "rules" / "bundles" / "ruleset.bundle.json"),
        "source_mode": source,
        "source_url": source_url if source == "bafa" else None,
        "fetched": fetch,
        "coverage_manifest": coverage_report,
    }
    write_json(base / "rules" / "build_report.json", build_report)

    if activation.ok:
        write_json(base / "rules" / "bundles" / "ruleset.active.json", bundle)

    return build_report


def load_measure_specs(base_dir: str | Path) -> Dict[str, MeasureSpec]:
    base = Path(base_dir)
    specs: Dict[str, MeasureSpec] = {}
    for path in (base / "rules" / "measures").glob("*.json"):
        payload = read_json(path, default={})
        if not payload:
            continue
        spec = MeasureSpec.from_dict(payload)
        specs[spec.measure_id] = spec
    return specs


def evaluate_offer(base_dir: str | Path, offer_path: str | Path) -> Dict[str, Any]:
    base = Path(base_dir)
    init_workspace(base)
    preflight_payload = preflight([str(offer_path)])

    parsed_offer = parse_offer_text(offer_path)
    parsed_offer["case_id"] = preflight_payload["case_id"]
    parsed_offer["quality_flags"] = preflight_payload["quality_flags"]

    ensure_valid(validate_offer_facts(parsed_offer))

    specs = load_measure_specs(base)
    report = evaluate_case(parsed_offer, specs, ruleset_version="active")
    payload = report.to_dict()

    derived_payload = {"notes": "derived values are embedded in evaluation decisions"}
    persist_pipeline_artifacts(
        base / "data" / "cases",
        parsed_offer["case_id"],
        parsed_offer,
        derived_payload,
        payload,
    )

    write_json(base / "data" / "cases" / parsed_offer["case_id"] / "evaluation.json", payload)
    memo = render_secretary_memo(payload)
    (base / "data" / "cases" / parsed_offer["case_id"] / "memo.txt").write_text(memo, encoding="utf-8")

    route = select_model(preflight_payload["quality_flags"], contradictions=False, ambiguity=False)
    write_json(base / "data" / "cases" / parsed_offer["case_id"] / "model_route.json", route)

    if should_escalate(payload, preflight_payload["quality_flags"]):
        ticket = build_escalation_ticket(parsed_offer["case_id"], payload, preflight_payload["quality_flags"])
        write_json(
            base / "data" / "cases" / parsed_offer["case_id"] / "escalation.json",
            {
                "case_id": ticket.case_id,
                "reasons": ticket.reasons,
                "severity": ticket.severity,
                "payload": ticket.payload,
            },
        )

    return payload


def load_active_bundle(base_dir: str | Path) -> Dict[str, Any]:
    base = Path(base_dir)
    return read_json(base / "rules" / "bundles" / "ruleset.active.json", default={})


def load_manifest_safe(base_dir: str | Path) -> Dict[str, Any]:
    base = Path(base_dir)
    manifest = load_manifest(base / "rules" / "manifest.json")
    return {
        "generated_at": manifest.generated_at,
        "docs": [doc.__dict__ for doc in manifest.docs],
    }
