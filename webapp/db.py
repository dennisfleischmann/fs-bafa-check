from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = BASE_DIR / "data" / "webapp_evaluations.db"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def db_path() -> Path:
    value = os.getenv("EVALUATIONS_DB_PATH", str(DEFAULT_DB_PATH))
    return Path(value)


def connect() -> sqlite3.Connection:
    target = db_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    schema = """
    CREATE TABLE IF NOT EXISTS evaluations (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      original_filename TEXT NOT NULL,
      stored_pdf_path TEXT NOT NULL,
      offer_pdf_bytes BLOB NOT NULL,
      offer_pdf_sha256 TEXT NOT NULL,
      offer_text TEXT NOT NULL,
      extraction_method TEXT NOT NULL,
      compile_returncode INTEGER NOT NULL,
      compile_stdout TEXT NOT NULL,
      compile_stderr TEXT NOT NULL,
      evaluate_returncode INTEGER NOT NULL,
      evaluate_stdout TEXT NOT NULL,
      evaluate_stderr TEXT NOT NULL,
      evaluation_path TEXT NOT NULL,
      evaluation_json TEXT NOT NULL,
      human_result TEXT NOT NULL,
      case_id TEXT NOT NULL,
      status TEXT NOT NULL,
      error_message TEXT NOT NULL DEFAULT '',
      is_modified INTEGER NOT NULL DEFAULT 0
    );
    """
    with closing(connect()) as conn:
        conn.executescript(schema)
        conn.commit()


def create_evaluation(record: Dict[str, Any]) -> int:
    now = utc_now_iso()
    payload = {
        "created_at": now,
        "updated_at": now,
        "original_filename": record.get("original_filename", ""),
        "stored_pdf_path": record.get("stored_pdf_path", ""),
        "offer_pdf_bytes": record.get("offer_pdf_bytes", b""),
        "offer_pdf_sha256": record.get("offer_pdf_sha256", ""),
        "offer_text": record.get("offer_text", ""),
        "extraction_method": record.get("extraction_method", ""),
        "compile_returncode": int(record.get("compile_returncode", -1)),
        "compile_stdout": record.get("compile_stdout", ""),
        "compile_stderr": record.get("compile_stderr", ""),
        "evaluate_returncode": int(record.get("evaluate_returncode", -1)),
        "evaluate_stdout": record.get("evaluate_stdout", ""),
        "evaluate_stderr": record.get("evaluate_stderr", ""),
        "evaluation_path": record.get("evaluation_path", ""),
        "evaluation_json": record.get("evaluation_json", "{}"),
        "human_result": record.get("human_result", ""),
        "case_id": record.get("case_id", ""),
        "status": record.get("status", "failed"),
        "error_message": record.get("error_message", ""),
        "is_modified": int(record.get("is_modified", 0)),
    }

    query = """
    INSERT INTO evaluations (
      created_at,
      updated_at,
      original_filename,
      stored_pdf_path,
      offer_pdf_bytes,
      offer_pdf_sha256,
      offer_text,
      extraction_method,
      compile_returncode,
      compile_stdout,
      compile_stderr,
      evaluate_returncode,
      evaluate_stdout,
      evaluate_stderr,
      evaluation_path,
      evaluation_json,
      human_result,
      case_id,
      status,
      error_message,
      is_modified
    ) VALUES (
      :created_at,
      :updated_at,
      :original_filename,
      :stored_pdf_path,
      :offer_pdf_bytes,
      :offer_pdf_sha256,
      :offer_text,
      :extraction_method,
      :compile_returncode,
      :compile_stdout,
      :compile_stderr,
      :evaluate_returncode,
      :evaluate_stdout,
      :evaluate_stderr,
      :evaluation_path,
      :evaluation_json,
      :human_result,
      :case_id,
      :status,
      :error_message,
      :is_modified
    );
    """

    with closing(connect()) as conn:
        cursor = conn.execute(query, payload)
        conn.commit()
        return int(cursor.lastrowid)


def list_evaluations() -> List[Dict[str, Any]]:
    query = """
    SELECT
      id,
      created_at,
      updated_at,
      original_filename,
      case_id,
      status,
      is_modified
    FROM evaluations
    ORDER BY id DESC;
    """
    with closing(connect()) as conn:
        rows = conn.execute(query).fetchall()
    return [dict(row) for row in rows]


def get_evaluation(evaluation_id: int) -> Optional[Dict[str, Any]]:
    query = "SELECT * FROM evaluations WHERE id = ? LIMIT 1;"
    with closing(connect()) as conn:
        row = conn.execute(query, (evaluation_id,)).fetchone()
    if row is None:
        return None
    return dict(row)


def update_evaluation(evaluation_id: int, evaluation_json: str, human_result: str, case_id: str = "") -> bool:
    now = utc_now_iso()
    query = """
    UPDATE evaluations
    SET
      updated_at = ?,
      evaluation_json = ?,
      human_result = ?,
      case_id = ?,
      is_modified = 1
    WHERE id = ?;
    """
    with closing(connect()) as conn:
        cursor = conn.execute(query, (now, evaluation_json, human_result, case_id, evaluation_id))
        conn.commit()
    return cursor.rowcount > 0
