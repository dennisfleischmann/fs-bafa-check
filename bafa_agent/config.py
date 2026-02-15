from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Iterable, Optional


def _strip_quotes(value: str) -> str:
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    return value


def parse_env_file(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not path.exists() or not path.is_file():
        return values

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = _strip_quotes(value.strip())
        values[key] = value
    return values


def apply_env(values: Dict[str, str], override: bool = False) -> None:
    for key, value in values.items():
        if override or key not in os.environ:
            os.environ[key] = value


def find_project_root(start: Optional[Path] = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in [current] + list(current.parents):
        if (candidate / ".git").exists() or (candidate / "config.env").exists():
            return candidate
    return current


def load_project_config(base_dir: Optional[str | Path] = None) -> Dict[str, str]:
    root = find_project_root(Path(base_dir) if base_dir else None)
    loaded: Dict[str, str] = {}

    config_env = root / "config.env"
    dotenv = root / ".env"

    defaults = parse_env_file(config_env)
    apply_env(defaults, override=False)
    loaded.update(defaults)

    local = parse_env_file(dotenv)
    apply_env(local, override=True)
    loaded.update(local)

    return loaded
