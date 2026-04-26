"""
src/agents/feature_position_assigner.py — Assigns face, alignment, and hints to subtract/modify features.

Part of the "Häppchen" architecture:
  Feature Tagger → Feature Assigner → **Feature Position Assigner** →
  Part Position Assigner → Blueprint Assembler

The Feature Position Assigner handles ONLY subtract/modify features:
  - Holes, slots, pockets, grooves (operation == "subtract")
  - Fillets, chamfers (modifier types)

For each qualifying feature it determines:
  1. face — which parent face does the feature cut into? (">Z", ">X", etc.)
  2. alignment — position on that face ("centered", "flush_right", etc.)
  3. orientation_hint — pass-through orientation info
  4. face_hint — pass-through face descriptions ("von der 80×40 Seite")
  5. axis_hint — slot/groove direction ("Y" for entlang Y-Achse)
  6. offset_x / offset_y — explicit offsets from specification

It does NOT handle add-operation parts (plates, boxes, extrusions) —
that's the Part Position Assigner's job.
It does NOT calculate final offsets — that's the Blueprint Assembler's job.

Model: qwen3.5:9b — focused task, spatial language understanding only.
"""

import json
import structlog
from src.agents.base import BaseAgent
from src.config.loader import get_config
from src.graph.state import PipelineState
from src.utils.prompt_loader import load_prompt
from src.rag.position_assigner_rag import PositionAssignerRAG

log = structlog.get_logger()

_prompt = load_prompt("prompt_feature_position_assigner.py")
SYSTEM_PROMPT = _prompt.SYSTEM_PROMPT
RAG_INJECTION_TEMPLATE = _prompt.RAG_INJECTION_TEMPLATE

# Feature types that are always handled by the Feature Position Assigner
# regardless of operation field
_MODIFIER_TYPES = {"fillet", "chamfer", "shell", "taper"}
_SUBTRACT_OPS = {"subtract", "cut"}


def _is_feature_position_target(fid: str, data: dict) -> bool:
    """Check if a feature should be handled by Feature Position Assigner."""
    if data.get("parent") is None:
        return False  # root features have no placement
    op = data.get("operation", "").lower()
    ftype = data.get("type", "").lower() if "type" in data else ""
    # Subtract operations (holes, slots, pockets)
    if op in _SUBTRACT_OPS:
        return True
    # Modifier types (fillet, chamfer) even if operation is "add"
    if ftype in _MODIFIER_TYPES:
        return True
    return False


