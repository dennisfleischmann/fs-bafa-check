from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Any, Dict, List

from .extraction import ExtractionOutput


REQ_PATTERN = re.compile(
    r"(muss|darf\s+nicht|voraussetzung|foerderfaehig|nicht\s+foerderfaehig|<=|>=|uw|u-wert)",
    flags=re.IGNORECASE,
)


@dataclass
class RequirementSnippet:
    doc_id: str
    page: int
    snippet_type: str
    quote: str
    bbox: List[float]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def detect_requirement_snippets(extracted: ExtractionOutput) -> List[RequirementSnippet]:
    snippets: List[RequirementSnippet] = []
    for line in extracted.lines:
        if REQ_PATTERN.search(line.text):
            snippets.append(
                RequirementSnippet(
                    doc_id=extracted.doc_id,
                    page=line.page,
                    snippet_type="paragraph",
                    quote=line.text,
                    bbox=[line.x0, line.y0, line.x1, line.y1],
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
                    )
                )
    return snippets
