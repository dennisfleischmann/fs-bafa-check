from __future__ import annotations

from typing import Any, Dict, List

from .engine import evaluate_case
from .models import MeasureSpec


def run_regression(
    corpus: List[Dict[str, Any]],
    specs: Dict[str, MeasureSpec],
    ruleset_version: str,
) -> Dict[str, Any]:
    total = 0
    passed = 0
    failures: List[Dict[str, Any]] = []

    for case in corpus:
        total += 1
        expected = case.get("expected", {})
        report = evaluate_case(case["offer_facts"], specs, ruleset_version)
        actual = {result.measure_id: result.status.value for result in report.results}
        if actual == expected:
            passed += 1
        else:
            failures.append(
                {
                    "case_id": case["offer_facts"].get("case_id"),
                    "expected": expected,
                    "actual": actual,
                }
            )

    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": (passed / total) if total else 0.0,
        "failures": failures,
    }
