"""
src/graph/blueprint_schema.py — Blueprint Schema V2: Semantic + Resolved.

Two-layer architecture:
  1. SEMANTIC BLUEPRINT — what the AI produces (natural-language intent)
  2. RESOLVED BLUEPRINT — what the codegen consumes (numerical values)

The AI never computes offsets, swaps dimensions, or picks face selectors.
It describes WHAT and WHERE in human terms. The deterministic Blueprint
Resolver converts semantic → resolved.

Schema is frozen after this definition. All training data collected from
this point forward uses this format.

Multi-part assembly:
  Parts are defined individually with their own features. Assembly
  relationships are expressed through parent references and semantic
  position descriptions. The resolver computes exact translations.

Supported geometry: boxes, cylinders, spheres, rounded parts, angled
placements, and all hole/slot/pocket/modifier types.

═══════════════════════════════════════════════════════════════════
STRUKTUR (bei Aenderungen pflegen! Siehe CLAUDE.md)
═══════════════════════════════════════════════════════════════════
Semantic Layer (AI schreibt, Mensch liest):
  SemanticAnchor       — Ecke/Kante/Flaeche-Anker: child_point/parent_point/
                         offset/pre_rotation (Default: center-auf-center)
  SemanticPosition     — WO? side/alignment/edge_distances/center_offset/
                         angle_deg/anchor/depth_reference/notes
                         Prioritaet: anchor > edge_distances > center_offset >
                         alignment+side
                         depth_reference: auto/pocket_floor/part_top — fuer
                         Feature-in-Feature (Bohrung in Tasche)
  SemanticFeature      — EIN Feature: id/type/params/orientation/parent/position/operation
                         parent darf Part-ID ODER Feature-ID sein
  SemanticBlueprint    — Gesamtplan: description/build_order/features
    .inject_feature_ids — Pydantic pre-validator (fuellt id aus dict-key)
    .is_semantic        — statisch: erkennt ob dict im semantic-Format ist

Resolved Layer (Resolver-Output, codegen liest):
  ResolvedPlacement    — face/offset_x/offset_y/alignment/angle_deg/pre_rotation
                         pre_rotation (Optional): 3D-Rotation um Kind-Centroid
                         vor der Platzierung (Assembler nutzt body.rotate())
  ResolvedFeature      — id/type/params (nach orientation-swap!)/parent/placement/operation
  ResolvedBlueprint    — description/build_order/features
    .to_dict            — fuer PipelineState.blueprint
    .is_resolved        — statisch: erkennt ob dict im resolved-Format ist

Schema-Regeln (WICHTIG):
  - Felder nur ADDITIV hinzufuegen (Optional + Default), nie umbenennen
  - Neue Feature-Typen als erweitertes type-Enum, nicht als neues Layer
  - Semantic-Felder spiegeln Nutzersprache, Resolved-Felder spiegeln CadQuery
  - orientation wirkt NUR zwischen semantic und resolved (Dim-Swap im Resolver)
═══════════════════════════════════════════════════════════════════
"""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field, model_validator


# ═══════════════════════════════════════════════════════════════════
# SEMANTIC BLUEPRINT — AI fills this
# ═══════════════════════════════════════════════════════════════════

