#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from bafa_agent.config import load_project_config
from bafa_agent.pipeline import evaluate_offer
from bafa_agent.utils import write_json

ALLOWED_BAFA_SUFFIXES = {".pdf", ".txt", ".md", ".json", ".doc", ".docx"}
DEFAULT_MODEL = "gpt-5.2"
PLAUSIBILITY_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "case_id",
        "overall_correct",
        "summary",
        "measure_checks",
        "critical_issues",
        "recommendations",
    ],
    "properties": {
        "case_id": {"type": "string"},
        "overall_correct": {"type": "boolean"},
        "summary": {"type": "string", "maxLength": 800},
        "measure_checks": {
            "type": "array",
            "maxItems": 20,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "measure_id",
                    "local_status",
                    "llm_verdict",
                    "reason",
                    "suggested_status",
                    "critical_quotes",
                ],
                "properties": {
                    "measure_id": {"type": "string"},
                    "local_status": {"type": "string"},
                    "llm_verdict": {"type": "string", "enum": ["correct", "incorrect", "unclear"]},
                    "reason": {"type": "string", "maxLength": 600},
                    "suggested_status": {"type": "string"},
                    "critical_quotes": {
                        "type": "array",
                        "maxItems": 4,
                        "items": {"type": "string", "maxLength": 280},
                    },
                },
            },
        },
        "critical_issues": {
            "type": "array",
            "maxItems": 8,
            "items": {"type": "string", "maxLength": 300},
        },
        "recommendations": {
            "type": "array",
            "maxItems": 8,
            "items": {"type": "string", "maxLength": 300},
        },
    },
}


def _fail(message: str, code: int = 1) -> int:
    print(f"error: {message}", file=sys.stderr)
    return code


def _collect_bafa_files(source_docs_dir: Path) -> List[Path]:
    if not source_docs_dir.exists():
        return []
    files: List[Path] = []
    for path in sorted(source_docs_dir.glob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in ALLOWED_BAFA_SUFFIXES:
            continue
        files.append(path)
    return files


def _extract_output_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    payload = None
    if hasattr(response, "model_dump"):
        payload = response.model_dump()
    elif isinstance(response, dict):
        payload = response
    if not isinstance(payload, dict):
        return ""

    chunks: List[str] = []
    for item in payload.get("output", []) or []:
        for content in item.get("content", []) or []:
            if not isinstance(content, dict):
                continue
            if content.get("type") == "output_text" and content.get("text"):
                chunks.append(str(content["text"]))
            text_obj = content.get("text")
            if isinstance(text_obj, dict) and text_obj.get("value"):
                chunks.append(str(text_obj["value"]))
            elif isinstance(text_obj, str):
                chunks.append(text_obj)
    return "\n".join(part for part in chunks if part).strip()


def _extract_json(text: str) -> Dict[str, Any]:
    stripped = text.strip()
    if not stripped:
        return {}

    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and start < end:
        candidate = stripped[start : end + 1]
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return {"_parse_error": "response_not_valid_json", "_raw": stripped}
    return {"_parse_error": "response_not_valid_json", "_raw": stripped}


def _upload_file(client: Any, path: Path) -> Dict[str, str]:
    last_error: Optional[Exception] = None
    for purpose in ("user_data", "assistants"):
        try:
            with path.open("rb") as handle:
                uploaded = client.files.create(file=handle, purpose=purpose)
            return {"path": str(path), "file_id": uploaded.id, "purpose": purpose}
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"failed to upload {path}: {last_error}")


def _read_text_limited(path: Path, max_chars: int = 200_000) -> str:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[TRUNCATED]"


