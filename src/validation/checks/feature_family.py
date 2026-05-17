"""Feature-family reverse checks.

These checks intentionally start conservative. They enumerate the feature
families that need future actual-geometry extraction, but return `unknown`
instead of claiming a pass without evidence.
"""
from __future__ import annotations

from src.validation.contracts import CheckResult, Evidence
from src.validation.fact_extraction import ExtractedFacts, FeatureFact


class _FamilyCheck:
    check_id = "feature_family.base"
    family_name = "feature"
    type_prefixes: tuple[str, ...] = ()

    def run(self, facts: ExtractedFacts) -> list[CheckResult]:
        features = [
            feature
            for feature in facts.features.values()
            if feature.feature_type.startswith(self.type_prefixes)
        ]
        if not features:
            return [
                CheckResult(
                    check_id=self.check_id,
                    status="not_applicable",
                    severity="info",
                    message=f"No {self.family_name} features present in the blueprint.",
                )
            ]
        return [self._unknown_for_feature(feature) for feature in features]

    def _unknown_for_feature(self, feature: FeatureFact) -> CheckResult:
        return CheckResult(
            check_id=self.check_id,
            status="unknown",
            severity="warning",
            message=(
                f"{self.family_name.capitalize()} feature is present in the blueprint, "
                "but actual feature extraction from STL is not implemented yet."
            ),
            feature_id=feature.feature_id,
            expected={
                "type": feature.feature_type,
                "params": feature.params,
                "placement": feature.placement,
                "operation": feature.operation,
            },
            evidence=(Evidence("resolved_blueprint", feature.source_path, feature.params),),
        )


class HoleFeatureCheck(_FamilyCheck):
    check_id = "feature_family.hole"
    family_name = "hole"
    type_prefixes = ("hole", "cbore_hole", "csk_hole", "bolt_circle")


class SlotFeatureCheck(_FamilyCheck):
    check_id = "feature_family.slot"
    family_name = "slot"
    type_prefixes = ("slot",)


class PocketFeatureCheck(_FamilyCheck):
    check_id = "feature_family.pocket"
    family_name = "pocket"
    type_prefixes = ("pocket",)
