from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .normalization import normalize_measure_values
from .semantic_matcher import SemanticMatch, match_offer_line
from .taxonomy import map_component, map_cost_category
from .utils import parse_float, read_text

U_PATTERN = re.compile(
    r"\bU(?:\s*-\s*Wert|\s*Wert)?\s*[=:]?\s*([0-9]+[.,]?[0-9]*)\s*W",
    flags=re.IGNORECASE,
)
UW_PATTERN = re.compile(
    r"\bUw(?:\s*-\s*Wert|\s*Wert)?\s*[=:]?\s*([0-9]+[.,]?[0-9]*)\s*W",
    flags=re.IGNORECASE,
)
LAMBDA_PATTERN = re.compile(r"(?:lambda|wls)\s*([0-9]+[.,]?[0-9]*)", flags=re.IGNORECASE)
THICKNESS_PATTERN = re.compile(r"([0-9]+[.,]?[0-9]*)\s*(mm|cm|m)\b", flags=re.IGNORECASE)
PAGE_PATTERN = re.compile(r"^=+\s*PAGE\s+(\d+)\s*=+$", flags=re.IGNORECASE)
AMOUNT_TOKEN = r"(?:[0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2}|[0-9]+,[0-9]{2})"
TABLE_ROW_PATTERN = re.compile(
    rf"^\s*[_-]?\s*(?P<position>\d+)\s+"
    rf"(?P<quantity>[0-9]+(?:[.,][0-9]+)?)\s*(?P<unit>\S+)?\s+"
    rf"(?P<description>.+?)\s+(?P<unit_price>{AMOUNT_TOKEN})\s+(?P<total_price>{AMOUNT_TOKEN})\s*$",
    flags=re.IGNORECASE,
)
GENERIC_PRICE_LINE_PATTERN = re.compile(
    rf"^\s*(?P<description>[A-Za-z].+?)\s+(?P<unit_price>{AMOUNT_TOKEN})\s+(?P<total_price>{AMOUNT_TOKEN})\s*$",
    flags=re.IGNORECASE,
)

SEMANTIC_ITEM_CONFIDENCE = 0.58
SEMANTIC_COMPONENT_OVERRIDE_CONFIDENCE = 0.74

NOISE_LINE_TOKENS = (
    "kontakt@",
    "st nr",
    "ust id",
    "iban",
    "bic",
    "blz",
    "kto",
    "www.",
    "sehr geehrter",
    "mit freundlichen",
)
SUMMARY_LINE_TOKENS = (
    "uebertrag",
    "summe netto",
    "summe brutto",
    "mwst",
    "angebot :",
    "an das angebot",
)


def _to_meters(value: float, unit: str) -> Optional[float]:
    if unit == "m":
        return value
    if unit == "cm":
        return value / 100.0
    if unit == "mm":
        return value / 1000.0
    return None


def _extract_values(line: str) -> Dict[str, Any]:
    values: Dict[str, Any] = {}
    uw_match = UW_PATTERN.search(line)
    if uw_match:
        values["uw"] = {
            "value": parse_float(uw_match.group(1)),
            "unit": "W/(m2K)",
            "evidence": line,
        }
    else:
        u_match = U_PATTERN.search(line)
        if u_match:
            values["u_value_target"] = {
                "value": parse_float(u_match.group(1)),
                "unit": "W/(m2K)",
                "evidence": line,
            }

    lamb_match = LAMBDA_PATTERN.search(line)
    thick_match = THICKNESS_PATTERN.search(line)
    if lamb_match and thick_match:
        lamb = parse_float(lamb_match.group(1))
        thickness = parse_float(thick_match.group(1))
        unit = thick_match.group(2).lower()
        d_m = _to_meters(thickness or 0.0, unit)
        if d_m is not None:
            values.setdefault("layers", []).append(
                {
                    "name": "layer",
                    "d_m": d_m,
                    "lambda": lamb,
                    "evidence": line,
                }
            )
    return values


def _normalize_token(text: str) -> str:
    return (
        text.lower()
        .replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )


def _parse_amount_token(value: str) -> Optional[float]:
    token = value.strip().replace(" ", "")
    token = token.replace(".", "").replace(",", ".")
    return parse_float(token)


def _line_has_noise_only(line: str) -> bool:
    token = _normalize_token(line)
    if not token:
        return True
    return any(noise in token for noise in NOISE_LINE_TOKENS)


def _line_is_summary(line: str) -> bool:
    token = _normalize_token(line)
    return any(marker in token for marker in SUMMARY_LINE_TOKENS)


def _iter_offer_lines(content: str) -> List[Dict[str, Any]]:
    page = 1
    rows: List[Dict[str, Any]] = []
    for raw in content.splitlines():
        line = raw.rstrip()
        marker = PAGE_PATTERN.match(line.strip())
        if marker:
            page = int(marker.group(1))
            continue
        rows.append({"page": page, "line": line})
    return rows


