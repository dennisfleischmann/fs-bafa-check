from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class BuildState:
    state: str = "staged"
    staged_bundle: Optional[str] = None
    active_bundle: Optional[str] = None

    def mark_validated(self) -> None:
        self.state = "validated"

    def activate(self) -> None:
        if self.staged_bundle is None:
            raise ValueError("staged bundle missing")
        self.active_bundle = self.staged_bundle
        self.state = "active"

    def reject(self) -> None:
        self.state = "staged"