class SemanticAnchor(BaseModel):
    """Explicit point-to-point anchoring between child and parent.

    Describes which point of the child part lands on which point of the
    parent part — in user language, not coordinates. The deterministic
    Resolver converts this to numeric translations.

    Default convention: both points are "center". If the user does not
    specify anything else, the child center sits on the parent center
    (of the placement face). Only override when the user explicitly
    names an edge, corner, or face.

    Vocabulary:
      center
      Corners (3D): front_top_left, front_top_right, front_bottom_left,
                    front_bottom_right, back_top_left, back_top_right,
                    back_bottom_left, back_bottom_right
      Corners (2D, on a face): top_left, top_right, bottom_left, bottom_right
      Edges: top_edge, bottom_edge, left_edge, right_edge,
             front_edge, back_edge
      Faces: top_face, bottom_face, left_face, right_face,
             front_face, back_face
    """

    child_point: str = Field(
        default="center",
        description=(
            "Which point of the child part acts as the anchor. "
            "Default 'center' = child centroid. Use corner/edge/face keywords "
            "(see class docstring) only when the user names them explicitly."
        )
    )
    parent_point: str = Field(
        default="center",
        description=(
            "Which point/region on the parent the child anchor lands on. "
            "Same vocabulary as child_point. Default 'center' = parent centroid "
            "of the placement face."
        )
    )
    offset: Optional[dict[str, float]] = Field(
        default=None,
        description=(
            "Translation in mm applied AFTER anchoring and pre_rotation. "
            "Keys: right, left, up, down, forward, backward. "
            "Example: {'down': 10} = shift 10mm downward from the anchor. "
            "null = no additional offset."
        )
    )
    pre_rotation: Optional[dict[str, float]] = Field(
        default=None,
        description=(
            "Rotation of the child part BEFORE anchoring, in degrees, around "
            "axes through the child centroid. Keys: x, y, z. Positive = CCW "
            "looking along the axis. Example: {'z': -10} = 10 deg CW around Z. "
            "null = no pre-rotation."
        )
    )


class SemanticPosition(BaseModel):
    """WHERE a part/feature goes — in human words, not numbers.

    The AI describes position using natural language concepts.
    The resolver converts these to face selectors and numeric offsets.

    Precedence (highest wins, resolver enforces):
      1. anchor             — explicit child-point on parent-point mapping
                              (default center-on-center when only anchor={} is set)
      2. edge_distances     — "20mm from right edge"
      3. center_offset      — "10mm left of center"
      4. alignment + side   — coarse placement ("flush_right", "centered")

    Convention: if nothing is specified, the resolver treats the placement
    as anchor={child_point:"center", parent_point:"center"} — i.e. child
    center on parent face center.
    """

    side: str = Field(
        default="oben",
        description=(
            "Which side of the parent: "
            "oben, unten, rechts, links, vorne, hinten, zentriert. "
            "For features on a surface: oben = top face of parent."
        )
    )
    alignment: str = Field(
        default="centered",
        description=(
            "How to align on the parent face: "
            "centered, flush_right, flush_left, flush_top, flush_bottom, "
            "flush_right_top, flush_left_bottom, etc."
        )
    )
    edge_distances: Optional[dict[str, float]] = Field(
        default=None,
        description=(
            "Distance from parent edges in mm. Keys: right, left, top, bottom, front, back. "
            "Example: {'right': 20, 'top': 10} = 20mm from right edge, 10mm from top edge. "
            "null = use alignment instead."
        )
    )
    center_offset: Optional[dict[str, float]] = Field(
        default=None,
        description=(
            "Offset from center of parent face, in mm toward a named direction. "
            "Keys: top, bottom, right, left, front, back. "
            "Example: {'left': 10} = from center, 10mm toward the left edge. "
            "Used for 'versatz von mitte' specifications. "
            "null = use edge_distances or alignment instead."
        )
    )
    angle_deg: float = Field(
        default=0.0,
        description=(
            "Rotation angle in degrees around the placement normal axis. "
            "0 = no rotation. 45 = tilted 45 degrees on the face. "
            "For full 3D pre-rotation of the child part (not just around the "
            "placement normal), use anchor.pre_rotation instead."
        )
    )
    anchor: Optional[SemanticAnchor] = Field(
        default=None,
        description=(
            "Explicit point-to-point anchoring (child corner/edge/face onto "
            "parent corner/edge/face), with optional pre-rotation and offset. "
            "Set when the user names specific points, e.g. 'upper-left corner "
            "of plate B on left edge of cube A, 10mm down, rotated 10deg CCW'. "
            "null = use edge_distances / center_offset / alignment instead. "
            "Takes precedence over the other position fields when set."
        )
    )
    depth_reference: str = Field(
        default="auto",
        description=(
            "Z-reference for depth-bearing features (holes, pockets) when the "
            "feature has a feature-parent (e.g. hole inside a pocket). "
            "Values: "
            "'auto' = pocket_floor if parent is a subtractive volume feature, "
            "         else part_top (default, used by AI). "
            "'pocket_floor' = depth measured from the bottom of the parent "
            "                 pocket; the resolver adds parent.depth to the "
            "                 child's depth so the cut starts at part_top and "
            "                 reaches pocket_floor + child.depth. "
            "'part_top' = standard behavior, depth measured from the placement "
            "             face."
        )
    )
    notes: str = Field(
        default="",
        description="Extra context for the resolver, e.g. 'mittig auf der langen Seite'"
    )


