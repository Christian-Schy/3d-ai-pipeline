"""
src/graph/geometry_state.py — Extracts and stores geometry info after each successful build.

GeometryState gives the Planner/PromptAssembler accurate current-state info:
  - Bounding box (actual dimensions after all features are applied)
  - Volume (to detect unexpected material loss)
  - Face info (which faces exist at what Z heights — critical for stacked unions)

Why this is needed:
  The Planner only knows the blueprint dimensions, not the actual resulting geometry.
  For modifications ("add holes to the plate"), the Planner needs to know the CURRENT
  bounding box — especially for stacked unions where >Z[-2] vs >Z matters.
"""

from __future__ import annotations
import structlog
from pydantic import BaseModel, Field

log = structlog.get_logger()


class FaceInfo(BaseModel):
    """Info about one face of the solid, usable for face selector decisions."""
    selector: str        # e.g. ">Z", "<Z", ">X", etc.
    z_height: float      # Z coordinate of the face center (for Z-faces)
    area: float          # mm² — larger = more prominent face


class GeometryState(BaseModel):
    """Bounding box and face info extracted after each successful STL build."""

    # Bounding box
    bbox_min: tuple[float, float, float] = (0.0, 0.0, 0.0)
    bbox_max: tuple[float, float, float] = (0.0, 0.0, 0.0)

    # Total dimensions
    total_width: float = 0.0    # X
    total_depth: float = 0.0    # Y
    total_height: float = 0.0   # Z

    # Volume
    volume: float = 0.0

    # Top faces sorted by Z height (descending) — useful for face selector decisions
    # e.g. z_faces[0] = highest Z face (">Z"), z_faces[1] = second highest (">Z[-2]")
    z_faces: list[float] = Field(default_factory=list)

    def format_for_prompt(self) -> str:
        """Format geometry state as a concise string for inclusion in prompts."""
        lines = [
            "\n## Current Geometry (after previous build)",
            f"  Dimensions: {self.total_width:.1f} × {self.total_depth:.1f} × {self.total_height:.1f} mm (X×Y×Z)",
            f"  BBox: X[{self.bbox_min[0]:.1f}…{self.bbox_max[0]:.1f}]  "
            f"Y[{self.bbox_min[1]:.1f}…{self.bbox_max[1]:.1f}]  "
            f"Z[{self.bbox_min[2]:.1f}…{self.bbox_max[2]:.1f}]",
            f"  Volume: {self.volume:.1f} mm³",
        ]
        if len(self.z_faces) >= 2:
            lines.append(
                f"  Z faces: top ('>Z') at Z={self.z_faces[0]:.1f}, "
                f"second ('>Z[-2]') at Z={self.z_faces[1]:.1f}"
            )
            if len(self.z_faces) >= 2 and self.z_faces[0] != self.z_faces[1]:
                lines.append(
                    "  ⚠ Multiple Z-heights detected (stacked union) — use '>Z[-2]' for base plate features!"
                )
        return "\n".join(lines)


def extract_geometry_state(stl_path: str) -> GeometryState:
    """Extract GeometryState from an STL file using trimesh.

    Called from executor_node after a successful sandbox run.
    Returns an empty GeometryState on any error (non-critical path).
    """
    try:
        import trimesh
        mesh = trimesh.load(stl_path, force="mesh")

        bb = mesh.bounds  # [[xmin,ymin,zmin], [xmax,ymax,zmax]]
        bbox_min = tuple(float(v) for v in bb[0])
        bbox_max = tuple(float(v) for v in bb[1])

        width = float(bb[1][0] - bb[0][0])
        depth = float(bb[1][1] - bb[0][1])
        height = float(bb[1][2] - bb[0][2])
        volume = float(mesh.volume)

        # Extract unique Z positions of horizontal faces (normal ≈ [0,0,±1])
        # These are the potential workplane Z heights
        z_face_heights = set()
        for face_normal, face_center in zip(mesh.face_normals, mesh.triangles_center):
            if abs(face_normal[2]) > 0.99:  # nearly horizontal face
                z_face_heights.add(round(float(face_center[2]), 2))

        # Sort descending: [highest, second-highest, ...]
        z_faces = sorted(z_face_heights, reverse=True)[:4]  # keep top 4

        state = GeometryState(
            bbox_min=bbox_min,
            bbox_max=bbox_max,
            total_width=width,
            total_depth=depth,
            total_height=height,
            volume=volume,
            z_faces=z_faces,
        )
        log.info("geometry_state_extracted",
                 dims=f"{width:.1f}×{depth:.1f}×{height:.1f}",
                 volume=f"{volume:.0f}mm³",
                 z_faces=z_faces)
        return state

    except Exception as e:
        log.warning("geometry_state_extraction_failed", error=str(e))
        return GeometryState()
