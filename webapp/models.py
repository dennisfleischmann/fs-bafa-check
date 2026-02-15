from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, LargeBinary, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from .db import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _json_type():
    # JSONB on postgres, JSON fallback on sqlite.
    return JSON().with_variant(JSONB(), "postgresql")


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(32), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    offers: Mapped[list["Offer"]] = relationship(back_populates="application", cascade="all, delete-orphan")
    evaluations: Mapped[list["Evaluation"]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
    )
    jobs: Mapped[list["JobRecord"]] = relationship(back_populates="application", cascade="all, delete-orphan")


class Offer(Base):
    __tablename__ = "offers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), index=True)
    filename: Mapped[str] = mapped_column(String(512))
    mime_type: Mapped[str] = mapped_column(String(128), default="application/octet-stream")
    file_bytes: Mapped[bytes] = mapped_column(LargeBinary)
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    extraction_status: Mapped[str] = mapped_column(String(32), default="queued")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    application: Mapped["Application"] = relationship(back_populates="offers")
    evaluations: Mapped[list["Evaluation"]] = relationship(back_populates="offer", cascade="all, delete-orphan")
    jobs: Mapped[list["JobRecord"]] = relationship(back_populates="offer", cascade="all, delete-orphan")


class Evaluation(Base):
    __tablename__ = "evaluations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), index=True)
    offer_id: Mapped[str] = mapped_column(ForeignKey("offers.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued")
    evaluation_payload: Mapped[dict] = mapped_column(_json_type(), default=dict)
    plausibility_payload: Mapped[dict] = mapped_column(_json_type(), default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    application: Mapped["Application"] = relationship(back_populates="evaluations")
    offer: Mapped["Offer"] = relationship(back_populates="evaluations")


class JobRecord(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_type: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    rq_job_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    application_id: Mapped[str | None] = mapped_column(ForeignKey("applications.id"), nullable=True, index=True)
    offer_id: Mapped[str | None] = mapped_column(ForeignKey("offers.id"), nullable=True, index=True)
    payload: Mapped[dict] = mapped_column(_json_type(), default=dict)
    result: Mapped[dict] = mapped_column(_json_type(), default=dict)
    error_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    application: Mapped["Application | None"] = relationship(back_populates="jobs")
    offer: Mapped["Offer | None"] = relationship(back_populates="jobs")
