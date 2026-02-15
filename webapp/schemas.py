from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ApplicationCreate(BaseModel):
    title: str = ""


class ApplicationResponse(BaseModel):
    id: str
    title: str
    status: str
    created_at: datetime
    updated_at: datetime


class OfferResponse(BaseModel):
    id: str
    application_id: str
    filename: str
    mime_type: str
    extraction_status: str
    created_at: datetime
    updated_at: datetime


class JobResponse(BaseModel):
    id: str
    job_type: str
    status: str
    application_id: str | None = None
    offer_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    error_message: str = ""
    created_at: datetime
    updated_at: datetime


class EvaluationResponse(BaseModel):
    id: str
    application_id: str
    offer_id: str
    status: str
    evaluation_payload: dict[str, Any] = Field(default_factory=dict)
    plausibility_payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