def _plausibility_prompt(case_id: str) -> str:
    return (
        "Du bist ein strenger BAFA/BEG-Pruefer. "
        "Dir liegen als Dateien BAFA-Quellen, das Angebotsdokument und die lokale Evaluation vor.\n\n"
        "Aufgabe:\n"
        "1) Pruefe primaer, ob die lokalen STATUS-Entscheidungen je measure fachlich plausibel sind "
        "(PASS/FAIL/CLARIFY/ABORT).\n"
        "2) Kosten-/Summenfragen nur dann als 'incorrect' werten, wenn sie den Status aendern wuerden.\n"
        "3) Wenn es nur Kosten-/Dokuhinweise gibt, aber der Status trotzdem tragfaehig ist, "
        "setze llm_verdict='correct' und schreibe Hinweise in critical_issues/recommendations.\n"
        "4) overall_correct = true, wenn keine measure mit llm_verdict='incorrect' vorliegt.\n"
        "5) Antworte NUR als gueltiges JSON.\n"
        "6) Beziehe dich nur auf die bereitgestellten Dateien.\n\n"
        "Erwartetes JSON-Schema:\n"
        "{\n"
        '  "case_id": "<string>",\n'
        '  "overall_correct": <true|false>,\n'
        '  "summary": "<kurze Zusammenfassung>",\n'
        '  "measure_checks": [\n'
        "    {\n"
        '      "measure_id": "<string>",\n'
        '      "local_status": "<PASS|FAIL|CLARIFY|ABORT|UNKNOWN>",\n'
        '      "llm_verdict": "<correct|incorrect|unclear>",\n'
        '      "reason": "<Begruendung>",\n'
        '      "suggested_status": "<PASS|FAIL|CLARIFY|ABORT|UNCHANGED>",\n'
        '      "critical_quotes": ["<quote1>", "<quote2>"]\n'
        "    }\n"
        "  ],\n"
        '  "critical_issues": ["<issue1>", "<issue2>"],\n'
        '  "recommendations": ["<rec1>", "<rec2>"]\n'
        "}\n\n"
        "Halte die Antwort knapp: pro measure maximal 2 kurze Quotes.\n"
        f"Hinweis: case_id ist {case_id}."
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Upload BAFA source files + offer + local evaluation and run LLM plausibility check."
    )
    parser.add_argument("--base-dir", default=os.getenv("BAFA_BASE_DIR", "."), help="project base directory")
    parser.add_argument("--offer", required=True, help="path to offer.txt")
    parser.add_argument(
        "--model",
        default=os.getenv("OPENAI_PLAUSIBILITY_MODEL", DEFAULT_MODEL),
        help=f"OpenAI model for plausibility check (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--source-docs-dir",
        default="rules/source_docs",
        help="relative path to BAFA source docs directory",
    )
    parser.add_argument(
        "--out",
        default="",
        help="output json report path (default: data/cases/<case_id>/plausibility_check.json)",
    )
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=4000,
        help="max output tokens for the plausibility model",
    )
    parser.add_argument(
        "--skip-evaluate",
        action="store_true",
        help="skip fresh local evaluation and use existing data/cases/<case_id>/evaluation.json",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="only print compact status line",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    base = Path(args.base_dir).resolve()
    offer_path = Path(args.offer).resolve()
    if not offer_path.exists():
        return _fail(f"offer file not found: {offer_path}")

    load_project_config(base)
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return _fail("OPENAI_API_KEY is not set")

    try:
        from openai import OpenAI
    except Exception:
        return _fail("python package 'openai' is not installed. Run: pip install openai")

    if args.skip_evaluate:
        case_dirs = sorted((base / "data" / "cases").glob("case_*"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not case_dirs:
            return _fail("no case found under data/cases; run evaluate first or remove --skip-evaluate")
        evaluation_path = case_dirs[0] / "evaluation.json"
        if not evaluation_path.exists():
            return _fail(f"evaluation file not found: {evaluation_path}")
        evaluation_payload = json.loads(evaluation_path.read_text(encoding="utf-8"))
    else:
        evaluation_payload = evaluate_offer(base, offer_path)

    case_id = str(evaluation_payload.get("case_id") or "unknown_case")
    case_dir = base / "data" / "cases" / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    evaluation_input_path = case_dir / "evaluation_for_plausibility.json"
    write_json(evaluation_input_path, evaluation_payload)

    source_docs_dir = (base / args.source_docs_dir).resolve()
    bafa_files = _collect_bafa_files(source_docs_dir)
    if not bafa_files:
        return _fail(f"no BAFA files found in {source_docs_dir}")

    client = OpenAI(api_key=api_key)

    uploaded: List[Dict[str, str]] = []

    # 1) Upload and reference all BAFA files (PDFs) as input_file.
    for file_path in bafa_files:
        uploaded.append(_upload_file(client, file_path))

    # 2) Upload offer file too (as requested), but only reference as input_file if it is a PDF.
    offer_upload = _upload_file(client, offer_path)
    uploaded.append(offer_upload)

    # 3) Upload local evaluation snapshot for traceability, pass its content as input_text.
    eval_upload = _upload_file(client, evaluation_input_path)
    uploaded.append(eval_upload)

    content: List[Dict[str, str]] = []
    referenced_file_ids: List[str] = []
    for item in uploaded:
        path = Path(item["path"])
        if path.suffix.lower() == ".pdf":
            content.append({"type": "input_file", "file_id": item["file_id"]})
            referenced_file_ids.append(item["file_id"])

    if offer_path.suffix.lower() != ".pdf":
        offer_text = _read_text_limited(offer_path)
        content.append(
            {
                "type": "input_text",
                "text": (
                    "ANGEBOT (Textdatei, da input_file in diesem Run nur PDF akzeptiert):\n\n"
                    f"{offer_text}"
                ),
            }
        )

    evaluation_text = _read_text_limited(evaluation_input_path)
    content.append(
        {
            "type": "input_text",
            "text": f"LOKALES EVALUATION JSON:\n\n{evaluation_text}",
        }
    )
    content.append({"type": "input_text", "text": _plausibility_prompt(case_id)})

    response = client.responses.create(
        model=args.model,
        input=[{"role": "user", "content": content}],
        max_output_tokens=args.max_output_tokens,
        text={
            "format": {
                "type": "json_schema",
                "name": "plausibility_report",
                "schema": PLAUSIBILITY_JSON_SCHEMA,
                "strict": True,
            }
        },
    )

    raw_text = _extract_output_text(response)
    parsed = _extract_json(raw_text)

    out_path = Path(args.out).resolve() if args.out else (case_dir / "plausibility_check.json")
    report = {
        "case_id": case_id,
        "model": args.model,
        "uploaded_files": uploaded,
        "referenced_file_ids": referenced_file_ids,
        "evaluation_path": str(case_dir / "evaluation.json"),
        "plausibility": parsed,
        "raw_model_output": raw_text,
    }
    write_json(out_path, report)

    print(f"plausibility check written: {out_path}")
    overall = parsed.get("overall_correct", "unknown")
    print({"case_id": case_id, "overall_correct": overall, "model": args.model})
    if not args.quiet:
        summary = parsed.get("summary")
        if isinstance(summary, str) and summary.strip():
            print(f"summary: {summary}")
        issues = parsed.get("critical_issues", [])
        if isinstance(issues, list) and issues:
            print("critical_issues:")
            for idx, issue in enumerate(issues[:5], start=1):
                print(f"{idx}. {issue}")
        checks = parsed.get("measure_checks", [])
        if isinstance(checks, list) and checks:
            print("measure_checks:")
            for item in checks:
                if not isinstance(item, dict):
                    continue
                print(
                    f"- {item.get('measure_id', 'unknown')}: "
                    f"local={item.get('local_status', 'UNKNOWN')} "
                    f"verdict={item.get('llm_verdict', 'unclear')} "
                    f"suggested={item.get('suggested_status', 'UNCHANGED')}"
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
