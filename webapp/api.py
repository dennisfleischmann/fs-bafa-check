from __future__ import annotations

import os
import uuid
from typing import Any

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from .db import Base, ENGINE, get_session
from .models import Application, Evaluation, JobRecord, Offer
from .queueing import get_queue
from .schemas import (
    ApplicationCreate,
    ApplicationResponse,
    EvaluationResponse,
    JobResponse,
    OfferResponse,
)

app = FastAPI(title="BAFA Web API", version="0.1.0")

_cors_raw = os.getenv("WEB_CORS_ORIGINS", "*").strip()
if _cors_raw == "*":
    _cors_origins = ["*"]
else:
    _cors_origins = [item.strip() for item in _cors_raw.split(",") if item.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    Base.metadata.create_all(bind=ENGINE)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": "BAFA Web API",
        "status": "ok",
        "health_url": "/health",
        "docs_url": "/docs",
    }


def _job_response(job: JobRecord) -> JobResponse:
    return JobResponse(
        id=job.id,
        job_type=job.job_type,
        status=job.status,
        application_id=job.application_id,
        offer_id=job.offer_id,
        payload=job.payload or {},
        result=job.result or {},
        error_message=job.error_message or "",
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def _enqueue_job(
    session: Session,
    job_type: str,
    payload: dict[str, Any],
    application_id: str | None = None,
    offer_id: str | None = None,
) -> JobRecord:
    job = JobRecord(
        id=str(uuid.uuid4()),
        job_type=job_type,
        status="queued",
        application_id=application_id,
        offer_id=offer_id,
        payload=payload,
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    rq_job = get_queue("default").enqueue("webapp.worker_tasks.run_job", job.id)
    job.rq_job_id = rq_job.id
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/applications", response_model=ApplicationResponse)
def create_application(payload: ApplicationCreate, session: Session = Depends(get_session)) -> ApplicationResponse:
    app_row = Application(title=payload.title or "", status="draft")
    session.add(app_row)
    session.commit()
    session.refresh(app_row)
    return ApplicationResponse(
        id=app_row.id,
        title=app_row.title,
        status=app_row.status,
        created_at=app_row.created_at,
        updated_at=app_row.updated_at,
    )


@app.get("/applications/{application_id}", response_model=ApplicationResponse)
def get_application(application_id: str, session: Session = Depends(get_session)) -> ApplicationResponse:
    app_row = session.get(Application, application_id)
    if app_row is None:
        raise HTTPException(status_code=404, detail="application not found")
    return ApplicationResponse(
        id=app_row.id,
        title=app_row.title,
        status=app_row.status,
        created_at=app_row.created_at,
        updated_at=app_row.updated_at,
    )


@app.get("/applications/{application_id}/offers", response_model=list[OfferResponse])
def list_offers(application_id: str, session: Session = Depends(get_session)) -> list[OfferResponse]:
    rows = (
        session.query(Offer)
        .filter(Offer.application_id == application_id)
        .order_by(Offer.created_at.desc())
        .all()
    )
    return [
        OfferResponse(
            id=row.id,
            application_id=row.application_id,
            filename=row.filename,
            mime_type=row.mime_type,
            extraction_status=row.extraction_status,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]


@app.get("/applications/{application_id}/evaluations", response_model=list[EvaluationResponse])
def list_evaluations(application_id: str, session: Session = Depends(get_session)) -> list[EvaluationResponse]:
    rows = (
        session.query(Evaluation)
        .filter(Evaluation.application_id == application_id)
        .order_by(Evaluation.created_at.desc())
        .all()
    )
    return [
        EvaluationResponse(
            id=row.id,
            application_id=row.application_id,
            offer_id=row.offer_id,
            status=row.status,
            evaluation_payload=row.evaluation_payload or {},
            plausibility_payload=row.plausibility_payload or {},
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]


@app.post("/actions/compile-latest", response_model=JobResponse)
def compile_latest(session: Session = Depends(get_session)) -> JobResponse:
    job = _enqueue_job(
        session=session,
        job_type="compile_latest_bafa",
        payload={},
        application_id=None,
        offer_id=None,
    )
    return _job_response(job)


@app.post("/applications/{application_id}/offers", response_model=JobResponse)
async def upload_offer(
    application_id: str,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> JobResponse:
    app_row = session.get(Application, application_id)
    if app_row is None:
        raise HTTPException(status_code=404, detail="application not found")

    filename = file.filename or "offer.pdf"
    suffix = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    if suffix not in {".pdf", ".txt"}:
        raise HTTPException(status_code=400, detail="only .pdf or .txt offers are supported")
    blob = await file.read()
    if not blob:
        raise HTTPException(status_code=400, detail="empty file")

    offer = Offer(
        application_id=application_id,
        filename=filename,
        mime_type=file.content_type or "application/octet-stream",
        file_bytes=blob,
        extraction_status="queued",
    )
    session.add(offer)
    app_row.status = "offer_uploaded"
    session.add(app_row)
    session.commit()
    session.refresh(offer)

    job = _enqueue_job(
        session=session,
        job_type="extract_offer",
        payload={"offer_id": offer.id},
        application_id=application_id,
        offer_id=offer.id,
    )
    return _job_response(job)


@app.post("/applications/{application_id}/offers/{offer_id}/evaluate", response_model=JobResponse)
def evaluate_offer_job(application_id: str, offer_id: str, session: Session = Depends(get_session)) -> JobResponse:
    app_row = session.get(Application, application_id)
    if app_row is None:
        raise HTTPException(status_code=404, detail="application not found")
    offer = session.get(Offer, offer_id)
    if offer is None or offer.application_id != application_id:
        raise HTTPException(status_code=404, detail="offer not found")
    if offer.extraction_status != "done":
        raise HTTPException(status_code=409, detail="offer extraction not finished")

    app_row.status = "evaluation_queued"
    session.add(app_row)
    session.commit()

    job = _enqueue_job(
        session=session,
        job_type="evaluate_offer",
        payload={"offer_id": offer_id},
        application_id=application_id,
        offer_id=offer_id,
    )
    return _job_response(job)


@app.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str, session: Session = Depends(get_session)) -> JobResponse:
    row = session.get(JobRecord, job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="job not found")
    return _job_response(row)


@app.get("/jobs/{job_id}/result")
def get_job_result(job_id: str, session: Session = Depends(get_session)) -> JSONResponse:
    row = session.get(JobRecord, job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="job not found")
    return JSONResponse(
        {
            "id": row.id,
            "status": row.status,
            "job_type": row.job_type,
            "result": row.result or {},
            "error": row.error_message or "",
        }
    )
