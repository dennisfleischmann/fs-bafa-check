import unittest
from pathlib import Path

from bafa_agent.offer_parser import parse_offer_text
from bafa_agent.semantic_matcher import match_offer_line


class SemanticParserTests(unittest.TestCase):
    def test_semantic_match_for_schlagregendicht_line(self):
        line = (
            "Herstellung eines schlagregendichten Anschlusses aussen "
            "Fassadendaemmung inkl Putzarbeiten"
        )
        matched = match_offer_line(line)
        self.assertIsNotNone(matched)
        assert matched is not None
        self.assertEqual(matched.item_code, "fugen_abdichtung")
        self.assertEqual(matched.component, "fenster")
        self.assertGreaterEqual(matched.confidence, 0.58)

    def test_offer_parser_extracts_position_16_with_semantic_item_code(self):
        offer_file = Path("offer.txt")
        self.assertTrue(offer_file.exists(), "offer.txt missing in project root")

        facts = parse_offer_text(offer_file)
        measures = {measure["measure_id"]: measure for measure in facts["offer"]["measures"]}
        self.assertIn("envelope_fenster", measures)
        self.assertNotIn("envelope_aussenwand", measures)

        fenster = measures["envelope_fenster"]
        pos16 = next((item for item in fenster["line_items"] if item.get("position") == 16), None)
        self.assertIsNotNone(pos16)
        assert pos16 is not None

        self.assertAlmostEqual(float(pos16["amount"]), 3250.0, places=2)
        self.assertEqual(pos16.get("item_code"), "fugen_abdichtung")
        self.assertGreaterEqual(float(pos16.get("semantic_confidence", 0.0)), 0.58)


if __name__ == "__main__":
    unittest.main()
