"""Step 1 — Orientation Resolution.

Resolve "hochkant"/"flach"/"AxB_liegt_auf"/"N_hoch" keywords into concrete
params with swapped dimensions. Returns (resolved_params, swap_type) where
swap_type ∈ {"none", "x_z", "y_z", "full"} — face.py uses it to remap
"oben"/"unten" after a part has been reoriented.
"""

from __future__ import annotations

import re


def _resolve_orientation(params: dict, orientation: str, feat_type: str,
                         side: str = "") -> tuple[dict, str]:
    """Resolve orientation keyword into concrete params with swapped dimensions.

    For box-like types (x, y, z):
      "hochkant"/"aufrecht"/"stehend" → largest dim becomes Z
      "flach"/"liegend" → smallest dim becomes Z
      "AxB_liegt_auf" → dimensions rearranged so AxB is the contact face
                        (depends on side: oben→XY, rechts→YZ, hinten→XZ)
      "N_hoch" → dim closest to N becomes Z

    For cylinder types (diameter, height): orientation can flip axis
      "liegend" → cylinder on its side (swap diameter↔height conceptually)

    Args:
      side: placement side (oben/unten/rechts/links/vorne/hinten).
            Only used for AxB_liegt_auf to determine which dims form the contact face.

    Returns:
      (resolved_params, swap_type)

      swap_type indicates which axis was swapped with Z:
        "none"  — no swap (standard orientation)
        "x_z"   — X and Z were swapped
        "y_z"   — Y and Z were swapped
        "full"  — full reorder (AxB_liegt_auf, N_hoch)
    """
    resolved = dict(params)  # shallow copy
    orientation = orientation.lower().strip()

    if orientation in ("standard", "", "normal"):
        return resolved, "none"

    # Box-like: has x, y, z
    if all(k in resolved for k in ("x", "y", "z")):
        x, y, z = float(resolved["x"]), float(resolved["y"]), float(resolved["z"])
        dims = [x, y, z]

        if orientation in ("hochkant", "aufrecht", "stehend", "vertikal"):
            # Largest dimension becomes Z (height)
            max_dim = max(dims)
            if z != max_dim:
                if x == max_dim:
                    resolved["x"], resolved["z"] = z, x
                    return resolved, "x_z"
                elif y == max_dim:
                    resolved["y"], resolved["z"] = z, y
                    return resolved, "y_z"
            return resolved, "none"

        elif orientation in ("flach", "liegend", "horizontal"):
            # Smallest dimension becomes Z (height)
            min_dim = min(dims)
            if z != min_dim:
                if x == min_dim:
                    resolved["x"], resolved["z"] = z, x
                    return resolved, "x_z"
                elif y == min_dim:
                    resolved["y"], resolved["z"] = z, y
                    return resolved, "y_z"
            return resolved, "none"

        elif "_liegt_auf" in orientation:
            # "AxB_liegt_auf" → A and B become the contact face dimensions,
            # remaining dimension = depth (perpendicular to contact face).
            match = re.match(r"(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)_liegt_auf", orientation)
            if match:
                target_a = float(match.group(1))
                target_b = float(match.group(2))
                remaining = list(dims)
                dim_a = _pop_closest(remaining, target_a)
                dim_b = _pop_closest(remaining, target_b)
                dim_depth = remaining[0] if remaining else x

                side_lower = (side or "").lower()
                if side_lower in ("oben", "unten"):
                    resolved["x"], resolved["y"], resolved["z"] = dim_a, dim_b, dim_depth
                elif side_lower in ("vorne", "hinten"):
                    resolved["x"], resolved["y"], resolved["z"] = dim_a, dim_depth, dim_b
                else:
                    resolved["x"], resolved["y"], resolved["z"] = dim_depth, dim_a, dim_b
                return resolved, "full"

        elif "_hoch" in orientation:
            # "80_hoch" → dimension closest to 80 becomes Z
            match = re.match(r"(\d+(?:\.\d+)?)_hoch", orientation)
            if match:
                target = float(match.group(1))
                remaining = list(dims)
                new_z = _pop_closest(remaining, target)
                resolved["x"], resolved["y"] = remaining[0], remaining[1]
                resolved["z"] = new_z
                return resolved, "full"

    # Cylinder: has diameter + height
    elif "diameter" in resolved and "height" in resolved:
        if orientation in ("liegend", "horizontal", "flach"):
            resolved["_orientation_hint"] = "horizontal"
        elif orientation in ("hochkant", "aufrecht", "stehend", "vertikal"):
            resolved["_orientation_hint"] = "vertical"  # default anyway

    return resolved, "none"


def _pop_closest(dims: list[float], target: float) -> float:
    """Remove and return the dimension closest to target from dims list."""
    if not dims:
        return target
    best_idx = min(range(len(dims)), key=lambda i: abs(dims[i] - target))
    return dims.pop(best_idx)
