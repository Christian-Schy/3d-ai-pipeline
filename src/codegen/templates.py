"""
src/codegen/templates.py — CadQuery code templates for standard features.

Each template function takes pre-computed parameters and returns a CadQuery
code string. Templates produce code strings, NOT CadQuery objects — this
keeps them testable without CadQuery installed.

All offsets, face selectors, and dimensions are pre-computed by the
BlueprintAssembler before templates are called.

═══════════════════════════════════════════════════════════════════
STRUKTUR (bei Aenderungen pflegen! Siehe CLAUDE.md)
═══════════════════════════════════════════════════════════════════
Root-Body-Templates (parent=None):
  root_box, root_cylinder, root_sphere

Add-Part-Templates (Sub-Assembly: Standalone-Build, spaeter translate+union):
  add_box, add_cylinder

Subtract-Feature-Templates (Loecher/Nuten/Taschen):
  hole_single                     — einzelne Bohrung (.hole)
  hole_counterbore                — Senkbohrung mit Einsenkung (.cboreHole)
  hole_countersink                — Senkbohrung konisch (.cskHole)
  hole_pattern_grid               — N x M Raster (.rarray)
  hole_pattern_circular           — Lochkreis (.polarArray)
  hole_pattern_linear             — Reihe mit Spacing, per-Loop
  slot                            — rect() oder slot2D() je nach angle
  pocket_rect                     — Rechtecktasche (.rect+.cutBlind)

Modifier-Templates:
  fillet                          — Kantenverrundung
  chamfer                         — Kantenfase
  shell                           — Wandstaerke/Aushoehlen

Helper:
  _face_selection(face, use_ntp, ntp_point)
    — ">Z"/"<X" Selector ODER NearestToPointSelector (nach erster Union)
  _hole_depth(d, depth)
    — through-hole (None) oder blind (float)

Registry (wird von assembler.py genutzt):
  TEMPLATE_REGISTRY               — dict: feature-type → template-func
═══════════════════════════════════════════════════════════════════
"""

from __future__ import annotations


# ──────────────────────────────────────────────────────────────────
# Root body templates (no parent)
# ──────────────────────────────────────────────────────────────────

def root_box(func_name: str, x: float, y: float, z: float) -> str:
    """Root box at origin."""
    return (
        f"def {func_name}() -> cq.Workplane:\n"
        f"    return cq.Workplane('XY').box("
        f"{x}, {y}, {z}, centered=(True, True, False))\n"
    )


def root_cylinder(func_name: str, radius: float, height: float) -> str:
    """Root cylinder at origin."""
    return (
        f"def {func_name}() -> cq.Workplane:\n"
        f"    return cq.Workplane('XY').circle({radius}).extrude({height})\n"
    )


def root_sphere(func_name: str, radius: float) -> str:
    """Root sphere at origin."""
    return (
        f"def {func_name}() -> cq.Workplane:\n"
        f"    return cq.Workplane('XY').sphere({radius})\n"
    )


# ──────────────────────────────────────────────────────────────────
# Add-part templates (sub-assembly: build standalone, translate, union)
# ──────────────────────────────────────────────────────────────────

def add_box(func_name: str, x: float, y: float, z: float) -> str:
    """Standalone box for sub-assembly pattern."""
    return (
        f"def {func_name}() -> cq.Workplane:\n"
        f"    return cq.Workplane('XY').box("
        f"{x}, {y}, {z}, centered=(True, True, False))\n"
    )


def add_cylinder(func_name: str, radius: float, height: float) -> str:
    """Standalone cylinder for sub-assembly pattern."""
    return (
        f"def {func_name}() -> cq.Workplane:\n"
        f"    return cq.Workplane('XY').circle({radius}).extrude({height})\n"
    )


# ──────────────────────────────────────────────────────────────────
# Subtract feature templates (holes, slots, pockets)
# ──────────────────────────────────────────────────────────────────

