#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Tuple

from flask import Flask, abort, redirect, render_template, request, send_file, url_for
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from bafa_agent.communications import render_secretary_memo
from bafa_agent.config import load_project_config
from bafa_agent.intake import build_case_id
from bafa_agent.utils import read_json
from webapp.db import (
    create_evaluation,
    db_path,
    get_evaluation,
    init_db,
    list_evaluations,
    update_evaluation,
    update_evaluation_fields,
)

WEBAPP_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = WEBAPP_DIR / "uploads"
OFFER_TEXT_PATH = BASE_DIR / "offer.txt"
EVALUATION_PATH_RE = re.compile(r"^evaluation written:\s*(?P<path>.+)$", re.MULTILINE)

COMPILE_CMD = ["python3", "-m", "bafa_agent", "compile", "--source", "bafa"]
EVALUATE_CMD = ["python3", "-m", "bafa_agent", "evaluate", "--offer", "./offer.txt"]

OCR_TIMEOUT_SEC = int(os.getenv("WEBAPP_OCR_TIMEOUT_SEC", "420"))
COMPILE_TIMEOUT_SEC = int(os.getenv("WEBAPP_COMPILE_TIMEOUT_SEC", "420"))
EVALUATE_TIMEOUT_SEC = int(os.getenv("WEBAPP_EVALUATE_TIMEOUT_SEC", "300"))

EXECUTOR = ThreadPoolExecutor(max_workers=max(1, int(os.getenv("WEBAPP_JOB_WORKERS", "2"))))

app = Flask(__name__, template_folder=str(WEBAPP_DIR / "templates"))
DB_READY = False


def ensure_db_ready() -> None:
    global DB_READY
    if DB_READY:
        return
    init_db()
    DB_READY = True


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(BASE_DIR))
    except ValueError:
        return str(path)


def _env_status() -> Dict[str, Any]:
    return {
        "openai_api_key_set": bool(os.getenv("OPENAI_API_KEY")),
        "db_path": str(db_path()),
    }


def extract_text_with_pdfplumber_stats(pdf_path: Path) -> Tuple[str, int]:
    import pdfplumber

    total_chars = 0
    chunks = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for index, page in enumerate(pdf.pages, start=1):
            page_text = (page.extract_text() or "").strip()
            total_chars += len(page_text)
            chunks.append(f"===== PAGE {index} =====")
            chunks.append(page_text)
            chunks.append("")

    text = "\n".join(chunks).strip() + "\n"
    return text, total_chars


def run_ocr_offer_extractor(pdf_path: Path, out_path: Path, timeout_sec: int) -> Dict[str, Any]:
    cmd = [
        "python3",
        "extract_text_from_offer.py",
        str(pdf_path),
        "--out",
        str(out_path),
    ]
    try:
        completed = subprocess.run(
            cmd,
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_sec,
        )
        return {
            "command": " ".join(cmd),
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": " ".join(cmd),
            "returncode": 124,
            "stdout": exc.stdout or "",
            "stderr": (exc.stderr or "") + f"\nTimeout after {timeout_sec}s.",
        }


def run_command(args: list[str], timeout_sec: int) -> Dict[str, Any]:
    try:
        completed = subprocess.run(
            args,
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_sec,
        )
        return {
            "command": " ".join(args),
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": " ".join(args),
            "returncode": 124,
            "stdout": exc.stdout or "",
            "stderr": (exc.stderr or "") + f"\nTimeout after {timeout_sec}s.",
        }


def find_evaluation_path(stdout: str) -> Path:
    match = EVALUATION_PATH_RE.search(stdout)
    if match:
        candidate = Path(match.group("path").strip())
        if not candidate.is_absolute():
            candidate = BASE_DIR / candidate
        return candidate
    case_id = build_case_id(["./offer.txt"])
    return BASE_DIR / "data" / "cases" / case_id / "evaluation.json"


def _mark_failed(evaluation_id: int, fields: Dict[str, Any], message: str) -> None:
    payload = dict(fields)
    payload["status"] = "failed"
    payload["error_message"] = message
    update_evaluation_fields(evaluation_id, payload)


