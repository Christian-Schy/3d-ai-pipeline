"""Assembler — per-feature CadQuery code generation.

Turns a single feature's params + placement into the source text of one
make_/drill_/cut_/apply_ function. Standard features map to deterministic
templates (src.codegen.templates); unknown types get a `pass` stub for
the LLM to fill.

Symbols (intra-package):
    _generate_constants  — Phase 1: DIMS / OFFSETS constants per feature
    _generate_root       — root feature → make_ function
    _generate_add_part   — add/union part → standalone make_ function
    _generate_subtract   — subtract/modify feature → dispatches on ftype
    _subtract_*          — one handler per feature-type group
    _safe_depth          — depth value → float | None (through-hole)
    _find_parent         — parent-id lookup
    _expand_tangent_hole — anti-tangent diameter growth
    _grid_layout         — grid params → (rows, cols, spacing_x, spacing_y)
"""

from __future__ import annotations

from src.codegen import templates as T


def _generate_constants(build_order: list, features: dict) -> list[str]:
    """Generate parameter constants for all features."""
    lines = []
    for fid in build_order:
        feat = features.get(fid, {})
        params = feat.get("params", {})
        placement = feat.get("placement") or {}
        prefix = fid.upper().replace("-", "_").replace(" ", "_")

        emitted = False
        for k, v in params.items():
            if isinstance(v, (int, float)) and v > 0:
                lines.append(f"{prefix}_{k.upper()} = {v}")
                emitted = True

        # Offset constants from placement (default 0.0 for add-parts)
        parent = feat.get("parent")
        ox = placement.get("offset_x")
        oy = placement.get("offset_y")
        needs_offset = (parent is not None)  # all child features need offsets

        if ox is not None:
            lines.append(f"{prefix}_OFFSET_X = {round(float(ox), 4)}")
            emitted = True
        elif needs_offset:
            lines.append(f"{prefix}_OFFSET_X = 0.0")
            emitted = True

        if oy is not None:
            lines.append(f"{prefix}_OFFSET_Y = {round(float(oy), 4)}")
            emitted = True
        elif needs_offset:
            lines.append(f"{prefix}_OFFSET_Y = 0.0")
            emitted = True

        if emitted:
            lines.append("")

    return lines


def _generate_root(func_name: str, ftype: str, params: dict) -> str:
    """Generate code for a root feature."""
    if ftype in ("box", "base_plate", "extrusion_rect", "step"):
        x = float(params.get("x") or 100)
        y = float(params.get("y") or 100)
        z = float(params.get("z") or 20)
        return T.root_box(func_name, x, y, z)
    elif ftype in ("cylinder", "base_cylinder", "extrusion_round"):
        r = float(params.get("radius") or (params.get("diameter") or 50) / 2)
        h = float(params.get("height") or params.get("z") or 50)
        return T.root_cylinder(func_name, r, h)
    elif ftype in ("sphere", "base_sphere"):
        r = float(params.get("radius") or (params.get("diameter") or 50) / 2)
        return T.root_sphere(func_name, r)
    # Complex root — stub
    return (
        f"def {func_name}() -> cq.Workplane:\n"
        f"    # TODO: Complex root type '{ftype}' — needs LLM\n"
        f"    pass\n"
    )


def _generate_add_part(func_name: str, ftype: str, params: dict) -> str:
    """Generate standalone add-part (sub-assembly build function)."""
    if ftype in ("box", "base_plate", "extrusion_rect", "step"):
        x = float(params.get("x") or 50)
        y = float(params.get("y") or 50)
        z = float(params.get("z") or 20)
        return T.add_box(func_name, x, y, z)
    elif ftype in ("cylinder", "base_cylinder", "extrusion_round"):
        r = float(params.get("radius") or (params.get("diameter") or 25) / 2)
        h = float(params.get("height") or params.get("z") or 30)
        return T.add_cylinder(func_name, r, h)
    # Complex add-part — stub
    return (
        f"def {func_name}() -> cq.Workplane:\n"
        f"    # TODO: Complex add-part type '{ftype}' — needs LLM\n"
        f"    pass\n"
    )


