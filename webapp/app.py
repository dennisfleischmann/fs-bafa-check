#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Tuple

from flask import Flask, render_template, request
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from bafa_agent.communications import render_secretary_memo
from bafa_agent.config import load_project_config
from bafa_agent.intake import build_case_id
from bafa_agent.utils import read_json

WEBAPP_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = WEBAPP_DIR / "uploads"
OFFER_TEXT_PATH = BASE_DIR / "offer.txt"
EVALUATION_PATH_RE = re.compile(r"^evaluation written:\s*(?P<path>.+)$", re.MULTILINE)

COMPILE_CMD = ["python3", "-m", "bafa_agent", "compile", "--source", "bafa"]
EVALUATE_CMD = ["python3", "-m", "bafa_agent", "evaluate", "--offer", "./offer.txt"]

app = Flask(__name__, template_folder=str(WEBAPP_DIR / "templates"))


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


@app.route("/", methods=["GET", "POST"])
def index() -> str:
    context: Dict[str, Any] = {
        "error": "",
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
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            stored_pdf = UPLOAD_DIR / f"{timestamp}_{filename}"
            uploaded.save(str(stored_pdf))
            context["uploaded_pdf_path"] = _relative(stored_pdf)

            extracted_text, char_count = extract_text_with_pdfplumber_stats(stored_pdf)
            if char_count > 30:
                OFFER_TEXT_PATH.write_text(extracted_text, encoding="utf-8")
                context["extraction_method"] = "pdfplumber"
            else:
                ocr_result = run_ocr_offer_extractor(stored_pdf, OFFER_TEXT_PATH)
                context["extraction_result"] = ocr_result
                if ocr_result["returncode"] != 0:
                    context["error"] = "Text extraction failed: pdfplumber found no text and OCR fallback failed."
                    return render_template("index.html", **context)
                context["extraction_method"] = "pdfplumber + OCR fallback (extract_text_from_offer.py)"
                extracted_text = OFFER_TEXT_PATH.read_text(encoding="utf-8", errors="ignore")

            context["offer_txt_path"] = _relative(OFFER_TEXT_PATH)
            context["offer_text_preview"] = extracted_text[:4000]

            compile_result = run_command(COMPILE_CMD)
            context["compile_result"] = compile_result
            if compile_result["returncode"] != 0:
                context["error"] = "Compile step failed."
                return render_template("index.html", **context)

            evaluate_result = run_command(EVALUATE_CMD)
            context["evaluate_result"] = evaluate_result
            if evaluate_result["returncode"] != 0:
                context["error"] = "Evaluate step failed."
                return render_template("index.html", **context)

            evaluation_path = find_evaluation_path(evaluate_result["stdout"])
            context["evaluation_path"] = _relative(evaluation_path)
            evaluation_payload = read_json(evaluation_path, default={}) or {}
            if not evaluation_payload:
                context["error"] = f"Evaluation JSON not found or empty: {context['evaluation_path']}"
                return render_template("index.html", **context)
            context["evaluation_json"] = json.dumps(evaluation_payload, indent=2, ensure_ascii=False)
            context["human_result"] = render_secretary_memo(evaluation_payload)
        except Exception as exc:
            context["error"] = f"{type(exc).__name__}: {exc}"

    return render_template("index.html", **context)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    debug = os.getenv("FLASK_DEBUG", "1") in {"1", "true", "True"}
    app.run(host="0.0.0.0", port=port, debug=debug)