def process_evaluation_async(evaluation_id: int, stored_pdf_path: str) -> None:
    ensure_db_ready()
    load_project_config(BASE_DIR)

    stored_pdf = Path(stored_pdf_path)
    update_evaluation_fields(evaluation_id, {"status": "running", "error_message": ""})

    extracted_text = ""
    extraction_method = ""
    ocr_result: Dict[str, Any] = {}

    try:
        extracted_text, char_count = extract_text_with_pdfplumber_stats(stored_pdf)
        if char_count > 30:
            extraction_method = "pdfplumber"
            OFFER_TEXT_PATH.write_text(extracted_text, encoding="utf-8")
        else:
            ocr_result = run_ocr_offer_extractor(stored_pdf, OFFER_TEXT_PATH, timeout_sec=OCR_TIMEOUT_SEC)
            extraction_method = "pdfplumber + OCR fallback (extract_text_from_offer.py)"
            extracted_text = OFFER_TEXT_PATH.read_text(encoding="utf-8", errors="ignore") if OFFER_TEXT_PATH.exists() else ""
            if ocr_result["returncode"] != 0:
                _mark_failed(
                    evaluation_id,
                    {
                        "extraction_method": extraction_method,
                        "offer_text": extracted_text,
                        "evaluate_stderr": ocr_result.get("stderr", ""),
                    },
                    "Text extraction failed (OCR fallback error).",
                )
                return
            if "[OCR_FAILED]" in extracted_text:
                _mark_failed(
                    evaluation_id,
                    {
                        "extraction_method": extraction_method,
                        "offer_text": extracted_text,
                        "evaluate_stderr": ocr_result.get("stderr", ""),
                    },
                    "Text extraction failed: OCR returned page failures. Check OPENAI_API_KEY.",
                )
                return

        update_evaluation_fields(
            evaluation_id,
            {
                "offer_text": extracted_text,
                "extraction_method": extraction_method,
            },
        )

        compile_result = run_command(COMPILE_CMD, timeout_sec=COMPILE_TIMEOUT_SEC)
        update_evaluation_fields(
            evaluation_id,
            {
                "compile_returncode": compile_result["returncode"],
                "compile_stdout": compile_result["stdout"],
                "compile_stderr": compile_result["stderr"],
            },
        )
        if compile_result["returncode"] != 0:
            _mark_failed(evaluation_id, {}, "Compile step failed.")
            return

        evaluate_result = run_command(EVALUATE_CMD, timeout_sec=EVALUATE_TIMEOUT_SEC)
        update_evaluation_fields(
            evaluation_id,
            {
                "evaluate_returncode": evaluate_result["returncode"],
                "evaluate_stdout": evaluate_result["stdout"],
                "evaluate_stderr": evaluate_result["stderr"],
            },
        )
        if evaluate_result["returncode"] != 0:
            _mark_failed(evaluation_id, {}, "Evaluate step failed.")
            return

        evaluation_path = find_evaluation_path(evaluate_result["stdout"])
        evaluation_payload = read_json(evaluation_path, default={}) or {}
        if not evaluation_payload:
            _mark_failed(
                evaluation_id,
                {"evaluation_path": _relative(evaluation_path)},
                f"Evaluation JSON not found or empty: {_relative(evaluation_path)}",
            )
            return

        evaluation_json = json.dumps(evaluation_payload, indent=2, ensure_ascii=False)
        human_result = render_secretary_memo(evaluation_payload)
        update_evaluation_fields(
            evaluation_id,
            {
                "evaluation_path": _relative(evaluation_path),
                "evaluation_json": evaluation_json,
                "human_result": human_result,
                "case_id": str(evaluation_payload.get("case_id", "")),
                "status": "success",
                "error_message": "",
            },
        )
    except Exception as exc:
        _mark_failed(evaluation_id, {}, f"{type(exc).__name__}: {exc}")


