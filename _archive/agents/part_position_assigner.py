"""
src/agents/part_position_assigner.py — Assigns face, alignment, and distance to add-operation parts.

Part of the "Häppchen" architecture:
  Feature Tagger → Feature Assigner → Feature Position Assigner →
  **Part Position Assigner** → Blueprint Assembler

The Part Position Assigner handles ONLY add-operation features with a parent:
  - Plates, boxes, extrusions positioned on/near other parts
  - Floating parts (e.g., "10mm above the base")
  - Parts with defined gaps between them

For each qualifying part it determines:
  1. face — which face of the parent does it sit on? (">Z", ">X", etc.)
  2. alignment — how is it aligned on that face? ("centered", "flush_right", etc.)
  3. orientation_hint — pass-through orientation info ("20×80 Fläche liegt auf")
  4. face_hint — pass-through face descriptions ("von der 80×40 Seite")
  5. distance_mm — float if part hovers above parent (e.g., 10.0 for 10mm gap)
  6. gap_mm — float for horizontal gap between adjacent parts
  7. relative_to — which feature is the reference (default: parent)

It does NOT handle subtract features (holes, slots) — Feature Position Assigner does that.
It does NOT calculate final offsets — that's the Blueprint Assembler's job.

Model: qwen3.5:9b — focused task, spatial language understanding only.
"""

import re
import structlog
from src.agents.base import BaseAgent
from src.config.loader import get_config
from src.graph.state import PipelineState
from src.utils.prompt_loader import load_prompt
from src.rag.part_position_rag import PartPositionRAG

log = structlog.get_logger()

_prompt = load_prompt("prompt_part_position_assigner.py")
SYSTEM_PROMPT = _prompt.SYSTEM_PROMPT
RAG_INJECTION_TEMPLATE = _prompt.RAG_INJECTION_TEMPLATE


def _is_part_position_target(fid: str, data: dict) -> bool:
    """Check if a feature should be handled by Part Position Assigner."""
    if data.get("parent") is None:
        return False  # root features have no placement
    op = data.get("operation", "").lower()
    # Only add-operation parts (not subtract, not modifiers)
    return op in ("add", "union")


