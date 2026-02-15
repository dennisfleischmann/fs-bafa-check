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

    def test_init_workspace_keeps_existing_measure_specs(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            init_workspace(base)

            measure_file = base / "rules" / "measures" / "envelope_fenster.json"
            payload = measure_file.read_text(encoding="utf-8")
            self.assertIn('"measure_id": "envelope_fenster"', payload)

            custom = payload.replace('"version": "bootstrap"', '"version": "custom_lock"')
            measure_file.write_text(custom, encoding="utf-8")

            init_workspace(base)
            after = measure_file.read_text(encoding="utf-8")
            self.assertIn('"version": "custom_lock"', after)


if __name__ == "__main__":
    unittest.main()
