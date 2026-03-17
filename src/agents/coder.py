"""
src/agents/coder.py — Generates CadQuery Python code from a Blueprint.

The Coder is the "craftsman" of the pipeline:
  - It reads the Blueprint from Planner
  - It optionally retrieves relevant examples via CoderRAG
  - It writes CadQuery Python code that will run in the sandbox

Two modes depending on the situation:
  normal:  blueprint → code (first attempt)
  fix:     blueprint + error + previous code → fixed code (error loop)

Model: qwen3:30b — code quality is critical.
"""

import json
import structlog
from pathlib import Path
from src.config.loader import get_config
from src.agents.base import BaseAgent
from src.rag.coder_rag import CoderRAG
from src.tools.code_extractor import CodeExtractor
from src.graph.state import PipelineState

log = structlog.get_logger()

SYSTEM_PROMPT = Path("data/prompts/agents/coder.md").read_text(encoding="utf-8")
FIX_SYSTEM_PROMPT = Path("data/prompts/agents/coder_fix.md").read_text(encoding="utf-8")


class CoderAgent(BaseAgent):
    """Generates or fixes CadQuery code based on a Blueprint.

    Uses CoderRAG to retrieve relevant examples before generating code.
    This improves output quality without making the model larger.
    """

    model = get_config().models.coder  # set from config.yaml
    name = "coder"

    def __init__(self):
        super().__init__()
        self._rag = CoderRAG()
        self._rag_ready = False
        self._extractor = CodeExtractor()

    def _ensure_rag(self):
        """Build RAG on first use — not at import/instantiation time."""
        if not self._rag_ready:
            self._rag.build()
            self._rag_ready = True

    def _log_code_preview(self, code: str):
        """Log first 6 non-empty, non-comment lines for the UI chat display.

        Uses ↵ as line separator so the value stays on one log line.
        """
        lines = [l for l in code.split("\n") if l.strip()][:6]
        preview = "↵".join(lines)
        self.log.info("coder_code_preview", preview=preview[:400])

    def run(self, state: PipelineState) -> dict:
        """Generate code from the Blueprint. Returns {"code": "..."}.

        If execution_error is set in state, we're in fix mode.
        """
        if state.get("execution_error") or state.get("validation_error"):
            return self._fix(state)
        return self._generate(state)

    # ------------------------------------------------------------------
    # Blueprint diff helper
    # ------------------------------------------------------------------

    def _diff_features(
        self, prev_bp: dict, curr_bp: dict
    ) -> list[tuple[int, str, dict]]:
        """Compare features in prev_bp vs curr_bp.

        Returns list of (index, status, feature_dict) where status is:
          'unchanged' — feature identical, must copy code verbatim
          'changed'   — feature exists in both but values differ
          'new'       — feature only in curr_bp (added)
        """
        prev = prev_bp.get("features", [])
        curr = curr_bp.get("features", [])
        result = []
        for i, feat in enumerate(curr):
            if i < len(prev):
                status = "unchanged" if prev[i] == feat else "changed"
            else:
                status = "new"
            result.append((i, status, feat))
        return result

    # ------------------------------------------------------------------
    # Generation (first attempt)
    # ------------------------------------------------------------------

    def _generate(self, state: PipelineState) -> dict:
        blueprint = state.get("blueprint", {})
        description = blueprint.get("description", state.get("description", ""))
        change_desc = state.get("change_description", "")

        # In validator-revision cycle: state["code"] holds the just-generated code
        # that the validator rejected on semantic grounds. Use it as the anchor so
        # slot/hole parameters from the first attempt are preserved even after a
        # Planner revision (which may change slot length or other details).
        # In fresh modification: use previous_code (the pre-modification working code).
        current_code = state.get("code", "")       # code from this run's Coder attempt
        previous_code = state.get("previous_code", "")  # code from the last successful run
        # Pick the best anchor: prefer current_code (validator revision) over previous_code
        anchor_code = current_code if current_code and change_desc else previous_code

        self.log.info("coder_generate_start",
                      description=description[:60],
                      has_anchor_code=bool(anchor_code),
                      mode="revision" if current_code and change_desc else "modification" if anchor_code else "fresh")

        # Remove internal error markers before sending to LLM
        clean_blueprint = {k: v for k, v in blueprint.items() if not k.startswith("_")}
        blueprint_text = json.dumps(clean_blueprint, indent=2)
        notes = clean_blueprint.get("notes", "")
        notes_hint = f"\n\nPLANNER NOTES (follow these exactly): {notes}" if notes else ""

        if anchor_code and change_desc:
            # --- Modification Guard / Revision mode ---
            # Build a feature diff: compare previous_blueprint vs current blueprint
            # to know exactly which features changed and which must be copied verbatim.
            prev_bp = state.get("previous_blueprint", {})
            feature_diff = self._diff_features(prev_bp, clean_blueprint)

            features = clean_blueprint.get("features", [])
            feature_types = [f.get("type", "?") for f in features]
            feature_order_note = (
                f"Features in updated blueprint (correct order): {', '.join(feature_types)}\n"
                if feature_types else ""
            )

            # Build explicit per-feature instructions
            feature_instructions = ""
            if feature_diff:
                lines = ["\n## Feature status (MUST follow exactly):"]
                for idx, status, feat in feature_diff:
                    ftype = feat.get("type", "?")
                    if status == "unchanged":
                        lines.append(
                            f"  Feature[{idx}] ({ftype}): UNCHANGED — "
                            f"copy its code line(s) from reference code CHARACTER FOR CHARACTER. "
                            f"Do NOT adjust its position, depth, size, or any value."
                        )
                    elif status == "changed":
                        lines.append(
                            f"  Feature[{idx}] ({ftype}): CHANGED — "
                            f"update according to the blueprint diff."
                        )
                    else:  # new
                        lines.append(
                            f"  Feature[{idx}] ({ftype}): NEW — "
                            f"generate from blueprint, insert at correct position (holes before slots)."
                        )
                feature_instructions = "\n".join(lines) + "\n"

            prompt = (
                f"## Change to apply\n{change_desc}\n\n"
                f"## Reference code — base for this modification\n"
                f"```python\n{anchor_code}\n```\n\n"
                f"## Updated Blueprint\n"
                f"```json\n{blueprint_text}\n```\n\n"
                f"{feature_instructions}"
                f"{feature_order_note}"
                f"{notes_hint}\n"
                f"Rules:\n"
                f"- UNCHANGED features: copy their code lines EXACTLY from reference — "
                f"no position, depth, or size adjustment whatsoever.\n"
                f"- CHANGED/NEW features: use their exact blueprint parameters.\n"
                f"- Each feature has its own .faces(face).workplane() — positions are "
                f"ABSOLUTE from face center, never relative to other features.\n"
                f"- Features with position=(0,0): no .center() call."
            )
            self.log.info("coder_modification_mode",
                          change=change_desc[:60],
                          unchanged=[i for i, s, _ in feature_diff if s == "unchanged"],
                          changed=[i for i, s, _ in feature_diff if s == "changed"],
                          new=[i for i, s, _ in feature_diff if s == "new"])
        else:
            # --- Fresh generation ---
            features = clean_blueprint.get("features", [])
            feature_hint = ""
            if features:
                feature_types = [f.get("type", "?") for f in features]
                feature_hint = (
                    f"\n\nThis blueprint has {len(features)} feature(s): {', '.join(feature_types)}.\n"
                    f"Build root first, then apply features in the listed order.\n"
                    f"⚠ Feature order is already correct — do NOT reorder (holes before slots)."
                )
            prompt = (
                f"Translate this Blueprint into CadQuery Python code."
                f"{feature_hint}{notes_hint}\n\n```json\n{blueprint_text}\n```"
            )

        # Enrich with relevant examples from RAG
        self._ensure_rag()
        prompt = self._rag.enrich_prompt(prompt, description)

        raw_response = self.call(prompt, system=SYSTEM_PROMPT)
        code = self._extractor.extract(raw_response)

        self.log.info("coder_generate_done", code_lines=code.count("\n") + 1)
        self._log_code_preview(code)
        return {"code": code}

    # ------------------------------------------------------------------
    # Fix mode (called during error loop)
    # ------------------------------------------------------------------

    def _fix(self, state: PipelineState) -> dict:
        blueprint = state.get("blueprint", {})
        previous_code = state.get("code", "")
        error = state.get("execution_error") or state.get("validation_error", "")
        attempt = state.get("attempts", 1)
        fix_plan = state.get("fix_plan", "")

        self.log.info("coder_fix_start", attempt=attempt, error=error[:80],
                      has_fix_plan=bool(fix_plan))

        blueprint_text = json.dumps(blueprint, indent=2)
        prompt = (
            f"## Blueprint\n```json\n{blueprint_text}\n```\n\n"
            f"## Code that failed\n```python\n{previous_code}\n```\n\n"
            f"## Error\n{error}\n\n"
        )

        # Phase 2: CodeFixer has provided a diagnosis — include it
        if fix_plan:
            prompt += f"## Diagnosis from CodeFixer\n{fix_plan}\n\n"

        # Auto-detect box-as-groove anti-pattern
        if ".box(" in previous_code and ".translate(" in previous_code and "slot" not in previous_code.lower():
            prompt += (
                "⚠ GROOVE ANTI-PATTERN DETECTED: Code uses box().translate() to cut a groove.\n"
                "Replace with face workplane + slot2D:\n"
                "  result = result.faces(\">Z\").workplane().slot2D(length, width, angle).cutBlind(-depth).clean()\n"
                "  cutBlind(-depth) = groove depth in mm (e.g. -5), NOT the cube height!\n\n"
            )

        # Auto-detect fillet error — give the coder a hard instruction
        if "fillet" in error.lower() and "fillet" in previous_code:
            prompt += (
                "⚠ FILLET ERROR DETECTED: Remove ALL .fillet() calls. "
                "Do not replace with .chamfer() — just delete the line entirely.\n\n"
            )

        prompt += "Fix the code so it runs correctly."

        raw_response = self.call(prompt, system=FIX_SYSTEM_PROMPT)
        code = self._extractor.extract(raw_response)

        self.log.info("coder_fix_done", code_lines=code.count("\n") + 1)
        self._log_code_preview(code)
        return {"code": code}