class PartPositionAssignerAgent(BaseAgent):
    """Assigns spatial placement to add-operation parts.

    Reads feature assignments and specification, then determines for each
    add-operation part where it's placed, including floating/gap distances.
    """

    name = "part_position_assigner"

    def __init__(self):
        super().__init__()
        self._rag = PartPositionRAG()
        self._rag_ready = False

    def _ensure_rag(self):
        if not self._rag_ready:
            try:
                self._rag.build()
            except FileNotFoundError:
                self.log.warning("part_position_rag_missing",
                                 path="data/knowledge/rag_agents/28_part_position")
            self._rag_ready = True

    @property
    def model(self) -> str:
        return get_config().models.position_assigner

    def assign(self, state: PipelineState) -> dict:
        """Assign face, alignment, distance, and hints to each add-operation part.

        Returns dict with:
          part_position_assignments: {feature_id: {face, alignment, distance_mm, gap_mm, ...}}
        """
        specification = state.get("specification") or state.get("description", "")
        feature_assignments = state.get("feature_assignments", {})

        if not feature_assignments:
            self.log.warning("part_position_no_assignments")
            return {"part_position_assignments": {}}

        # Filter to only add-operation parts with a parent
        target_parts = {
            fid: data for fid, data in feature_assignments.items()
            if _is_part_position_target(fid, data)
        }

        if not target_parts:
            self.log.info("part_position_no_targets",
                          total_features=len(feature_assignments))
            return {"part_position_assignments": {}}

        # Build a compact summary of target parts for the prompt
        # Include spec context per part so the model can read directional words
        spec_lower = specification.lower()
        used_positions: set[int] = set()
        lines = []
        for fid, data in target_parts.items():
            parent = data.get("parent", "null")
            params = data.get("params", {})
            params_str = ", ".join(f"{k}={v}" for k, v in params.items())

            # Extract relevant spec context for this part
            spec_ctx = self._find_spec_context(fid, params, spec_lower, used_positions)
            ctx_str = f'  Spec-Kontext: "{spec_ctx}"' if spec_ctx else ""

            lines.append(f"  {fid}: parent={parent}, op=add, params=({params_str})")
            if ctx_str:
                lines.append(ctx_str)

        # Include parent dimensions for reference
        parent_info_lines = []
        for fid, data in target_parts.items():
            parent_id = data.get("parent")
            if parent_id and parent_id in feature_assignments:
                p_params = feature_assignments[parent_id].get("params", {})
                if p_params:
                    p_str = ", ".join(f"{k}={v}" for k, v in p_params.items())
                    parent_info_lines.append(f"  {parent_id}: params=({p_str})")
        parent_info = "\n".join(dict.fromkeys(parent_info_lines))

        assignments_summary = "\n".join(lines)
        if parent_info:
            assignments_summary += f"\n\nPARENT-DIMENSIONEN:\n{parent_info}"

        prompt = RAG_INJECTION_TEMPLATE.format(
            specification=specification,
            assignments_summary=assignments_summary,
        )

        self._ensure_rag()
        prompt = self._rag.enrich_prompt(prompt, specification)

        try:
            result = self.call_json(prompt, system=SYSTEM_PROMPT)

            self.log.info("part_position_raw_response",
                          keys=list(result.keys()) if isinstance(result, dict) else type(result).__name__)

            # Robust key detection
            positions = result.get("positions", {})
            if not isinstance(positions, dict) or not positions:
                for alt_key in ("part_positions", "placements", "position_assignments"):
                    positions = result.get(alt_key, {})
                    if isinstance(positions, dict) and positions:
                        self.log.info("part_position_alt_key", key=alt_key)
                        break
                else:
                    if isinstance(result, dict) and any(
                        isinstance(v, dict) and "face" in v for v in result.values()
                    ):
                        positions = {k: v for k, v in result.items()
                                     if isinstance(v, dict) and "face" in v}
                        self.log.info("part_position_bare_dict",
                                      features=len(positions))

            if not isinstance(positions, dict):
                positions = {}

            # Filter: only keep parts that are in our target set
            positions = {fid: data for fid, data in positions.items()
                         if fid in target_parts}

            # Validate and set defaults
            for fid, data in positions.items():
                if not isinstance(data, dict):
                    positions[fid] = {
                        "face": ">Z", "alignment": "centered",
                        "offset_x": None, "offset_y": None,
                        "orientation_hint": None, "face_hint": None,
                        "distance_mm": None, "gap_mm": None,
                        "relative_to": None,
                    }
                    continue
                data.setdefault("face", ">Z")
                data.setdefault("alignment", "centered")
                data.setdefault("offset_x", None)
                data.setdefault("offset_y", None)
                data.setdefault("orientation_hint", None)
                data.setdefault("face_hint", None)
                data.setdefault("distance_mm", None)
                data.setdefault("gap_mm", None)
                data.setdefault("relative_to", None)

            if not positions:
                self.log.warning("part_position_empty",
                                 target_count=len(target_parts))

            self.log.info("part_position_done",
                          parts=len(positions))

            return {
                "part_position_assignments": positions,
            }

        except (ValueError, ConnectionRefusedError) as e:
            self.log.error("part_position_failed", error=str(e))
            return {"part_position_assignments": {}}

    @staticmethod
    def _find_spec_context(
        fid: str, params: dict, spec_lower: str,
        used_positions: set[int] | None = None,
    ) -> str:
        """Find the relevant specification context for a part.

        Searches for part-identifying terms (dimensions, ID parts) in the
        specification and returns the surrounding text.
        Tracks used positions to avoid assigning the same context to multiple parts.
        """
        if used_positions is None:
            used_positions = set()

        search_terms = []

        # Search by dimension string (e.g. "20x80x40")
        px = params.get("x")
        py = params.get("y")
        pz = params.get("z")
        if px and py and pz:
            # Try both orderings (spec might use × or x)
            dim_str = f"{px}x{py}x{pz}"
            search_terms.append(dim_str)
            search_terms.append(dim_str.replace("x", "×"))

        # Search by diameter/height for cylinders
        if "diameter" in params and params["diameter"]:
            d = params["diameter"]
            search_terms.extend([f"∅{d}", f"{d}mm"])
        if "height" in params and params["height"]:
            search_terms.append(f"{params['height']}mm")

        # Search by feature ID parts
        for part in fid.replace("_", " ").split():
            if len(part) > 2 and part not in ("base", "plate", "box", "part"):
                search_terms.append(part)

        # Find the best matching position, skipping already-used positions
        for term in search_terms:
            start_search = 0
            while True:
                idx = spec_lower.find(term.lower(), start_search)
                if idx < 0:
                    break
                # Check if this position is too close to an already-used one
                too_close = any(abs(idx - up) < 20 for up in used_positions)
                if not too_close:
                    used_positions.add(idx)
                    start = max(0, idx - 40)
                    end = min(len(spec_lower), idx + len(term) + 80)
                    return spec_lower[start:end].strip()
                start_search = idx + 1

        return ""
