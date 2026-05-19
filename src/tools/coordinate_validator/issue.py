"""Coordinate Validator — the issue record type.

Kept in its own leaf module so every check sub-module can import it
without creating an import cycle through core.py.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CoordIssue:
    severity: str          # "ERROR" or "WARNING"
    feature_id: str
    check: str
    message: str

    def as_text(self) -> str:
        return f"  [{self.severity}] {self.feature_id} — {self.check}: {self.message}"
