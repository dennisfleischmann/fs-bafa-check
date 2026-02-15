from __future__ import annotations

from typing import Any, Dict, List


def _threshold_index(bundle: Dict[str, Any]) -> Dict[str, Any]:
    index: Dict[str, Any] = {}
    measures = bundle.get("measures", {})
    for measure_id, spec in measures.items():
        thresholds = spec.get("technical_requirements", {}).get("thresholds", [])
        for item in thresholds:
            cond = item.get("condition", {})
            key = f"{measure_id}:{cond.get('field')}:{cond.get('op')}"
            index[key] = cond.get("value")
    return index


def diff_bundles(previous: Dict[str, Any], current: Dict[str, Any]) -> Dict[str, List[str]]:
    prev_measures = set(previous.get("measures", {}).keys())
    curr_measures = set(current.get("measures", {}).keys())

    added = sorted(curr_measures - prev_measures)
    removed = sorted(prev_measures - curr_measures)

    prev_idx = _threshold_index(previous)
    curr_idx = _threshold_index(current)
    changed: List[str] = []
    for key in sorted(set(prev_idx.keys()) | set(curr_idx.keys())):
        if prev_idx.get(key) != curr_idx.get(key):
            changed.append(f"{key}: {prev_idx.get(key)} -> {curr_idx.get(key)}")

    return {
        "added_measures": added,
        "removed_measures": removed,
        "changed_thresholds": changed,
    }


def requires_human_review(diff_report: Dict[str, List[str]]) -> bool:
    return bool(diff_report.get("changed_thresholds") or diff_report.get("removed_measures"))
