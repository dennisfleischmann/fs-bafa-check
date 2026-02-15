import unittest

from bafa_agent.taxonomy import map_component, map_cost_category


class TaxonomyTests(unittest.TestCase):
    def test_component_mapping(self):
        self.assertEqual(map_component("WDVS Fassade"), "aussenwand")
        self.assertEqual(map_component("Oberste Geschossdecke"), "ogd")

    def test_cost_mapping(self):
        self.assertEqual(map_cost_category("Geruestbau"), "geruest")


if __name__ == "__main__":
    unittest.main()
