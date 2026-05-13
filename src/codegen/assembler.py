"""
src/codegen/assembler.py — Assembles CadQuery code from Feature Tree + templates.

Takes a Feature Tree blueprint (with pre-computed offsets from BlueprintAssembler)
and generates a complete, executable Python file using templates.

For standard features: deterministic template code.
For complex features: function stubs with `pass` (LLM fills these).

═══════════════════════════════════════════════════════════════════
STRUKTUR (bei Aenderungen pflegen! Siehe CLAUDE.md)
═══════════════════════════════════════════════════════════════════
Public API:
  generate_code(blueprint)        — Blueprint → fertige .py-Datei als str

Code-Generierungs-Phasen (innerhalb generate_code):
  Phase 1: _generate_constants    — Konstanten pro Feature (DIMS, OFFSETS)
  Phase 2: _generate_root / _generate_add_part / _generate_subtract
                                  — eine make_/cut_/apply_-Funktion pro Feature
  Phase 3: _generate_sub_assembly_builds
                                  — build_<part>() Funktionen: make + subtract-children
                                    + nested add-children (translate+union)
  Phase 4: _generate_assemble     — assemble(): root + sub-assemblies zusammenfuegen
  Phase 5: main                   — exporters.export(result, OUTPUT_PATH)

Helpers:
  _make_func_name                 — fid → make_/drill_/cut_/apply_ Prefix
  _safe_depth                     — None/'through' → None, sonst float
  _find_parent                    — parent-id Lookup in features-dict
  _emit_pre_rotation              — placement.pre_rotation → .rotate(...) Lines
                                    (rotiert um Child-Centroid VOR translate;
                                     Keys x/y/z in Grad)
  _emit_face_rotation             — placement.angle_deg → .rotate(...) um
                                    Flaechen-Normale durch Child-Centroid
                                    (VOR translate; fuer Sub-Assembly-Adds)
  _compute_translate              — face+parent/child dims → translate-Tuple
                                    (Face-Semantik: >Z oben, <X links, etc.;
                                     XY-Center, Z-Bottom; Offset-Mapping je Face)

Feature-Type-Mapping (_generate_subtract):
  hole/hole_single/cylinder       — Auto-Pattern-Detect via params
  hole_counterbore/countersink    — Cbore/Csk mit Default-Verhaeltnissen
  hole_pattern_grid/circular/linear — Muster; Pattern-Mathe im Template
  slot/groove                     — Notes/length-Heuristik fuer Achse
  pocket_rect/cutout/box(subtract) — rect().cutBlind
  fillet/chamfer/shell            — edge/face-Selector
  unbekannt                       — TODO-Stub fuer LLM
═══════════════════════════════════════════════════════════════════
"""

from __future__ import annotations
from src.codegen.feature_classifier import is_standard
from src.codegen import templates as T


def generate_code(blueprint: dict) -> str:
    """Generate complete CadQuery Python code from a Feature Tree blueprint.

    Returns a complete, executable Python file as a string.
    Complex features get `pass` stubs for LLM to fill.
    """
    build_order = blueprint.get("build_order", [])
    features = blueprint.get("features", {})
    description = blueprint.get("description", "")

    if not build_order or not features:
        return ""

    # Identify root and sub-assembly structure
    root_id = build_order[0]
    root_feat = features.get(root_id, {})

    # Collect all parts
    lines: list[str] = []
    lines.append("import cadquery as cq")
    lines.append("from cadquery.selectors import NearestToPointSelector")
    lines.append("")
    lines.append(f"OUTPUT_PATH = 'output.stl'")
    lines.append("")

    # Phase 1: Generate constants
    const_lines = _generate_constants(build_order, features)
    if const_lines:
        lines.extend(const_lines)
        lines.append("")

    # Phase 2: Generate function definitions
    func_map: dict[str, str] = {}  # fid → func_name
    sub_assemblies: list[dict] = []

    for fid in build_order:
        feat = features.get(fid, {})
        ftype = feat.get("type", "box").lower()
        operation = feat.get("operation", "add").lower()
        parent = feat.get("parent")
        params = feat.get("params", {})
        placement = feat.get("placement") or {}

        func_name = _make_func_name(fid, operation)
        func_map[fid] = func_name

        # Modifiers (fillet, chamfer, shell) are always treated as subtract/modify
        # regardless of what operation field says
        is_modifier = ftype in ("fillet", "chamfer", "shell")

        if parent is None and not is_modifier:
            # Root feature
            code = _generate_root(func_name, ftype, params)
        elif operation in ("add", "union") and not is_modifier:
            # Sub-assembly part — build standalone
            code = _generate_add_part(func_name, ftype, params)
            sub_assemblies.append({
                "fid": fid,
                "func_name": func_name,
                "parent": parent,
                "placement": placement,
                "params": params,
            })
        else:
            # Subtract/modify feature
            code = _generate_subtract(func_name, fid, ftype, params, placement, features)

        if code:
            lines.append(code)
            lines.append("")

    # Phase 3: Generate sub-assembly build functions
    # Group: which subtract features belong to which add-part?
    sa_builds = _generate_sub_assembly_builds(
        build_order, features, func_map, sub_assemblies
    )
    if sa_builds:
        lines.extend(sa_builds)

    # Phase 4: Generate assemble() function
    assemble_lines = _generate_assemble(
        root_id, build_order, features, func_map, sub_assemblies
    )
    lines.extend(assemble_lines)

    # Phase 5: Main
    lines.append("")
    lines.append("result = assemble()")
    lines.append("cq.exporters.export(result, OUTPUT_PATH)")
    lines.append("")

    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────

