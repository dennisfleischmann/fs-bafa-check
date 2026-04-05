import unittest
from pathlib import Path
from tempfile import NamedTemporaryFile

from bafa_agent.engine import evaluate_case
from bafa_agent.models import MeasureSpec
from bafa_agent.offer_parser import parse_offer_text


def _spec(measure_id: str, threshold: float) -> MeasureSpec:
    payload = {
        "measure_id": measure_id,
        "module": "envelope",
        "title": measure_id,
        "version": "test",
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
                    "name": "threshold",
                    "condition": {
                        "field": "derived.u_value_target",
                        "op": "<=",
                        "value": threshold,
                        "unit": "W/(m2K)",
                        "severity_if_missing": "CLARIFY",
                    },
                }
            ],
            "calculation_methods": [],
        },
        "cost_rules": {"eligible_cost_categories": [], "ineligible_cost_categories": [], "split_rules": []},
        "documentation": {"must_have": [], "nice_to_have": []},
    }
    return MeasureSpec.from_dict(payload)


class OfferBugRegressionTests(unittest.TestCase):
    def test_offer_txt_fenster_pass_without_false_aussenwand(self):
        offer_file = Path("offer.txt")
        self.assertTrue(offer_file.exists(), "offer.txt missing in project root")

        facts = parse_offer_text(offer_file)
        facts["case_id"] = "regression_offer_txt"

        specs = {
            "envelope_fenster": _spec("envelope_fenster", 0.95),
            "envelope_aussenwand": _spec("envelope_aussenwand", 0.20),
        }

        report = evaluate_case(facts, specs, ruleset_version="test")
        result_map = {result.measure_id: result for result in report.results}

        self.assertIn("envelope_fenster", result_map)
        self.assertNotIn("envelope_aussenwand", result_map)
        self.assertEqual(result_map["envelope_fenster"].status.value, "PASS")

    def test_pure_fassade_line_still_triggers_aussenwand_clarify(self):
        content = (
            "===== PAGE 1 =====\n"
            "16 1 Stueck Fassadendaemmung inkl Putzarbeiten 3250,00 3250,00\n"
        )
        with NamedTemporaryFile("w+", suffix=".txt", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            facts = parse_offer_text(handle.name)

        facts["case_id"] = "regression_pure_fassade"
        specs = {
            "envelope_fenster": _spec("envelope_fenster", 0.95),
            "envelope_aussenwand": _spec("envelope_aussenwand", 0.20),
        }
        report = evaluate_case(facts, specs, ruleset_version="test")
        result_map = {result.measure_id: result for result in report.results}

        self.assertIn("envelope_aussenwand", result_map)
        aussenwand = result_map["envelope_aussenwand"]
        self.assertEqual(aussenwand.status.value, "CLARIFY")
        self.assertTrue(
            any(
                "U-Wert nach Sanierung ODER Daemmstaerke + Material (lambda) + Wandaufbau" in q
                for q in aussenwand.questions
            ),
            f"unexpected questions: {aussenwand.questions}",
        )


if __name__ == "__main__":
    unittest.main()
