import unittest

from bafa_agent.derived import (
    u_value_from_layers,
    roof_bandwidth_u,
    roof_decision_from_bandwidth,
    wall_worst_case_u,
    wall_decision,
)


class DerivedTests(unittest.TestCase):
    def test_u_value_from_layers(self):
        layers = [{"d_m": 0.16, "lambda": 0.035}, {"d_m": 0.10, "lambda": 0.044}]
        value = u_value_from_layers(layers)
        self.assertIsNotNone(value)
        self.assertLess(value, 0.30)

    def test_roof_bandwidth_decision(self):
        ins = [{"d_m": 0.16, "lambda": 0.035}]
        wood = [{"d_m": 0.16, "lambda": 0.13}]
        bandwidth = roof_bandwidth_u(ins, wood)
        decision = roof_decision_from_bandwidth(0.25, bandwidth)
        self.assertIn(decision["status"], {"PASS", "FAIL", "CLARIFY"})

    def test_wall_worst_case(self):
        layers = [{"d_m": 0.14, "lambda": 0.035}]
        u_upper = wall_worst_case_u(layers)
        self.assertIsNotNone(u_upper)
        self.assertGreater(u_upper, 0.0)

    def test_wall_decision_clarify_on_missing(self):
        decision = wall_decision(0.20, None, [])
        self.assertEqual(decision["status"], "CLARIFY")


if __name__ == "__main__":
    unittest.main()
