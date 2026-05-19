"""Assembler — geometric transform emitters.

Emits CadQuery `.rotate()` / `.translate()` source lines for placing a
sub-assembly body relative to its parent. All three functions return
source-code strings/lists, not geometry — the actual transform runs when
the generated file executes.

Symbols (intra-package):
    _emit_pre_rotation   — placement.pre_rotation → .rotate() lines (3D)
    _emit_face_rotation  — placement.angle_deg → .rotate() around face normal
    _compute_translate   — face + dims → .translate() tuple string
"""

from __future__ import annotations


def _emit_pre_rotation(
    var_name: str,
    sa_prefix: str,
    sa_params: dict,
    pre_rotation: dict | None,
) -> list[str]:
    """Emit .rotate() lines for a pre_rotation dict.

    Rotates around axes through the child centroid, BEFORE translate.
    Bodies are centered=(True, True, False): XY at 0, Z from 0..height.
    Centroid is therefore (0, 0, height/2).

    Keys: x, y, z (degrees, positive = CCW looking along axis).
    """
    if not pre_rotation:
        return []
    sa_z = f"{sa_prefix}_Z" if "z" in sa_params else f"{sa_prefix}_HEIGHT"
    lines: list[str] = []
    for axis in ("x", "y", "z"):
        angle = pre_rotation.get(axis)
        if angle is None or float(angle) == 0.0:
            continue
        a = float(angle)
        if axis == "z":
            # Axis through (0,0,*) — XY center
            lines.append(
                f"    {var_name} = {var_name}.rotate((0, 0, 0), (0, 0, 1), {a})"
            )
        elif axis == "x":
            lines.append(
                f"    {var_name} = {var_name}.rotate((0, 0, {sa_z}/2), (1, 0, {sa_z}/2), {a})"
            )
        else:  # y
            lines.append(
                f"    {var_name} = {var_name}.rotate((0, 0, {sa_z}/2), (0, 1, {sa_z}/2), {a})"
            )
    return lines


def _emit_face_rotation(
    var_name: str,
    sa_prefix: str,
    sa_params: dict,
    face: str,
    angle_deg: float,
) -> list[str]:
    """Emit .rotate() for placement.angle_deg around face normal, pre-translate.

    Rotates around the face-normal axis through the child centroid. Because
    translation is applied AFTER this rotation, rotating around the centroid
    is equivalent to rotating around the final placement point (for axes
    parallel to the face normal).

    Child body is centered=(True, True, False): centroid at (0, 0, z/2).
    """
    if float(angle_deg) == 0.0:
        return []
    sa_z = f"{sa_prefix}_Z" if "z" in sa_params else f"{sa_prefix}_HEIGHT"
    a = float(angle_deg)
    # Map face → axis through centroid. Z-axis rotations translation-invariant.
    axis_map = {
        ">Z": "(0, 0, 0), (0, 0, 1)",
        "<Z": "(0, 0, 0), (0, 0, 1)",
        ">X": f"(0, 0, {sa_z}/2), (1, 0, {sa_z}/2)",
        "<X": f"(0, 0, {sa_z}/2), (1, 0, {sa_z}/2)",
        ">Y": f"(0, 0, {sa_z}/2), (0, 1, {sa_z}/2)",
        "<Y": f"(0, 0, {sa_z}/2), (0, 1, {sa_z}/2)",
    }
    axis = axis_map.get(face, axis_map[">Z"])
    return [f"    {var_name} = {var_name}.rotate({axis}, {a})"]


def _compute_translate(
    face: str,
    parent_prefix: str,
    parent_params: dict,
    sa_prefix: str,
    sa_params: dict,
) -> str:
    """Compute translate tuple string for sub-assembly placement.

    Face semantics (where the child sits relative to the parent):
      >Z = on top      → Z += parent height
      <Z = on bottom   → Z -= child height
      >X = to the right → X += parent_X/2 + child_X/2
      <X = to the left  → X -= parent_X/2 + child_X/2
      >Y = to the back  → Y += parent_Y/2 + child_Y/2
      <Y = to the front → Y -= parent_Y/2 + child_Y/2

    All bodies are centered=(True, True, False) so XY origin is at center,
    Z origin is at bottom.

    For side faces (X/Y), Z-centering is applied: child center aligns with
    parent center vertically → Z = (parent_Z - child_Z) / 2.

    Offset mapping per face (resolver offset_x = face-width, offset_y = face-height):
      >Z/<Z: offset_x → global X, offset_y → global Y  (Z is perpendicular)
      >X/<X: offset_x → global Y, offset_y → global Z  (X is perpendicular)
      >Y/<Y: offset_x → global X, offset_y → global Z  (Y is perpendicular)
    """
    parent_z = f"{parent_prefix}_Z" if "z" in parent_params else f"{parent_prefix}_HEIGHT"
    sa_z = f"{sa_prefix}_Z" if "z" in sa_params else f"{sa_prefix}_HEIGHT"

    # Keep these formulas as branches: each face maps offsets differently.
    if face == ">Z":  # noqa: SIM116
        # On top: same XY, shift up by parent height
        return f"({sa_prefix}_OFFSET_X, {sa_prefix}_OFFSET_Y, {parent_z})"
    elif face == "<Z":
        # On bottom: same XY, shift down by child height
        return f"({sa_prefix}_OFFSET_X, {sa_prefix}_OFFSET_Y, -{sa_z})"
    elif face == ">X":
        # Right side: child center at parent_X/2 + child_X/2
        # Face workplane: width=globalY, height=globalZ
        # offset_x → globalY, offset_y → globalZ (added to Z-centering)
        return (
            f"({parent_prefix}_X/2 + {sa_prefix}_X/2, "
            f"{sa_prefix}_OFFSET_X, "
            f"({parent_z} - {sa_z}) / 2 + {sa_prefix}_OFFSET_Y)"
        )
    elif face == "<X":
        # Left side: child center at -(parent_X/2 + child_X/2)
        return (
            f"(-({parent_prefix}_X/2 + {sa_prefix}_X/2), "
            f"{sa_prefix}_OFFSET_X, "
            f"({parent_z} - {sa_z}) / 2 + {sa_prefix}_OFFSET_Y)"
        )
    elif face == ">Y":
        # Back side: child center at parent_Y/2 + child_Y/2
        # Face workplane: width=globalX, height=globalZ
        # offset_x → globalX, offset_y → globalZ (added to Z-centering)
        return (
            f"({sa_prefix}_OFFSET_X, "
            f"{parent_prefix}_Y/2 + {sa_prefix}_Y/2, "
            f"({parent_z} - {sa_z}) / 2 + {sa_prefix}_OFFSET_Y)"
        )
    elif face == "<Y":
        # Front side: child center at -(parent_Y/2 + child_Y/2)
        return (
            f"({sa_prefix}_OFFSET_X, "
            f"-({parent_prefix}_Y/2 + {sa_prefix}_Y/2), "
            f"({parent_z} - {sa_z}) / 2 + {sa_prefix}_OFFSET_Y)"
        )
    # Fallback: treat as >Z
    return f"({sa_prefix}_OFFSET_X, {sa_prefix}_OFFSET_Y, {parent_z})"