def _make_func_name(fid: str, operation: str) -> str:
    """Generate a function name from feature ID."""
    clean = fid.replace("-", "_").replace(" ", "_")
    if operation in ("subtract", "cut"):
        if clean.startswith(("hole", "drill")):
            return f"drill_{clean}"
        elif clean.startswith(("slot", "groove", "nut")):
            return f"cut_{clean}"
        elif clean.startswith(("fillet", "chamfer")):
            return f"apply_{clean}"
        return f"cut_{clean}"
    return f"make_{clean}"


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
        operation = feat.get("operation", "add").lower()
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
    """Generate code for a subtract/modify feature."""
    face = placement.get("face", ">Z")
    ox = float(placement.get("offset_x", 0) or 0)
    oy = float(placement.get("offset_y", 0) or 0)
    # TODO: NTP detection based on build order position
    use_ntp = False
    ntp_point = None

    if ftype in ("hole", "hole_single", "cylinder"):
        # cylinder with subtract operation = cylindrical hole/cut
        # Auto-detect grid/circular patterns by params
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
        # Anti-tangent expansion: if the hole's edge sits mathematically on a
        # parent edge (e.g. user spec "10mm vom Rand" with 20mm Bohrung), grow
        # the diameter by 0.02mm so it cleanly cuts through instead of touching.
        # Tangent edges produce non-manifold tessellation in OCCT (see run
        # 0ef217ab). 0.01mm tolerance covers FP rounding from the resolver.
        parent_id = _find_parent(fid, all_features)
        pp = all_features.get(parent_id, {}).get("params", {}) if parent_id else {}
        if pp:
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
            if tangent_x or tangent_y:
                d += 0.02
        return T.hole_single(func_name, d, depth, face, ox, oy, use_ntp, ntp_point)

    elif ftype == "hole_counterbore":
        d = float(params.get("diameter") or 10)
        depth = _safe_depth(params.get("depth"))
        cbd = float(params.get("cbore_diameter") or d * 1.8)
        cbdepth = float(params.get("cbore_depth") or 5)
        return T.hole_counterbore(
            func_name, d, depth, cbd, cbdepth, face, ox, oy, use_ntp, ntp_point
        )

    elif ftype == "hole_countersink":
        d = float(params.get("diameter") or 10)
        depth = _safe_depth(params.get("depth"))
        csd = float(params.get("csk_diameter") or d * 2)
        angle = float(params.get("csk_angle") or 82)
        return T.hole_countersink(
            func_name, d, depth, csd, angle, face, ox, oy, use_ntp, ntp_point
        )

    elif ftype == "hole_pattern_grid":
        hd = float(params.get("hole_diameter") or params.get("diameter") or 10)
        depth = _safe_depth(params.get("depth"))
        count = int(params.get("count") or 4)
        inset = float(params.get("inset") or 20)
        parent_id = _find_parent(fid, all_features)
        pp = all_features.get(parent_id, {}).get("params", {}) if parent_id else {}
        px = float(pp.get("x") or 100)
        py = float(pp.get("y") or 100)
        pz = float(pp.get("z") or 10)
        return T.hole_pattern_grid(
            func_name, hd, depth, count, inset, px, py, pz,
            face, ox, oy, use_ntp, ntp_point
        )

    elif ftype == "hole_pattern_circular":
        hd = float(params.get("hole_diameter") or params.get("diameter") or 10)
        depth = _safe_depth(params.get("depth"))
        count = int(params.get("count", 6))
        bolt_d = float(params.get("bolt_circle_diameter") or params.get("diameter") or 60)
        return T.hole_pattern_circular(
            func_name, hd, depth, count, bolt_d, face, ox, oy, use_ntp, ntp_point
        )

    elif ftype == "hole_pattern_linear":
        hd = float(params.get("hole_diameter") or params.get("diameter") or 10)
        depth = _safe_depth(params.get("depth"))
        count = int(params.get("count") or 4)
        spacing = float(params.get("spacing") or 20)

        # Determine direction from notes first, then params, then default
        notes = placement.get("notes", "")
        notes_lower = notes.lower()
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

        parent_id = _find_parent(fid, all_features)
        pp = all_features.get(parent_id, {}).get("params", {}) if parent_id else {}
        px = float(pp.get("x") or 100)
        py = float(pp.get("y") or 100)
        pz = float(pp.get("z") or 10)
        return T.hole_pattern_linear(
            func_name, hd, depth, count, spacing, direction,
            face, ox, oy, px, py, pz, use_ntp, ntp_point
        )

    elif ftype in ("slot", "groove"):
        w = float(params.get("width") or 5)
        d = float(params.get("depth") or 5)
        # Determine axis from notes first, then translate to workplane angle per face.
        # On top/bottom faces: workplane-X=globalX, workplane-Y=globalY → angle=0=X, 90=Y
        # On left/right faces: workplane-X=globalY, workplane-Y=globalZ → angle=0=Y, 90=Z
        # On front/back faces: workplane-X=globalX, workplane-Y=globalZ → angle=0=X, 90=Z
        notes = placement.get("notes", "")
        axis_hint = None
        notes_lower = notes.lower()
        if "entlang z" in notes_lower or "along z" in notes_lower or "z-achse" in notes_lower:
            axis_hint = "Z"
        elif "entlang y" in notes_lower or "along y" in notes_lower or "y-achse" in notes_lower:
            axis_hint = "Y"
        elif "entlang x" in notes_lower or "along x" in notes_lower or "x-achse" in notes_lower:
            axis_hint = "X"

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
        return T.slot(func_name, length, w, d, angle, face, ox, oy, use_ntp, ntp_point)

    elif ftype in ("pocket_rect", "cutout", "box"):
        # box with subtract operation = rectangular pocket/cutout
        x = float(params.get("x") or 30)
        y = float(params.get("y") or 30)
        d = float(params.get("depth") or params.get("z") or 5)
        # placement.angle_deg rotates the rectangular cutter around the face normal.
        angle_deg = float(placement.get("angle_deg") or 0)
        return T.pocket_rect(
            func_name, x, y, d, face, ox, oy, angle_deg, use_ntp, ntp_point
        )

    elif ftype == "fillet":
        r = float(params.get("radius") or 2)
        sel = params.get("edge_selector", "|Z")
        return T.fillet(func_name, r, sel)

    elif ftype == "chamfer":
        s = float(params.get("size") or 2)
        sel = params.get("edge_selector", "|Z")
        return T.chamfer(func_name, s, sel)

    elif ftype == "shell":
        t = float(params.get("thickness") or 2)
        face_rm = params.get("face", ">Z")
        return T.shell(func_name, t, face_rm)

    # Complex subtract — stub
    return (
        f"def {func_name}(body: cq.Workplane) -> cq.Workplane:\n"
        f"    # TODO: Complex type '{ftype}' — needs LLM\n"
        f"    pass\n"
    )


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


