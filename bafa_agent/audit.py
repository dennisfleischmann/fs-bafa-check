from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from .utils import ensure_dir, write_json


def persist_case_snapshot(base_dir: str | Path, case_id: str, payload: Dict[str, Any]) -> Path:
    target_dir = Path(base_dir) / case_id
    ensure_dir(target_dir)
    write_json(target_dir / "snapshot.json", payload)
    return target_dir


def persist_pipeline_artifacts(
    base_dir: str | Path,
    case_id: str,
    offer_facts: Dict[str, Any],
    derived: Dict[str, Any],
    evaluation: Dict[str, Any],
) -> Path:
    target_dir = Path(base_dir) / case_id
    ensure_dir(target_dir)
    write_json(target_dir / "offer_facts.json", offer_facts)
    write_json(target_dir / "derived.json", derived)
    write_json(target_dir / "evaluation.json", evaluation)
    return target_dir
