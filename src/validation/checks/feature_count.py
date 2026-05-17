"""Feature structure checks that do not parse raw user text."""
from __future__ import annotations

from src.validation.contracts import CheckResult, Evidence
from src.validation.fact_extraction import ExtractedFacts


class FeatureCountCheck:
    """Check internal feature/build_order consistency.

    This is not a semantic "did the user ask for N holes" check. That remains
    an LLM/text-understanding task. Here we only verify structured blueprint
    consistency that can be checked deterministically.
    """

    check_id = "feature_count.structure"

    def run(self, facts: ExtractedFacts) -> list[CheckResult]:
        if facts.blueprint_format == "unknown":
            return [
                CheckResult(
                    check_id=self.check_id,
                    status="unknown",
                    severity="warning",
                    message="Blueprint format unknown; feature structure cannot be checked.",
                )
            ]

        results: list[CheckResult] = []
        feature_ids = set(facts.features)
        build_order = list(facts.build_order)
        build_order_set = set(build_order)

        missing_from_features = sorted(build_order_set - feature_ids)
        if missing_from_features:
            results.append(
                CheckResult(
                    check_id=self.check_id,
                    status="failed",
                    severity="error",
                    message="Build order references feature IDs that are not present.",
                    expected=sorted(feature_ids),
                    actual=missing_from_features,
                    evidence=(
                        Evidence("resolved_blueprint", "build_order", build_order),
                        Evidence("resolved_blueprint", "features", sorted(feature_ids)),
                    ),
                )
            )

        missing_from_order = sorted(feature_ids - build_order_set)
        if facts.blueprint_format == "feature_tree" and missing_from_order:
            results.append(
                CheckResult(
                    check_id=self.check_id,
                    status="failed",
                    severity="error",
                    message="Feature map contains IDs missing from build_order.",
                    expected=sorted(feature_ids),
                    actual=missing_from_order,
                    evidence=(
                        Evidence("resolved_blueprint", "build_order", build_order),
                        Evidence("resolved_blueprint", "features", sorted(feature_ids)),
                    ),
                )
            )

        duplicate_ids = _duplicates(build_order)
        if duplicate_ids:
            results.append(
                CheckResult(
                    check_id=self.check_id,
                    status="failed",
                    severity="error",
                    message="Build order contains duplicate feature IDs.",
                    actual=duplicate_ids,
                    evidence=(Evidence("resolved_blueprint", "build_order", build_order),),
                )
            )

        missing_parents = sorted(
            {
                feature.parent
                for feature in facts.features.values()
                if feature.parent and feature.parent not in feature_ids
            }
        )
        if missing_parents:
            results.append(
                CheckResult(
                    check_id=self.check_id,
                    status="failed",
                    severity="error",
                    message="Features reference parent IDs that are not present.",
                    expected=sorted(feature_ids),
                    actual=missing_parents,
                    evidence=(Evidence("resolved_blueprint", "features", sorted(feature_ids)),),
                )
            )

        if results:
            return results

        return [
            CheckResult(
                check_id=self.check_id,
                status="passed",
                severity="info",
                message="Feature IDs, build_order, and parent references are internally consistent.",
                expected={"features": len(feature_ids), "build_order": len(build_order)},
                actual={"features": len(feature_ids), "build_order": len(build_order)},
                evidence=(
                    Evidence("resolved_blueprint", "build_order", build_order),
                    Evidence("resolved_blueprint", "features", sorted(feature_ids)),
                ),
            )
        ]


def _duplicates(items: list[str]) -> list[str]:
    seen: set[str] = set()
    dupes: set[str] = set()
    for item in items:
        if item in seen:
            dupes.add(item)
        seen.add(item)
    return sorted(dupes)
