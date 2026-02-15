import unittest

from bafa_agent.compiler import compile_measure_specs
from bafa_agent.costs import evaluate_costs
from bafa_agent.requirements import snippets_to_requirements
from bafa_agent.snippets import RequirementSnippet


class InfoblattRuleTests(unittest.TestCase):
    def test_einbaufuge_snippet_maps_to_fenster_cost_rule(self):
        snippets = [
            RequirementSnippet(
                doc_id="infoblatt_sanieren",
                page=12,
                snippet_type="bullet",
                quote="Dämmung der Einbaufuge",
                bbox=[0.0, 0.0, 1.0, 1.0],
            )
        ]
        records = snippets_to_requirements(
            snippets,
            measure_id="envelope_aussenwand",
            component="aussenwand",
            priority=80,
        )
        self.assertEqual(len(records), 1)
        req = records[0]
        self.assertEqual(req["scope"]["measure"], "envelope_fenster")
        self.assertEqual(req["scope"]["component"], "fenster")
        self.assertEqual(req["req_type"], "COST_ELIGIBILITY")
        self.assertEqual(req["rule"].get("item_code"), "einbaufuge_daemmung")

    def test_compiler_adds_split_rule_for_einbaufuge(self):
        requirements = [
            {
                "req_id": "envelope_fenster.1",
                "req_type": "COST_ELIGIBILITY",
                "scope": {
                    "module": "envelope",
                    "measure": "envelope_fenster",
                    "component": "fenster",
                    "case": "default",
                },
                "rule": {
                    "kind": "COST_ITEM",
                    "item_code": "einbaufuge_daemmung",
                    "decision": "ELIGIBLE",
                    "match_keywords": ["einbaufuge", "anschlussfuge"],
                    "text": "Dämmung der Einbaufuge",
                },
                "severity_if_missing": "CLARIFY",
                "priority": 80,
                "evidence": [],
            }
        ]
        compiled = compile_measure_specs(requirements, version="test")
        fenster = compiled["envelope_fenster"]
        split_rules = fenster["cost_rules"]["split_rules"]
        self.assertTrue(any(rule.get("note_key") == "einbaufuge_daemmung" for rule in split_rules))

    def test_cost_evaluation_matches_split_rule(self):
        measure = {
            "line_items": [
                {
                    "description": "Dämmung der Einbaufuge am Fenster",
                    "amount": 120.0,
                    "category": "material",
                }
            ]
        }
        cost_rules = {
            "eligible_cost_categories": ["material"],
            "ineligible_cost_categories": ["finanzierung"],
            "split_rules": [
                {
                    "when": {
                        "field": "line_item.description",
                        "op": "contains_any",
                        "value": ["einbaufuge"],
                    },
                    "result": "ELIGIBLE",
                    "note_key": "einbaufuge_daemmung",
                }
            ],
        }
        summary = evaluate_costs(measure, cost_rules)
        self.assertEqual(summary["eligible_total"], 120.0)
        self.assertEqual(summary["ineligible_total"], 0.0)


if __name__ == "__main__":
    unittest.main()
