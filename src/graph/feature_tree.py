"""
src/graph/feature_tree.py — Pydantic schema for Feature Tree Blueprints.

Phase 1 restructuring: replaces the CSG-Tree with a feature-centric tree.
Each feature has a unique ID, parent reference, relative placement, and
operation type (add/subtract). This enables:
  - Modular code generation (one function per feature)
  - Progressive build/test (feature by feature)
  - Targeted RAG queries per feature type
  - Clean modification paths (patch only affected function)

Detectable via FeatureTree.is_feature_tree(blueprint_dict):
  Feature Tree → has "build_order" key + "features" is a dict
  CSG-Tree     → has "root" key + "features" is a list
"""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field, model_validator


class PlacementInfo(BaseModel):
    """Relative placement of a child feature on its parent's face."""

    face: str = Field(
        default=">Z",
        description="CadQuery face selector: >Z (top), <Z (bottom), >X (right), <X (left), >Y (front), <Y (back)"
    )
    alignment: Optional[str] = Field(
        default=None,
        description="Alignment on face: flush_right, flush_left, flush_top, flush_bottom, centered"
    )
    z_position: Optional[str] = Field(
        default=None,
        description="Z-axis placement: on_top (union on top of face), flush (embedded), below"
    )
    position: str = Field(
        default="center",
        description=(
            "Position on face: center, corner_TL, corner_TR, corner_BL, corner_BR, "
            "offset(dx,dy) — dx/dy in mm from face center"
        )
    )
    offset_x: Optional[float] = Field(
        default=None,
        description="Explicit X offset in mm from face center. Overrides position string parsing."
    )
    offset_y: Optional[float] = Field(
        default=None,
        description="Explicit Y offset in mm from face center. Overrides position string parsing."
    )
    notes: str = Field(default="", description="Additional placement hints for the Coder")


class FeatureEntry(BaseModel):
    """One feature in the Feature Tree build plan."""

    id: str = Field(description="Unique feature identifier, referenced in build_order")
    type: str = Field(
        description=(
            "Feature geometry type. Examples: box, cylinder, sphere, hole, hole_pattern, "
            "hole_grid, cbore_hole, csk_hole, bolt_circle, slot, fillet, chamfer, "
            "polygon, corner_cut, text, shell, rib, extrusion_rectangular, "
            "extrusion_cylindrical, boss_cylindrical"
        )
    )
    params: dict = Field(
        default_factory=dict,
        description=(
            "Type-specific parameters. Examples: "
            "box → {x, y, z}, "
            "cylinder → {radius, height}, "
            "hole → {diameter, depth}, "
            "hole_pattern → {diameter, depth, positions: [[x,y],...]}, "
            "hole_grid → {diameter, depth, x_spacing, y_spacing, x_count, y_count}, "
            "slot → {length, width, depth, angle}"
        )
    )
    parent: Optional[str] = Field(
        default=None,
        description="ID of parent feature. null = root feature placed at global origin."
    )
    origin: str = Field(
        default="relative",
        description="'global' for root feature (no parent), 'relative' for all children"
    )
    position: Optional[dict] = Field(
        default=None,
        description="Global position {x, y, z} for root features only. Children use placement."
    )
    placement: Optional[PlacementInfo] = Field(
        default=None,
        description="Relative placement on parent face. Required when parent is set."
    )
    operation: str = Field(
        default="add",
        description="'add' (union onto parent) or 'subtract' (cut from parent)"
    )
    notes: str = Field(
        default="",
        description="Coder hints: tolerances, face-selection advice, tricky geometry notes"
    )


class FeatureTree(BaseModel):
    """Feature Tree blueprint — Phase 1+ replacement for the CSG-Tree.

    build_order: feature IDs in assembly sequence. Parents before children.
    features:    dict mapping feature ID → FeatureEntry with all geometry info.

    Distinguishable from legacy CSG-Tree blueprints by the presence of
    'build_order' key and 'features' being a dict (not a list).
    """

    description: str = Field(description="Human-readable summary of the model")
    build_order: list[str] = Field(
        description="Feature IDs in build sequence. Parent features come before their children."
    )
    features: dict[str, FeatureEntry] = Field(
        description="Map from feature ID → FeatureEntry with geometry and placement info"
    )
    notes: str = Field(
        default="",
        description="Optional assembly notes for the Coder (tolerances, ordering hints, etc.)"
    )

    @model_validator(mode="before")
    @classmethod
    def inject_feature_ids(cls, data: dict) -> dict:
        """Inject the dict key as 'id' into each feature entry if missing.

        The Planner outputs features like {"base_cube": {"type": "box", ...}}
        without an explicit 'id' field. This validator auto-fills it so
        FeatureEntry validation passes without requiring prompt changes.
        """
        features = data.get("features")
        if isinstance(features, dict):
            for key, value in features.items():
                if isinstance(value, dict) and "id" not in value:
                    value["id"] = key
        return data

    def to_dict(self) -> dict:
        """Serialize to plain dict for storage in PipelineState.blueprint."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict) -> "FeatureTree":
        """Deserialize from dict stored in PipelineState.blueprint."""
        return cls.model_validate(data)

    @staticmethod
    def is_feature_tree(blueprint: dict) -> bool:
        """Return True if the blueprint dict is Feature Tree format.

        Feature Tree: has 'build_order' key AND 'features' is a dict.
        CSG-Tree:     has 'root' key AND 'features' is a list (or absent).
        """
        return (
            "build_order" in blueprint
            and isinstance(blueprint.get("features"), dict)
        )
