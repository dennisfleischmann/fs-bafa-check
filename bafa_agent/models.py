from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional


class DecisionStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    CLARIFY = "CLARIFY"
    ABORT = "ABORT"


class Severity(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    CLARIFY = "CLARIFY"
    ABORT = "ABORT"


class DocClass(str, Enum):
    PDF_TEXT = "pdf_text"
    PDF_SCAN = "pdf_scan"
    DOCX = "docx"
    EMAIL_TEXT = "email_text"
    UNKNOWN = "unknown"


@dataclass
class Evidence:
    doc_id: str
    page: int
    quote: str
    bbox: Optional[List[float]] = None
    source_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Condition:
    field: str
    op: str
    value: Any = None
    value_from: Optional[str] = None
    unit: Optional[str] = None
    evidence_required: bool = False
    severity_if_missing: Severity = Severity.CLARIFY

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["severity_if_missing"] = self.severity_if_missing.value
        return payload


@dataclass
class RequiredField:
    path: str
    severity_if_missing: Severity = Severity.CLARIFY


@dataclass
class Exclusion:
    when_all_of: List[Condition] = field(default_factory=list)
    result: DecisionStatus = DecisionStatus.CLARIFY
    message_key: str = ""


@dataclass
class CostRule:
    eligible_cost_categories: List[str] = field(default_factory=list)
    ineligible_cost_categories: List[str] = field(default_factory=list)
    split_rules: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class DocumentationRule:
    must_have: List[Dict[str, Any]] = field(default_factory=list)
    nice_to_have: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class TechnicalRequirements:
    thresholds: List[Dict[str, Any]] = field(default_factory=list)
    calculation_methods: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class MeasureSpec:
    measure_id: str
    module: str
    title: str
    version: str
    legal_basis: List[Dict[str, Any]] = field(default_factory=list)
    scope: Dict[str, Any] = field(default_factory=dict)
    required_fields: List[RequiredField] = field(default_factory=list)
    eligibility: Dict[str, Any] = field(default_factory=dict)
    technical_requirements: TechnicalRequirements = field(default_factory=TechnicalRequirements)
    cost_rules: CostRule = field(default_factory=CostRule)
    documentation: DocumentationRule = field(default_factory=DocumentationRule)
    outputs: Dict[str, Any] = field(default_factory=dict)
    examples: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MeasureSpec":
        required = [
            RequiredField(
                path=item["path"],
                severity_if_missing=Severity(item.get("severity_if_missing", "CLARIFY")),
            )
            for item in data.get("required_fields", [])
        ]
        technical = TechnicalRequirements(**data.get("technical_requirements", {}))
        cost_rules = CostRule(**data.get("cost_rules", {}))
        documentation = DocumentationRule(**data.get("documentation", {}))
        return cls(
            measure_id=data["measure_id"],
            module=data.get("module", ""),
            title=data.get("title", ""),
            version=data.get("version", ""),
            legal_basis=data.get("legal_basis", []),
            scope=data.get("scope", {}),
            required_fields=required,
            eligibility=data.get("eligibility", {}),
            technical_requirements=technical,
            cost_rules=cost_rules,
            documentation=documentation,
            outputs=data.get("outputs", {}),
            examples=data.get("examples", {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["required_fields"] = [
            {
                "path": rf.path,
                "severity_if_missing": rf.severity_if_missing.value,
            }
            for rf in self.required_fields
        ]
        return payload


@dataclass
class LineItem:
    description: str
    amount: float
    currency: str = "EUR"
    category: Optional[str] = None
    evidence: Optional[Evidence] = None


@dataclass
class MeasureFact:
    measure_id: Optional[str]
    component_type: str
    input_mode: str
    values: Dict[str, Any] = field(default_factory=dict)
    layers: List[Dict[str, Any]] = field(default_factory=list)
    geometry: Dict[str, Any] = field(default_factory=dict)
    costs: Dict[str, Any] = field(default_factory=dict)
    line_items: List[LineItem] = field(default_factory=list)
    evidence: List[Evidence] = field(default_factory=list)


@dataclass
class OfferFacts:
    case_id: str
    building: Dict[str, Any]
    applicant: Dict[str, Any]
    offer: Dict[str, Any]
    docs: Dict[str, Any]
    quality_flags: List[str] = field(default_factory=list)


@dataclass
class EvaluationResult:
    measure_id: str
    status: DecisionStatus
    reason: str
    used_evidence: List[Evidence] = field(default_factory=list)
    questions: List[str] = field(default_factory=list)
    cost_summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "measure_id": self.measure_id,
            "status": self.status.value,
            "reason": self.reason,
            "used_evidence": [ev.to_dict() for ev in self.used_evidence],
            "questions": self.questions,
            "cost_summary": self.cost_summary,
        }


@dataclass
class EvaluationReport:
    case_id: str
    results: List[EvaluationResult]
    generated_at: str
    ruleset_version: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "generated_at": self.generated_at,
            "ruleset_version": self.ruleset_version,
            "results": [result.to_dict() for result in self.results],
        }


@dataclass
class ManifestDocument:
    doc_id: str
    source_url: str
    download_date: str
    version_hint: str
    valid_from: Optional[str]
    sha256: str
    priority: int
    module_tags: List[str]
    normative: bool
    local_path: str


@dataclass
class Manifest:
    generated_at: str
    docs: List[ManifestDocument] = field(default_factory=list)


@dataclass
class BuildReport:
    staged_bundle: str
    active_bundle: Optional[str]
    validation_passed: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class EscalationTicket:
    case_id: str
    reasons: List[str]
    severity: str
    payload: Dict[str, Any]