def _generate_subtract(
    func_name: str,
    fid: str,
    ftype: str,
    params: dict,
    placement: dict,
    all_features: dict,
) -> str:
    """Generate code for a subtract/modify feature — dispatches on ftype.

    Each feature-type group has its own `_subtract_*` handler; this
    function only resolves the common placement values and routes. NTP
    (NearestToPoint) detection is a future TODO — handlers currently emit
    use_ntp=False.
    """
    face = placement.get("face", ">Z")
    ox = float(placement.get("offset_x", 0) or 0)
    oy = float(placement.get("offset_y", 0) or 0)

    if ftype in ("hole", "hole_single", "cylinder"):
        return _subtract_hole(func_name, fid, params, placement, all_features, face, ox, oy)
    if ftype == "hole_counterbore":
        return _subtract_counterbore(func_name, params, face, ox, oy)
    if ftype == "hole_countersink":
        return _subtract_countersink(func_name, params, face, ox, oy)
    if ftype == "hole_pattern_grid":
        return _subtract_pattern_grid(func_name, fid, params, placement, all_features, face, ox, oy)
    if ftype == "hole_pattern_circular":
        return _subtract_pattern_circular(func_name, params, face, ox, oy)
    if ftype == "hole_pattern_linear":
        return _subtract_pattern_linear(func_name, fid, params, placement, all_features, face, ox, oy)
    if ftype in ("slot", "groove"):
        return _subtract_slot(func_name, fid, params, placement, all_features, face, ox, oy)
    if ftype in ("pocket_rect", "cutout", "box"):
        return _subtract_pocket(func_name, params, placement, face, ox, oy)
    if ftype == "fillet":
        return T.fillet(func_name, float(params.get("radius") or 2),
                        params.get("edge_selector", "|Z"))
    if ftype == "chamfer":
        return T.chamfer(func_name, float(params.get("size") or 2),
                         params.get("edge_selector", "|Z"))
    if ftype == "shell":
        return T.shell(func_name, float(params.get("thickness") or 2),
                       params.get("face", ">Z"))

    # Complex subtract — stub
    return (
        f"def {func_name}(body: cq.Workplane) -> cq.Workplane:\n"
        f"    # TODO: Complex type '{ftype}' — needs LLM\n"
        f"    pass\n"
    )


def _subtract_hole(
    func_name: str, fid: str, params: dict, placement: dict,
    all_features: dict, face: str, ox: float, oy: float,
) -> str:
    """hole / hole_single / cylinder(subtract) → cylindrical cut.

    Auto-redirects to a pattern handler when params reveal a mistyped
    grid/circular pattern. Applies anti-tangent diameter expansion when
    the hole edge sits exactly on a parent edge.
    """
    if params.get("inset") and params.get("count", 1) > 1:
        # Actually a hole_pattern_grid mistyped as "hole"
        return _generate_subtract(func_name, fid, "hole_pattern_grid",
                                  params, placement, all_features)
    if params.get("bolt_circle_diameter") or (params.get("count", 1) > 4 and not params.get("inset")):
        # Actually a hole_pattern_circular
        return _generate_subtract(func_name, fid, "hole_pattern_circular",
                                  params, placement, all_features)
    d = float(params.get("diameter") or params.get("hole_diameter") or (params.get("radius", 5) * 2))
    depth = _safe_depth(params.get("depth") or params.get("height"))
    d = _expand_tangent_hole(d, fid, face, ox, oy, all_features)
    return T.hole_single(func_name, d, depth, face, ox, oy, False, None)


def _expand_tangent_hole(
    d: float, fid: str, face: str, ox: float, oy: float, all_features: dict,
) -> float:
    """Grow a hole diameter by 0.02mm when its edge sits mathematically on a
    parent edge (e.g. user spec "10mm vom Rand" with 20mm Bohrung).

    Tangent edges produce non-manifold tessellation in OCCT (see run
    0ef217ab); 0.01mm tolerance covers FP rounding from the resolver.
    Returns the diameter unchanged when no edge is tangent.
    """
    parent_id = _find_parent(fid, all_features)
    pp = all_features.get(parent_id, {}).get("params", {}) if parent_id else {}
    if not pp:
        return d
    if face in (">Z", "<Z"):
        face_w, face_h = float(pp.get("x") or 0), float(pp.get("y") or 0)
    elif face in (">X", "<X"):
        face_w, face_h = float(pp.get("y") or 0), float(pp.get("z") or 0)
    elif face in (">Y", "<Y"):
        face_w, face_h = float(pp.get("x") or 0), float(pp.get("z") or 0)
    else:
        face_w = face_h = 0.0
    r = d / 2.0
    tangent_x = face_w > 0 and abs(abs(ox) + r - face_w / 2.0) < 0.01
    tangent_y = face_h > 0 and abs(abs(oy) + r - face_h / 2.0) < 0.01
    return d + 0.02 if (tangent_x or tangent_y) else d


