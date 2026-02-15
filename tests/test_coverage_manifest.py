import tempfile
import unittest
from pathlib import Path

from bafa_agent.guards import coverage_manifest_guard, coverage_manifest_report
from bafa_agent.pipeline import compile_rules, init_workspace
from bafa_agent.utils import write_json


class CoverageManifestTests(unittest.TestCase):
    def test_guard_reports_missing_sections(self):
        requirements = [
            {
                "scope": {
                    "source_doc_id": "infoblatt_sanieren",
                    "section_id": "2.4",
                }
            },
            {
                "scope": {
                    "source_doc_id": "infoblatt_sanieren",
                    "section_id": "2.5",
                }
            },
        ]
        manifest = {
            "source_doc_id": "infoblatt_sanieren",
            "sections": [
                {"section_id": "2.4", "required": True},
                {"section_id": "2.5", "required": True},
                {"section_id": "3.1", "required": True},
            ],
        }
        report = coverage_manifest_report(requirements, manifest, source_doc_id="infoblatt_sanieren")
        self.assertEqual(report["missing_sections"], ["3.1"])

        guard = coverage_manifest_guard(requirements, manifest, source_doc_id="infoblatt_sanieren")
        self.assertFalse(guard.ok)
        self.assertTrue(any("coverage_manifest_missing_sections" in err for err in guard.errors))

    def test_compile_fails_on_required_section_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            init_workspace(base)
            write_json(
                base / "rules" / "coverage_manifest.json",
                {
                    "source_doc_id": "infoblatt_sanieren",
                    "sections": [
                        {"section_id": "2.4", "required": True},
                        {"section_id": "9.9.9", "required": True},
                    ],
                },
            )
            report = compile_rules(base, source="local-default", fetch=False)
            self.assertFalse(report["validation_passed"])
            self.assertTrue(any("coverage_manifest_missing_sections" in err for err in report["errors"]))


if __name__ == "__main__":
    unittest.main()
