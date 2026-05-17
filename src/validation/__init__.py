"""Dormant reverse-validation package.

The package is intentionally not wired into `src.graph.pipeline`. It can be
used for manual/shadow reports while the active validator path remains stable.
"""
from src.validation.contracts import CheckResult, Evidence, ReverseValidationReport
from src.validation.reverse_validator import (
    BLOCKING_ENABLED,
    GRAPH_INTEGRATION_ENABLED,
    ReverseValidator,
)

__all__ = [
    "BLOCKING_ENABLED",
    "GRAPH_INTEGRATION_ENABLED",
    "CheckResult",
    "Evidence",
    "ReverseValidationReport",
    "ReverseValidator",
]
