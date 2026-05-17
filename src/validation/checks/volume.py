"""Conservative volume checks for reverse validation."""
from __future__ import annotations

import math

from src.validation.contracts import CheckResult, Evidence
from src.validation.fact_extraction import ExtractedFacts, FeatureFact


class VolumeCheck:
    """Compare observed volume against simple deterministic expectations.

    For subtractive or multi-feature blueprints, this check avoids false
    certainty. It only fails when the observed volume is impossible against a
    simple solid upper bound.
    """

    check_id = "geometry.volume"

    def __init__(self, rel_tolerance: float = 0.05) -> None:
        self.rel_tolerance = rel_tolerance

    def run(self, facts: ExtractedFacts) -> list[CheckResult]:
        actual = _observed_volume(facts)
        if actual is None:
            return [
                CheckResult(
                    check_id=self.check_id,
                    status="unknown",
                    severity="warning",
                    message="No observed volume available.",
                )
            ]

        roots = [facts.features[root_id] for root_id in facts.root_feature_ids if root_id in facts.features]
        if len(roots) != 1:
            return [
                CheckResult(
                    check_id=self.check_id,
                    status="unknown",
                    severity="warning",
                    message="Volume check only supports blueprints with exactly one root feature.",
                    actual={"root_feature_ids": facts.root_feature_ids},
                )
            ]

        expected_solid = _solid_volume(roots[0])
        if expected_solid is None:
            return [
                CheckResult(
                    check_id=self.check_id,
                    status="unknown",
                    severity="warning",
                    message=f"Root feature type '{roots[0].feature_type}' has no deterministic volume rule yet.",
                    feature_id=roots[0].feature_id,
                )
            ]

        subtractive_features = [
            feature
            for feature in facts.features.values()
            if feature.operation == "subtract" or feature.feature_type.startswith(("hole", "slot", "pocket"))
        ]
        upper_bound = expected_solid * (1.0 + self.rel_tolerance)
        if actual > upper_bound:
            return [
                CheckResult(
                    check_id=self.check_id,
                    status="failed",
                    severity="error",
                    message="Observed volume exceeds the expected solid root volume.",
                    feature_id=roots[0].feature_id,
                    expected={"max_volume_mm3": upper_bound, "solid_volume_mm3": expected_solid},
                    actual=actual,
                    evidence=(
                        Evidence("resolved_blueprint", roots[0].source_path, roots[0].params),
                        Evidence("executor_geometry_state", "geometry.volume_mm3", actual),
                    ),
                    metadata={"rel_tolerance": self.rel_tolerance},
                )
            ]

        if subtractive_features:
            return [
                CheckResult(
                    check_id=self.check_id,
                    status="unknown",
                    severity="warning",
                    message=(
                        "Observed volume is within the root solid upper bound, "
                        "but subtractive feature volume is not modeled yet."
                    ),
                    feature_id=roots[0].feature_id,
                    expected={"solid_volume_upper_bound_mm3": upper_bound},
                    actual=actual,
                    evidence=(
                        Evidence("resolved_blueprint", roots[0].source_path, roots[0].params),
                        Evidence("executor_geometry_state", "geometry.volume_mm3", actual),
                    ),
                    metadata={
                        "rel_tolerance": self.rel_tolerance,
                        "subtractive_feature_ids": [feature.feature_id for feature in subtractive_features],
                    },
                )
            ]

        lower_bound = expected_solid * (1.0 - self.rel_tolerance)
        matches = lower_bound <= actual <= upper_bound
        return [
            CheckResult(
                check_id=self.check_id,
                status="passed" if matches else "failed",
                severity="info" if matches else "error",
                message=(
                    "Observed volume matches the simple solid root volume."
                    if matches
                    else "Observed volume differs from the simple solid root volume."
                ),
                feature_id=roots[0].feature_id,
                expected={
                    "min_volume_mm3": lower_bound,
                    "max_volume_mm3": upper_bound,
                    "solid_volume_mm3": expected_solid,
                },
                actual=actual,
                evidence=(
                    Evidence("resolved_blueprint", roots[0].source_path, roots[0].params),
                    Evidence("executor_geometry_state", "geometry.volume_mm3", actual),
                ),
                metadata={"rel_tolerance": self.rel_tolerance},
            )
        ]


def _observed_volume(facts: ExtractedFacts) -> float | None:
    volume = facts.geometry.get("volume_mm3", facts.validator_stats.get("volume_mm3"))
    if volume is None:
        return None
    return float(volume)


def _solid_volume(feature: FeatureFact) -> float | None:
    params = feature.params
    if feature.feature_type == "box" and all(key in params for key in ("x", "y", "z")):
        return float(params["x"]) * float(params["y"]) * float(params["z"])
    if feature.feature_type == "cylinder":
        radius = params.get("radius")
        diameter = params.get("diameter")
        height = params.get("height")
        if radius is None and diameter is not None:
            radius = float(diameter) / 2.0
        if radius is not None and height is not None:
            return math.pi * float(radius) ** 2 * float(height)
    if feature.feature_type == "sphere":
        radius = params.get("radius")
        if radius is not None:
            return (4.0 / 3.0) * math.pi * float(radius) ** 3
    return None