def _resolve_part_root(fid: str, features: dict) -> str | None:
    """Walk the parent chain upward until we hit a feature that owns a body.

    A "body owner" is either:
      - a root feature (parent is None)
      - an add/union feature (sub-assembly with its own build_ function)

    Subtractive feature parents (e.g. a pocket between a hole and its
    part) are skipped — their cuts are applied to the same body the
    feature-in-feature ultimately attaches to. Returns None if the chain
    is broken (e.g. dangling parent reference).
    """
    visited: set[str] = set()
    current = features.get(fid, {}).get("parent") if isinstance(features.get(fid), dict) else None
    while current is not None:
        if current in visited:
            return None  # cycle — defensive guard
        visited.add(current)
        parent_feat = features.get(current)
        if not isinstance(parent_feat, dict):
            return None
        op = parent_feat.get("operation", "add").lower()
        # Body owners: root (no parent) or any add/union feature
        if parent_feat.get("parent") is None or op in ("add", "union"):
            return current
        # Subtractive ancestor — keep walking up
        current = parent_feat.get("parent")
    return None


def _generate_sub_assembly_builds(
    build_order: list,
    features: dict,
    func_map: dict,
    sub_assemblies: list[dict],
) -> list[str]:
    """Generate build_XYZ() functions that chain sub-assembly operations.

    Handles both subtract-children (holes, slots applied to the part)
    and add-children (nested sub-assemblies translated+unioned onto the part).
    """
    lines = []
    sa_fids = {sa["fid"] for sa in sub_assemblies}
    sa_lookup = {sa["fid"]: sa for sa in sub_assemblies}

    for sa in sub_assemblies:
        sa_fid = sa["fid"]
        sa_prefix = sa_fid.upper().replace("-", "_").replace(" ", "_")
        sa_params = sa["params"]

        # Find ALL children of this sub-assembly part (in build_order sequence)
        subtract_children = []
        add_children = []
        for fid in build_order:
            if fid == sa_fid:
                continue
            feat = features.get(fid, {})
            op = feat.get("operation", "add").lower()
            # Direct add-children (nested sub-assemblies)
            if op in ("add", "union"):
                if feat.get("parent") == sa_fid:
                    add_children.append(fid)
                continue
            # Subtract/modify: include direct children AND descendants
            # whose effective body-owner walks back to this sub-assembly
            # (e.g. hole-in-pocket where pocket.parent == sa_fid).
            if op in ("subtract", "cut", "modify"):
                if feat.get("parent") == sa_fid:
                    subtract_children.append(fid)
                elif _resolve_part_root(fid, features) == sa_fid:
                    subtract_children.append(fid)

        if not subtract_children and not add_children:
            continue  # No build function needed — make_XYZ() suffices

        make_func = func_map.get(sa_fid, f"make_{sa_fid}")
        build_name = f"build_{sa_fid.replace('-', '_').replace(' ', '_')}"

        lines.append(f"def {build_name}() -> cq.Workplane:")
        lines.append(f"    result = {make_func}()")

        # _ref: unmodified body snapshot — used by subtract-children for
        # stable face-bounding-box centers (Cadquery's CenterOfBoundBox shifts
        # after subtractions, which causes drift on later operations).
        # See run 81505d2f for the bug pattern this prevents.
        if subtract_children:
            lines.append(f"    _ref = result")

        # 1) Apply subtract-children (holes, slots, modifiers)
        for child_fid in subtract_children:
            child_func = func_map.get(child_fid)
            if child_func:
                lines.append(f"    result = {child_func}(result, _ref)")

        # 2) Nested add-children (sub-assemblies on this part)
        for child_fid in add_children:
            child_feat = features.get(child_fid, {})
            child_params = child_feat.get("params", {})
            child_placement = child_feat.get("placement") or {}
            child_prefix = child_fid.upper().replace("-", "_").replace(" ", "_")
            clean_child = child_fid.replace("-", "_").replace(" ", "_")

            # Does this nested SA itself have children? → use build_ or make_
            nested_has_children = any(
                fid2 != child_fid
                and features.get(fid2, {}).get("parent") == child_fid
                for fid2 in build_order
            )
            if nested_has_children:
                child_build = f"build_{clean_child}"
            else:
                child_build = func_map.get(child_fid, f"make_{clean_child}")

            face = child_placement.get("face", ">Z")
            translate_code = _compute_translate(
                face, sa_prefix, sa_params, child_prefix, child_params
            )

            lines.append(f"    {clean_child} = {child_build}()")
            pre_rot = child_placement.get("pre_rotation")
            lines.extend(_emit_pre_rotation(clean_child, child_prefix, child_params, pre_rot))
            child_angle = float(child_placement.get("angle_deg", 0) or 0)
            if child_angle != 0.0:
                lines.extend(_emit_face_rotation(clean_child, child_prefix, child_params, face, child_angle))
            lines.append(f"    {clean_child} = {clean_child}.translate({translate_code})")
            lines.append(f"    result = result.union({clean_child}).clean()")

        lines.append(f"    return result")
        lines.append("")

    return lines


