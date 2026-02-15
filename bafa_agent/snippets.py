from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

from .extraction import ExtractionOutput


REQ_PATTERN = re.compile(
    r"(muss|darf\s+nicht|voraussetzung|foerderfaehig|nicht\s+foerderfaehig|<=|>=|uw|u-wert|einbaufuge|anschlussfuge|fuge|abdichtung)",
    flags=re.IGNORECASE,
)
SECTION_HEADER_PATTERN = re.compile(r"^\s*([1-9](?:\.\d+){0,3})\s+(.+?)\s*$")


@dataclass
class RequirementSnippet:
    doc_id: str
    page: int
    snippet_type: str
    quote: str
    bbox: List[float]
    section_id: Optional[str] = None
    section_title: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def detect_requirement_snippets(extracted: ExtractionOutput) -> List[RequirementSnippet]:
    snippets: List[RequirementSnippet] = []
    current_section_id: Optional[str] = None
    current_section_title: Optional[str] = None

    for line in extracted.lines:
        header_match = SECTION_HEADER_PATTERN.match(line.text)
        if header_match:
            current_section_id = header_match.group(1).strip()
            current_section_title = header_match.group(2).strip()
            snippets.append(
                RequirementSnippet(
                    doc_id=extracted.doc_id,
                    page=line.page,
                    snippet_type="section_header",
                    quote=line.text,
                    bbox=[line.x0, line.y0, line.x1, line.y1],
                    section_id=current_section_id,
                    section_title=current_section_title,
                )
            )
        if REQ_PATTERN.search(line.text):
            snippets.append(
                RequirementSnippet(
                    doc_id=extracted.doc_id,
                    page=line.page,
                    snippet_type="paragraph",
                    quote=line.text,
                    bbox=[line.x0, line.y0, line.x1, line.y1],
                    section_id=current_section_id,
                    section_title=current_section_title,
                )
            )
    for table in extracted.tables:
        for row in table.rows:
            quote = " | ".join(row)
            if REQ_PATTERN.search(quote):
                snippets.append(
                    RequirementSnippet(
                    doc_id=extracted.doc_id,
                    page=table.page,
                    snippet_type="table_row",
                    quote=quote,
                    bbox=table.bbox,
                    section_id=current_section_id,
                    section_title=current_section_title,
                )
            )
    return snippets
