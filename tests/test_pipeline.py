import tempfile
import unittest
from pathlib import Path

from bafa_agent.pipeline import compile_rules, evaluate_offer, init_workspace


class PipelineTests(unittest.TestCase):
    def test_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            init_workspace(base)

            offer = base / "offer.txt"
            offer.write_text(
                "Außenwand WDVS 14 cm WLS 035 Material 12000 EUR\n"
                "Fenster Uw = 0,90 W/m2K Montage 5000 EUR\n",
                encoding="utf-8",
            )

            report = compile_rules(base, fetch=False)
            self.assertIn("validation_passed", report)

            evaluation = evaluate_offer(base, offer)
            self.assertIn("results", evaluation)
            self.assertTrue(len(evaluation["results"]) >= 1)


if __name__ == "__main__":
    unittest.main()
