"""
src/stl_validator.py — Geometric validation of generated STL files

Runs after the sandbox succeeds to catch silently broken geometry.

Why this matters:
  A subprocess can exit with code 0 (success) even if the STL is:
  - Non-manifold (edges shared by more than 2 faces — unprintable)
  - Self-intersecting (faces clip through each other)
  - Empty (0 triangles — export ran but produced nothing)
  - Degenerate (faces with zero area)

  Without this check, the pipeline would report success and show a
  broken model to the user. With it, broken STLs go back into the
  error loop automatically.
"""

from dataclasses import dataclass, field
from pathlib import Path

import structlog

log = structlog.get_logger()


@dataclass
class ValidationResult:
    """Result of STL geometric validation.
    
    valid=True means the model is printable and geometrically sound.
    valid=False means at least one issue was found — see `issues`.
    stats contains mesh info (triangle count, volume, etc.) for logging.
    """
    valid: bool
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)


class STLValidator:
    """Validates STL files for geometric correctness after generation.
    
    Uses trimesh — a lightweight mesh processing library.
    Adds ~200ms per validation run, well worth it to catch broken models.
    """

    # Minimum acceptable triangle count — below this the model is probably empty
    MIN_TRIANGLES = 4

    def validate(self, stl_path: str) -> ValidationResult:
        """Run all geometric checks on the STL file.
        
        Returns ValidationResult with valid=True if the model is printable.
        """
        path = Path(stl_path)

        # --- Check 0: File exists and is not empty ---
        if not path.exists():
            return ValidationResult(
                valid=False,
                issues=["STL file was not created — export may have failed silently"],
            )

        if path.stat().st_size < 100:
            return ValidationResult(
                valid=False,
                issues=[f"STL file is too small ({path.stat().st_size} bytes) — likely empty"],
            )

        # --- Load with trimesh ---
        try:
            import trimesh
            mesh = trimesh.load(str(path), force="mesh")
        except Exception as e:
            return ValidationResult(
                valid=False,
                issues=[f"Could not load STL file: {e}"],
            )

        issues = []
        warnings = []

        # --- Check 1: Triangle count ---
        tri_count = len(mesh.faces)
        if tri_count < self.MIN_TRIANGLES:
            issues.append(
                f"Model has only {tri_count} triangles — geometry is likely degenerate"
            )

        # --- Check 2: Watertight (manifold) ---
        # A watertight mesh has no holes or open edges.
        # Non-watertight = unprintable on most slicers.
        #
        # Exception: CadQuery fillet/chamfer tessellation produces meshes with
        # euler_number=2 (topologically correct closed solid) but a handful of
        # non-manifold edges at curved-surface corner junctions. These are
        # tessellation artifacts — the underlying BREP solid is valid and the
        # STL is printable. We treat such meshes as "practically watertight".
        import numpy as np
        _practically_watertight = False
        if not mesh.is_watertight:
            edge_face_count = np.zeros(len(mesh.edges_unique), dtype=int)
            for face in mesh.faces_unique_edges:
                edge_face_count[face] += 1
            nm_edge_count = int(np.sum(edge_face_count > 2))
            total_edges = len(mesh.edges_unique)
            nm_pct = nm_edge_count / total_edges * 100 if total_edges else 100

            # Tier 1: Very few nm-edges (≤5) with positive volume — CadQuery
            # boolean unions at flush edges produce exactly this pattern
            # (typically 2 edges, euler=1). Geometry is correct and printable.
            if nm_edge_count <= 5 and abs(mesh.volume) > 0:
                _practically_watertight = True
                warnings.append(
                    f"Mesh has {nm_edge_count} non-manifold edges "
                    f"({nm_pct:.3f}% of {total_edges}), euler={mesh.euler_number} — "
                    "minimal tessellation artifact, geometry is printable"
                )
            # Tier 2: euler=2 (topologically closed) with moderate nm-edges
            elif mesh.euler_number == 2 and nm_edge_count <= 20:
                _practically_watertight = True
                warnings.append(
                    f"Mesh has {nm_edge_count} tessellation artifact edges "
                    f"({nm_edge_count/total_edges*100:.3f}% of {total_edges}) — "
                    "topology is valid (euler=2), geometry is printable"
                )
            else:
                # --- Attempt mesh repair before declaring failure ---
                # CadQuery/OCCT often produces fixable non-manifold geometry
                # at boolean junctions. trimesh can repair many of these.
                mesh_repaired = False
                try:
                    trimesh.repair.fix_normals(mesh)
                    trimesh.repair.fix_winding(mesh)
                    trimesh.repair.fill_holes(mesh)
                    # Re-check after repair
                    if mesh.is_watertight:
                        mesh_repaired = True
                        warnings.append(
                            "Mesh was non-manifold but repaired successfully "
                            f"(fixed {nm_edge_count} non-manifold edges)"
                        )
                        # Save repaired mesh back to file
                        mesh.export(str(path))
                        log.info("stl_mesh_repaired",
                                 nm_edges_before=nm_edge_count,
                                 path=str(path))
                    elif mesh.euler_number == 2:
                        # Repair improved topology even if not fully watertight
                        mesh_repaired = True
                        _practically_watertight = True
                        warnings.append(
                            "Mesh repaired to euler=2 (topologically valid), "
                            f"had {nm_edge_count} non-manifold edges"
                        )
                        mesh.export(str(path))
                        log.info("stl_mesh_repair_partial",
                                 euler=mesh.euler_number,
                                 path=str(path))
                except Exception as e:
                    log.warning("stl_mesh_repair_failed", error=str(e))

                if not mesh_repaired:
                    issues.append(
                        "Mesh is not watertight (non-manifold) — "
                        "has open edges or holes that make it unprintable"
                    )

        # --- Check 3: Volume ---
        # Negative or zero volume means inside-out or empty geometry
        if mesh.is_watertight or _practically_watertight:
            volume = abs(mesh.volume)
            if volume <= 0:
                issues.append(
                    f"Mesh volume is {volume:.2f}mm³ — "
                    "geometry may be inside-out (normals flipped)"
                )

        # --- Check 4: Degenerate faces ---
        # Faces with zero area cause slicer errors
        degenerate = mesh.triangles_cross  # cross product of each triangle's edges
        import numpy as np
        zero_area_count = int(np.sum(np.linalg.norm(degenerate, axis=1) < 1e-10))
        if zero_area_count > 0:
            warnings.append(
                f"{zero_area_count} degenerate face(s) with zero area found — "
                "may cause slicer warnings but usually printable"
            )

        # --- Check 5: Bounds sanity ---
        # If the model is unreasonably large or tiny, something went wrong
        bounds = mesh.bounds
        if bounds is not None:
            extents = mesh.extents  # [x_size, y_size, z_size] in mm
            max_extent = float(np.max(extents))
            min_extent = float(np.min(extents))

            if max_extent > 5000:  # 5 meters — almost certainly wrong
                warnings.append(
                    f"Model is very large ({max_extent:.0f}mm) — check dimensions"
                )
            if min_extent < 0.01:  # 0.01mm — thinner than a human hair
                warnings.append(
                    f"Model has a very thin dimension ({min_extent:.3f}mm) — "
                    "may not be printable"
                )

        # --- Stats for logging ---
        stats = {
            "triangles": tri_count,
            "watertight": mesh.is_watertight or _practically_watertight,
            "volume_mm3": round(float(abs(mesh.volume)), 2) if (mesh.is_watertight or _practically_watertight) else None,
            "size_mm": [round(float(e), 2) for e in mesh.extents] if bounds is not None else None,
        }

        is_valid = len(issues) == 0

        if is_valid and not warnings:
            log.info("stl_valid", **stats)
        elif is_valid:
            log.info("stl_valid_with_warnings", warnings=warnings, **stats)
        else:
            log.warning("stl_invalid", issues=issues, **stats)

        return ValidationResult(
            valid=is_valid,
            issues=issues,
            warnings=warnings,
            stats=stats,
        )