def _subtract_counterbore(
    func_name: str, params: dict, face: str, ox: float, oy: float,
) -> str:
    """hole_counterbore → Cbore with default 1.8× diameter / 5mm depth."""
    d = float(params.get("diameter") or 10)
    depth = _safe_depth(params.get("depth"))
    cbd = float(params.get("cbore_diameter") or d * 1.8)
    cbdepth = float(params.get("cbore_depth") or 5)
    return T.hole_counterbore(func_name, d, depth, cbd, cbdepth, face, ox, oy, False, None)


def _subtract_countersink(
    func_name: str, params: dict, face: str, ox: float, oy: float,
) -> str:
    """hole_countersink → Csk with default 2× diameter / 82° angle."""
    d = float(params.get("diameter") or 10)
    depth = _safe_depth(params.get("depth"))
    csd = float(params.get("csk_diameter") or d * 2)
    angle = float(params.get("csk_angle") or 82)
    return T.hole_countersink(func_name, d, depth, csd, angle, face, ox, oy, False, None)


def _subtract_pattern_grid(
    func_name: str, fid: str, params: dict, placement: dict,
    all_features: dict, face: str, ox: float, oy: float,
) -> str:
    """hole_pattern_grid → grid of holes; layout via _grid_layout."""
    hd = float(params.get("hole_diameter") or params.get("diameter") or 10)
    depth = _safe_depth(params.get("depth"))
    parent_id = _find_parent(fid, all_features)
    pp = all_features.get(parent_id, {}).get("params", {}) if parent_id else {}
    px = float(pp.get("x") or 100)
    py = float(pp.get("y") or 100)
    pz = float(pp.get("z") or 10)
    rows, cols, spacing_x, spacing_y = _grid_layout(params, face, px, py, pz)
    grid_angle = float(placement.get("angle_deg") or 0)
    return T.hole_pattern_grid(
        func_name, hd, depth, rows, cols, spacing_x, spacing_y,
        face, ox, oy, grid_angle, False, None
    )


def _subtract_pattern_circular(
    func_name: str, params: dict, face: str, ox: float, oy: float,
) -> str:
    """hole_pattern_circular → bolt-circle of holes."""
    hd = float(params.get("hole_diameter") or params.get("diameter") or 10)
    depth = _safe_depth(params.get("depth"))
    count = int(params.get("count", 6))
    bolt_d = float(params.get("bolt_circle_diameter") or params.get("diameter") or 60)
    start_angle = float(params.get("start_angle_deg") or 0.0)
    return T.hole_pattern_circular(
        func_name, hd, depth, count, bolt_d, face, ox, oy, False, None,
        start_angle_deg=start_angle,
    )


def _subtract_pattern_linear(
    func_name: str, fid: str, params: dict, placement: dict,
    all_features: dict, face: str, ox: float, oy: float,
) -> str:
    """hole_pattern_linear → row of holes along a face-local axis."""
    hd = float(params.get("hole_diameter") or params.get("diameter") or 10)
    depth = _safe_depth(params.get("depth"))
    count = int(params.get("count") or 4)
    spacing = float(params.get("spacing") or 20)

    # Determine direction from notes first, then params, then default
    notes_lower = placement.get("notes", "").lower()
    if "entlang x" in notes_lower or "along x" in notes_lower or "x-achse" in notes_lower:
        direction = "x"
    elif "entlang y" in notes_lower or "along y" in notes_lower or "y-achse" in notes_lower:
        direction = "y"
    elif "entlang z" in notes_lower or "along z" in notes_lower or "z-achse" in notes_lower:
        direction = "z"
    else:
        direction = str(params.get("direction", "x")).lower()

    # Map global axis to face-local direction (same logic as slots)
    # On >Z/<Z: workplane-X=globalX, workplane-Y=globalY
    # On >X/<X: workplane-X=globalY, workplane-Y=globalZ
    # On >Y/<Y: workplane-X=globalX, workplane-Y=globalZ
    _axis_to_dir = {
        ">Z": {"x": "x", "y": "y", "z": "x"},
        "<Z": {"x": "x", "y": "y", "z": "x"},
        ">X": {"y": "x", "z": "y", "x": "x"},
        "<X": {"y": "x", "z": "y", "x": "x"},
        ">Y": {"x": "x", "z": "y", "y": "x"},
        "<Y": {"x": "x", "z": "y", "y": "x"},
    }
    if face in _axis_to_dir:
        direction = _axis_to_dir[face].get(direction, "x")

    linear_angle = float(placement.get("angle_deg") or 0)
    return T.hole_pattern_linear(
        func_name, hd, depth, count, spacing, direction,
        face, ox, oy, linear_angle, False, None
    )