def _extract_line_item(line: str) -> Optional[Dict[str, Any]]:
    if _line_is_summary(line):
        return None

    matched = TABLE_ROW_PATTERN.match(line)
    if matched:
        total_amount = _parse_amount_token(matched.group("total_price"))
        if total_amount is None:
            return None
        return {
            "position": int(matched.group("position")),
            "quantity": parse_float(matched.group("quantity")),
            "unit": matched.group("unit") or None,
            "description": " ".join(matched.group("description").split()),
            "amount": total_amount,
            "currency": "EUR",
        }

    matched = GENERIC_PRICE_LINE_PATTERN.match(line)
    if matched:
        description = " ".join(matched.group("description").split())
        if _line_is_summary(description):
            return None
        total_amount = _parse_amount_token(matched.group("total_price"))
        if total_amount is None:
            return None
        return {
            "position": None,
            "quantity": None,
            "unit": None,
            "description": description,
            "amount": total_amount,
            "currency": "EUR",
        }

    return None


def _new_measure(component: str) -> Dict[str, Any]:
    return {
        "measure_id": f"envelope_{component}",
        "component_type": component,
        "input_mode": "direct_u",
        "values": {},
        "layers": [],
        "geometry": {},
        "costs": {"total": 0.0, "currency": "EUR"},
        "line_items": [],
        "evidence": [],
    }


def _ensure_bucket(measures: Dict[str, Dict[str, Any]], component: str) -> Dict[str, Any]:
    return measures.setdefault(component, _new_measure(component))


def _resolve_item_component(
    lexical_component: Optional[str],
    semantic: Optional[SemanticMatch],
    active_component: Optional[str],
) -> Optional[str]:
    if semantic and semantic.confidence >= SEMANTIC_ITEM_CONFIDENCE:
        return semantic.component
    if lexical_component:
        return lexical_component
    return active_component


def _resolve_evidence_component(
    lexical_component: Optional[str],
    semantic: Optional[SemanticMatch],
    extracted: Dict[str, Any],
) -> Optional[str]:
    # Prefer a strong semantic match over lexical taxonomy in ambiguous lines,
    # e.g. "schlagregendichter Anschluss ... Fassadendaemmung".
    if semantic and semantic.confidence >= SEMANTIC_COMPONENT_OVERRIDE_CONFIDENCE:
        return semantic.component
    if "uw" in extracted:
        return "fenster"
    if lexical_component:
        return lexical_component
    if semantic and semantic.confidence >= SEMANTIC_ITEM_CONFIDENCE:
        return semantic.component
    return None


def _append_evidence(bucket: Dict[str, Any], page: int, line: str) -> None:
    bucket["evidence"].append(
        {
            "doc_id": "offer",
            "page": page,
            "quote": line,
            "bbox": None,
            "source_path": None,
        }
    )


def parse_offer_text(path: str | Path) -> Dict[str, Any]:
    content = read_text(path)
    measures: Dict[str, Dict[str, Any]] = {}
    active_component: Optional[str] = None

    for row in _iter_offer_lines(content):
        page = int(row["page"])
        line = str(row["line"]).strip()
        if not line:
            continue
        if _line_has_noise_only(line):
            continue

        extracted = _extract_values(line)
        lexical_component = map_component(line)
        semantic = match_offer_line(line)
        evidence_component = _resolve_evidence_component(lexical_component, semantic, extracted)
        item = _extract_line_item(line)
        item_component = _resolve_item_component(lexical_component, semantic, active_component) if item else None

        if evidence_component is None and item_component is not None:
            evidence_component = item_component

        if evidence_component is None and not extracted and item is None:
            continue

        if evidence_component is not None:
            active_component = evidence_component
            bucket = _ensure_bucket(measures, evidence_component)
        elif active_component is not None:
            bucket = _ensure_bucket(measures, active_component)
        else:
            continue

        if "uw" in extracted:
            bucket["values"]["uw"] = extracted["uw"]
        if "u_value_target" in extracted:
            bucket["values"]["u_value_target"] = extracted["u_value_target"]
        layers = extracted.get("layers", [])
        if layers:
            bucket["input_mode"] = "layers"
            bucket["layers"].extend(layers)

        _append_evidence(bucket, page, line)

        if item and item_component:
            target = _ensure_bucket(measures, item_component)
            if target is not bucket:
                _append_evidence(target, page, line)

            category = map_cost_category(item["description"]) or map_cost_category(line) or "material"
            if semantic and semantic.component == item_component and semantic.confidence >= SEMANTIC_ITEM_CONFIDENCE:
                category = semantic.category or category

            item_payload: Dict[str, Any] = {
                "description": item["description"],
                "amount": float(item["amount"]),
                "currency": item["currency"],
                "category": category,
            }
            if item.get("position") is not None:
                item_payload["position"] = item["position"]
            if item.get("quantity") is not None:
                item_payload["quantity"] = item["quantity"]
            if item.get("unit"):
                item_payload["unit"] = item["unit"]

            if semantic and semantic.component == item_component and semantic.confidence >= SEMANTIC_ITEM_CONFIDENCE:
                item_payload["item_code"] = semantic.item_code
                item_payload["semantic_confidence"] = semantic.confidence
                item_payload["semantic_method"] = semantic.method

            target["line_items"].append(item_payload)
            target["costs"]["total"] += float(item["amount"])

    normalized_measures: List[Dict[str, Any]] = []
    for measure in measures.values():
        normalized_measures.append(normalize_measure_values(measure))

    return {
        "building": {"is_existing": True, "type": "WG", "monument": False},
        "applicant": {"income_bonus_requested": False},
        "offer": {
            "input_mode": "mixed",
            "measures": normalized_measures,
        },
        "docs": {
            "fachunternehmererklaerung_present": False,
            "tauwassernachweis_present": None,
        },
    }
