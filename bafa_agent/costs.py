from __future__ import annotations

from typing import Any, Dict, List


def _normalize_text(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def _evaluate_split_rule(item: Dict[str, Any], rule: Dict[str, Any]) -> str | None:
    when = rule.get("when", {})
    field = when.get("field")
    op = when.get("op")
    expected = when.get("value")
    decision = rule.get("result")
    if not isinstance(decision, str):
        return None

    if field == "line_item.category" and op == "==" and isinstance(expected, str):
        if item.get("category", "") == expected:
            return decision

    if field == "line_item.description" and op == "contains_any" and isinstance(expected, list):
        description = _normalize_text(str(item.get("description", "")))
        for token in expected:
            if _normalize_text(str(token)) in description:
                return decision

    return None


def _apply_decision(amount: float, decision: str, totals: Dict[str, float]) -> None:
    if decision == "ELIGIBLE":
        totals["eligible_total"] += amount
    elif decision == "INELIGIBLE":
        totals["ineligible_total"] += amount
    else:
        totals["conditional_total"] += amount


def evaluate_costs(measure: Dict[str, Any], cost_rules: Dict[str, Any]) -> Dict[str, Any]:
    eligible_set = set(cost_rules.get("eligible_cost_categories", []))
    ineligible_set = set(cost_rules.get("ineligible_cost_categories", []))
    split_rules = cost_rules.get("split_rules", [])

    totals = {
        "eligible_total": 0.0,
        "ineligible_total": 0.0,
        "conditional_total": 0.0,
    }
    item_results: List[Dict[str, Any]] = []

    for item in measure.get("line_items", []):
        category = item.get("category", "")
        amount = float(item.get("amount", 0.0))
        decision = None

        for rule in split_rules:
            decision = _evaluate_split_rule(item, rule)
            if decision:
                break

        if not decision:
            if category in eligible_set:
                decision = "ELIGIBLE"
            elif category in ineligible_set:
                decision = "INELIGIBLE"
            else:
                decision = "UNCLASSIFIED"

        _apply_decision(amount, decision, totals)

        item_results.append(
            {
                "description": item.get("description", ""),
                "category": category,
                "amount": amount,
                "decision": decision,
            }
        )

    return {
        "eligible_total": round(totals["eligible_total"], 2),
        "ineligible_total": round(totals["ineligible_total"], 2),
        "conditional_total": round(totals["conditional_total"], 2),
        "items": item_results,
    }
