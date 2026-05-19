"""Coordinate Validator — geometry helpers.

Pure functions that derive bounding boxes and face-local extents from a
feature dict. No issue reporting — leaf module shared by every check.
"""

from __future__ import annotations


def _get_bbox(feature: dict) -> tuple[float, float, float] | None:
    """Returns (x, y, z) dimensions of a feature, or None if not determinable."""
    params = feature.get("params", {})

    # Explicit box dimensions (all three must be non-None numbers)
    if all(params.get(k) is not None for k in ("x", "y", "z")):
        try:
            return (float(params["x"]), float(params["y"]), float(params["z"]))
        except (TypeError, ValueError):
            pass

    # Cylinder / hole → approximate as bounding box
    if params.get("diameter") is not None and "depth" in params:
        try:
            d = float(params["diameter"])
            depth = params.get("depth")
            z = float(depth) if depth is not None else None
            if d > 0 and z:
                return (d, d, z)
        except (TypeError, ValueError):
            pass

    # hole_pattern_circular → use circle_diameter as bounding
    if params.get("circle_diameter") is not None and params.get("diameter") is not None:
        try:
            cd = float(params["circle_diameter"])
            depth_val = params.get("depth", 1) or 1
            return (cd * 2, cd * 2, float(depth_val))
        except (TypeError, ValueError):
            pass

    return None


def _face_half_dims(
    parent_bbox: tuple[float, float, float], face: str
) -> tuple[float, float]:
    """Half-extents of the parent face a feature sits on, in face-local
    (width, height) order.

      >Z / <Z → (x/2, y/2)
      >X / <X → (y/2, z/2)
      >Y / <Y → (x/2, z/2)

    An unknown face falls back to the >Z mapping.
    """
    px, py, pz = parent_bbox
    if face in (">Z", "<Z"):
        return px / 2, py / 2
    if face in (">X", "<X"):
        return py / 2, pz / 2
    if face in (">Y", "<Y"):
        return px / 2, pz / 2
    return px / 2, py / 2
