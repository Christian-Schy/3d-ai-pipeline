"""
src/graph/run_status.py -- Shared success/failure classification for pipeline runs.

STL remains the preview/download artifact, but a run is only considered a
successful training/regression sample when the deterministic pipeline also
produced a blueprint and did not leave validation errors unresolved.
"""

from __future__ import annotations

from typing import Any


def has_blueprint_content(state: dict[str, Any] | None) -> bool:
    """Return True when the state contains a non-empty blueprint payload."""
    if not isinstance(state, dict):
        return False
    blueprint = state.get("blueprint") or {}
    if not isinstance(blueprint, dict):
        return False

    features = blueprint.get("features")
    if isinstance(features, dict):
        return bool(features)
    if isinstance(features, list):
        return bool(features)

    # Legacy CSG-tree path: keep old successful runs classifiable.
    return bool(blueprint.get("root"))


def failure_reason(state: dict[str, Any] | None) -> str:
    """Return an empty string for success, otherwise the first blocking reason."""
    if not isinstance(state, dict):
        return "No pipeline state produced"

    for key in ("execution_error", "validation_error", "validator_feedback"):
        value = state.get(key)
        if value:
            return str(value)

    if state.get("coordinate_errors_unresolved"):
        return (
            str(state.get("coordinate_validation_issues") or "").strip()
            or "Coordinate validation errors remain unresolved"
        )

    if not state.get("stl_path"):
        return "No STL produced"

    if not has_blueprint_content(state):
        return "No blueprint produced"

    return ""


def is_successful_state(state: dict[str, Any] | None) -> bool:
    """Shared success gate for UI, API, logs, and training exports."""
    return failure_reason(state) == ""
