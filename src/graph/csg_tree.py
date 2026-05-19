"""
src/graph/csg_tree.py — Pydantic schema for CSG-Tree Blueprints.

A Blueprint describes a 3D model as:
  - root:     The base solid (CSG tree: box, cylinder, union, cut, …)
  - features: Ordered list of CadQuery operations applied to the solid
              (holes, slots, polygons, text, …)

Why features instead of encoding everything in the CSG tree?
  Boolean CSG (cut + cylinder) is ambiguous — the Coder must guess
  whether to use .hole(), .cboreHole(), .pushPoints() etc.
  Typed feature nodes remove that ambiguity completely: each type maps
  to exactly one CadQuery method with no interpretation needed.

  Order in the features list is the execution order — holes are listed
  before slots to match CadQuery's face-selection requirements.

Tree structure (root):
  Every root node is either:
    - A Primitive  (leaf): box, cylinder, sphere
    - An Operation (branch): union, cut, intersect + two child nodes
    - A Transform  (wrapper): fillet, chamfer, shell + one child node

Feature nodes (features list — applied sequentially after root is built):
    hole, hole_pattern, hole_grid,
    cbore_hole, csk_hole,
    slot,
    polygon, corner_cut, text
"""

from __future__ import annotations

from typing import Literal, Union

from pydantic import BaseModel, Field

# ------------------------------------------------------------------
# Position and orientation helpers
# ------------------------------------------------------------------

class Position(BaseModel):
    """3D position in mm relative to the workplane origin."""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


class Rotation(BaseModel):
    """Rotation in degrees around each axis."""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


# ------------------------------------------------------------------
# Primitive nodes (leaves of the CSG tree)
# ------------------------------------------------------------------

class CSGBox(BaseModel):
    """Rectangular box centered at position."""
    type: Literal["box"] = "box"
    x: float = Field(..., gt=0, description="Width in mm")
    y: float = Field(..., gt=0, description="Depth in mm")
    z: float = Field(..., gt=0, description="Height in mm")
    position: Position = Field(default_factory=Position)


class CSGCylinder(BaseModel):
    """Upright cylinder centered at position."""
    type: Literal["cylinder"] = "cylinder"
    radius: float = Field(..., gt=0, description="Radius in mm")
    height: float = Field(..., gt=0, description="Height in mm")
    position: Position = Field(default_factory=Position)


class CSGSphere(BaseModel):
    """Sphere centered at position."""
    type: Literal["sphere"] = "sphere"
    radius: float = Field(..., gt=0, description="Radius in mm")
    position: Position = Field(default_factory=Position)


# ------------------------------------------------------------------
# Modifier nodes (apply to a single child — always last in the tree)
# ------------------------------------------------------------------

class CSGFillet(BaseModel):
    """Round selected edges of the child shape."""
    type: Literal["fillet"] = "fillet"
    radius: float = Field(..., gt=0, description="Fillet radius in mm")
    edges: str = Field(
        default="all",
        description='Which edges to fillet: "all", ">Z" (top), "<Z" (bottom), etc.'
    )
    child: CSGNode


class CSGChamfer(BaseModel):
    """Chamfer selected edges of the child shape."""
    type: Literal["chamfer"] = "chamfer"
    distance: float = Field(..., gt=0, description="Chamfer distance in mm")
    edges: str = Field(default="all")
    child: CSGNode


class CSGShell(BaseModel):
    """Hollow out a solid, keeping the specified face open."""
    type: Literal["shell"] = "shell"
    thickness: float = Field(..., gt=0, description="Wall thickness in mm")
    open_face: str = Field(
        default=">Z",
        description='Face selector to open: ">Z" (top), "<Z" (bottom), etc.'
    )
    child: CSGNode


# ------------------------------------------------------------------
# Boolean operation nodes (combine two shapes)
# ------------------------------------------------------------------

class CSGUnion(BaseModel):
    """Merge two shapes into one."""
    type: Literal["union"] = "union"
    target: CSGNode
    tool: CSGNode


class CSGCut(BaseModel):
    """Subtract tool from target."""
    type: Literal["cut"] = "cut"
    target: CSGNode
    tool: CSGNode


class CSGIntersect(BaseModel):
    """Keep only the volume shared by both shapes."""
    type: Literal["intersect"] = "intersect"
    target: CSGNode
    tool: CSGNode


# ------------------------------------------------------------------
# Union type — any node can be one of these
# ------------------------------------------------------------------