def hole_single(
    func_name: str,
    diameter: float,
    depth: float | None,
    face: str,
    offset_x: float,
    offset_y: float,
    use_ntp: bool = False,
    ntp_point: tuple[float, float, float] | None = None,
) -> str:
    """Single hole on a face."""
    face_sel = _face_selection(face, use_ntp, ntp_point)
    depth_call = _hole_depth(diameter, depth)
    return (
        f"def {func_name}(body: cq.Workplane) -> cq.Workplane:\n"
        f"    return (\n"
        f"        body\n"
        f"        {face_sel}\n"
        f"        .center({offset_x}, {offset_y})\n"
        f"        {depth_call}\n"
        f"    ).clean()\n"
    )


def hole_counterbore(
    func_name: str,
    diameter: float,
    depth: float | None,
    cbore_diameter: float,
    cbore_depth: float,
    face: str,
    offset_x: float,
    offset_y: float,
    use_ntp: bool = False,
    ntp_point: tuple[float, float, float] | None = None,
) -> str:
    """Counterbore hole."""
    face_sel = _face_selection(face, use_ntp, ntp_point)
    d_arg = f", {depth}" if depth else ""
    return (
        f"def {func_name}(body: cq.Workplane) -> cq.Workplane:\n"
        f"    return (\n"
        f"        body\n"
        f"        {face_sel}\n"
        f"        .center({offset_x}, {offset_y})\n"
        f"        .cboreHole({diameter}, {cbore_diameter}, {cbore_depth}{d_arg})\n"
        f"    ).clean()\n"
    )


def hole_countersink(
    func_name: str,
    diameter: float,
    depth: float | None,
    csk_diameter: float,
    csk_angle: float,
    face: str,
    offset_x: float,
    offset_y: float,
    use_ntp: bool = False,
    ntp_point: tuple[float, float, float] | None = None,
) -> str:
    """Countersink hole."""
    face_sel = _face_selection(face, use_ntp, ntp_point)
    d_arg = f", {depth}" if depth else ""
    return (
        f"def {func_name}(body: cq.Workplane) -> cq.Workplane:\n"
        f"    return (\n"
        f"        body\n"
        f"        {face_sel}\n"
        f"        .center({offset_x}, {offset_y})\n"
        f"        .cskHole({diameter}, {csk_diameter}, {csk_angle}{d_arg})\n"
        f"    ).clean()\n"
    )


def hole_pattern_grid(
    func_name: str,
    hole_diameter: float,
    depth: float | None,
    count: int,
    inset: float,
    parent_x: float,
    parent_y: float,
    parent_z: float,
    face: str,
    offset_x: float,
    offset_y: float,
    use_ntp: bool = False,
    ntp_point: tuple[float, float, float] | None = None,
) -> str:
    """Grid pattern of holes (typically 4 corner holes)."""
    face_sel = _face_selection(face, use_ntp, ntp_point)
    depth_call = _hole_depth(hole_diameter, depth)

    # Compute face dimensions based on face selector
    # >Z/<Z: face is X×Y, >X/<X: face is Y×Z, >Y/<Y: face is X×Z
    if face in (">Z", "<Z"):
        face_w, face_h = parent_x, parent_y
    elif face in (">X", "<X"):
        face_w, face_h = parent_y, parent_z
    else:  # >Y, <Y
        face_w, face_h = parent_x, parent_z

    # Grid layout: count=4 → 2×2, count=6 → 3×2, count=9 → 3×3
    if count == 4:
        nx, ny = 2, 2
    elif count == 6:
        nx, ny = 3, 2
    elif count == 9:
        nx, ny = 3, 3
    else:
        nx = ny = max(1, int(count ** 0.5))

    spacing_x = face_w - 2 * inset
    spacing_y = face_h - 2 * inset

    return (
        f"def {func_name}(body: cq.Workplane) -> cq.Workplane:\n"
        f"    return (\n"
        f"        body\n"
        f"        {face_sel}\n"
        f"        .center({offset_x}, {offset_y})\n"
        f"        .rarray({spacing_x}, {spacing_y}, {nx}, {ny})\n"
        f"        {depth_call}\n"
        f"    ).clean()\n"
    )


