import unittest

from bafa_agent.engine import evaluate_case
from bafa_agent.models import MeasureSpec


class EngineTests(unittest.TestCase):
    def test_missing_required_field_triggers_clarify_or_abort(self):
        spec_payload = {
            "measure_id": "envelope_aussenwand",
            "module": "envelope",
            "title": "Aussenwand",
            "version": "1",
            "required_fields": [
                {"path": "offer.component_type", "severity_if_missing": "ABORT"},
                {"path": "building.is_existing", "severity_if_missing": "CLARIFY"},
            ],
            "eligibility": {"all_of": [{"field": "building.is_existing", "op": "==", "value": True}]},
            "technical_requirements": {
                "thresholds": [
                    {
                        "condition": {
                            "field": "derived.u_value_target",
                            "op": "<=",
                            "value": 0.2,
                            "severity_if_missing": "CLARIFY",
                        }
                    }
                ],
                "calculation_methods": [],
            },
            "cost_rules": {"eligible_cost_categories": [], "ineligible_cost_categories": []},
            "documentation": {"must_have": [], "nice_to_have": []},
        }
        spec = MeasureSpec.from_dict(spec_payload)

        offer_facts = {
            "case_id": "c1",
            "building": {"is_existing": True},
            "applicant": {},
            "docs": {},
            "offer": {"measures": [{"measure_id": "envelope_aussenwand", "input_mode": "direct_u", "values": {}}]},
        }

        report = evaluate_case(offer_facts, {"envelope_aussenwand": spec}, "v1")
        self.assertEqual(len(report.results), 1)
        self.assertIn(report.results[0].status.value, {"ABORT", "CLARIFY"})


if __name__ == "__main__":
    unittest.main()