CSGNode = Union[
    CSGBox, CSGCylinder, CSGSphere,
    CSGFillet, CSGChamfer, CSGShell,
    CSGUnion, CSGCut, CSGIntersect,
]

# Pydantic v2 needs this to resolve forward references in recursive models
CSGFillet.model_rebuild()
CSGChamfer.model_rebuild()
CSGShell.model_rebuild()
CSGUnion.model_rebuild()
CSGCut.model_rebuild()
CSGIntersect.model_rebuild()


# ------------------------------------------------------------------
# Feature nodes — applied sequentially after the root solid is built.
# Each maps 1:1 to a CadQuery method. No interpretation by the Coder.
# ------------------------------------------------------------------

class FeatureHole(BaseModel):
    """Single drilled hole.
    Coder: result.faces(face).workplane().center(x,y).hole(diameter[, depth])
    """
    type: Literal["hole"] = "hole"
    diameter: float = Field(..., gt=0, description="Hole diameter in mm (NOT radius!)")
    depth: float | None = Field(default=None, description="Depth in mm. null = through-hole.")
    position: Position = Field(default_factory=Position, description="XY center on the face")
    face: str = Field(default=">Z", description='Face to drill from: ">Z" top, "<Z" bottom, ">X" etc.')


class FeatureHolePattern(BaseModel):
    """Multiple holes at explicit positions — same diameter.
    Coder: result.faces(face).workplane().pushPoints([[x,y],...]).hole(diameter[, depth])
    """
    type: Literal["hole_pattern"] = "hole_pattern"
    diameter: float = Field(..., gt=0, description="Hole diameter in mm")
    depth: float | None = Field(default=None, description="Depth in mm. null = through-hole.")
    positions: list[list[float]] = Field(
        ..., description="List of [x, y] positions on the face in mm from center"
    )
    face: str = Field(default=">Z")


class FeatureHoleGrid(BaseModel):
    """Regular rectangular grid of holes.
    Coder: result.faces(face).workplane().rarray(x_spacing, y_spacing, x_count, y_count).hole(d)
    """
    type: Literal["hole_grid"] = "hole_grid"
    diameter: float = Field(..., gt=0)
    depth: float | None = None
    x_spacing: float = Field(..., gt=0, description="Spacing between holes in X direction")
    y_spacing: float = Field(..., gt=0, description="Spacing between holes in Y direction")
    x_count: int = Field(..., gt=0, description="Number of holes in X direction")
    y_count: int = Field(..., gt=0, description="Number of holes in Y direction")
    face: str = ">Z"


class FeatureCboreHole(BaseModel):
    """Counterbore hole (socket-head screws).
    Coder: result.faces(face).workplane().center(x,y).cboreHole(diameter, cbore_diameter, cbore_depth[, depth])
    """
    type: Literal["cbore_hole"] = "cbore_hole"
    diameter: float = Field(..., gt=0, description="Through-hole diameter in mm")
    cbore_diameter: float = Field(..., gt=0, description="Counterbore diameter in mm")
    cbore_depth: float = Field(..., gt=0, description="Counterbore depth in mm")
    depth: float | None = Field(default=None, description="Total hole depth. null = through.")
    position: Position = Field(default_factory=Position)
    face: str = ">Z"


class FeatureCskHole(BaseModel):
    """Countersink hole (flat-head screws).
    Coder: result.faces(face).workplane().center(x,y).cskHole(diameter, csk_diameter, csk_angle[, depth])
    """
    type: Literal["csk_hole"] = "csk_hole"
    diameter: float = Field(..., gt=0, description="Through-hole diameter in mm")
    csk_diameter: float = Field(..., gt=0, description="Countersink outer diameter in mm")
    csk_angle: float = Field(default=82.0, description="Countersink angle in degrees (82=DIN, 90=common)")
    depth: float | None = Field(default=None, description="Hole depth. null = through.")
    position: Position = Field(default_factory=Position)
    face: str = ">Z"


