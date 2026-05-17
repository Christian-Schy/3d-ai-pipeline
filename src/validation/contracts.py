"""Contracts for the dormant reverse-validation path.

The reverse validator is intentionally not wired into the LangGraph. These
contracts define the report shape so future checks can be added without
changing the active pipeline or overloading one validator with many jobs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

CheckStatus = Literal["passed", "failed", "unknown", "not_applicable"]
IssueSeverity = Literal["info", "warning", "error", "critical"]
EvidenceSource = Literal[
    "resolved_blueprint",
    "semantic_blueprint",
    "executor_geometry_state",
    "validator_stats",
    "generated_code",
    "llm_semantics",
    "derived",
]


@dataclass(frozen=True)
class Evidence:
    """One small piece of evidence used by a check."""

    source: EvidenceSource
    path: str
    value: Any
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "path": self.path,
            "value": self.value,
            "note": self.note,
        }


@dataclass(frozen=True)
class CheckResult:
    """Result of one narrow validation question."""

    check_id: str
    status: CheckStatus
    severity: IssueSeverity
    message: str
    feature_id: str | None = None
    expected: Any = None
    actual: Any = None
    evidence: tuple[Evidence, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_blocking_failure(self) -> bool:
        """True only for explicit hard failures, never for unknowns."""
        return self.status == "failed" and self.severity in {"error", "critical"}

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "status": self.status,
            "severity": self.severity,
            "message": self.message,
            "feature_id": self.feature_id,
            "expected": self.expected,
            "actual": self.actual,
            "evidence": [item.to_dict() for item in self.evidence],
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class ReverseValidationReport:
    """Aggregated report for the dormant reverse validator.

    `blocking_enabled` is deliberately false for the scaffold. The report may
    contain hard failures, but nothing in the active graph consumes it yet.
    """

    blueprint_format: str
    checks: tuple[CheckResult, ...]
    summary: str
    blocking_enabled: bool = False
    graph_integrated: bool = False

    @property
    def has_failures(self) -> bool:
        return any(check.status == "failed" for check in self.checks)

    @property
    def has_unknowns(self) -> bool:
        return any(check.status == "unknown" for check in self.checks)

    @property
    def would_block_if_enabled(self) -> bool:
        return any(check.is_blocking_failure for check in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "blueprint_format": self.blueprint_format,
            "blocking_enabled": self.blocking_enabled,
            "graph_integrated": self.graph_integrated,
            "has_failures": self.has_failures,
            "has_unknowns": self.has_unknowns,
            "would_block_if_enabled": self.would_block_if_enabled,
            "summary": self.summary,
            "checks": [check.to_dict() for check in self.checks],
        }