def enqueue_evaluation(stored_pdf: Path, filename: str) -> int:
    ensure_db_ready()
    pdf_bytes = stored_pdf.read_bytes()
    record = {
        "original_filename": filename,
        "stored_pdf_path": _relative(stored_pdf),
        "offer_pdf_bytes": pdf_bytes,
        "offer_pdf_sha256": hashlib.sha256(pdf_bytes).hexdigest(),
        "offer_text": "",
        "extraction_method": "",
        "compile_returncode": -1,
        "compile_stdout": "",
        "compile_stderr": "",
        "evaluate_returncode": -1,
        "evaluate_stdout": "",
        "evaluate_stderr": "",
        "evaluation_path": "",
        "evaluation_json": "{}",
        "human_result": "",
        "case_id": "",
        "status": "queued",
        "error_message": "",
        "is_modified": 0,
    }
    evaluation_id = create_evaluation(record)
    EXECUTOR.submit(process_evaluation_async, evaluation_id, str(stored_pdf))
    return evaluation_id


@app.route("/healthz", methods=["GET"])
def healthz() -> Dict[str, Any]:
    try:
        ensure_db_ready()
        return {"ok": True, "db_path": str(db_path())}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}, 500


@app.route("/", methods=["GET", "POST"])
def index() -> str:
    context: Dict[str, Any] = {
        "error": "",
        "env_status": _env_status(),
    }

    if request.method == "POST":
        try:
            load_project_config(BASE_DIR)
            uploaded = request.files.get("offer_pdf")
            if uploaded is None or not uploaded.filename:
                context["error"] = "Please upload a PDF file."
                return render_template("index.html", **context)

            filename = secure_filename(uploaded.filename)
            if not filename.lower().endswith(".pdf"):
                context["error"] = "Only .pdf uploads are supported."
                return render_template("index.html", **context)

            UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            stored_pdf = UPLOAD_DIR / f"{timestamp}_{filename}"
            uploaded.save(str(stored_pdf))

            evaluation_id = enqueue_evaluation(stored_pdf, filename)
            return redirect(url_for("evaluation_edit", evaluation_id=evaluation_id))
        except Exception as exc:
            context["error"] = f"{type(exc).__name__}: {exc}"

    return render_template("index.html", **context)


@app.route("/evaluations", methods=["GET"])
def evaluations_list() -> str:
    error = ""
    evaluations = []
    try:
        ensure_db_ready()
        evaluations = list_evaluations()
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    return render_template("evaluations.html", evaluations=evaluations, error=error)


@app.route("/evaluations/<int:evaluation_id>", methods=["GET", "POST"])
def evaluation_edit(evaluation_id: int) -> str:
    ensure_db_ready()
    payload = get_evaluation(evaluation_id)
    if payload is None:
        abort(404)

    error = ""
    success = ""
    if request.method == "POST":
        updated_json = (request.form.get("evaluation_json") or "").strip()
        updated_human_result = (request.form.get("human_result") or "").strip()
        if not updated_json:
            error = "evaluation_json cannot be empty."
        else:
            try:
                parsed = json.loads(updated_json)
            except json.JSONDecodeError as exc:
                error = f"Invalid JSON: {exc}"
            else:
                normalized_json = json.dumps(parsed, indent=2, ensure_ascii=False)
                case_id = str(parsed.get("case_id", "")) if isinstance(parsed, dict) else ""
                if update_evaluation(evaluation_id, normalized_json, updated_human_result, case_id=case_id):
                    success = "Evaluation updated."
                    payload = get_evaluation(evaluation_id) or payload
                else:
                    error = "Update failed."

    return render_template("evaluation_edit.html", evaluation=payload, error=error, success=success)


@app.route("/evaluations/<int:evaluation_id>/offer.pdf", methods=["GET"])
def evaluation_offer_pdf(evaluation_id: int):
    ensure_db_ready()
    payload = get_evaluation(evaluation_id)
    if payload is None:
        abort(404)

    pdf_bytes = payload.get("offer_pdf_bytes")
    if not isinstance(pdf_bytes, (bytes, bytearray)) or not pdf_bytes:
        abort(404)

    filename = payload.get("original_filename", "") or f"offer_{evaluation_id}.pdf"
    return send_file(
        io.BytesIO(bytes(pdf_bytes)),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    debug = os.getenv("FLASK_DEBUG", "1") in {"1", "true", "True"}
    app.run(host="0.0.0.0", port=port, debug=debug)