class FeaturePositionAssignerAgent(BaseAgent):
    """Assigns spatial placement (face, alignment, hints) to subtract/modify features.

    Reads the feature assignments from Feature Assigner and the specification,
    then determines for each subtract/modify feature where and how it's placed.
    Add-operation parts are skipped — handled by PartPositionAssignerAgent.
    """

    name = "feature_position_assigner"

    def __init__(self):
        super().__init__()
        self._rag = PositionAssignerRAG()
        self._rag_ready = False

    def _ensure_rag(self):
        if not self._rag_ready:
            try:
                self._rag.build()
            except FileNotFoundError:
                self.log.warning("feature_position_rag_missing",
                                 path="data/knowledge/rag_agents/25_position_assigner")
            self._rag_ready = True

    @property
    def model(self) -> str:
        return get_config().models.position_assigner

    def assign(self, state: PipelineState) -> dict:
        """Assign face, alignment, and hints to each subtract/modify feature.

        Returns dict with:
          feature_position_assignments: {feature_id: {face, alignment, orientation_hint, ...}}
        """
        specification = state.get("specification") or state.get("description", "")
        feature_assignments = state.get("feature_assignments", {})

        if not feature_assignments:
            self.log.warning("feature_position_no_assignments")
            return {"feature_position_assignments": {}}

        # Filter to only subtract/modify features
        target_features = {
            fid: data for fid, data in feature_assignments.items()
            if _is_feature_position_target(fid, data)
        }

        if not target_features:
            self.log.info("feature_position_no_targets",
                          total_features=len(feature_assignments))
            return {"feature_position_assignments": {}}

        # Build a compact summary of target features for the prompt
        # Include spec context per feature so the model can map directional words
        spec_lower = specification.lower()
        used_positions: set[int] = set()  # Track used spec positions to avoid duplicates
        lines = []
        for fid, data in target_features.items():
            parent = data.get("parent", "null")
            op = data.get("operation", "?")
            params = data.get("params", {})
            params_str = ", ".join(f"{k}={v}" for k, v in params.items())

            # Extract relevant spec context for this feature
            spec_ctx = self._find_spec_context(fid, params, spec_lower, used_positions)
            ctx_str = f'  Spec-Kontext: "{spec_ctx}"' if spec_ctx else ""

            lines.append(f"  {fid}: parent={parent}, op={op}, params=({params_str})")
            if ctx_str:
                lines.append(ctx_str)

        # Also include parent dimensions for face calculation
        parent_info_lines = []
        for fid, data in target_features.items():
            parent_id = data.get("parent")
            if parent_id and parent_id in feature_assignments:
                p_params = feature_assignments[parent_id].get("params", {})
                if p_params:
                    p_str = ", ".join(f"{k}={v}" for k, v in p_params.items())
                    parent_info_lines.append(f"  {parent_id}: params=({p_str})")
        parent_info = "\n".join(dict.fromkeys(parent_info_lines))  # deduplicate

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
            positions = self._call_and_parse(prompt, target_features)

            # Retry once if empty — the 9b model sometimes fails JSON on first attempt
            if not positions:
                self.log.warning("feature_position_empty_retry",
                                 target_count=len(target_features))
                positions = self._call_and_parse(prompt, target_features)

            # Last resort: generate defaults for any missing features
            for fid in target_features:
                if fid not in positions:
                    positions[fid] = {
                        "face": ">Z", "alignment": "centered",
                        "offset_x": None, "offset_y": None,
                        "orientation_hint": None, "face_hint": None, "axis_hint": None,
                    }
                    self.log.warning("feature_position_default_used", feature=fid)

            self.log.info("feature_position_done",
                          features=len(positions))

            return {
                "feature_position_assignments": positions,
            }

        except (ValueError, ConnectionRefusedError) as e:
            self.log.error("feature_position_failed", error=str(e))
            # Still return defaults so pipeline doesn't break
            positions = {}
            for fid in target_features:
                positions[fid] = {
                    "face": ">Z", "alignment": "centered",
                    "offset_x": None, "offset_y": None,
                    "orientation_hint": None, "face_hint": None, "axis_hint": None,
                }
            return {"feature_position_assignments": positions}

    @staticmethod
    def _find_spec_context(
        fid: str, params: dict, spec_lower: str,
        used_positions: set[int] | None = None,
    ) -> str:
        """Find the relevant specification context for a feature.

        Searches for feature-identifying terms (diameter, dimensions, ID parts)
        in the specification and returns the surrounding text.
        Tracks used positions to avoid assigning the same context to multiple features.
        """
        import re
        if used_positions is None:
            used_positions = set()

        search_terms = []

        # Search by dimension values
        if "diameter" in params and params["diameter"]:
            d = params["diameter"]
            search_terms.extend([f"{d}mm", f"∅{d}", str(d)])
        if "width" in params and params["width"]:
            w = params["width"]
            d = params.get("depth", "")
            if d:
                search_terms.append(f"{w}x{d}")
            search_terms.append(f"{w}mm")

        # Search by feature ID parts
        for part in fid.replace("_", " ").split():
            if len(part) > 2 and part not in ("hole", "single", "pattern", "axis"):
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
                    start = max(0, idx - 60)
                    end = min(len(spec_lower), idx + 40)
                    return spec_lower[start:end].strip()
                start_search = idx + 1

        return ""

    def _call_and_parse(self, prompt: str, target_features: dict) -> dict:
        """Call LLM and parse positions from response."""
        result = self.call_json(prompt, system=SYSTEM_PROMPT)

        self.log.info("feature_position_raw_response",
                      keys=list(result.keys()) if isinstance(result, dict) else type(result).__name__)

        # Robust key detection
        positions = result.get("positions", {})
        if not isinstance(positions, dict) or not positions:
            for alt_key in ("feature_positions", "placements", "position_assignments"):
                positions = result.get(alt_key, {})
                if isinstance(positions, dict) and positions:
                    self.log.info("feature_position_alt_key", key=alt_key)
                    break
            else:
                if isinstance(result, dict) and any(
                    isinstance(v, dict) and "face" in v for v in result.values()
                ):
                    positions = {k: v for k, v in result.items()
                                 if isinstance(v, dict) and "face" in v}
                    self.log.info("feature_position_bare_dict",
                                  features=len(positions))

        if not isinstance(positions, dict):
            positions = {}

        # Filter: only keep features that are in our target set
        positions = {fid: data for fid, data in positions.items()
                     if fid in target_features}

        # Validate and set defaults
        for fid, data in positions.items():
            if not isinstance(data, dict):
                positions[fid] = {
                    "face": ">Z", "alignment": "centered",
                    "offset_x": None, "offset_y": None,
                    "orientation_hint": None, "face_hint": None, "axis_hint": None,
                }
                continue
            data.setdefault("face", ">Z")
            data.setdefault("alignment", "centered")
            data.setdefault("offset_x", None)
            data.setdefault("offset_y", None)
            data.setdefault("orientation_hint", None)
            data.setdefault("face_hint", None)
            data.setdefault("axis_hint", None)

        return positions
