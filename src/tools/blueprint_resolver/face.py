"""Step 2 — Face Calculation.

Convert a `side` keyword ("oben"/"rechts"/...) into a CadQuery face selector
(">Z"/">X"/...) and remap when the parent was reoriented.

Convention: "oben" always means the original X×Y face of the part (as the
user described it). After orientation swap, this face moves:
  - x_z swap: original >Z face becomes >X face (and <Z becomes <X)
  - y_z swap: original >Z face becomes >Y face (and <Z becomes <Y)
"""

from __future__ import annotations

# Side keyword → CadQuery face selector
_SIDE_TO_FACE: dict[str, str] = {
    "oben":    ">Z",
    "top":     ">Z",
    "drauf":   ">Z",
    "unten":   "<Z",
    "bottom":  "<Z",
    "rechts":  ">X",
    "right":   ">X",
    "links":   "<X",
    "left":    "<X",
    "vorne":   "<Y",
    "front":   "<Y",
    "hinten":  ">Y",
    "back":    ">Y",
    "zentriert": ">Z",  # default face for centered
    "centered":  ">Z",
}


def _resolve_face(side: str, parent_swap: str = "none") -> str:
    """Convert a side keyword to a CadQuery face selector.

    When a parent was reoriented (orientation.py), we remap the child's
    "oben"/"unten" to point at the face where the original X×Y surface
    ended up.
    """
    side_lower = side.lower().strip()
    face = _SIDE_TO_FACE.get(side_lower, ">Z")

    if parent_swap == "none" or parent_swap == "full":
        return face

    # x_z swap: X↔Z → original top (>Z) is now right (>X), original bottom (<Z) is now left (<X)
    # y_z swap: Y↔Z → original top (>Z) is now back (>Y), original bottom (<Z) is now front (<Y)
    if parent_swap == "x_z":
        remap = {
            ">Z": ">X",
            "<Z": "<X",
            ">X": ">Z",
            "<X": "<Z",
        }
    elif parent_swap == "y_z":
        remap = {
            ">Z": ">Y",
            "<Z": "<Y",
            ">Y": ">Z",
            "<Y": "<Z",
        }
    else:
        return face

    return remap.get(face, face)
