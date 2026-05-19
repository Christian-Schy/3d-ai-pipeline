"""Coordinate Validator — deterministic geometry/dimension checks.

Public API:
    run_coordinate_check(blueprint) -> list[CoordIssue]
    format_issues_for_planner(issues) -> str
    CoordIssue                          — issue record (severity/feature/check/message)

Package layout — see core.py module docstring.
"""

from .core import format_issues_for_planner, run_coordinate_check
from .issue import CoordIssue

__all__ = ["run_coordinate_check", "format_issues_for_planner", "CoordIssue"]
