"""Bounding-box checks for simple roots with observed geometry extents."""
from __future__ import annotations

from math import isclose

from src.validation.contracts import CheckResult, Evidence
from src.validation.fact_extraction import ExtractedFacts, FeatureFact


class BBoxCheck:
    """Compare expected simple-root dimensions against executor extents."""

    check_id = "geometry.bbox"

    def __init__(self, abs_tolerance_mm: float = 0.5) -> None:
        self.abs_tolerance_mm = abs_tolerance_mm

    def run(self, facts: ExtractedFacts) -> list[CheckResult]:
        extents = _observed_extents(facts)
        if not extents:
            return [
                CheckResult(
                    check_id=self.check_id,
                    status="unknown",
                    severity="warning",
                    message="No observed geometry extents available.",
                )
            ]

        root = _single_root_feature(facts)
        if root is None:
            return [
                CheckResult(
                    check_id=self.check_id,
                    status="unknown",
                    severity="warning",
                    message="BBox check only supports blueprints with exactly one root feature.",
                    actual={"root_feature_ids": facts.root_feature_ids},
                )
            ]

        expected = _expected_root_extents(root)
        if expected is None:
            return [
                CheckResult(
                    check_id=self.check_id,
                    status="unknown",
                    severity="warning",
                    message=f"Root feature type '{root.feature_type}' has no deterministic BBox rule yet.",
                    feature_id=root.feature_id,
                    evidence=(Evidence("resolved_blueprint", root.source_path, root.params),),
                )
            ]

        expected_sorted = sorted(expected)
        actual_sorted = sorted(extents)
        matches = all(
            isclose(exp, act, abs_tol=self.abs_tolerance_mm, rel_tol=0.0)
            for exp, act in zip(expected_sorted, actual_sorted, strict=True)
        )

        return [
            CheckResult(
                check_id=self.check_id,
                status="passed" if matches else "failed",
                severity="info" if matches else "error",
                message=(
                    "Observed BBox matches expected simple-root dimensions."
                    if matches
                    else "Observed BBox differs from expected simple-root dimensions."
                ),
                feature_id=root.feature_id,
                expected=expected_sorted,
                actual=actual_sorted,
                evidence=(
                    Evidence("resolved_blueprint", root.source_path, root.params),
                    Evidence("executor_geometry_state", "geometry.extents_mm", extents),
                ),
                metadata={"abs_tolerance_mm": self.abs_tolerance_mm},
            )
        ]


def _observed_extents(facts: ExtractedFacts) -> list[float]:
    extents = facts.geometry.get("extents_mm") or facts.validator_stats.get("extents_mm")
    if not extents:
        extents = facts.validator_stats.get("size_mm")
    if not extents:
        return []
    return [float(item) for item in extents]


def _single_root_feature(facts: ExtractedFacts) -> FeatureFact | None:
    if len(facts.root_feature_ids) != 1:
        return None
    return facts.features.get(facts.root_feature_ids[0])


def _expected_root_extents(feature: FeatureFact) -> list[float] | None:
    params = feature.params
    if feature.feature_type == "box" and all(key in params for key in ("x", "y", "z")):
        return [float(params["x"]), float(params["y"]), float(params["z"])]
    if feature.feature_type == "cylinder":
        diameter = params.get("diameter")
        if diameter is None and params.get("radius") is not None:
            diameter = float(params["radius"]) * 2.0
        height = params.get("height")
        if diameter is not None and height is not None:
            return [float(diameter), float(diameter), float(height)]
    return None