def _slot_axis_hint(notes_lower: str) -> str | None:
    """Extract an explicit slot cutting axis (X/Y/Z) from placement notes."""
    if "entlang z" in notes_lower or "along z" in notes_lower or "z-achse" in notes_lower:
        return "Z"
    if "entlang y" in notes_lower or "along y" in notes_lower or "y-achse" in notes_lower:
        return "Y"
    if "entlang x" in notes_lower or "along x" in notes_lower or "x-achse" in notes_lower:
        return "X"
    return None


def _subtract_slot(
    func_name: str, fid: str, params: dict, placement: dict,
    all_features: dict, face: str, ox: float, oy: float,
) -> str:
    """slot / groove → channel cut, axis resolved from notes/length/angle."""
    w = float(params.get("width") or 5)
    d = float(params.get("depth") or 5)

    # Determine axis from notes first, then translate to workplane angle per face.
    notes_lower = placement.get("notes", "").lower()
    axis_hint = _slot_axis_hint(notes_lower)

    # Deterministic fallback: if slot has explicit length matching a parent
    # dimension, infer the axis from which dimension matches.
    if axis_hint is None and params.get("length") is not None:
        slot_len = float(params["length"])
        parent_id = _find_parent(fid, all_features)
        pp = all_features.get(parent_id, {}).get("params", {}) if parent_id else {}
        px = float(pp.get("x") or 0)
        py = float(pp.get("y") or 0)
        if face in (">Z", "<Z"):
            if slot_len == py and slot_len != px:
                axis_hint = "Y"
            elif slot_len == px and slot_len != py:
                axis_hint = "X"

    # Map global axis to workplane angle per face.
    # Each face has two directions; the third axis is perpendicular (into the face).
    #
    # Face    | workplane-X (angle=0) | workplane-Y (angle=90) | perpendicular
    # --------|----------------------|------------------------|-------------
    # >Z, <Z  | global X             | global Y               | Z
    # >X, <X  | global Y             | global Z               | X
    # >Y, <Y  | global X             | global Z               | Y
    #
    # If the requested axis IS the perpendicular one, we fall back to angle=0
    # (first workplane direction) since the axis doesn't exist on this face.
    _axis_to_angle = {
        ">Z": {"X": 0, "Y": 90, "Z": 0},    # Z is perp → fallback 0
        "<Z": {"X": 0, "Y": 90, "Z": 0},
        ">X": {"Y": 0, "Z": 90, "X": 0},    # X is perp → fallback 0
        "<X": {"Y": 0, "Z": 90, "X": 0},
        ">Y": {"X": 0, "Z": 90, "Y": 0},    # Y is perp → fallback 0
        "<Y": {"X": 0, "Z": 90, "Y": 0},
    }
    if axis_hint and face in _axis_to_angle:
        angle = _axis_to_angle[face].get(axis_hint, 0)
    else:
        angle = float(params.get("angle") or 0)
    # placement.angle_deg from resolver wins when set explicitly (non-zero).
    # Lets the user say "Nut um 30 Grad gedreht" and have the resolver
    # propagate that through the standard placement channel.
    placement_angle = float(placement.get("angle_deg") or 0)
    if placement_angle != 0.0:
        angle = placement_angle

    length = params.get("length")
    if length is None:
        # Full parent length — pick the parent dimension along the cutting direction in 3D
        parent_id = _find_parent(fid, all_features)
        pp = all_features.get(parent_id, {}).get("params", {}) if parent_id else {}
        px = float(pp.get("x") or 100)
        py = float(pp.get("y") or 100)
        pz = float(pp.get("z") or 100)
        if face in (">Z", "<Z"):
            length = py if angle == 90 else px
        elif face in (">X", "<X"):
            # angle=0 → cuts along workplane-X = global Y; angle=90 → along Z
            length = pz if angle == 90 else py
        elif face in (">Y", "<Y"):
            # angle=0 → cuts along workplane-X = global X; angle=90 → along Z
            length = pz if angle == 90 else px
        else:
            length = py if angle == 90 else px
        # Anti-tangent overshoot: a slot whose ends sit exactly on the parent
        # edges produces non-manifold tessellation in OCCT (see run 0ef217ab).
        # Extend by 0.02mm so each end pokes 0.01mm past the parent edge.
        # This matches user intent for "Nut entlang der Achse" (a through
        # channel that opens at both ends), and the cut is geometrically
        # clean (open cut, not tangent).
        length += 0.02
    else:
        length = float(length)
    return T.slot(func_name, length, w, d, angle, face, ox, oy, False, None)


