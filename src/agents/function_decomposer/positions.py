"""Geometric helpers — offsets, face centers, NTP-eligibility.

Pure functions over a FeatureTree. No code emission.
"""

from src.graph.feature_tree import FeatureTree


def compute_alignment_offsets(
    alignment: str,
    pw: float,
    pl: float,
    fw: float,
    fl: float,
    explicit_ox: float | None = None,
    explicit_oy: float | None = None,
) -> tuple[float, float]:
    """Compute (offset_x, offset_y) from alignment + parent/feature dims."""
    ox = float(explicit_ox) if explicit_ox is not None else 0.0
    oy = float(explicit_oy) if explicit_oy is not None else 0.0

    if explicit_ox is None and alignment:
        if "right" in alignment and pw and fw:
            ox = pw / 2 - fw / 2
        elif "left" in alignment and pw and fw:
            ox = -(pw / 2 - fw / 2)
    if explicit_oy is None and alignment:
        if "top" in alignment and pl and fl:
            oy = pl / 2 - fl / 2
        elif "bottom" in alignment and pl and fl:
            oy = -(pl / 2 - fl / 2)
    return (ox, oy)


def _place_on_face(
    face: str,
    parent_center: tuple[float, float, float],
    parent_half: tuple[float, float, float],
    ox: float,
    oy: float,
    fw: float,
    fl: float,
    fh: float,
) -> dict:
    """Project a feature onto the given parent face. Returns center + half-extents."""
    pcx, pcy, pcz = parent_center
    phx, phy, phz = parent_half

    if face == ">Z":
        return {"center": (pcx + ox, pcy + oy, pcz + phz + fh / 2),
                "half": (fw / 2, fl / 2, fh / 2)}
    if face == "<Z":
        return {"center": (pcx + ox, pcy + oy, pcz - phz - fh / 2),
                "half": (fw / 2, fl / 2, fh / 2)}
    if face == ">X":
        return {"center": (pcx + phx + fh / 2, pcy + ox, pcz + oy),
                "half": (fh / 2, fw / 2, fl / 2)}
    if face == "<X":
        return {"center": (pcx - phx - fh / 2, pcy + ox, pcz + oy),
                "half": (fh / 2, fw / 2, fl / 2)}
    if face == ">Y":
        return {"center": (pcx + ox, pcy + phy + fh / 2, pcz + oy),
                "half": (fw / 2, fh / 2, fl / 2)}
    if face == "<Y":
        return {"center": (pcx + ox, pcy - phy - fh / 2, pcz + oy),
                "half": (fw / 2, fh / 2, fl / 2)}
    return {"center": (pcx, pcy, pcz), "half": (fw / 2, fl / 2, fh / 2)}


def compute_feature_positions(ft: FeatureTree) -> dict[str, dict]:
    """Compute absolute center and half-extents of all additive features.

    Used to generate NearestToPointSelector constants for features after union.
    Only computes for root + add features (subtract features don't change shape).

    Returns: {feature_id: {"center": (cx,cy,cz), "half": (hx,hy,hz)}}
    """
    pos: dict[str, dict] = {}

    for fid in ft.build_order:
        feature = ft.features.get(fid)
        if not feature:
            continue
        params = feature.params or {}

        if feature.parent is None:
            w = float(params.get("x") or params.get("diameter") or 0)
            l = float(params.get("y") or params.get("diameter") or 0)
            h = float(params.get("z") or params.get("height") or 0)
            pos[fid] = {"center": (0.0, 0.0, h / 2),
                        "half": (w / 2, l / 2, h / 2)}
            continue

        if feature.operation != "add":
            continue

        parent_pos = pos.get(feature.parent)
        if not parent_pos or not feature.placement:
            continue

        fw = float(params.get("x") or 0)
        fl = float(params.get("y") or 0)
        fh = float(params.get("z") or params.get("height") or 0)

        parent_feat = ft.features.get(feature.parent)
        pp = (parent_feat.params or {}) if parent_feat else {}
        pw = float(pp.get("x") or 0)
        py_dim = float(pp.get("y") or 0)

        ox, oy = compute_alignment_offsets(
            feature.placement.alignment or "", pw, py_dim, fw, fl,
            feature.placement.offset_x, feature.placement.offset_y,
        )

        pos[fid] = _place_on_face(
            feature.placement.face or ">Z",
            parent_pos["center"], parent_pos["half"],
            ox, oy, fw, fl, fh,
        )

    return pos


def face_center_point(parent_pos: dict, face: str) -> tuple[float, float, float] | None:
    """Compute the center point of a specific face on the parent feature."""
    if not parent_pos:
        return None
    cx, cy, cz = parent_pos["center"]
    hx, hy, hz = parent_pos["half"]
    return {
        ">Z": (cx, cy, cz + hz),
        "<Z": (cx, cy, cz - hz),
        ">X": (cx + hx, cy, cz),
        "<X": (cx - hx, cy, cz),
        ">Y": (cx, cy + hy, cz),
        "<Y": (cx, cy - hy, cz),
    }.get(face)


def features_needing_ntp(ft: FeatureTree) -> set[str]:
    """Return feature IDs that need NearestToPointSelector (after first union)."""
    first_union_idx = None
    for i, fid in enumerate(ft.build_order):
        f = ft.features.get(fid)
        if f and f.parent is not None and f.operation == "add":
            first_union_idx = i
            break
    if first_union_idx is None:
        return set()
    return {fid for i, fid in enumerate(ft.build_order) if i > first_union_idx}


def z_param_name(params: dict) -> str:
    """Return the parameter name used for height (Z or HEIGHT)."""
    return "Z" if "z" in params else "HEIGHT"
