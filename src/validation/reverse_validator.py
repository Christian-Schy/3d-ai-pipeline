"""Dormant reverse-validator orchestrator.

This module is safe to import and call manually, but it is not connected to
the active LangGraph. The design keeps each check small and evidence-based:
deterministic code checks only structured facts, while text understanding
remains upstream LLM responsibility.
"""
from __future__ import annotations

from typing import Protocol

from src.validation.checks import (
    BBoxCheck,
    FeatureCountCheck,
    HoleFeatureCheck,
    PocketFeatureCheck,
    SlotFeatureCheck,
    VolumeCheck,
)
from src.validation.contracts import CheckResult, ReverseValidationReport
from src.validation.fact_extraction import ExtractedFacts, extract_facts_from_state

GRAPH_INTEGRATION_ENABLED = False
BLOCKING_ENABLED = False


class ReverseCheck(Protocol):
    check_id: str

    def run(self, facts: ExtractedFacts) -> list[CheckResult]:
        """Return one or more results for this narrow check."""


class ReverseValidator:
    """Runs the dormant reverse-validation checks in a fixed order."""

    def __init__(self, checks: tuple[ReverseCheck, ...] | None = None) -> None:
        self.checks = checks or (
            FeatureCountCheck(),
            BBoxCheck(),
            VolumeCheck(),
            HoleFeatureCheck(),
            SlotFeatureCheck(),
            PocketFeatureCheck(),
        )

    def run(self, state: dict) -> ReverseValidationReport:
        facts = extract_facts_from_state(state)
        results: list[CheckResult] = []
        for check in self.checks:
            results.extend(check.run(facts))

        return ReverseValidationReport(
            blueprint_format=facts.blueprint_format,
            checks=tuple(results),
            summary=_summarize(results),
            blocking_enabled=BLOCKING_ENABLED,
            graph_integrated=GRAPH_INTEGRATION_ENABLED,
        )


def _summarize(results: list[CheckResult]) -> str:
    failed = sum(1 for result in results if result.status == "failed")
    unknown = sum(1 for result in results if result.status == "unknown")
    passed = sum(1 for result in results if result.status == "passed")
    skipped = sum(1 for result in results if result.status == "not_applicable")

    if failed:
        return (
            f"{failed} hard failure(s), {unknown} unknown check(s), "
            f"{passed} passed, {skipped} not applicable. Report is non-blocking."
        )
    if unknown:
        return (
            f"No hard failures; {unknown} unknown check(s), "
            f"{passed} passed, {skipped} not applicable. Report is non-blocking."
        )
    return f"All {passed} applicable reverse checks passed. Report is non-blocking."
