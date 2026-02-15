from __future__ import annotations

import json

from bafa_agent.pipeline import compile_rules

from .config import project_root


def main() -> int:
    report = compile_rules(base_dir=project_root(), source="bafa")
    print(json.dumps(report, ensure_ascii=True))
    return 0 if report.get("validation_passed") else 2


if __name__ == "__main__":
    raise SystemExit(main())