def _generate_assemble(
    root_id: str,
    build_order: list,
    features: dict,
    func_map: dict,
    sub_assemblies: list[dict],
) -> list[str]:
    """Generate the assemble() function."""
    lines = []
    root_func = func_map.get(root_id, f"make_{root_id}")
    root_params = features.get(root_id, {}).get("params", {})
    root_prefix = root_id.upper().replace("-", "_").replace(" ", "_")

    lines.append("def assemble() -> cq.Workplane:")
    lines.append(f"    result = {root_func}()")
    lines.append("")

    # Apply base subtracts (features directly on root, before any union)
    sa_fids = {sa["fid"] for sa in sub_assemblies}
    base_subtract_fids = []
    for fid in build_order:
        if fid == root_id or fid in sa_fids:
            continue
        feat = features.get(fid, {})
        op = feat.get("operation", "add").lower()
        if op not in ("subtract", "cut", "modify"):
            continue
        # Direct child of root, OR feature-in-feature whose effective
        # body-owner walks back to root (e.g. hole-in-pocket-on-root).
        if feat.get("parent") == root_id:
            base_subtract_fids.append(fid)
        elif _resolve_part_root(fid, features) == root_id:
            base_subtract_fids.append(fid)

    # _ref: unmodified body snapshot for stable face origins (see assembler.py:540 comment).
    if base_subtract_fids:
        lines.append(f"    _ref = result")
    for fid in base_subtract_fids:
        func = func_map.get(fid)
        if func:
            lines.append(f"    result = {func}(result, _ref)")

    # Sub-assemblies: build, translate, union
    # Process only root-level sub-assemblies here; nested ones are handled
    # inside their parent's build_ function
    for sa in sub_assemblies:
        sa_fid = sa["fid"]
        sa_parent = sa["parent"]

        # Skip nested sub-assemblies (their parent is not root)
        if sa_parent != root_id:
            continue

        placement = sa["placement"]
        sa_params = sa["params"]
        sa_prefix = sa_fid.upper().replace("-", "_").replace(" ", "_")

        # Check if this sa has any children (subtract OR add)
        has_children = any(
            fid != sa_fid
            and features.get(fid, {}).get("parent") == sa_fid
            for fid in build_order
        )
        if has_children:
            build_func = f"build_{sa_fid.replace('-', '_').replace(' ', '_')}"
        else:
            build_func = func_map.get(sa_fid, f"make_{sa_fid}")

        clean_fid = sa_fid.replace("-", "_").replace(" ", "_")
        lines.append(f"")
        lines.append(f"    # --- Sub-assembly: {sa_fid} ---")
        lines.append(f"    {clean_fid} = {build_func}()")

        pre_rot = placement.get("pre_rotation")
        lines.extend(_emit_pre_rotation(clean_fid, sa_prefix, sa_params, pre_rot))

        # Translate based on face — use PARENT dimensions, not always root
        face = placement.get("face", ">Z")
        sa_angle = float(placement.get("angle_deg", 0) or 0)
        if sa_angle != 0.0:
            lines.extend(_emit_face_rotation(clean_fid, sa_prefix, sa_params, face, sa_angle))
        translate_code = _compute_translate(
            face, root_prefix, root_params, sa_prefix, sa_params
        )
        lines.append(f"    {clean_fid} = {clean_fid}.translate({translate_code})")
        lines.append(f"    result = result.union({clean_fid}).clean()")

    lines.append("")
    lines.append("    return result")

    return lines


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
        ">Z": f"(0, 0, 0), (0, 0, 1)",
        "<Z": f"(0, 0, 0), (0, 0, 1)",
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

    if face == ">Z":
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