def _subtract_pocket(
    func_name: str, params: dict, placement: dict, face: str, ox: float, oy: float,
) -> str:
    """pocket_rect / cutout / box(subtract) → rectangular pocket cut."""
    x = float(params.get("x") or 30)
    y = float(params.get("y") or 30)
    d = float(params.get("depth") or params.get("z") or 5)
    # placement.angle_deg rotates the rectangular cutter around the face normal.
    angle_deg = float(placement.get("angle_deg") or 0)
    return T.pocket_rect(func_name, x, y, d, face, ox, oy, angle_deg, False, None)


def _safe_depth(value) -> float | None:
    """Convert depth to float, treating 'through'/None as through-hole (None)."""
    if value is None:
        return None
    if isinstance(value, str):
        if value.lower() in ("through", "null", "none", ""):
            return None
        try:
            return float(value)
        except ValueError:
            return None
    return float(value)


def _find_parent(fid: str, features: dict) -> str | None:
    """Find the immediate parent feature ID for a given feature."""
    feat = features.get(fid, {})
    return feat.get("parent")


def _grid_layout(
    params: dict, face: str, px: float, py: float, pz: float
) -> tuple[int, int, float, float]:
    """Derive (rows, cols, spacing_x, spacing_y) for a hole_pattern_grid.

    Explizite Form: params traegt `rows`/`cols` + `spacing_x`/`spacing_y`
    (oder `spacing` isotrop) — direkt uebernommen.
    Legacy-Form: `count` + `inset` — Raster aus count abgeleitet
    (4→2x2, 6→3x2, 9→3x3, sonst sqrt), Spacing aus den Face-Massen
    (aeussere Loecher `inset` von der Kante).
    """
    rows = params.get("rows")
    cols = params.get("cols")
    if rows and cols:
        rows, cols = int(rows), int(cols)
        iso = params.get("spacing") or params.get("rasterabstand") or 0
        sx = float(params.get("spacing_x") or iso or 0)
        sy = float(params.get("spacing_y") or iso or sx)
        if not sx:
            sx = sy
        return rows, cols, sx, sy

    # Legacy count + inset.
    count = int(params.get("count") or 4)
    inset = float(params.get("inset") or 20)
    if count == 4:
        nx, ny = 2, 2
    elif count == 6:
        nx, ny = 3, 2
    elif count == 9:
        nx, ny = 3, 3
    else:
        nx = ny = max(1, int(count ** 0.5))
    if face in (">Z", "<Z"):
        fw, fh = px, py
    elif face in (">X", "<X"):
        fw, fh = py, pz
    else:  # >Y, <Y
        fw, fh = px, pz
    sx = (fw - 2 * inset) / (nx - 1) if nx > 1 else 0.0
    sy = (fh - 2 * inset) / (ny - 1) if ny > 1 else 0.0
    # nx zaehlt entlang Face-X → cols, ny entlang Face-Y → rows.
    return ny, nx, sx, sy
