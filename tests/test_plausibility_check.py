import tempfile
import unittest
from pathlib import Path

from execute_plausibility_check import _collect_bafa_files, _extract_json


class PlausibilityCheckTests(unittest.TestCase):
    def test_collect_bafa_files_filters_supported_suffixes(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "a.pdf").write_text("x", encoding="utf-8")
            (base / "b.txt").write_text("x", encoding="utf-8")
            (base / "c.exe").write_text("x", encoding="utf-8")

            found = _collect_bafa_files(base)
            self.assertEqual([item.name for item in found], ["a.pdf", "b.txt"])

    def test_extract_json_from_wrapped_text(self):
        text = "Intro\n{\"overall_correct\": true, \"summary\": \"ok\"}\nFooter"
        parsed = _extract_json(text)
        self.assertTrue(parsed.get("overall_correct"))
        self.assertEqual(parsed.get("summary"), "ok")


if __name__ == "__main__":
    unittest.main()