def hole_pattern_circular(
    func_name: str,
    hole_diameter: float,
    depth: float | None,
    count: int,
    bolt_circle_diameter: float,
    face: str,
    offset_x: float,
    offset_y: float,
    use_ntp: bool = False,
    ntp_point: tuple[float, float, float] | None = None,
) -> str:
    """Circular pattern of holes (bolt circle)."""
    face_sel = _face_selection(face, use_ntp, ntp_point)
    depth_call = _hole_depth(hole_diameter, depth)
    radius = bolt_circle_diameter / 2

    return (
        f"def {func_name}(body: cq.Workplane) -> cq.Workplane:\n"
        f"    return (\n"
        f"        body\n"
        f"        {face_sel}\n"
        f"        .center({offset_x}, {offset_y})\n"
        f"        .polarArray({radius}, 0, 360, {count})\n"
        f"        {depth_call}\n"
        f"    ).clean()\n"
    )


def hole_pattern_linear(
    func_name: str,
    hole_diameter: float,
    depth: float | None,
    count: int,
    spacing: float,
    start_offset: float,
    direction: str,
    face: str,
    offset_x: float,
    offset_y: float,
    parent_x: float,
    parent_y: float,
    parent_z: float,
    use_ntp: bool = False,
    ntp_point: tuple[float, float, float] | None = None,
) -> str:
    """Linear pattern of holes (row with equal spacing).

    Generates individual positioned holes using .center() offsets.
    start_offset = distance of first hole from the face edge.
    direction = "x" or "y" — which face axis the row runs along.
    """
    face_sel = _face_selection(face, use_ntp, ntp_point)
    depth_call = _hole_depth(hole_diameter, depth)

    # Compute face dimensions based on face selector
    if face in (">Z", "<Z"):
        face_w, face_h = parent_x, parent_y
    elif face in (">X", "<X"):
        face_w, face_h = parent_y, parent_z
    else:  # >Y, <Y
        face_w, face_h = parent_x, parent_z

    # Compute hole positions along the direction axis
    lines = [
        f"def {func_name}(body: cq.Workplane) -> cq.Workplane:",
    ]

    if direction.lower() == "x":
        dim = face_w
    else:
        dim = face_h

    # Calculate positions: center the row on the face.
    # Total row span = (count - 1) * spacing
    # Offset from center to first hole = -span / 2
    total_span = (count - 1) * spacing
    first_pos = -total_span / 2

    lines.append(f"    positions = [{', '.join(str(round(first_pos + i * spacing, 2)) for i in range(count))}]")
    lines.append(f"    for pos in positions:")
    lines.append(f"        body = (")
    lines.append(f"            body")
    lines.append(f"            {face_sel}")

    if direction.lower() == "x":
        lines.append(f"            .center(pos + {-offset_x}, {offset_y})")
    else:
        lines.append(f"            .center({offset_x}, pos + {-offset_y})")

    lines.append(f"            {depth_call}")
    lines.append(f"        ).clean()")
    lines.append(f"    return body")
    lines.append("")

    return "\n".join(lines) + "\n"


def slot(
    func_name: str,
    length: float,
    width: float,
    depth: float,
    angle: float,
    face: str,
    offset_x: float,
    offset_y: float,
    use_ntp: bool = False,
    ntp_point: tuple[float, float, float] | None = None,
) -> str:
    """Slot/groove on a face.

    For straight slots (angle=0 or 90), uses .rect().cutBlind() to produce
    a full-length rectangular cut that reaches part edges. Only uses .slot2D()
    for diagonal slots where rounded ends are needed.
    """
    face_sel = _face_selection(face, use_ntp, ntp_point)
    # Straight slots use rect() to cut edge-to-edge.
    # slot2D() has rounded ends (radius=width/2) that stay inside part edges.
    if angle == 0:
        shape = f".rect({length}, {width})"
    elif angle == 90:
        shape = f".rect({width}, {length})"
    else:
        shape = f".slot2D({length}, {width}, {angle})"
    return (
        f"def {func_name}(body: cq.Workplane) -> cq.Workplane:\n"
        f"    return (\n"
        f"        body\n"
        f"        {face_sel}\n"
        f"        .center({offset_x}, {offset_y})\n"
        f"        {shape}\n"
        f"        .cutBlind(-{depth})\n"
        f"    ).clean()\n"
    )