class FeatureSlot(BaseModel):
    """Slot or groove cut into a face.
    Coder: result.faces(face).workplane().center(x,y).slot2D(length, width, angle).cutBlind(-depth)
    For through-slot (depth=null): .slot2D(length, width, angle).cutThruAll()
    """
    type: Literal["slot"] = "slot"
    length: float = Field(..., gt=0, description="Running length in mm. Formula: solid_dim_along_slot + slot_width + 2. E.g. 5mm slot through 30mm solid → 37mm. Using solid+2 leaves visible rounded ends!")
    width: float = Field(..., gt=0, description="Slot width in mm")
    depth: float | None = Field(default=None, description="Groove depth in mm from face. null = through.")
    angle: float = Field(default=0.0, description="0 = X-axis slot, 90 = Y-axis slot")
    position: Position = Field(default_factory=Position, description="Center of slot on the face")
    face: str = ">Z"


class FeaturePolygon(BaseModel):
    """Regular polygon extruded (hexagon, square peg, etc.).
    Coder: cq.Workplane("XY").polygon(sides, diameter).extrude(height).translate((x,y,z))
           then result = result.union(polygon).clean()  or  result = result.cut(polygon).clean()
    """
    type: Literal["polygon"] = "polygon"
    sides: int = Field(..., gt=2, description="Number of sides: 6=hex, 4=square, 3=triangle")
    diameter: float = Field(..., gt=0, description="Inscribed circle diameter in mm")
    height: float = Field(..., gt=0, description="Extrusion height in mm")
    position: Position = Field(default_factory=Position)
    subtract: bool = Field(default=False, description="True = cut polygon from solid, False = add to solid")


class FeatureText(BaseModel):
    """Engraved or embossed text on a face.
    Coder (engrave): result.faces(face).workplane().text(text, font_size, -depth, cut=True)
    Coder (emboss):  result.faces(face).workplane().text(text, font_size, depth, cut=False)
    """
    type: Literal["text"] = "text"
    text: str = Field(..., description="The text string to engrave/emboss")
    font_size: float = Field(..., gt=0, description="Font size in mm")
    depth: float = Field(..., gt=0, description="Engrave/emboss depth in mm")
    cut: bool = Field(default=True, description="True = engrave (subtract), False = emboss (add material)")
    face: str = ">Z"


class FeatureCornerCut(BaseModel):
    """Right-angle triangular prism cut at a face corner.
    The two legs run along the X and Y axes inward from the corner.
    Coder: moveTo/lineTo polygon on face workplane then cutBlind(-depth)
    """
    type: Literal["corner_cut"] = "corner_cut"
    corner_x: float = Field(..., description="X coordinate of the corner on the face (e.g. +15 or -15 for a 30mm box)")
    corner_y: float = Field(..., description="Y coordinate of the corner on the face (e.g. +15 or -15 for a 30mm box)")
    x_leg: float = Field(..., gt=0, description="Length of leg along X axis in mm")
    y_leg: float = Field(..., gt=0, description="Length of leg along Y axis in mm")
    depth: float = Field(..., gt=0, description="Depth of cut in mm from the face")
    face: str = Field(default=">Z", description='Face to cut from: ">Z" top, "<Z" bottom, etc.')


# Union of all feature types — validated by Pydantic
Feature = Union[
    FeatureHole,
    FeatureHolePattern,
    FeatureHoleGrid,
    FeatureCboreHole,
    FeatureCskHole,
    FeatureSlot,
    FeaturePolygon,
    FeatureCornerCut,
    FeatureText,
]


# ------------------------------------------------------------------
# Top-level Blueprint
# ------------------------------------------------------------------

class Blueprint(BaseModel):
    """The complete build plan for one 3D model.

    root:     Base solid (box, cylinder, union/cut of primitives, …)
    features: Ordered CadQuery operations applied after the root is built.
              Each feature maps to exactly one CadQuery method — no guessing.
              Order matters: list all holes BEFORE slots on the same face.

    Legacy: blueprints without features are still valid (features defaults to []).
    """
    description: str = Field(..., description="Human-readable summary of the model")
    root: CSGNode = Field(..., description="The root node of the CSG tree (base solid)")
    features: list[Feature] = Field(
        default_factory=list,
        description=(
            "Ordered CadQuery operations: hole, hole_pattern, hole_grid, "
            "cbore_hole, csk_hole, slot, polygon, corner_cut, text. "
            "List holes BEFORE slots. Applied sequentially after root is built."
        )
    )
    notes: str = Field(
        default="",
        description="Optional notes for the Coder (tricky geometry, tolerances, etc.)"
    )

    def to_dict(self) -> dict:
        """Serialize to a plain dict for JSON storage in PipelineState."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict) -> Blueprint:
        """Deserialize from the dict stored in PipelineState."""
        return cls.model_validate(data)
