from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_dir(path: str | Path) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def read_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def write_text(path: str | Path, content: str) -> None:
    target = Path(path)
    ensure_dir(target.parent)
    target.write_text(content, encoding="utf-8")


def read_json(path: str | Path, default: Optional[Any] = None) -> Any:
    target = Path(path)
    if not target.exists():
        return default
    return json.loads(target.read_text(encoding="utf-8"))


def write_json(path: str | Path, data: Any, indent: int = 2) -> None:
    target = Path(path)
    ensure_dir(target.parent)
    target.write_text(json.dumps(data, indent=indent, ensure_ascii=True) + "\n", encoding="utf-8")


def append_jsonl(path: str | Path, rows: Iterable[Dict[str, Any]]) -> None:
    target = Path(path)
    ensure_dir(target.parent)
    with target.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def read_jsonl(path: str | Path) -> List[Dict[str, Any]]:
    target = Path(path)
    if not target.exists():
        return []
    rows: List[Dict[str, Any]] = []
    with target.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dotted_get(payload: Dict[str, Any], dotted_path: str, default: Any = None) -> Any:
    current: Any = payload
    parts = dotted_path.split(".")
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
            continue
        if isinstance(current, list):
            if part.endswith("[]"):
                key = part[:-2]
                values = []
                for item in current:
                    if isinstance(item, dict) and key in item:
                        values.append(item[key])
                current = values
                continue
            return default
        return default
    return current


def dotted_set(payload: Dict[str, Any], dotted_path: str, value: Any) -> None:
    parts = dotted_path.split(".")
    current = payload
    for part in parts[:-1]:
        if part not in current or not isinstance(current[part], dict):
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value


def normalize_decimal(value: str) -> str:
    return value.replace(",", ".")


def parse_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (float, int)):
        return float(value)
    if not isinstance(value, str):
        return None
    cleaned = normalize_decimal(value)
    cleaned = re.sub(r"[^0-9.+-]", "", cleaned)
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def normalize_unit(unit: Optional[str]) -> Optional[str]:
    if unit is None:
        return None
    canonical = unit.strip().lower().replace(" ", "")
    variants = {
        "w/m2k": "W/(m2K)",
        "w/(m2k)": "W/(m2K)",
        "w/(m2.k)": "W/(m2K)",
        "w/(m2*k)": "W/(m2K)",
        "w/(m2.kelvin)": "W/(m2K)",
    }
    return variants.get(canonical, unit)


def is_probably_scan(text_coverage_ratio: float, file_extension: str) -> bool:
    if file_extension.lower() != ".pdf":
        return False
    return text_coverage_ratio < 0.20


def stable_case_id(seed: str) -> str:
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]
    return f"case_{digest}"


def safe_slug(value: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_")
    return clean.lower() or "item"


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}
