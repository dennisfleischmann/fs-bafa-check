from __future__ import annotations

from typing import Any, Dict, List


def evaluate_costs(measure: Dict[str, Any], cost_rules: Dict[str, Any]) -> Dict[str, Any]:
    eligible_set = set(cost_rules.get("eligible_cost_categories", []))
    ineligible_set = set(cost_rules.get("ineligible_cost_categories", []))

    eligible_total = 0.0
    ineligible_total = 0.0
    conditional_total = 0.0
    item_results: List[Dict[str, Any]] = []

    for item in measure.get("line_items", []):
        category = item.get("category", "")
        amount = float(item.get("amount", 0.0))

        if category in eligible_set:
            decision = "ELIGIBLE"
            eligible_total += amount
        elif category in ineligible_set:
            decision = "INELIGIBLE"
            ineligible_total += amount
        elif category == "geruest":
            decision = "ELIGIBLE_IF_NECESSARY"
            conditional_total += amount
        else:
            decision = "UNCLASSIFIED"
            conditional_total += amount

        item_results.append(
            {
                "description": item.get("description", ""),
                "category": category,
                "amount": amount,
                "decision": decision,
            }
        )

    return {
        "eligible_total": round(eligible_total, 2),
        "ineligible_total": round(ineligible_total, 2),
        "conditional_total": round(conditional_total, 2),
        "items": item_results,
    }
