from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List

from .utils import utc_now_iso, write_json, read_json


PII_PATTERNS = {
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "phone": re.compile(r"\+?[0-9][0-9\-\s()]{6,}[0-9]"),
    "iban": re.compile(r"\b[A-Z]{2}[0-9A-Z]{13,32}\b"),
    "postal": re.compile(r"\b\d{5}\b"),
}


def redact_pii(text: str) -> str:
    redacted = text
    for label, pattern in PII_PATTERNS.items():
        redacted = pattern.sub(f"<{label}_redacted>", redacted)
    return redacted


def redact_payload(payload: Dict[str, str]) -> Dict[str, str]:
    return {key: redact_pii(value) if isinstance(value, str) else value for key, value in payload.items()}


def log_access(log_file: str | Path, actor: str, action: str, case_id: str) -> None:
    record = {
        "timestamp": utc_now_iso(),
        "actor": actor,
        "action": action,
        "case_id": case_id,
    }
    entries: List[Dict[str, str]] = read_json(log_file, default=[])
    if not isinstance(entries, list):
        entries = []
    entries.append(record)
    write_json(log_file, entries)
