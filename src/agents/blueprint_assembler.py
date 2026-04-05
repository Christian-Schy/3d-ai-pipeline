"""
src/agents/blueprint_assembler.py — Deterministic blueprint assembly from pre-assigned features.

Part of the "Häppchen" architecture:
  Feature Tagger → Feature Assigner → Feature Position Assigner →
  Part Position Assigner → **Blueprint Assembler**

This is a DETERMINISTIC component (no LLM). It takes:
  - feature_assignments (from Feature Assigner): parent, operation, params per feature
  - feature_position_assignments (from Feature Position Assigner): face, alignment for subtract/modify
  - part_position_assignments (from Part Position Assigner): face, alignment, distance_mm, gap_mm for add parts
  - position_assignments (legacy fallback): combined positions from old single Position Assigner

And computes:
  - Offsets (from alignment + parent/child dimensions)
  - Build order (topological sort of parent-child graph)
  - Orientation resolution ("20×80 Fläche liegt auf" → remap axes)
  - Face resolution from face_hints ("von der 80×40 Seite" → ">Y")
  - Distance/gap handling for floating parts
  - Final Feature Tree blueprint dict

No LLM needed — pure arithmetic and graph operations.
"""

import re
import structlog
from src.graph.state import PipelineState

log = structlog.get_logger()


