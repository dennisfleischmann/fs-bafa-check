from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from .snippets import RequirementSnippet
from .utils import append_jsonl, normalize_decimal, parse_float, read_jsonl


THRESHOLD_PATTERN = re.compile(r"([a-zA-Z_]+)?\s*([<>]=?)\s*([0-9]+[.,]?[0-9]*)")
U_VALUE_PATTERN = re.compile(r"([0-9]+[.,]?[0-9]*)\s*(w\/?\(?m2k\)?)", flags=re.IGNORECASE)
FENSTER_TOKENS = (
    "fenster",
    "uw",
    "einbaufuge",
    "anschlussfuge",
    "fensteranschlussfuge",
    "fensteranschlussfugen",
    "fugendichtheit",
    "abdichtung der fugen",
)
AUSSENWAND_TOKENS = ("aussenwand", "außenwand", "fassade", "wdvs", "wanddaemmung", "wanddämmung")
DACH_TOKENS = ("dach", "steildach", "flachdach", "oberste geschossdecke", "ogd")
KELLERDECKE_TOKENS = ("kellerdecke", "bodenplatte")
COST_RULE_TOKENS = ("einbaufuge", "anschlussfuge", "fugendichtheit", "abdichtung der fugen", "fugen")


def _infer_req_type(quote: str) -> str:
    q = quote.lower()
    normalized = normalize_decimal(q)
    has_numeric_threshold = bool(THRESHOLD_PATTERN.search(normalized) or U_VALUE_PATTERN.search(normalized))
    if any(token in q for token in COST_RULE_TOKENS):
        return "COST_ELIGIBILITY"
    if "nicht foerderfaehig" in q:
        return "EXCLUSION"
    if "foerderfaehig" in q and not has_numeric_threshold:
        return "ELIGIBILITY"
    if "kosten" in q:
        return "COST_ELIGIBILITY"
    if "nachweis" in q:
        return "DOC_REQUIREMENT"
    if has_numeric_threshold:
        return "TECH_THRESHOLD"
    return "PROCESS_RULE"


def _extract_threshold(quote: str) -> Dict[str, Any]:
    normalized = normalize_decimal(quote)
    match = THRESHOLD_PATTERN.search(normalized)
    if match:
        _, op, value = match.groups()
        return {
            "field": "derived.u_value_target",
            "op": op,
            "value": parse_float(value),
            "unit": "W/(m2K)",
        }
    u_match = U_VALUE_PATTERN.search(normalized)
    if u_match:
        value, _ = u_match.groups()
        return {
            "field": "derived.u_value_target",
            "op": "<=",
            "value": parse_float(value),
            "unit": "W/(m2K)",
        }
    return {}


def _infer_scope(quote: str, default_measure: str, default_component: str) -> Tuple[str, str]:
    q = quote.lower()
    if any(token in q for token in FENSTER_TOKENS):
        return "envelope_fenster", "fenster"
    if any(token in q for token in DACH_TOKENS):
        return "envelope_dach", "dach"
    if any(token in q for token in KELLERDECKE_TOKENS):
        return "envelope_kellerdecke", "kellerdecke"
    if any(token in q for token in AUSSENWAND_TOKENS):
        return "envelope_aussenwand", "aussenwand"
    return default_measure, default_component


def _extract_cost_rule(quote: str) -> Dict[str, Any]:
    q = quote.lower()
    if "einbaufuge" in q or "anschlussfuge" in q or "fensteranschlussfuge" in q:
        return {
            "kind": "COST_ITEM",
            "item_code": "einbaufuge_daemmung",
            "decision": "ELIGIBLE",
            "match_keywords": ["einbaufuge", "anschlussfuge", "fensteranschlussfuge", "fensteranschlussfugen"],
            "text": quote,
        }
    if "abdichtung der fugen" in q or "fugendichtheit" in q:
        return {
            "kind": "COST_ITEM",
            "item_code": "fugen_abdichtung",
            "decision": "ELIGIBLE_IF_NECESSARY",
            "match_keywords": ["abdichtung der fugen", "fugendichtheit", "fugenabdichtung"],
            "text": quote,
        }
    return {"text": quote}


def snippets_to_requirements(
    snippets: List[RequirementSnippet],
    measure_id: str,
    component: str,
    priority: int,
) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for idx, snippet in enumerate(snippets, start=1):
        scoped_measure, scoped_component = _infer_scope(
            snippet.quote,
            default_measure=measure_id,
            default_component=component,
        )
        req_type = "SECTION_MARKER" if snippet.snippet_type == "section_header" else _infer_req_type(snippet.quote)
        if req_type == "TECH_THRESHOLD":
            rule = _extract_threshold(snippet.quote)
        elif req_type == "COST_ELIGIBILITY":
            rule = _extract_cost_rule(snippet.quote)
        elif req_type == "SECTION_MARKER":
            rule = {"text": snippet.quote, "section_title": snippet.section_title}
        else:
            rule = {"text": snippet.quote}
        if req_type == "TECH_THRESHOLD" and not rule:
            req_type = "PROCESS_RULE"
            rule = {"text": snippet.quote}
        records.append(
            {
                "req_id": f"{scoped_measure}.{idx}",
                "req_type": req_type,
                "scope": {
                    "module": "envelope",
                    "measure": scoped_measure,
                    "component": scoped_component,
                    "case": "default",
                    "section_id": snippet.section_id,
                    "section_title": snippet.section_title,
                    "source_doc_id": snippet.doc_id,
                },
                "rule": rule,
                "severity_if_missing": "CLARIFY",
                "priority": priority,
                "evidence": [
                    {
                        "doc_id": snippet.doc_id,
                        "page": snippet.page,
                        "quote": snippet.quote,
                        "bbox": snippet.bbox,
                    }
                ],
            }
        )
    return records


def write_requirements_jsonl(path: str, records: List[Dict[str, Any]]) -> None:
    append_jsonl(path, records)


def load_requirements_jsonl(path: str) -> List[Dict[str, Any]]:
    return read_jsonl(path)
