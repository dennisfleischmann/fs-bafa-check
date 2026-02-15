from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict

from bafa_agent.pipeline import compile_rules, evaluate_offer

from .config import project_root
from .db import SessionLocal
from .models import Application, Evaluation, JobRecord, Offer


def _repo_root() -> Path:
    return project_root()


def _set_job_status(
    session,
    job: JobRecord,
    status: str,
    result: Dict[str, Any] | None = None,
    error: str = "",
) -> None:
    job.status = status
    if result is not None:
        job.result = result
    if error:
        job.error_message = error
    session.add(job)
    session.commit()


def _run_subprocess(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd),
        env=os.environ.copy(),
        text=True,
        capture_output=True,
        check=True,
    )


def _extract_offer_job(session, job: JobRecord) -> Dict[str, Any]:
    offer_id = str(job.payload.get("offer_id", ""))
    offer = session.get(Offer, offer_id)
    if offer is None:
        raise RuntimeError(f"offer not found: {offer_id}")

    suffix = Path(offer.filename).suffix.lower()
    if suffix == ".txt":
        extracted_text = offer.file_bytes.decode("utf-8", errors="ignore")
    elif suffix == ".pdf":
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            in_path = tmp / offer.filename
            out_path = tmp / "offer.txt"
            in_path.write_bytes(offer.file_bytes)
            _run_subprocess(
                [
                    sys.executable,
                    str(_repo_root() / "extract_text_from_offer.py"),
                    str(in_path),
                    "--out",
                    str(out_path),
                ],
                cwd=_repo_root(),
            )
            extracted_text = out_path.read_text(encoding="utf-8")
    else:
        raise RuntimeError("unsupported offer file type; only .pdf and .txt are supported")

    offer.extracted_text = extracted_text
    offer.extraction_status = "done"
    session.add(offer)
    session.commit()

    return {
        "offer_id": offer.id,
        "filename": offer.filename,
        "text_length": len(extracted_text),
        "status": "done",
    }


def _compile_latest_bafa_job(session, job: JobRecord) -> Dict[str, Any]:
    report = compile_rules(base_dir=_repo_root(), source="bafa")
    status = "done" if report.get("validation_passed") else "failed"
    if status == "done" and job.application_id:
        app = session.get(Application, job.application_id)
        if app:
            app.status = "rules_compiled"
            session.add(app)
            session.commit()
    return report


def _evaluate_offer_job(session, job: JobRecord) -> Dict[str, Any]:
    offer_id = str(job.payload.get("offer_id", ""))
    offer = session.get(Offer, offer_id)
    if offer is None:
        raise RuntimeError(f"offer not found: {offer_id}")
    if not offer.extracted_text:
        raise RuntimeError("offer text is empty; run extract job first")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        offer_txt_path = tmp / "offer.txt"
        offer_txt_path.write_text(offer.extracted_text, encoding="utf-8")

        evaluation_payload = evaluate_offer(base_dir=_repo_root(), offer_path=offer_txt_path)

        plausibility_path = tmp / "plausibility_check.json"
        _run_subprocess(
            [
                sys.executable,
                str(_repo_root() / "execute_plausibility_check.py"),
                "--base-dir",
                str(_repo_root()),
                "--offer",
                str(offer_txt_path),
                "--quiet",
                "--out",
                str(plausibility_path),
            ],
            cwd=_repo_root(),
        )
        plausibility_report = json.loads(plausibility_path.read_text(encoding="utf-8"))

    evaluation = Evaluation(
        application_id=offer.application_id,
        offer_id=offer.id,
        status="done",
        evaluation_payload=evaluation_payload,
        plausibility_payload=plausibility_report.get("plausibility", {}),
    )
    session.add(evaluation)

    app = session.get(Application, offer.application_id)
    if app:
        app.status = "evaluated"
        session.add(app)
    session.commit()

    return {
        "evaluation_id": evaluation.id,
        "case_id": evaluation_payload.get("case_id"),
        "overall_correct": plausibility_report.get("plausibility", {}).get("overall_correct"),
    }


JOB_HANDLERS: Dict[str, Callable[[Any, JobRecord], Dict[str, Any]]] = {
    "extract_offer": _extract_offer_job,
    "compile_latest_bafa": _compile_latest_bafa_job,
    "evaluate_offer": _evaluate_offer_job,
}


def run_job(job_id: str) -> Dict[str, Any]:
    session = SessionLocal()
    try:
        job = session.get(JobRecord, job_id)
        if job is None:
            raise RuntimeError(f"job not found: {job_id}")
        handler = JOB_HANDLERS.get(job.job_type)
        if handler is None:
            raise RuntimeError(f"unknown job_type: {job.job_type}")

        _set_job_status(session, job, status="running")
        result = handler(session, job)
        _set_job_status(session, job, status="done", result=result)
        return result
    except Exception as exc:
        if "job" in locals() and job is not None:
            _set_job_status(session, job, status="failed", error=str(exc))
        raise
    finally:
        session.close()
