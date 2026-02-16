#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Tuple

from flask import Flask, abort, render_template, request, send_file
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from bafa_agent.communications import render_secretary_memo
from bafa_agent.config import load_project_config
from bafa_agent.intake import build_case_id
from bafa_agent.utils import read_json
from webapp.db import create_evaluation, get_evaluation, init_db, list_evaluations, update_evaluation

WEBAPP_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = WEBAPP_DIR / "uploads"
OFFER_TEXT_PATH = BASE_DIR / "offer.txt"
EVALUATION_PATH_RE = re.compile(r"^evaluation written:\s*(?P<path>.+)$", re.MULTILINE)

COMPILE_CMD = ["python3", "-m", "bafa_agent", "compile", "--source", "bafa"]
EVALUATE_CMD = ["python3", "-m", "bafa_agent", "evaluate", "--offer", "./offer.txt"]

app = Flask(__name__, template_folder=str(WEBAPP_DIR / "templates"))
DB_READY = False


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(BASE_DIR))
    except ValueError:
        return str(path)


def extract_text_with_pdfplumber(pdf_path: Path) -> str:
    import pdfplumber

    chunks = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for index, page in enumerate(pdf.pages, start=1):
            page_text = (page.extract_text() or "").strip()
            chunks.append(f"===== PAGE {index} =====")
            chunks.append(page_text)
            chunks.append("")
    return "\n".join(chunks).strip() + "\n"


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


def run_ocr_offer_extractor(pdf_path: Path, out_path: Path) -> Dict[str, Any]:
    cmd = [
        "python3",
        "extract_text_from_offer.py",
        str(pdf_path),
        "--out",
        str(out_path),
    ]
    completed = subprocess.run(cmd, cwd=BASE_DIR, capture_output=True, text=True, check=False)
    return {
        "command": " ".join(cmd),
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def run_command(args: list[str]) -> Dict[str, Any]:
    completed = subprocess.run(args, cwd=BASE_DIR, capture_output=True, text=True, check=False)
    return {
        "command": " ".join(args),
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
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


def persist_record(context: Dict[str, Any], record: Dict[str, Any]) -> None:
    try:
        ensure_db_ready()
        context["saved_evaluation_id"] = create_evaluation(record)
    except Exception as exc:
        context["persistence_error"] = f"{type(exc).__name__}: {exc}"


def ensure_db_ready() -> None:
    global DB_READY
    if DB_READY:
        return
    init_db()
    DB_READY = True


@app.route("/", methods=["GET", "POST"])
def index() -> str:
    context: Dict[str, Any] = {
        "error": "",
        "persistence_error": "",
        "saved_evaluation_id": None,
        "uploaded_pdf_path": "",
        "offer_txt_path": "",
        "offer_text_preview": "",
        "extraction_method": "",
        "extraction_result": None,
        "evaluation_path": "",
        "evaluation_json": "",
        "human_result": "",
        "compile_result": None,
        "evaluate_result": None,
    }
    record: Dict[str, Any] = {}

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
            context["uploaded_pdf_path"] = _relative(stored_pdf)
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
                "status": "failed",
                "error_message": "",
                "is_modified": 0,
            }

            extracted_text, char_count = extract_text_with_pdfplumber_stats(stored_pdf)
            if char_count > 30:
                OFFER_TEXT_PATH.write_text(extracted_text, encoding="utf-8")
                context["extraction_method"] = "pdfplumber"
            else:
                ocr_result = run_ocr_offer_extractor(stored_pdf, OFFER_TEXT_PATH)
                context["extraction_result"] = ocr_result
                if ocr_result["returncode"] != 0:
                    context["error"] = "Text extraction failed: pdfplumber found no text and OCR fallback failed."
                    record["error_message"] = context["error"]
                    record["extraction_method"] = "pdfplumber + OCR fallback (extract_text_from_offer.py)"
                    persist_record(context, record)
                    return render_template("index.html", **context)
                context["extraction_method"] = "pdfplumber + OCR fallback (extract_text_from_offer.py)"
                extracted_text = OFFER_TEXT_PATH.read_text(encoding="utf-8", errors="ignore")

            context["offer_txt_path"] = _relative(OFFER_TEXT_PATH)
            context["offer_text_preview"] = extracted_text[:4000]
            record["offer_text"] = extracted_text
            record["extraction_method"] = context["extraction_method"]

            compile_result = run_command(COMPILE_CMD)
            context["compile_result"] = compile_result
            record["compile_returncode"] = compile_result["returncode"]
            record["compile_stdout"] = compile_result["stdout"]
            record["compile_stderr"] = compile_result["stderr"]
            if compile_result["returncode"] != 0:
                context["error"] = "Compile step failed."
                record["error_message"] = context["error"]
                persist_record(context, record)
                return render_template("index.html", **context)

            evaluate_result = run_command(EVALUATE_CMD)
            context["evaluate_result"] = evaluate_result
            record["evaluate_returncode"] = evaluate_result["returncode"]
            record["evaluate_stdout"] = evaluate_result["stdout"]
            record["evaluate_stderr"] = evaluate_result["stderr"]
            if evaluate_result["returncode"] != 0:
                context["error"] = "Evaluate step failed."
                record["error_message"] = context["error"]
                persist_record(context, record)
                return render_template("index.html", **context)

            evaluation_path = find_evaluation_path(evaluate_result["stdout"])
            context["evaluation_path"] = _relative(evaluation_path)
            record["evaluation_path"] = context["evaluation_path"]
            evaluation_payload = read_json(evaluation_path, default={}) or {}
            if not evaluation_payload:
                context["error"] = f"Evaluation JSON not found or empty: {context['evaluation_path']}"
                record["error_message"] = context["error"]
                persist_record(context, record)
                return render_template("index.html", **context)
            context["evaluation_json"] = json.dumps(evaluation_payload, indent=2, ensure_ascii=False)
            context["human_result"] = render_secretary_memo(evaluation_payload)
            record["evaluation_json"] = context["evaluation_json"]
            record["human_result"] = context["human_result"]
            record["case_id"] = str(evaluation_payload.get("case_id", ""))
            record["status"] = "success"
            record["error_message"] = ""
            persist_record(context, record)
        except Exception as exc:
            context["error"] = f"{type(exc).__name__}: {exc}"
            if record:
                record["error_message"] = context["error"]
                persist_record(context, record)

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
