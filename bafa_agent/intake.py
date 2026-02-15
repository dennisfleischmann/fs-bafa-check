from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from .models import DocClass
from .utils import read_text, stable_case_id


def classify_document(path: str | Path) -> DocClass:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        text_sample = ""
        try:
            text_sample = read_text(path)[:500]
        except UnicodeDecodeError:
            return DocClass.PDF_SCAN
        ascii_ratio = sum(char.isprintable() for char in text_sample) / float(max(1, len(text_sample)))
        if ascii_ratio < 0.5 or not text_sample.strip():
            return DocClass.PDF_SCAN
        return DocClass.PDF_TEXT
    if suffix == ".docx":
        return DocClass.DOCX
    if suffix in {".txt", ".eml"}:
        return DocClass.EMAIL_TEXT
    return DocClass.UNKNOWN


def build_case_id(input_paths: List[str]) -> str:
    seed = "|".join(sorted(input_paths))
    return stable_case_id(seed)


def preflight(input_paths: List[str]) -> Dict[str, Any]:
    case_id = build_case_id(input_paths)
    docs = []
    quality_flags: List[str] = []
    for path in input_paths:
        kind = classify_document(path)
        docs.append({"path": path, "doc_class": kind.value})
        if kind == DocClass.PDF_SCAN:
            quality_flags.append("ocr_required")
        if kind == DocClass.UNKNOWN:
            quality_flags.append("unknown_doc_type")
    return {
        "case_id": case_id,
        "docs": docs,
        "quality_flags": sorted(set(quality_flags)),
    }
