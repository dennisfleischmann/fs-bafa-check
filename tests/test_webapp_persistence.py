from __future__ import annotations

import importlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class TestWebappPersistence(unittest.TestCase):
    @staticmethod
    def _submit_immediate(fn, *args, **kwargs):
        class _DoneFuture:
            def result(self, timeout=None):
                return None

        fn(*args, **kwargs)
        return _DoneFuture()

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)
        self.db_path = self.tmp_path / "evaluations.db"
        os.environ["EVALUATIONS_DB_PATH"] = str(self.db_path)

        import webapp.app as app_module

        self.app_module = importlib.reload(app_module)
        self.app_module.UPLOAD_DIR = self.tmp_path / "uploads"
        self.app_module.OFFER_TEXT_PATH = self.tmp_path / "offer.txt"
        self.client = self.app_module.app.test_client()

    def tearDown(self) -> None:
        os.environ.pop("EVALUATIONS_DB_PATH", None)
        self.temp_dir.cleanup()

    def test_evaluate_offer_persists_and_can_edit(self) -> None:
        evaluation_payload = {
            "case_id": "case_test_001",
            "generated_at": "2026-02-16T00:00:00Z",
            "ruleset_version": "active",
            "results": [],
        }
        compile_result = {
            "command": "compile",
            "returncode": 0,
            "stdout": "compile ok",
            "stderr": "",
        }
        evaluate_result = {
            "command": "evaluate",
            "returncode": 0,
            "stdout": "evaluation written: data/cases/case_test_001/evaluation.json\n",
            "stderr": "",
        }

        with (
            patch.object(
                self.app_module,
                "extract_text_with_pdfplumber_stats",
                return_value=("===== PAGE 1 =====\noffer text\n", 100),
            ),
            patch.object(
                self.app_module,
                "run_command",
                side_effect=[compile_result, evaluate_result],
            ),
            patch.object(self.app_module, "read_json", return_value=evaluation_payload),
            patch.object(self.app_module.EXECUTOR, "submit", side_effect=self._submit_immediate),
        ):
            response = self.client.post(
                "/",
                data={"offer_pdf": (io.BytesIO(b"%PDF-1.4 test document"), "offer.pdf")},
                content_type="multipart/form-data",
                follow_redirects=True,
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Evaluation", response.data)

        from webapp.db import get_evaluation, list_evaluations

        rows = list_evaluations()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "success")

        evaluation_id = rows[0]["id"]
        detail_response = self.client.get(f"/evaluations/{evaluation_id}")
        self.assertEqual(detail_response.status_code, 200)
        self.assertIn(b"Evaluation", detail_response.data)

        list_response = self.client.get("/evaluations")
        self.assertEqual(list_response.status_code, 200)
        self.assertIn(str(evaluation_id).encode("utf-8"), list_response.data)

        updated_json = (
            '{\n'
            '  "case_id": "case_test_001",\n'
            '  "generated_at": "2026-02-16T00:00:00Z",\n'
            '  "ruleset_version": "active",\n'
            '  "results": [],\n'
            '  "manual_note": "edited"\n'
            '}'
        )
        update_response = self.client.post(
            f"/evaluations/{evaluation_id}",
            data={"evaluation_json": updated_json, "human_result": "manually adjusted"},
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertIn(b"Evaluation updated.", update_response.data)

        edited = get_evaluation(evaluation_id)
        self.assertIsNotNone(edited)
        assert edited is not None
        self.assertEqual(int(edited["is_modified"]), 1)
        self.assertIn("manual_note", edited["evaluation_json"])
        self.assertEqual(edited["human_result"], "manually adjusted")

        pdf_response = self.client.get(f"/evaluations/{evaluation_id}/offer.pdf")
        self.assertEqual(pdf_response.status_code, 200)
        self.assertEqual(pdf_response.mimetype, "application/pdf")
        self.assertIn(b"%PDF-1.4 test document", pdf_response.data)

    def test_compile_failure_is_persisted(self) -> None:
        compile_result = {
            "command": "compile",
            "returncode": 2,
            "stdout": "",
            "stderr": "compile failed",
        }

        with (
            patch.object(
                self.app_module,
                "extract_text_with_pdfplumber_stats",
                return_value=("===== PAGE 1 =====\ntext\n", 100),
            ),
            patch.object(self.app_module, "run_command", return_value=compile_result),
            patch.object(self.app_module.EXECUTOR, "submit", side_effect=self._submit_immediate),
        ):
            response = self.client.post(
                "/",
                data={"offer_pdf": (io.BytesIO(b"%PDF-1.4 test document"), "offer-fail.pdf")},
                content_type="multipart/form-data",
                follow_redirects=True,
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Compile step failed.", response.data)

        from webapp.db import list_evaluations

        rows = list_evaluations()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "failed")


if __name__ == "__main__":
    unittest.main()