class BlueprintAssembler:
    """Assembles a complete Feature Tree blueprint from pre-assigned features.

    Deterministic — no LLM calls. All computation is rule-based.
    """

    name = "blueprint_assembler"

    def __init__(self):
        self.log = structlog.get_logger().bind(agent=self.name)

    def assemble(self, state: PipelineState) -> dict:
        """Assemble a complete blueprint from feature and position assignments.

        Merges feature_position_assignments + part_position_assignments into
        a single position dict. Falls back to legacy position_assignments if
        the split dicts are empty.

        Returns dict with:
          blueprint: Feature Tree dict (same format as Planner output)
        """
        specification = state.get("specification") or state.get("description", "")
        feature_assignments = state.get("feature_assignments", {})

        # Merge split position dicts (new architecture) with fallback to legacy
        feature_positions = state.get("feature_position_assignments", {})
        part_positions = state.get("part_position_assignments", {})
        legacy_positions = state.get("position_assignments", {})

        # Merge: feature positions + part positions, legacy as fallback
        position_assignments = {}
        if feature_positions or part_positions:
            position_assignments.update(feature_positions)
            position_assignments.update(part_positions)
            self.log.info("blueprint_assembler_split_merge",
                          feature_positions=len(feature_positions),
                          part_positions=len(part_positions))
        elif legacy_positions:
            position_assignments = legacy_positions
            self.log.info("blueprint_assembler_legacy_positions",
                          positions=len(legacy_positions))

        if not feature_assignments:
            self.log.warning("blueprint_assembler_no_assignments")
            return {"blueprint": {}}

        if not position_assignments:
            self.log.warning("blueprint_assembler_no_positions",
                             hint="Position Assigners returned empty — using defaults")

        # Step 1: Build order (topological sort)
        build_order = self._topological_sort(feature_assignments)

        # Step 2: Resolve orientation hints
        for fid, data in feature_assignments.items():
            if not data.get("params") or data.get("parent") is None:
                continue
            pos = position_assignments.get(fid, {})
            hint = pos.get("orientation_hint") or ""
            if hint:
                # Explicit hint from PPA — apply directly
                data["params"] = self._resolve_orientation(
                    data["params"], hint, specification
                )
            elif data.get("operation") == "add":
                # No hint but this is an add-part: check if the spec mentions
                # orientation keywords near this feature's dimensions
                spec_ctx = self._find_orientation_context(
                    data["params"], specification
                )
                if spec_ctx:
                    data["params"] = self._resolve_orientation(
                        data["params"], spec_ctx, specification
                    )

        # Step 3: Resolve face_hints to concrete face selectors
        _face_resolved: set[str] = set()  # Track which features were resolved
        for fid, pos in position_assignments.items():
            face_hint = pos.get("face_hint")
            if face_hint:
                parent_id = feature_assignments.get(fid, {}).get("parent")
                parent_params = feature_assignments.get(parent_id, {}).get("params", {}) if parent_id else {}
                resolved_face = self._resolve_face_hint(
                    face_hint, feature_assignments.get(fid, {}).get("params", {}), parent_params
                )
                if resolved_face:
                    pos["face"] = resolved_face
                    _face_resolved.add(fid)

        # Step 3.5: Validate faces from specification (catches LLM mistakes)
        # Only skip features that Step 3 SUCCESSFULLY resolved
        self._validate_faces_from_spec(
            feature_assignments, position_assignments, specification,
            skip_fids=_face_resolved,
        )

        # Step 3.6: Validate directional keywords ("links", "rechts", etc.)
        self._validate_directional_faces(
            feature_assignments, position_assignments, specification,
            skip_fids=_face_resolved,
        )

        # Step 3.7: Deterministic offset computation from spec text
        # Catches "Xmm von rechter/linker/oberer/unterer Kante" patterns
        self._compute_offsets_from_spec(
            feature_assignments, position_assignments, specification,
        )

        # Step 3.8: Fix hole patterns on reoriented parts
        # Corner holes should be on the LARGE face, not the thin one
        self._fix_pattern_faces_on_reoriented(
            feature_assignments, position_assignments,
        )

        # Step 3.9: Validate add-parts without positional spec context
        # If the spec doesn't mention direction/alignment for a part → force centered
        self._validate_add_part_defaults(
            feature_assignments, position_assignments, specification,
        )

        # Step 3.10: Fix add-part alignment from spec "bündig" patterns
        # e.g. "rechts bündig" + "vorne bündig" → flush_right_bottom
        self._fix_add_part_alignment_from_spec(
            feature_assignments, position_assignments, specification,
        )

        # Step 3.11: Convert diagonal custom_shape_cut → slot
        # When the spec mentions "diagonal" and a custom_shape_cut has 2 vertices
        # (LLM approximation), convert to slot with computed angle/length.
        self._convert_diagonal_slots(
            feature_assignments, position_assignments, specification,
        )

        # Step 4: Compute offsets from alignment + dimensions
        features_dict = {}
        for fid in build_order:
            assign = feature_assignments.get(fid, {})
            pos = position_assignments.get(fid, {})
            parent_id = assign.get("parent")

            # Build placement info
            placement = None
            if parent_id is not None:
                parent_params = feature_assignments.get(parent_id, {}).get("params", {})
                child_params = assign.get("params", {})
                face = pos.get("face", ">Z")
                alignment = pos.get("alignment", "centered")

                # Compute offsets: alignment first, then override with explicit values
                align_ox, align_oy = self._compute_offsets(
                    alignment, parent_params, child_params, face
                )
                explicit_ox = pos.get("offset_x")
                explicit_oy = pos.get("offset_y")
                # Explicit offsets override alignment, but per-axis independently
                offset_x = float(explicit_ox) if explicit_ox is not None else align_ox
                offset_y = float(explicit_oy) if explicit_oy is not None else align_oy
                if explicit_ox is not None or explicit_oy is not None:
                    self.log.info("using_mixed_offsets",
                                  feature=fid,
                                  align_x=align_ox, align_y=align_oy,
                                  explicit_x=explicit_ox, explicit_y=explicit_oy,
                                  final_x=offset_x, final_y=offset_y)

                axis_hint = pos.get("axis_hint")
                notes_parts = []
                if axis_hint:
                    notes_parts.append(f"Nut entlang {axis_hint}")
                if pos.get("face_hint"):
                    notes_parts.append(pos["face_hint"])

                # Handle floating parts (distance_mm) and gaps (gap_mm)
                distance_mm = pos.get("distance_mm")
                gap_mm = pos.get("gap_mm")
                relative_to = pos.get("relative_to")

                if distance_mm is not None:
                    try:
                        distance_mm = float(distance_mm)
                        notes_parts.append(f"schwebend {distance_mm}mm")
                    except (ValueError, TypeError):
                        distance_mm = None

                if gap_mm is not None:
                    try:
                        gap_mm = float(gap_mm)
                        notes_parts.append(f"Abstand {gap_mm}mm")
                    except (ValueError, TypeError):
                        gap_mm = None

                # Handle rotation_deg (diagonal/angle positioning)
                rotation_deg = pos.get("rotation_deg")
                if rotation_deg is not None:
                    try:
                        rotation_deg = float(rotation_deg)
                        if rotation_deg != 0:
                            notes_parts.append(f"Rotation {rotation_deg}°")
                    except (ValueError, TypeError):
                        rotation_deg = None

                placement = {
                    "face": face,
                    "alignment": alignment,
                    "z_position": "on_top" if assign.get("operation") == "add" else "flush",
                    "position": "center" if alignment == "centered" else "offset",
                    "offset_x": offset_x,
                    "offset_y": offset_y,
                    "distance_mm": distance_mm,
                    "gap_mm": gap_mm,
                    "relative_to": relative_to,
                    "rotation_deg": rotation_deg,
                    "notes": ", ".join(notes_parts) if notes_parts else "",
                }

            # Build feature entry
            feature_entry = {
                "id": fid,
                "type": self._infer_type(assign),
                "params": assign.get("params", {}),
                "parent": parent_id,
                "origin": "global" if parent_id is None else "relative",
                "position": {"x": 0, "y": 0, "z": 0} if parent_id is None else None,
                "placement": placement,
                "operation": assign.get("operation", "add"),
                "notes": "",
            }
            features_dict[fid] = feature_entry

        blueprint = {
            "description": specification[:200],
            "build_order": build_order,
            "features": features_dict,
            "notes": "",
        }

        self.log.info("blueprint_assembler_done",
                      features=len(features_dict),
                      build_order=build_order)

        return {
            "blueprint": blueprint,
            "plan_valid": False,  # Force validation
        }

    # ------------------------------------------------------------------
    # Topological sort
    # ------------------------------------------------------------------

    def _topological_sort(self, assignments: dict) -> list[str]:
        """Sort features so parents come before children."""
        # Build adjacency: parent → [children]
        children_of: dict[str, list[str]] = {}
        for fid, data in assignments.items():
            parent = data.get("parent")
            if parent:
                children_of.setdefault(parent, []).append(fid)

        # Find root(s)
        roots = [fid for fid, data in assignments.items() if data.get("parent") is None]

        # BFS from roots
        order = []
        queue = list(roots)
        visited = set()
        while queue:
            fid = queue.pop(0)
            if fid in visited:
                continue
            visited.add(fid)
            order.append(fid)
            for child in children_of.get(fid, []):
                queue.append(child)

        # Add any orphans not reached by BFS
        for fid in assignments:
            if fid not in visited:
                order.append(fid)

        return order

    # ------------------------------------------------------------------
    # Offset computation
    # ------------------------------------------------------------------

    def _compute_offsets(
        self, alignment: str, parent_params: dict, child_params: dict, face: str
    ) -> tuple[float, float]:
        """Compute (offset_x, offset_y) from alignment + parent/child dimensions.

        On >Z face: offset_x maps to X-axis, offset_y maps to Y-axis
        On >X/<X face: offset_x maps to Y-axis, offset_y maps to Z-axis
        On >Y/<Y face: offset_x maps to X-axis, offset_y maps to Z-axis
        """
        if face in (">Z", "<Z"):
            pw = float(parent_params.get("x", 0))
            pl = float(parent_params.get("y", 0))
            fw = float(child_params.get("x", child_params.get("diameter", 0)))
            fl = float(child_params.get("y", child_params.get("diameter", 0)))
        elif face in (">X", "<X"):
            pw = float(parent_params.get("y", 0))
            pl = float(parent_params.get("z", 0))
            fw = float(child_params.get("y", child_params.get("diameter", 0)))
            fl = float(child_params.get("z", child_params.get("diameter", 0)))
        elif face in (">Y", "<Y"):
            pw = float(parent_params.get("x", 0))
            pl = float(parent_params.get("z", 0))
            fw = float(child_params.get("x", child_params.get("diameter", 0)))
            fl = float(child_params.get("z", child_params.get("diameter", 0)))
        else:
            pw, pl, fw, fl = 0, 0, 0, 0

        ox, oy = 0.0, 0.0

        if not alignment or alignment == "centered":
            return (0.0, 0.0)

        # Flush alignments
        if "right" in alignment and pw and fw:
            ox = pw / 2 - fw / 2
        elif "left" in alignment and pw and fw:
            ox = -(pw / 2 - fw / 2)

        if "top" in alignment and pl and fl:
            oy = pl / 2 - fl / 2
        elif "bottom" in alignment and pl and fl:
            oy = -(pl / 2 - fl / 2)

        return (round(ox, 4), round(oy, 4))

    # ------------------------------------------------------------------
    # Orientation context detection
    # ------------------------------------------------------------------

    def _find_orientation_context(self, params: dict, specification: str) -> str:
        """Find orientation keywords near a feature's dimensions in the spec.

        Returns the relevant orientation context string if found, else "".
        Used as a fallback when PPA didn't provide an orientation_hint.
        """
        spec_lower = specification.lower().replace("×", "x")
        # Look for the feature's dimensions in the spec
        px = params.get("x", 0)
        py = params.get("y", 0)
        pz = params.get("z", 0)
        dim_str = f"{px}x{py}x{pz}"

        idx = spec_lower.find(dim_str.lower())
        if idx < 0:
            # Try with spaces around x
            for combo in [f"{px} x {py} x {pz}", f"{px}x{py}x{pz}"]:
                idx = spec_lower.find(combo.lower())
                if idx >= 0:
                    break

        if idx < 0:
            return ""

        # Extend context to next 3D-dimension reference or 250 chars,
        # whichever comes first — enough to capture "die 20mm bündig an
        # der vorderen kante" even when it follows the dims by >80 chars.
        start = max(0, idx - 30)
        tail = spec_lower[idx + len(dim_str):]
        next_3d = re.search(r'\b\d+\s*x\s*\d+\s*x\s*\d+\b', tail)
        if next_3d:
            end = idx + len(dim_str) + next_3d.start()
        else:
            end = min(len(spec_lower), idx + len(dim_str) + 250)
        context = spec_lower[start:end]

        if re.search(r"aufrecht|stehend|hochkant|hoch\b|nach\s*oben|gehts?\s*nach\s*oben", context):
            return context

        # Pattern 4 trigger: "Nmm bündig [an der] {vorne/hinten/rechts/links}"
        if re.search(
            r"\d+(?:\.\d+)?\s*mm\s*bündig\s*(?:an\s*der\s*)?"
            r"(?:vorderen?|hinteren?|vorne?|hinten?|rechts?|links?|rechten?|linken?)",
            context,
        ):
            return context

        return ""

    # ------------------------------------------------------------------
    # Orientation resolution
    # ------------------------------------------------------------------

    def _resolve_orientation(self, params: dict, hint: str, specification: str) -> dict:
        """Resolve orientation hints into correct axis mapping.

        Handles multiple patterns:
        1. "AxB Fläche liegt auf" → contact face becomes X×Y, remaining = Z
        2. "N gehts nach oben" / "N nach oben" / "N hoch" → that dimension becomes Z
        3. "hochkant" / "stehend" → largest dimension becomes Z
        """
        text = f"{hint} {specification}".lower().replace("×", "x")
        px = float(params.get("x", 0))
        py = float(params.get("y", 0))
        pz = float(params.get("z", 0))

        if not all(d > 0 for d in (px, py, pz)):
            return params

        dims = [px, py, pz]

        # Pattern 1: "AxB Fläche liegt auf"
        m = re.search(
            r"(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)\s*(?:fläche|auflagefläche|seite)?\s*"
            r"(?:liegt\s*auf|aufliegt|kontakt|auflage)",
            text
        )
        if m:
            contact_d1 = float(m.group(1))
            contact_d2 = float(m.group(2))

            plate_dims = sorted(dims)
            contact_sorted = sorted([contact_d1, contact_d2])

            remaining = list(plate_dims)
            matched = []
            for cd in contact_sorted:
                best = min(remaining, key=lambda d: abs(d - cd))
                if abs(best - cd) < 1.0:
                    matched.append(best)
                    remaining.remove(best)

            if len(matched) == 2 and len(remaining) == 1:
                new_x = contact_d1
                new_y = contact_d2
                new_z = remaining[0]

                if abs(new_x - px) > 0.1 or abs(new_y - py) > 0.1 or abs(new_z - pz) > 0.1:
                    self.log.info("orientation_resolved",
                                  pattern="contact_face",
                                  original=f"{px}x{py}x{pz}",
                                  corrected=f"{new_x}x{new_y}x{new_z}")
                    return {**params, "x": new_x, "y": new_y, "z": new_z}
            return params

        # Pattern 2: "N gehts nach oben" / "N nach oben" / "N mm hoch" / "N hoch"
        m2 = re.search(
            r"(\d+(?:\.\d+)?)\s*(?:mm\s*)?(?:gehts?\s*nach\s*oben|nach\s*oben|hoch\b)",
            text
        )
        if m2:
            target_z = float(m2.group(1))
            # Find the matching dimension and make it Z
            best_idx = min(range(3), key=lambda i: abs(dims[i] - target_z))
            if abs(dims[best_idx] - target_z) < 1.0 and abs(dims[best_idx] - pz) > 0.1:
                remaining = [d for i, d in enumerate(dims) if i != best_idx]
                new_x = remaining[0]
                new_y = remaining[1]
                new_z = dims[best_idx]
                self.log.info("orientation_resolved",
                              pattern="dimension_nach_oben",
                              original=f"{px}x{py}x{pz}",
                              corrected=f"{new_x}x{new_y}x{new_z}")
                return {**params, "x": new_x, "y": new_y, "z": new_z}

        # Pattern 3: "hochkant" / "stehend" → largest dimension becomes Z
        if re.search(r"hochkant|stehend|aufrecht", text):
            max_dim = max(dims)
            if abs(max_dim - pz) > 0.1:  # Largest is not already Z
                # Remove ONE instance of max_dim to get the other two
                remaining = list(dims)
                remaining.remove(max_dim)
                remaining.sort(reverse=True)
                if len(remaining) >= 2:
                    new_x = remaining[0]
                    new_y = remaining[1]
                    new_z = max_dim
                    self.log.info("orientation_resolved",
                                  pattern="hochkant",
                                  original=f"{px}x{py}x{pz}",
                                  corrected=f"{new_x}x{new_y}x{new_z}")
                    return {**params, "x": new_x, "y": new_y, "z": new_z}

        # Pattern 4: "Nmm bündig [an der] {vorne|hinten}" → y=N (front-facing depth)
        #            "Mmm bündig [an der] {rechts|links}"  → x=M (right-facing width)
        #            remaining dimension → z (height)
        #  Example: "die 20mm bündig an der vorderen kante, die 50mm bündig rechts"
        #           → plate(50,50,20) becomes x=50, y=20, z=50 (upright)
        m4_front = re.search(
            r"(\d+(?:\.\d+)?)\s*mm\s*bündig\s*(?:an\s*der\s*)?"
            r"(?:vorderen?|hinteren?|vorne?|hinten?|front)\s*(?:kante|seite|rand|ecke)?",
            text,
        )
        m4_right = re.search(
            r"(\d+(?:\.\d+)?)\s*mm\s*bündig\s*(?:an\s*der\s*)?"
            r"(?:rechts?|rechten?|links?|linken?)\s*(?:kante|seite|rand|ecke)?",
            text,
        )
        if m4_front or m4_right:
            target_y = float(m4_front.group(1)) if m4_front else None
            target_x = float(m4_right.group(1)) if m4_right else None

            # Match each target to the closest available dimension
            remaining_dims = list(dims)
            new_y, new_x, new_z = py, px, pz  # defaults

            if target_y is not None:
                best = min(remaining_dims, key=lambda d: abs(d - target_y))
                if abs(best - target_y) < 1.0:
                    new_y = best
                    remaining_dims.remove(best)

            if target_x is not None:
                best = min(remaining_dims, key=lambda d: abs(d - target_x))
                if abs(best - target_x) < 1.0:
                    new_x = best
                    remaining_dims.remove(best)

            if remaining_dims:
                new_z = remaining_dims[0]
            else:
                # Fallback: all dims assigned, use current z
                pass

            if (abs(new_x - px) > 0.1 or abs(new_y - py) > 0.1 or abs(new_z - pz) > 0.1):
                self.log.info("orientation_resolved",
                              pattern="bundig_kante",
                              original=f"{px}x{py}x{pz}",
                              corrected=f"{new_x}x{new_y}x{new_z}")
                return {**params, "x": new_x, "y": new_y, "z": new_z}

        return params

    # ------------------------------------------------------------------
    # Face hint resolution
    # ------------------------------------------------------------------

    def _resolve_face_hint(
        self, face_hint: str, child_params: dict, parent_params: dict
    ) -> str | None:
        """Resolve 'von der 80×40 Seite' to a concrete CadQuery face selector.

        Matches the AxB dimensions to the parent's faces to determine
        which face the feature should be on.
        """
        text = face_hint.lower().replace("×", "x")

        m = re.search(r"(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)", text)
        if not m:
            return None

        d1 = float(m.group(1))
        d2 = float(m.group(2))
        dims = sorted([d1, d2])

        px = float(parent_params.get("x", 0))
        py = float(parent_params.get("y", 0))
        pz = float(parent_params.get("z", 0))

        # >Y/<Y face has dimensions (X, Z)
        if self._dims_match(dims, sorted([px, pz])):
            return ">Y"
        # >X/<X face has dimensions (Y, Z)
        if self._dims_match(dims, sorted([py, pz])):
            return ">X"
        # >Z/<Z face has dimensions (X, Y)
        if self._dims_match(dims, sorted([px, py])):
            return ">Z"

        return None

    # ------------------------------------------------------------------
    # Face validation from specification
    # ------------------------------------------------------------------

    def _validate_faces_from_spec(
        self,
        feature_assignments: dict,
        position_assignments: dict,
        specification: str,
        skip_fids: set[str] | None = None,
    ) -> None:
        """Validate face assignments for subtract features using the specification.

        When the specification mentions "von der AxB Seite" for a feature,
        deterministically resolves which face has dimensions AxB on the parent.
        Overrides the Position Assigner's face if it's wrong.

        This is a safety net: the Position Assigner (9b) sometimes assigns the
        wrong face despite having the formula in its prompt.
        """
        # Extract all "AxB Seite" dimension hints from the spec
        spec_lower = specification.lower().replace("×", "x")
        side_matches = list(re.finditer(
            r"(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)\s*(?:seite|fläche\b(?!.*liegt\s*auf))",
            spec_lower,
        ))
        if not side_matches:
            return

        # For each subtract feature with a parent, check if a spec AxB Seite
        # matches one of the parent's faces
        for fid, assign in feature_assignments.items():
            if assign.get("operation") != "subtract":
                continue
            parent_id = assign.get("parent")
            if not parent_id:
                continue

            pos = position_assignments.get(fid, {})
            if skip_fids and fid in skip_fids:
                continue  # Successfully resolved by Step 3

            parent_params = feature_assignments.get(parent_id, {}).get("params", {})
            if not parent_params:
                continue

            px = float(parent_params.get("x", 0))
            py = float(parent_params.get("y", 0))
            pz = float(parent_params.get("z", 0))
            if not all(d > 0 for d in (px, py, pz)):
                continue

            # Face dimension lookup for the parent
            face_dims = {
                ">X": sorted([py, pz]),
                ">Y": sorted([px, pz]),
                ">Z": sorted([px, py]),
            }

            for m in side_matches:
                d1, d2 = float(m.group(1)), float(m.group(2))
                dims = sorted([d1, d2])

                # Find which face matches these dimensions
                for face, fdims in face_dims.items():
                    if abs(dims[0] - fdims[0]) < 1.0 and abs(dims[1] - fdims[1]) < 1.0:
                        current_face = pos.get("face", ">Z")
                        if current_face != face:
                            self.log.info("face_corrected_from_spec",
                                          feature=fid, old=current_face, new=face,
                                          spec_dims=f"{d1}x{d2}")
                            pos["face"] = face
                        break

    # ------------------------------------------------------------------
    # Directional face validation
    # ------------------------------------------------------------------

    # Directional keyword → face mapping
    _DIRECTION_FACE_MAP = {
        "links": "<X", "linke": "<X", "linken": "<X", "linker": "<X",
        "rechts": ">X", "rechte": ">X", "rechten": ">X", "rechter": ">X",
        "vorne": "<Y", "vorn": "<Y", "front": "<Y", "vordere": "<Y", "vorderen": "<Y",
        "hinten": ">Y", "hintere": ">Y", "hinteren": ">Y", "rückseite": ">Y",
        "oben": ">Z", "obere": ">Z", "oberen": ">Z", "oberseite": ">Z",
        "unten": "<Z", "untere": "<Z", "unteren": "<Z", "unterseite": "<Z",
    }

    def _validate_directional_faces(
        self,
        feature_assignments: dict,
        position_assignments: dict,
        specification: str,
        skip_fids: set[str] | None = None,
    ) -> None:
        """Validate face assignments using directional keywords from the specification.

        Splits the specification into per-feature segments and looks for
        directional keywords like "links", "rechts", "vorne", "hinten" to
        determine which face each feature sits on.

        Only applies to subtract/modify features with a parent.
        """
        spec_lower = specification.lower()

        # Build a map: feature_id → position in spec (approximate, by feature characteristics)
        # Strategy: find each feature's mention in the spec by looking for its
        # type keywords (bohrung, nut, loch, etc.) or its ID
        feature_contexts = self._extract_feature_contexts(
            feature_assignments, spec_lower
        )

        for fid, assign in feature_assignments.items():
            if assign.get("operation") not in ("subtract", "cut"):
                continue
            parent_id = assign.get("parent")
            if not parent_id:
                continue
            if skip_fids and fid in skip_fids:
                continue

            pos = position_assignments.get(fid, {})
            context = feature_contexts.get(fid, "")
            if not context:
                continue

            # Find directional keywords in this feature's context
            detected_face = self._detect_face_from_context(context)
            if detected_face:
                current_face = pos.get("face", ">Z")
                if current_face != detected_face:
                    self.log.info("face_corrected_directional",
                                  feature=fid, old=current_face, new=detected_face,
                                  context=context[:60])
                    pos["face"] = detected_face

    def _extract_feature_contexts(
        self, feature_assignments: dict, spec_lower: str,
        truncate_after: bool = True,
    ) -> dict[str, str]:
        """Extract the specification context for each subtract feature.

        Segments the spec by feature-type keywords and matches segments to
        features using distinguishing params (diameter, dimensions, etc.).
        Handles multiple features with same params by matching in order.

        Args:
            truncate_after: If True, limit segment to 40 chars after keyword
                (for face detection, prevents leaking). If False, extend to
                next keyword (for offset extraction, needs full text).
        """
        # Feature-type keywords that indicate a new feature description
        _FEATURE_KEYWORDS = [
            "bohrung", "bohrloch", "loch",
            "nut", "groove", "kerbe", "rille",
            "tasche", "pocket",
            "fase", "chamfer",
            "verrundung", "fillet",
            "durchmesser",
        ]

        # Split spec into segments at feature keyword boundaries
        segments = []
        keyword_positions = []
        for kw in _FEATURE_KEYWORDS:
            for m in re.finditer(rf'\b{kw}\b', spec_lower):
                keyword_positions.append(m.start())
        # Also detect ∅ (U+2205) as a feature indicator
        for m in re.finditer(r'∅', spec_lower):
            keyword_positions.append(m.start())

        keyword_positions = sorted(set(keyword_positions))

        if not keyword_positions:
            return {}

        # Create segments: from the PREVIOUS keyword position to 40 chars
        # AFTER the current keyword. This captures all directional text between
        # features while preventing text from the NEXT feature leaking in.
        for i, pos in enumerate(keyword_positions):
            prev_kw = keyword_positions[i - 1] if i > 0 else 0
            start = prev_kw  # Start from previous keyword (or spec start)
            next_kw = keyword_positions[i + 1] if i + 1 < len(keyword_positions) else len(spec_lower)
            if truncate_after:
                end = min(pos + 40, next_kw)
            else:
                end = next_kw
            segments.append(spec_lower[start:end])

        # Collect subtract features to match
        subtract_features = [
            (fid, data) for fid, data in feature_assignments.items()
            if data.get("operation") in ("subtract", "cut") and data.get("parent")
        ]

        if not subtract_features:
            return {}

        # Match each segment to a feature using distinguishing params
        contexts: dict[str, str] = {}
        used_segments: set[int] = set()

        for fid, data in subtract_features:
            params = data.get("params", {})
            best_segment_idx = -1
            best_score = 0

            for si, seg in enumerate(segments):
                if si in used_segments:
                    continue
                score = 0

                # Score by matching params in segment text
                if "diameter" in params and params["diameter"]:
                    d = str(params["diameter"])
                    if d in seg:
                        score += 10
                if "width" in params and params["width"]:
                    w = str(params["width"])
                    if w in seg:
                        score += 5

                # Score by feature ID parts matching in segment (English)
                for part in fid.replace("_", " ").split():
                    if len(part) > 2 and part in seg:
                        score += 8

                # Score by German directional words matching feature ID direction
                # (e.g., "hole_left" → high score if "links" in segment)
                # Mask offset phrases first so "von der linken Kante" doesn't
                # falsely match when checking directional position words.
                _DIR_GERMAN = {
                    "left":   ["links", "linke", "linken", "linker"],
                    "right":  ["rechts", "rechte", "rechten", "rechter"],
                    "front":  ["vorne", "vorn", "front", "frontal"],
                    "back":   ["hinten", "hintere", "hinteren", "rückseite"],
                    "top":    ["oben", "obere", "oberkante"],
                    "bottom": ["unten", "untere", "unterkante"],
                    "center": ["mittig", "mitte", "zentral", "center"],
                }
                seg_masked = self._OFFSET_PATTERNS.sub(
                    lambda m: " " * len(m.group()), seg
                )
                fid_lower = fid.lower()
                for dir_en, dir_de_list in _DIR_GERMAN.items():
                    if dir_en in fid_lower:
                        for dir_de in dir_de_list:
                            if dir_de in seg_masked:
                                score += 12  # Strong signal — directional match
                                break

                # Score by feature type keywords in segment
                ftype_hints = {
                    "hole": ["bohrung", "bohrloch", "loch"],
                    "nut": ["nut", "groove", "kerbe", "rille"],
                    "slot": ["nut", "groove", "kerbe", "rille"],
                    "pocket": ["tasche", "pocket"],
                }
                for type_key, keywords in ftype_hints.items():
                    if type_key in fid.lower():
                        for kw in keywords:
                            if kw in seg:
                                score += 3
                                break

                # First-wins on tie: features appear in spec order, so
                # the earliest segment with the highest score is the best match.
                # Prefer-later tie-breaking causes false matches when later
                # segments have incidental directional words (e.g., "rechten Ecke"
                # in a path description matching "slot_right").
                if score > best_score:
                    best_score = score
                    best_segment_idx = si

            if best_segment_idx >= 0 and best_score > 0:
                contexts[fid] = segments[best_segment_idx]
                used_segments.add(best_segment_idx)

        return contexts

    # Phrases where directional words describe offsets, NOT face direction
    _OFFSET_PATTERNS = re.compile(
        r"(?:von\s+(?:der\s+)?(?:linken?|rechten?|oberen?|unteren?|vorderen?|hinteren?)\s+(?:kante|seite|rand))"
        r"|(?:(?:von\s+)?(?:oberkante|unterkante|vorderkante|hinterkante))"
        r"|(?:\d+\s*mm\s+von\s+(?:links|rechts|oben|unten|vorne?|hinten))"
        r"|(?:von\s+oben\s+\d+)"
        r"|(?:von\s+unten\s+\d+)"
        r"|(?:von\s+vorne?\s+\d+)"
        r"|(?:von\s+hinten\s+\d+)"
    )

    def _detect_face_from_context(self, context: str) -> str | None:
        """Detect the face from directional keywords in a context string.

        Ignores directional words that are part of offset descriptions
        (e.g., "von der linken Kante 10mm" describes an offset, not a face).

        Returns the face selector (">Z", "<X", etc.) or None.
        """
        # Mask out offset phrases so they don't match as face directions
        masked = self._OFFSET_PATTERNS.sub(lambda m: "_" * len(m.group()), context)

        best_face = None
        best_pos = len(masked)

        for keyword, face in self._DIRECTION_FACE_MAP.items():
            for m in re.finditer(rf'\b{keyword}\b', masked):
                if m.start() < best_pos:
                    best_pos = m.start()
                    best_face = face

        return best_face

    # ------------------------------------------------------------------
    # Deterministic offset computation from spec
    # ------------------------------------------------------------------

    # Pattern: "Xmm von [der] rechten/linken/oberen/unteren Kante/Rand"
    # Also: "von oben Xmm", "von Oberkante Xmm"
    _SPEC_OFFSET_PATTERN = re.compile(
        r"(?:(?:von\s+(?:der\s+)?(?P<dir1>rechten?|linken?|oberen?|unteren?|vorderen?|hinteren?)\s+"
        r"(?:kante|rand|seite)\s+(?P<val1>\d+(?:\.\d+)?)\s*(?:mm)?)"
        r"|(?:von\s+(?P<dir2>oben|unten|links|rechts|vorne?|hinten)\s+(?P<val2>\d+(?:\.\d+)?)\s*(?:mm)?)"
        r"|(?:(?P<dir3>oberkante|unterkante|vorderkante|hinterkante)\s+(?P<val3>\d+(?:\.\d+)?)\s*(?:mm)?)"
        r"|(?:(?P<val4>\d+(?:\.\d+)?)\s*(?:mm)?\s+von\s+(?:der\s+)?"
        r"(?P<dir4>rechten?|linken?|oberen?|unteren?|vorderen?|hinteren?|oberkante|unterkante|vorderkante|hinterkante)\s*(?:kante|rand|seite)?))"
    )

    def _compute_offsets_from_spec(
        self,
        feature_assignments: dict,
        position_assignments: dict,
        specification: str,
    ) -> None:
        """Deterministically compute offsets from specification text.

        Parses patterns like "10mm von rechter Kante" and computes the
        correct offset_x/offset_y values based on the feature's face
        and parent dimensions.
        """
        spec_lower = specification.lower()

        # Get per-feature contexts with FULL segments (not truncated)
        # Unlike face detection which needs truncated segments to avoid leaking,
        # offset patterns can appear anywhere in the feature's description
        feature_contexts = self._extract_feature_contexts(
            feature_assignments, spec_lower, truncate_after=False
        )

        for fid, assign in feature_assignments.items():
            if assign.get("operation") not in ("subtract", "cut"):
                continue
            parent_id = assign.get("parent")
            if not parent_id:
                continue

            pos = position_assignments.get(fid, {})
            context = feature_contexts.get(fid, "")
            if not context:
                continue

            face = pos.get("face", ">Z")
            parent_params = feature_assignments.get(parent_id, {}).get("params", {})
            if not parent_params:
                continue

            # Determine which parent dims map to offset_x / offset_y on this face
            dim_x, dim_y = self._face_dims_for_offsets(face, parent_params)
            if dim_x <= 0 and dim_y <= 0:
                continue

            # Find all offset patterns in the context
            computed_ox = None
            computed_oy = None

            for m in self._SPEC_OFFSET_PATTERN.finditer(context):
                direction = (m.group("dir1") or m.group("dir2")
                             or m.group("dir3") or m.group("dir4") or "")
                value_str = (m.group("val1") or m.group("val2")
                             or m.group("val3") or m.group("val4") or "")
                if not direction or not value_str:
                    continue
                value = float(value_str)
                direction = direction.lower()

                # Map direction to offset axis and sign
                if direction in ("rechte", "rechten", "rechter", "rechts"):
                    # Right edge → positive offset_x
                    computed_ox = dim_x / 2 - value
                elif direction in ("linke", "linken", "linker", "links"):
                    # Left edge → negative offset_x
                    computed_ox = -(dim_x / 2 - value)
                elif direction in ("obere", "oberen", "oberer", "oben",
                                   "oberkante"):
                    # Top/back edge → positive offset_y
                    computed_oy = dim_y / 2 - value
                elif direction in ("untere", "unteren", "unterer", "unten",
                                   "unterkante"):
                    # Bottom/front edge → negative offset_y
                    computed_oy = -(dim_y / 2 - value)
                elif direction in ("hintere", "hinteren", "hinterer", "hinten",
                                   "hinterkante"):
                    # Back edge (+Y direction) → positive offset_y
                    computed_oy = dim_y / 2 - value
                elif direction in ("vordere", "vorderen", "vorderer",
                                   "vorne", "vorn", "vorderkante"):
                    # Front edge (-Y direction) → negative offset_y
                    computed_oy = -(dim_y / 2 - value)

            # Apply computed offsets (override LLM values)
            if computed_ox is not None:
                old_ox = pos.get("offset_x")
                pos["offset_x"] = round(computed_ox, 2)
                if old_ox != pos["offset_x"]:
                    self.log.info("offset_x_corrected_from_spec",
                                  feature=fid, old=old_ox,
                                  new=pos["offset_x"])
            if computed_oy is not None:
                old_oy = pos.get("offset_y")
                pos["offset_y"] = round(computed_oy, 2)
                if old_oy != pos["offset_y"]:
                    self.log.info("offset_y_corrected_from_spec",
                                  feature=fid, old=old_oy,
                                  new=pos["offset_y"])

    @staticmethod
    def _face_dims_for_offsets(face: str, parent_params: dict) -> tuple[float, float]:
        """Return (dim_for_offset_x, dim_for_offset_y) based on the face.

        On >Z/<Z: offset_x = X-axis (parent.x), offset_y = Y-axis (parent.y)
        On >X/<X: offset_x = Y-axis (parent.y), offset_y = Z-axis (parent.z)
        On >Y/<Y: offset_x = X-axis (parent.x), offset_y = Z-axis (parent.z)
        """
        px = float(parent_params.get("x", 0))
        py = float(parent_params.get("y", 0))
        pz = float(parent_params.get("z", 0))

        if face in (">Z", "<Z"):
            return px, py
        elif face in (">X", "<X"):
            return py, pz
        elif face in (">Y", "<Y"):
            return px, pz
        return 0.0, 0.0

    # ------------------------------------------------------------------
    # Pattern face fix on reoriented parts
    # ------------------------------------------------------------------

    def _fix_pattern_faces_on_reoriented(
        self,
        feature_assignments: dict,
        position_assignments: dict,
    ) -> None:
        """Fix hole_pattern face assignments on reoriented parts.

        When a parent part has been reoriented (e.g., 180x180x20 → 180x20x180),
        hole_pattern_grid features should be on the LARGEST face, not the default >Z.
        A hole_pattern_grid with inset=20 on a face that's only 20mm wide doesn't work.
        """
        for fid, assign in feature_assignments.items():
            if assign.get("operation") != "subtract":
                continue
            params = assign.get("params", {})
            if "inset" not in params or "count" not in params:
                continue  # Only apply to hole_pattern_grid

            parent_id = assign.get("parent")
            if not parent_id:
                continue

            parent_params = feature_assignments.get(parent_id, {}).get("params", {})
            px = float(parent_params.get("x", 0))
            py = float(parent_params.get("y", 0))
            pz = float(parent_params.get("z", 0))
            if not all(d > 0 for d in (px, py, pz)):
                continue

            pos = position_assignments.get(fid, {})
            face = pos.get("face", ">Z")
            inset = float(params.get("inset", 0))

            # Check if the current face is too small for the pattern
            face_w, face_h = self._face_dims_for_offsets(face, parent_params)
            if face_w >= 2 * inset + 1 and face_h >= 2 * inset + 1:
                continue  # Current face is big enough

            # Find the largest face that fits the pattern
            face_options = [
                (">Z", px, py),
                (">X", py, pz),
                (">Y", px, pz),
            ]
            # Sort by area (largest first)
            face_options.sort(key=lambda f: f[1] * f[2], reverse=True)

            for new_face, fw, fh in face_options:
                if fw >= 2 * inset + 1 and fh >= 2 * inset + 1:
                    if new_face != face:
                        self.log.info("pattern_face_corrected_reoriented",
                                      feature=fid, old=face, new=new_face,
                                      face_dims=f"{fw}x{fh}",
                                      inset=inset)
                        pos["face"] = new_face
                    break

    # ------------------------------------------------------------------
    # Validate add-part defaults (no spec context → centered)
    # ------------------------------------------------------------------

    _ADD_PART_DIRECTION_WORDS = re.compile(
        r"(?:bündig|flush|rechts|links|hinten|vorne|front|rückseite"
        r"|ecke|versetzt|abstand|rand|kante"
        r"|aufrecht|stehend|hochkant|oben|unten)",
        re.IGNORECASE,
    )

    def _validate_add_part_defaults(
        self,
        feature_assignments: dict,
        position_assignments: dict,
        specification: str,
    ) -> None:
        """Reset add-parts to centered if spec has no positional keywords for them.

        LLMs sometimes hallucinate alignment/offsets when the spec only says
        "Teil auf das andere" without any positioning detail.

        SKIP if PPA returned orientation_hint or face_hint — those indicate
        the PPA made intentional positioning choices based on spec context.
        """
        spec_lower = specification.lower().replace("×", "x")

        for fid, assign in feature_assignments.items():
            if assign.get("operation") != "add" or assign.get("parent") is None:
                continue

            pos = position_assignments.get(fid)
            if not pos:
                continue

            # Already centered → nothing to do
            alignment = pos.get("alignment", "centered")
            if alignment == "centered" and not pos.get("offset_x") and not pos.get("offset_y"):
                continue

            # If PPA set face_hint, trust the PPA (dimensional, reliable)
            if pos.get("face_hint"):
                continue

            # If PPA set orientation_hint, verify it actually comes from the spec
            # LLMs sometimes hallucinate hints like "20×80 Fläche liegt auf"
            hint = pos.get("orientation_hint", "")
            if hint:
                hint_lower = hint.lower().replace("×", "x")
                # Extract key words from the hint and check if they appear in spec
                hint_words = [w for w in re.split(r"[\s,]+", hint_lower)
                              if len(w) > 3 and w not in ("null", "none")]
                # If 2+ hint words appear in spec, trust the PPA
                matches = sum(1 for w in hint_words if w in spec_lower)
                if matches >= 2 or (len(hint_words) <= 2 and matches >= 1):
                    continue

            # Find this feature's spec context using ALL dimension permutations
            # (orientation resolution may have swapped x/y/z)
            params = assign.get("params", {})
            px = params.get("x")
            py = params.get("y")
            pz = params.get("z")

            has_context = False
            if px and py and pz:
                # Try all permutations since orientation may have swapped dims
                dim_variants = set()
                dims = [float(px), float(py), float(pz)]
                for a in dims:
                    for b in dims:
                        for c in dims:
                            if sorted([a, b, c]) == sorted(dims):
                                dim_variants.add(f"{int(a)}x{int(b)}x{int(c)}")

                for dim_str in dim_variants:
                    idx = spec_lower.find(dim_str.lower())
                    if idx >= 0:
                        start = max(0, idx - 40)
                        end = min(len(spec_lower), idx + len(dim_str) + 80)
                        context = spec_lower[start:end]
                        if self._ADD_PART_DIRECTION_WORDS.search(context):
                            has_context = True
                            break

            # Also search by feature ID parts (German terms)
            if not has_context:
                for part in fid.replace("_", " ").split():
                    if len(part) > 2 and part not in ("base", "plate", "box", "part"):
                        idx = spec_lower.find(part)
                        if idx >= 0:
                            start = max(0, idx - 30)
                            end = min(len(spec_lower), idx + len(part) + 60)
                            context = spec_lower[start:end]
                            if self._ADD_PART_DIRECTION_WORDS.search(context):
                                has_context = True
                                break

            if not has_context:
                # No directional context → force centered
                old_align = pos.get("alignment")
                old_ox = pos.get("offset_x")
                old_oy = pos.get("offset_y")
                pos["alignment"] = "centered"
                pos["offset_x"] = None
                pos["offset_y"] = None
                self.log.info("add_part_forced_centered",
                              feature=fid, old_alignment=old_align,
                              old_offset_x=old_ox, old_offset_y=old_oy)

    # ------------------------------------------------------------------
    # Fix add-part alignment from spec "bündig" patterns
    # ------------------------------------------------------------------

    _FLUSH_DIRECTION_MAP = {
        "rechts": "right", "rechte": "right", "rechten": "right", "rechter": "right",
        "links": "left", "linke": "left", "linken": "left", "linker": "left",
        "vorne": "bottom", "vorn": "bottom", "front": "bottom",
        "vordere": "bottom", "vorderen": "bottom", "vorderer": "bottom",
        "hinten": "top", "hintere": "top", "hinteren": "top", "hinterer": "top",
    }

    def _fix_add_part_alignment_from_spec(
        self,
        feature_assignments: dict,
        position_assignments: dict,
        specification: str,
    ) -> None:
        """Deterministically fix alignment for add-parts based on 'bündig' patterns.

        Scans the spec context for each add-part and detects combined flush
        patterns like "rechts bündig, vorne bündig" → flush_right_bottom.
        """
        spec_lower = specification.lower().replace("×", "x")

        for fid, assign in feature_assignments.items():
            if assign.get("operation") != "add" or assign.get("parent") is None:
                continue

            pos = position_assignments.get(fid)
            if not pos:
                continue

            # Find this feature's context in the spec
            params = assign.get("params", {})
            px, py, pz = params.get("x"), params.get("y"), params.get("z")
            context = ""

            if px and py and pz:
                # Search all dim permutations
                dims = [float(px), float(py), float(pz)]
                from itertools import permutations
                for perm in permutations(dims):
                    dim_str = f"{int(perm[0])}x{int(perm[1])}x{int(perm[2])}"
                    idx = spec_lower.find(dim_str)
                    if idx >= 0:
                        start = max(0, idx - 20)
                        # Extend to the next 3D-dimension reference (NxNxN) so we
                        # capture alignment words even when "bündig" appears far
                        # after the dimension string (e.g. 241 chars later).
                        next_3d = re.search(
                            r'\b\d+\s*x\s*\d+\s*x\s*\d+\b',
                            spec_lower[idx + len(dim_str):]
                        )
                        if next_3d:
                            end = idx + len(dim_str) + next_3d.start()
                        else:
                            end = len(spec_lower)
                        context = spec_lower[start:end]
                        break

            if not context:
                continue

            # Scan for "bündig" near direction words
            flush_dirs: set[str] = set()
            # Pattern: "rechts ... bündig" or "bündig ... rechts" within 30 chars
            for word, direction in self._FLUSH_DIRECTION_MAP.items():
                # Check: "word ... bündig" or "bündig ... word"
                for pattern in [
                    rf"\b{word}\b.{{0,30}}bündig",
                    rf"bündig.{{0,30}}\b{word}\b",
                    rf"\b{word}\b.{{0,20}}flush",
                ]:
                    if re.search(pattern, context):
                        flush_dirs.add(direction)

            if not flush_dirs:
                continue

            # Combine directions into alignment label
            has_right = "right" in flush_dirs
            has_left = "left" in flush_dirs
            has_top = "top" in flush_dirs
            has_bottom = "bottom" in flush_dirs

            if has_right and has_top:
                new_align = "flush_right_top"
            elif has_right and has_bottom:
                new_align = "flush_right_bottom"
            elif has_left and has_top:
                new_align = "flush_left_top"
            elif has_left and has_bottom:
                new_align = "flush_left_bottom"
            elif has_right:
                new_align = "flush_right"
            elif has_left:
                new_align = "flush_left"
            elif has_top:
                new_align = "flush_top"
            elif has_bottom:
                new_align = "flush_bottom"
            else:
                continue

            old_align = pos.get("alignment", "centered")
            if old_align != new_align:
                self.log.info("add_part_alignment_fixed_from_spec",
                              feature=fid, old=old_align, new=new_align,
                              flush_dirs=list(flush_dirs))
                pos["alignment"] = new_align
                # Clear explicit offsets that conflict with the new alignment
                # (they were likely wrong if the alignment was wrong)
                if has_right or has_left:
                    pos["offset_x"] = None
                if has_top or has_bottom:
                    pos["offset_y"] = None

    # ------------------------------------------------------------------
    # Convert diagonal custom_shape_cut → slot
    # ------------------------------------------------------------------

    def _convert_diagonal_slots(
        self,
        feature_assignments: dict,
        position_assignments: dict,
        specification: str,
    ) -> None:
        """Convert diagonal custom_shape_cut features to slot type.

        When the LLM outputs a custom_shape_cut with 2 vertices for a diagonal
        nut (spec mentions "diagonal"), we convert it to a proper slot with:
          - length = full face diagonal (sqrt(fw² + fh²))
          - width from params (or spec "NxN")
          - depth from params
          - angle = 45 (or angle computed from vertices if available)
          - offset_x/y = 0 (centered, full-face diagonal)

        The face must already be resolved before this step.
        """
        import math
        spec_lower = specification.lower()

        for fid, assign in feature_assignments.items():
            params = assign.get("params", {})
            if "vertices" not in params:
                continue
            vertices = params.get("vertices") or []
            if len(vertices) != 2:
                continue
            if assign.get("operation") not in ("subtract", "cut"):
                continue

            # Check if spec context mentions "diagonal"
            if "diagonal" not in spec_lower:
                continue

            parent_id = assign.get("parent")
            if not parent_id:
                continue

            parent_params = feature_assignments.get(parent_id, {}).get("params", {})
            px = float(parent_params.get("x", 60))
            py = float(parent_params.get("y", 60))
            pz = float(parent_params.get("z", 60))

            face = (position_assignments.get(fid) or {}).get("face", ">Z")

            # Face dimensions in workplane coords
            if face in (">Z", "<Z"):
                fw, fh = px, py
            elif face in (">X", "<X"):
                fw, fh = py, pz
            else:  # >Y, <Y
                fw, fh = px, pz

            # Compute angle from vertices if they look plausible
            try:
                v0 = vertices[0]
                v1 = vertices[1]
                dx = float(v1[0]) - float(v0[0])
                dy = float(v1[1]) - float(v0[1])
                if abs(dx) > 1e-3 or abs(dy) > 1e-3:
                    angle = math.degrees(math.atan2(abs(dy), abs(dx)))
                    # Snap to nearest 45° increment
                    angle = round(angle / 45) * 45
                else:
                    angle = 45
            except (IndexError, TypeError, ValueError):
                angle = 45

            length = math.sqrt(fw ** 2 + fh ** 2)

            # Extract width from existing params or slot label
            width = float(params.get("width", params.get("depth", 6)))
            depth = float(params.get("depth", width))

            # Override feature params
            assign["params"] = {
                "width": width,
                "depth": depth,
                "length": round(length, 2),
                "angle": angle,
            }
            self.log.info("diagonal_slot_converted",
                          feature=fid, face=face,
                          length=round(length, 2), angle=angle,
                          width=width, depth=depth)

    @staticmethod
    def _dims_match(dims1: list, dims2: list) -> bool:
        """Check if two sorted dimension pairs match within tolerance."""
        if len(dims1) != 2 or len(dims2) != 2:
            return False
        return abs(dims1[0] - dims2[0]) < 1.0 and abs(dims1[1] - dims2[1]) < 1.0

    # ------------------------------------------------------------------
    # Type inference
    # ------------------------------------------------------------------

    @staticmethod
    def _infer_type(assign: dict) -> str:
        """Infer the feature type string for the blueprint."""
        params = assign.get("params", {})
        op = assign.get("operation", "add")

        # Hole patterns (bolt circle, corner holes, grid)
        if "count" in params and "hole_diameter" in params:
            if "inset" in params:
                return "hole_pattern_grid"  # corner holes
            return "hole_pattern_circular"  # bolt circle
        if "diameter" in params and op == "subtract":
            return "hole"
        if "width" in params and "depth" in params:
            return "slot"
        if "size" in params:
            return "chamfer" if op == "subtract" else "fillet"
        if "diameter" in params and "height" in params:
            return "cylinder"
        # Shape cutting/adding types
        if "vertices" in params:
            return "custom_shape_cut" if op == "subtract" else "custom_shape_add"
        if "arc_type" in params or "radius" in params and "depth" in params:
            return "arc_cut"
        if "base" in params and "height" in params and op == "subtract":
            return "triangle_cut"
        return "box"