class SemanticFeature(BaseModel):
    """One feature in the semantic blueprint — AI-friendly format.

    The AI fills in dimensions as stated by the user (raw_dimensions),
    orientation as a keyword, and position as natural language.
    No numerical offset computation needed.
    """

    id: str = Field(description="Unique feature identifier")
    type: str = Field(
        description=(
            "Feature type. "
            "ROOT: box, cylinder, sphere. "
            "ADD: box, cylinder, extrusion_rect, extrusion_round, step. "
            "SUBTRACT: hole_single, hole_counterbore, hole_countersink, "
            "hole_pattern_grid, hole_pattern_circular, hole_pattern_linear, "
            "slot, groove, pocket_rect, cutout. "
            "MODIFY: fillet, chamfer, shell. "
            "COMPLEX: angled_extrusion, arc_cut, custom_shape_cut, loft, sweep, revolution."
        )
    )
    params: dict = Field(
        default_factory=dict,
        description=(
            "Geometry parameters — dimensions as the user stated them (NOT reoriented). "
            "Box: {x, y, z}, Cylinder: {diameter, height}, Hole: {diameter, depth}, "
            "Pattern Grid: {inset, count, hole_diameter, depth}, "
            "Pattern Circular: {bolt_circle_diameter, count, hole_diameter, depth}, "
            "Pattern Linear: {spacing, count, start_offset, hole_diameter, depth, direction}, "
            "Slot: {width, depth, length}, Fillet: {radius}, Chamfer: {size}, Shell: {thickness}. "
            "depth=null means through-hole."
        )
    )
    orientation: str = Field(
        default="standard",
        description=(
            "How the part is oriented: "
            "standard = as defined by params (x=width, y=length, z=height). "
            "hochkant/aufrecht/stehend = largest dimension becomes Z (height). "
            "flach/liegend = smallest dimension becomes Z. "
            "AxB_liegt_auf = specified face on bottom (e.g. '20x80_liegt_auf'). "
            "N_hoch = dimension N becomes Z (e.g. '80_hoch')."
        )
    )
    parent: Optional[str] = Field(
        default=None,
        description=(
            "ID of parent. May reference either a part (root box/cylinder) or "
            "another feature (e.g. a pocket — see hole-in-pocket pattern). "
            "Position fields are interpreted in the parent's local frame: "
            "for a part-parent, the placement face of the part; for a "
            "feature-parent, the feature's footprint on its own placement face. "
            "null = root feature."
        )
    )
    position: SemanticPosition = Field(
        default_factory=SemanticPosition,
        description="Where this feature goes relative to its parent."
    )
    operation: str = Field(
        default="add",
        description="add (union), subtract (cut), or modify (fillet/chamfer/shell)"
    )
    notes: str = Field(
        default="",
        description="Extra context from user text, max 80 chars. Orientation hints, special instructions."
    )


class SemanticBlueprint(BaseModel):
    """The AI-produced blueprint — semantic, human-readable, no math.

    This is what the Blueprint Architect LLM outputs.
    The Blueprint Resolver converts it to a ResolvedBlueprint.
    """

    description: str = Field(description="Short model description")
    build_order: list[str] = Field(
        description="Feature IDs in assembly sequence. Parents before children."
    )
    features: dict[str, SemanticFeature] = Field(
        description="Map from feature ID to its semantic definition."
    )

    @model_validator(mode="before")
    @classmethod
    def inject_feature_ids(cls, data: dict) -> dict:
        """Auto-fill 'id' from dict key if missing."""
        features = data.get("features")
        if isinstance(features, dict):
            for key, value in features.items():
                if isinstance(value, dict) and "id" not in value:
                    value["id"] = key
                # Ensure position is a dict (not missing)
                if isinstance(value, dict) and "position" not in value:
                    value["position"] = {}
        return data

    @staticmethod
    def is_semantic(blueprint: dict) -> bool:
        """Check if a blueprint dict is in semantic format.

        Semantic blueprints have features with 'orientation' field.
        Resolved blueprints have features with 'placement' field instead.
        """
        features = blueprint.get("features", {})
        if not isinstance(features, dict) or not features:
            return False
        sample = next(iter(features.values()))
        if not isinstance(sample, dict):
            return False
        return "orientation" in sample or "position" in sample and isinstance(sample.get("position"), dict) and "side" in sample.get("position", {})


