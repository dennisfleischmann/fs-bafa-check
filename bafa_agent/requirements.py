from __future__ import annotations

import re
from typing import Any, Dict, List

from .snippets import RequirementSnippet
from .utils import append_jsonl, normalize_decimal, parse_float, read_jsonl


THRESHOLD_PATTERN = re.compile(r"([a-zA-Z_]+)?\s*([<>]=?)\s*([0-9]+[.,]?[0-9]*)")
U_VALUE_PATTERN = re.compile(r"([0-9]+[.,]?[0-9]*)\s*(w\/?\(?m2k\)?)", flags=re.IGNORECASE)


def _infer_req_type(quote: str) -> str:
    q = quote.lower()
    normalized = normalize_decimal(q)
    has_numeric_threshold = bool(THRESHOLD_PATTERN.search(normalized) or U_VALUE_PATTERN.search(normalized))
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


def snippets_to_requirements(
    snippets: List[RequirementSnippet],
    measure_id: str,
    component: str,
    priority: int,
) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for idx, snippet in enumerate(snippets, start=1):
        req_type = _infer_req_type(snippet.quote)
        rule = _extract_threshold(snippet.quote) if req_type == "TECH_THRESHOLD" else {"text": snippet.quote}
        if req_type == "TECH_THRESHOLD" and not rule:
            req_type = "PROCESS_RULE"
            rule = {"text": snippet.quote}
        records.append(
            {
                "req_id": f"{measure_id}.{idx}",
                "req_type": req_type,
                "scope": {
                    "module": "envelope",
                    "measure": measure_id,
                    "component": component,
                    "case": "default",
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
