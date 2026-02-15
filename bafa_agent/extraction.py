from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .utils import is_probably_scan, read_text


@dataclass
class LayoutLine:
    page: int
    x0: float
    y0: float
    x1: float
    y1: float
    text: str


@dataclass
class ExtractedTable:
    page: int
    bbox: List[float]
    rows: List[List[str]]


@dataclass
class ExtractionOutput:
    doc_id: str
    lines: List[LayoutLine]
    tables: List[ExtractedTable]
    text_coverage_ratio: float
    used_ocr: bool
    quality_flags: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "lines": [asdict(line) for line in self.lines],
            "tables": [asdict(table) for table in self.tables],
            "text_coverage_ratio": self.text_coverage_ratio,
            "used_ocr": self.used_ocr,
            "quality_flags": self.quality_flags,
        }


def _line_coordinates(index: int, text: str) -> Tuple[float, float, float, float]:
    y0 = float(index * 10)
    y1 = y0 + 8.0
    x0 = 0.0
    x1 = float(max(1, len(text)))
    return x0, y0, x1, y1


def layout_extract_text(path: str | Path, page: int = 1) -> List[LayoutLine]:
    content = _load_document_text(path)
    lines: List[LayoutLine] = []
    for index, raw in enumerate(content.splitlines()):
        text = raw.strip()
        if not text:
            continue
        x0, y0, x1, y1 = _line_coordinates(index, text)
        lines.append(LayoutLine(page=page, x0=x0, y0=y0, x1=x1, y1=y1, text=text))
    return lines


def _load_document_text(path: str | Path) -> str:
    path = Path(path)
    if path.suffix.lower() == ".pdf":
        text = _extract_pdf_text(path)
        if text:
            return text
    try:
        return read_text(path)
    except UnicodeDecodeError:
        return path.read_bytes().decode("latin-1", errors="ignore")


def _extract_pdf_text(path: Path) -> str:
    tool = shutil.which("pdftotext")
    if tool:
        with tempfile.NamedTemporaryFile(suffix=".txt") as output_file:
            cmd = [tool, "-layout", str(path), output_file.name]
            completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
            if completed.returncode == 0:
                content = Path(output_file.name).read_text(encoding="utf-8", errors="ignore")
                if content.strip():
                    return content
    return path.read_bytes().decode("latin-1", errors="ignore")


def estimate_text_coverage(path: str | Path, lines: List[LayoutLine]) -> float:
    size = max(1, Path(path).stat().st_size)
    chars = sum(len(line.text) for line in lines)
    ratio = chars / float(size)
    return min(1.0, ratio)


def table_extract(lines: List[LayoutLine]) -> List[ExtractedTable]:
    tables: List[ExtractedTable] = []
    grid_rows: List[List[str]] = []
    for line in lines:
        if "|" in line.text:
            row = [cell.strip() for cell in line.text.split("|") if cell.strip()]
            if len(row) >= 2:
                grid_rows.append(row)
        elif re.search(r"\s{2,}", line.text):
            row = [cell.strip() for cell in re.split(r"\s{2,}", line.text) if cell.strip()]
            if len(row) >= 3:
                grid_rows.append(row)
    if grid_rows:
        tables.append(ExtractedTable(page=1, bbox=[0.0, 0.0, 100.0, 100.0], rows=grid_rows))
    return tables


def ocr_fallback(path: str | Path, doc_id: str) -> ExtractionOutput:
    lines = layout_extract_text(path, page=1)
    tables = table_extract(lines)
    quality_flags = ["ocr_used"]
    return ExtractionOutput(
        doc_id=doc_id,
        lines=lines,
        tables=tables,
        text_coverage_ratio=estimate_text_coverage(path, lines),
        used_ocr=True,
        quality_flags=quality_flags,
    )


def extract_document(path: str | Path, doc_id: str) -> ExtractionOutput:
    path = Path(path)
    lines = layout_extract_text(path)
    coverage = estimate_text_coverage(path, lines)
    if is_probably_scan(coverage, path.suffix):
        return ocr_fallback(path, doc_id)
    tables = table_extract(lines)
    quality_flags: List[str] = []
    if not tables:
        quality_flags.append("no_tables_detected")
    if coverage < 0.35:
        quality_flags.append("low_text_coverage")
    return ExtractionOutput(
        doc_id=doc_id,
        lines=lines,
        tables=tables,
        text_coverage_ratio=coverage,
        used_ocr=False,
        quality_flags=quality_flags,
    )
