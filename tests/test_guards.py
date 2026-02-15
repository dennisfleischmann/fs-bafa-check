import unittest

from bafa_agent.guards import evidence_binding_guard, threshold_guard


class GuardTests(unittest.TestCase):
    def test_evidence_binding_ok(self):
        records = [
            {
                "req_id": "r1",
                "req_type": "TECH_THRESHOLD",
                "rule": {"field": "derived.u_value_target", "op": "<=", "value": 0.2},
                "evidence": [{"quote": "Außenwand 0,20"}],
            }
        ]
        result = evidence_binding_guard(records)
        self.assertTrue(result.ok)

    def test_evidence_binding_fail(self):
        records = [
            {
                "req_id": "r2",
                "req_type": "TECH_THRESHOLD",
                "rule": {"field": "derived.u_value_target", "op": "<=", "value": 0.2},
                "evidence": [{"quote": "Außenwand ohne Zahl"}],
            }
        ]
        result = evidence_binding_guard(records)
        self.assertFalse(result.ok)

    def test_threshold_guard_fail_on_missing_thresholds(self):
        measures = {
            "envelope_fenster": {
                "technical_requirements": {
                    "thresholds": [],
                }
            }
        }
        result = threshold_guard(measures, required_measure_ids={"envelope_fenster"})
        self.assertFalse(result.ok)
        self.assertTrue(any("missing_thresholds:envelope_fenster" == err for err in result.errors))

    def test_threshold_guard_ok_on_numeric_threshold(self):
        measures = {
            "envelope_fenster": {
                "technical_requirements": {
                    "thresholds": [
                        {
                            "condition": {
                                "field": "derived.u_value_target",
                                "op": "<=",
                                "value": 0.95,
                            }
                        }
                    ],
                }
            }
        }
        result = threshold_guard(measures, required_measure_ids={"envelope_fenster"})
        self.assertTrue(result.ok)


if __name__ == "__main__":
    unittest.main()