def pocket_rect(
    func_name: str,
    x: float,
    y: float,
    depth: float,
    face: str,
    offset_x: float,
    offset_y: float,
    use_ntp: bool = False,
    ntp_point: tuple[float, float, float] | None = None,
) -> str:
    """Rectangular pocket on a face."""
    face_sel = _face_selection(face, use_ntp, ntp_point)
    return (
        f"def {func_name}(body: cq.Workplane) -> cq.Workplane:\n"
        f"    return (\n"
        f"        body\n"
        f"        {face_sel}\n"
        f"        .center({offset_x}, {offset_y})\n"
        f"        .rect({x}, {y})\n"
        f"        .cutBlind(-{depth})\n"
        f"    ).clean()\n"
    )


# ──────────────────────────────────────────────────────────────────
# Modifier templates (fillet, chamfer, shell)
# ──────────────────────────────────────────────────────────────────

def fillet(func_name: str, radius: float, edge_selector: str = "|Z") -> str:
    """Fillet on edges."""
    return (
        f"def {func_name}(body: cq.Workplane) -> cq.Workplane:\n"
        f"    return body.edges(\"{edge_selector}\").fillet({radius}).clean()\n"
    )


def chamfer(func_name: str, size: float, edge_selector: str = "|Z") -> str:
    """Chamfer on edges."""
    return (
        f"def {func_name}(body: cq.Workplane) -> cq.Workplane:\n"
        f"    return body.edges(\"{edge_selector}\").chamfer({size}).clean()\n"
    )


def shell(func_name: str, thickness: float, faces_to_remove: str = ">Z") -> str:
    """Shell (hollow out) a body."""
    return (
        f"def {func_name}(body: cq.Workplane) -> cq.Workplane:\n"
        f"    return body.faces(\"{faces_to_remove}\").shell({thickness}).clean()\n"
    )


# ──────────────────────────────────────────────────────────────────
# Helper functions
# ──────────────────────────────────────────────────────────────────

def _face_selection(
    face: str,
    use_ntp: bool = False,
    ntp_point: tuple[float, float, float] | None = None,
) -> str:
    """Generate face selection code.

    After first union, face selectors like ">Z" become ambiguous.
    In that case, use NearestToPointSelector to find the correct face.
    """
    if use_ntp and ntp_point:
        x, y, z = ntp_point
        return (
            f".faces(cq.selectors.NearestToPointSelector(({x}, {y}, {z})))\n"
            f"        .workplane(centerOption='CenterOfBoundBox')"
        )
    return (
        f".faces(\"{face}\")\n"
        f"        .workplane(centerOption='CenterOfBoundBox')"
    )


def _hole_depth(diameter: float, depth: float | None) -> str:
    """Generate hole call — through-hole or blind hole."""
    if depth is None:
        return f".hole({diameter})"
    return f".hole({diameter}, {depth})"


# ──────────────────────────────────────────────────────────────────
# Template registry — maps feature type to template function
# ──────────────────────────────────────────────────────────────────

TEMPLATE_REGISTRY: dict[str, callable] = {
    # Root bodies
    "box": root_box,
    "base_plate": root_box,
    "cylinder": root_cylinder,
    "base_cylinder": root_cylinder,
    "sphere": root_sphere,
    "base_sphere": root_sphere,
    # Add-parts (sub-assembly)
    "extrusion_rect": add_box,
    "step": add_box,
    # Holes
    "hole": hole_single,
    "hole_single": hole_single,
    "hole_counterbore": hole_counterbore,
    "hole_countersink": hole_countersink,
    "hole_pattern_grid": hole_pattern_grid,
    "hole_pattern_circular": hole_pattern_circular,
    "hole_pattern_linear": hole_pattern_linear,
    # Slots & pockets
    "slot": slot,
    "groove": slot,
    "pocket_rect": pocket_rect,
    "cutout": pocket_rect,
    # Modifiers
    "fillet": fillet,
    "chamfer": chamfer,
    "shell": shell,
}
