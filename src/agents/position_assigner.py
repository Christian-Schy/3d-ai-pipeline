"""
src/agents/position_assigner.py — Assigns face, alignment, and orientation hints to each feature.

Part of the "Häppchen" architecture:
  Feature Tagger → Feature Assigner → **Position Assigner** → Blueprint Assembler → Planner

The Position Assigner's ONLY job:
  - For each non-root feature, determine:
    1. face — which face of the parent does it sit on? (">Z", ">X", etc.)
    2. alignment — how is it aligned on that face? ("centered", "flush_right", etc.)
    3. orientation_hint — pass through any orientation info ("20×80 Fläche liegt auf")
    4. face_hint — pass through face descriptions ("von der 80×40 Seite")
    5. axis_hint — slot/groove direction ("Y" for entlang Y-Achse)

It does NOT calculate offsets — that's the Blueprint Assembler's job (deterministic).

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

_prompt = load_prompt("prompt_position_assigner.py")
SYSTEM_PROMPT = _prompt.SYSTEM_PROMPT
RAG_INJECTION_TEMPLATE = _prompt.RAG_INJECTION_TEMPLATE


class PositionAssignerAgent(BaseAgent):
    """Assigns spatial placement (face, alignment, hints) to each feature.

    Reads the feature assignments from Feature Assigner and the specification,
    then determines for each non-root feature where and how it's placed.
    """

    name = "position_assigner"

    def __init__(self):
        super().__init__()
        self._rag = PositionAssignerRAG()
        self._rag_ready = False

    def _ensure_rag(self):
        if not self._rag_ready:
            try:
                self._rag.build()
            except FileNotFoundError:
                self.log.warning("position_assigner_rag_missing",
                                 path="data/knowledge/rag_agents/25_position_assigner")
            self._rag_ready = True

    @property
    def model(self) -> str:
        return get_config().models.position_assigner

    def assign(self, state: PipelineState) -> dict:
        """Assign face, alignment, and hints to each non-root feature.

        Returns dict with:
          position_assignments: {feature_id: {face, alignment, orientation_hint, face_hint, axis_hint}}
        """
        specification = state.get("specification") or state.get("description", "")
        feature_assignments = state.get("feature_assignments", {})

        if not feature_assignments:
            self.log.warning("position_assigner_no_assignments")
            return {"position_assignments": {}}

        # Build a compact summary of assignments for the prompt
        lines = []
        for fid, data in feature_assignments.items():
            parent = data.get("parent", "null")
            op = data.get("operation", "?")
            params = data.get("params", {})
            params_str = ", ".join(f"{k}={v}" for k, v in params.items())
            lines.append(f"  {fid}: parent={parent}, op={op}, params=({params_str})")
        assignments_summary = "\n".join(lines)

        prompt = RAG_INJECTION_TEMPLATE.format(
            specification=specification,
            assignments_summary=assignments_summary,
        )

        self._ensure_rag()
        prompt = self._rag.enrich_prompt(prompt, specification)

        try:
            result = self.call_json(prompt, system=SYSTEM_PROMPT)

            # Debug: log the raw response structure so we can diagnose parsing failures
            self.log.info("position_assigner_raw_response",
                          keys=list(result.keys()) if isinstance(result, dict) else type(result).__name__,
                          sample={k: type(v).__name__ for k, v in (result.items() if isinstance(result, dict) else [])})

            # Robust key detection: LLMs sometimes use alternative key names
            positions = result.get("positions", {})
            if not isinstance(positions, dict) or not positions:
                # Try alternative keys the LLM might use
                for alt_key in ("feature_positions", "placements", "position_assignments"):
                    positions = result.get(alt_key, {})
                    if isinstance(positions, dict) and positions:
                        self.log.info("position_assigner_alt_key", key=alt_key)
                        break
                else:
                    # Last resort: if result itself looks like positions
                    # (keys are feature IDs with dict values containing "face")
                    if isinstance(result, dict) and any(
                        isinstance(v, dict) and "face" in v for v in result.values()
                    ):
                        positions = {k: v for k, v in result.items()
                                     if isinstance(v, dict) and "face" in v}
                        self.log.info("position_assigner_bare_dict",
                                      features=len(positions))

            if not isinstance(positions, dict):
                positions = {}

            # Validate and set defaults
            for fid, data in positions.items():
                if not isinstance(data, dict):
                    positions[fid] = {
                        "face": ">Z", "alignment": "centered",
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

            if not positions:
                self.log.warning("position_assigner_empty",
                                 result_keys=list(result.keys()) if isinstance(result, dict) else "not_dict")

            self.log.info("position_assigner_done",
                          features=len(positions))

            return {
                "position_assignments": positions,
            }

        except (ValueError, ConnectionRefusedError) as e:
            self.log.error("position_assigner_failed", error=str(e))
            return {"position_assignments": {}}
