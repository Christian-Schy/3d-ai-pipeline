"""Structured fact extraction for reverse validation.

This module only reads structured pipeline artifacts: blueprint dictionaries,
executor geometry state, validator stats, and generated code. It deliberately
does not parse raw user text; semantic text understanding remains an LLM job.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class FeatureFact:
    """Normalized view of one blueprint feature."""

    feature_id: str
    feature_type: str
    params: dict[str, Any] = field(default_factory=dict)
    parent: str | None = None
    operation: str = "add"
    placement: dict[str, Any] | None = None
    source_path: str = ""


@dataclass(frozen=True)
class ExtractedFacts:
    """Facts available to narrow reverse-validation checks."""

    blueprint_format: str
    features: dict[str, FeatureFact]
    build_order: tuple[str, ...] = ()
    root_feature_ids: tuple[str, ...] = ()
    geometry: dict[str, Any] = field(default_factory=dict)
    validator_stats: dict[str, Any] = field(default_factory=dict)
    generated_code: str = ""

    def features_by_type(self, *types: str) -> list[FeatureFact]:
        wanted = set(types)
        return [feature for feature in self.features.values() if feature.feature_type in wanted]


def extract_facts_from_state(state: dict[str, Any]) -> ExtractedFacts:
    """Build `ExtractedFacts` from a PipelineState-like dict."""
    return extract_facts(
        blueprint=state.get("blueprint") or {},
        geometry_state=state.get("geometry_state") or {},
        validator_stats=state.get("validator_stats") or {},
        generated_code=state.get("code") or "",
    )


def extract_facts(
    blueprint: dict[str, Any],
    geometry_state: dict[str, Any] | None = None,
    validator_stats: dict[str, Any] | None = None,
    generated_code: str = "",
) -> ExtractedFacts:
    """Normalize expected blueprint facts and observed geometry facts."""
    geometry_state = geometry_state or {}
    validator_stats = validator_stats or {}

    if _is_feature_tree(blueprint):
        return _extract_feature_tree(
            blueprint, geometry_state, validator_stats, generated_code
        )
    if _is_csg_tree(blueprint):
        return _extract_csg_tree(blueprint, geometry_state, validator_stats, generated_code)

    return ExtractedFacts(
        blueprint_format="unknown",
        features={},
        geometry=_normalize_geometry(geometry_state),
        validator_stats=dict(validator_stats),
        generated_code=generated_code,
    )


def _is_feature_tree(blueprint: dict[str, Any]) -> bool:
    return "build_order" in blueprint and isinstance(blueprint.get("features"), dict)


def _is_csg_tree(blueprint: dict[str, Any]) -> bool:
    return isinstance(blueprint.get("root"), dict)


def _extract_feature_tree(
    blueprint: dict[str, Any],
    geometry_state: dict[str, Any],
    validator_stats: dict[str, Any],
    generated_code: str,
) -> ExtractedFacts:
    features: dict[str, FeatureFact] = {}
    raw_features = blueprint.get("features") or {}
    for feature_id, raw in raw_features.items():
        if not isinstance(raw, dict):
            continue
        features[str(feature_id)] = FeatureFact(
            feature_id=str(feature_id),
            feature_type=str(raw.get("type", "")),
            params=dict(raw.get("params") or {}),
            parent=raw.get("parent"),
            operation=str(raw.get("operation") or "add"),
            placement=_dict_or_none(raw.get("placement")),
            source_path=f"features.{feature_id}",
        )

    root_ids = tuple(
        feature.feature_id
        for feature in features.values()
        if not feature.parent
    )
    return ExtractedFacts(
        blueprint_format="feature_tree",
        features=features,
        build_order=tuple(str(item) for item in blueprint.get("build_order", ())),
        root_feature_ids=root_ids,
        geometry=_normalize_geometry(geometry_state),
        validator_stats=dict(validator_stats),
        generated_code=generated_code,
    )


def _extract_csg_tree(
    blueprint: dict[str, Any],
    geometry_state: dict[str, Any],
    validator_stats: dict[str, Any],
    generated_code: str,
) -> ExtractedFacts:
    features: dict[str, FeatureFact] = {}
    root = blueprint.get("root") or {}
    if isinstance(root, dict) and root:
        features["root"] = FeatureFact(
            feature_id="root",
            feature_type=str(root.get("type", "")),
            params={k: v for k, v in root.items() if k not in {"type", "target", "tool"}},
            parent=None,
            operation="add",
            placement=None,
            source_path="root",
        )

    for index, raw in enumerate(blueprint.get("features") or []):
        if not isinstance(raw, dict):
            continue
        feature_id = str(raw.get("id") or raw.get("name") or f"feature_{index}")
        features[feature_id] = FeatureFact(
            feature_id=feature_id,
            feature_type=str(raw.get("type", "")),
            params=dict(raw.get("params") or raw),
            parent=raw.get("parent"),
            operation=str(raw.get("operation") or raw.get("op") or "unknown"),
            placement=_dict_or_none(raw.get("placement")),
            source_path=f"features[{index}]",
        )

    return ExtractedFacts(
        blueprint_format="csg_tree",
        features=features,
        build_order=tuple(features),
        root_feature_ids=("root",) if "root" in features else (),
        geometry=_normalize_geometry(geometry_state),
        validator_stats=dict(validator_stats),
        generated_code=generated_code,
    )


def _normalize_geometry(geometry_state: dict[str, Any]) -> dict[str, Any]:
    geometry = dict(geometry_state)

    # executor_node stores geometry_state via GeometryState.model_dump().
    extents = geometry.get("extents_mm") or geometry.get("size_mm")
    if not extents:
        width = geometry.get("total_width") or geometry.get("width")
        depth = geometry.get("total_depth") or geometry.get("depth")
        height = geometry.get("total_height") or geometry.get("height")
        if width is not None and depth is not None and height is not None:
            extents = [width, depth, height]

    if extents:
        geometry["extents_mm"] = [float(item) for item in extents]

    volume = geometry.get("volume_mm3", geometry.get("volume"))
    if volume is not None:
        geometry["volume_mm3"] = float(volume)

    return geometry


def _dict_or_none(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return dict(value)
    return None