# ═══════════════════════════════════════════════════════════════════
# RESOLVED BLUEPRINT — what codegen consumes (deterministic output)
# ═══════════════════════════════════════════════════════════════════

class ResolvedPlacement(BaseModel):
    """Computed placement — numeric offsets and CadQuery face selector.

    This is the output of the Blueprint Resolver.
    The codegen/assembler reads these values directly.
    """

    face: str = Field(
        default=">Z",
        description="CadQuery face selector: >Z, <Z, >X, <X, >Y, <Y"
    )
    alignment: str = Field(
        default="centered",
        description="Alignment keyword (preserved from semantic for readability)"
    )
    offset_x: float = Field(
        default=0.0,
        description="Computed X offset on face workplane, in mm"
    )
    offset_y: float = Field(
        default=0.0,
        description="Computed Y offset on face workplane, in mm"
    )
    angle_deg: float = Field(
        default=0.0,
        description="Rotation around face normal, in degrees"
    )
    pre_rotation: Optional[dict[str, float]] = Field(
        default=None,
        description=(
            "Full 3D pre-rotation of the child BEFORE placement, in degrees, "
            "around axes through the child centroid. Keys: x, y, z. "
            "Preserved from SemanticAnchor.pre_rotation. "
            "null = no pre-rotation (most common case). "
            "The assembler applies this via body.rotate() before translate()."
        )
    )
    notes: str = Field(default="", description="Preserved from semantic position notes")


class ResolvedFeature(BaseModel):
    """One feature with all values computed — ready for codegen."""

    id: str = Field(description="Unique feature identifier")
    type: str = Field(description="Feature type (same as semantic)")
    params: dict = Field(
        default_factory=dict,
        description="Geometry params — dimensions AFTER orientation rewrite (x/y/z swapped if needed)"
    )
    parent: Optional[str] = Field(default=None, description="Parent feature ID or null for root")
    placement: Optional[ResolvedPlacement] = Field(
        default=None,
        description="Computed placement. null for root features."
    )
    operation: str = Field(default="add", description="add, subtract, or modify")
    notes: str = Field(default="", description="Preserved from semantic feature notes")


class ResolvedBlueprint(BaseModel):
    """Fully resolved blueprint — every value computed, ready for codegen.

    This is the output of the Blueprint Resolver and the input to
    function_decomposer / codegen / assembler.

    Compatible with the existing codegen pipeline:
    - features have 'placement' with face/offset_x/offset_y
    - params have reoriented dimensions
    - build_order preserved
    """

    description: str = Field(description="Short model description")
    build_order: list[str] = Field(description="Feature IDs in assembly sequence")
    features: dict[str, ResolvedFeature] = Field(
        description="Map from feature ID to resolved feature"
    )

    @model_validator(mode="before")
    @classmethod
    def inject_feature_ids(cls, data: dict) -> dict:
        """Auto-fill 'id' from dict key if missing."""
        features = data.get("features")
        if isinstance(features, dict):
            for key, value in features.items():
                if isinstance(value, dict) and "id" not in value:
                    value["id"] = key
        return data

    def to_dict(self) -> dict:
        """Serialize to plain dict for PipelineState.blueprint."""
        return self.model_dump()

    @staticmethod
    def is_resolved(blueprint: dict) -> bool:
        """Check if a blueprint dict is in resolved format."""
        features = blueprint.get("features", {})
        if not isinstance(features, dict) or not features:
            return False
        sample = next(iter(features.values()))
        if not isinstance(sample, dict):
            return False
        return "placement" in sample and "orientation" not in sample
