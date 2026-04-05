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
from src.config.loader import get_config
from src.agents.base import BaseAgent
from src.rag.coder_rag import CoderRAG
from src.tools.code_extractor import CodeExtractor
from src.graph.state import PipelineState
from src.graph.feature_tree import FeatureTree
from src.utils.prompt_loader import load_prompt

log = structlog.get_logger()

_prompt = load_prompt("prompt_coder.py")
SYSTEM_PROMPT = _prompt.SYSTEM_PROMPT
FIX_PROMPT_TEMPLATE = _prompt.FIX_PROMPT_TEMPLATE


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

    def _enrich(self, prompt: str, description: str, state: PipelineState) -> str:
        """Enrich the prompt with RAG context.

        Phase 3: uses multi-tag queries from Feature Tagger when available.
        Falls back to single description query for legacy blueprints.
        Also injects feature-specific RAG based on agent_flags from Dispatcher.
        """
        self._ensure_rag()
        rag_queries = (state.get("feature_tree") or {}).get("rag_queries", [])
        is_feature_tree = FeatureTree.is_feature_tree(state.get("blueprint", {}))

        if rag_queries and is_feature_tree:
            self.log.info("coder_rag_multi_tag", queries=len(rag_queries))
            prompt = self._rag.enrich_prompt_with_tags(prompt, rag_queries, include_always=True)
        else:
            prompt = self._rag.enrich_prompt(prompt, description)

        # Inject feature-specific RAG based on Dispatcher flags
        agent_flags = state.get("agent_flags", [])
        if "inject_cylinder_rag" in agent_flags:
            prompt = self._inject_extra_rag(prompt, description, "cylinder")
        if "inject_shape_rag" in agent_flags:
            prompt = self._inject_extra_rag(prompt, description, "shape")

        return prompt

    def _inject_extra_rag(self, prompt: str, query: str, rag_type: str) -> str:
        """Inject additional feature-specific RAG chunks into the prompt."""
        if rag_type == "cylinder":
            from src.rag.cylinder_rag import CylinderRAG
            if not hasattr(self, "_cylinder_rag"):
                self._cylinder_rag = CylinderRAG()
                try:
                    self._cylinder_rag.build()
                except FileNotFoundError:
                    self.log.warning("cylinder_rag_missing")
                    return prompt
            extra = self._cylinder_rag.enrich_prompt("", query)
            if extra.strip():
                self.log.info("coder_cylinder_rag_injected",
                              chars=len(extra))
                prompt += f"\n\n--- ZYLINDER-SPEZIFISCHE BEISPIELE ---\n{extra}"
        elif rag_type == "shape":
            from src.rag.shape_cutting_rag import ShapeCuttingRAG
            if not hasattr(self, "_shape_rag"):
                self._shape_rag = ShapeCuttingRAG()
                try:
                    self._shape_rag.build()
                except FileNotFoundError:
                    self.log.warning("shape_cutting_rag_missing")
                    return prompt
            extra = self._shape_rag.enrich_prompt("", query)
            if extra.strip():
                self.log.info("coder_shape_rag_injected",
                              chars=len(extra))
                prompt += f"\n\n--- SHAPE-CUTTING BEISPIELE ---\n{extra}"
        return prompt

    @staticmethod
    def _fix_imports(code: str) -> str:
        """Deterministic post-processing: add missing imports.

        The Coder LLM often drops imports even when they're in the skeleton.
        The sandbox prepends 'import cadquery as cq' but NOT NearestToPointSelector.
        """
        import re

        ntp_import = "from cadquery.selectors import NearestToPointSelector"

        # NearestToPointSelector used but not imported
        if "NearestToPointSelector" in code:
            has_import = bool(re.search(
                r"from\s+cadquery\.selectors\s+import\s+NearestToPointSelector",
                code,
            ))
            if not has_import:
                # Try inserting after "import cadquery as cq"
                new_code = re.sub(
                    r"(import cadquery as cq\s*\n)",
                    r"\1" + ntp_import + "\n",
                    code,
                    count=1,
                )
                if new_code != code:
                    code = new_code
                else:
                    # Coder dropped cadquery import too (sandbox adds it) —
                    # prepend both at the very top of the file
                    code = f"import cadquery as cq\n{ntp_import}\n{code}"

        # Ensure 'import cadquery as cq' is present (Coder sometimes drops it)
        elif "import cadquery" not in code and "cq." in code:
            code = f"import cadquery as cq\n{code}"

        return code

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
        Phase 1: if code_skeleton is set (Feature Tree pipeline), fills the skeleton.
        """
        if state.get("execution_error") or state.get("validation_error"):
            return self._fix(state)
        skeleton = state.get("code_skeleton", "")
        if skeleton and FeatureTree.is_feature_tree(state.get("blueprint", {})):
            return self._fill_skeleton(state)
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

        Handles both Feature Tree (dict) and CSG-Tree (list) formats.
        """
        prev_raw = prev_bp.get("features", [])
        curr_raw = curr_bp.get("features", [])

        # Normalize Feature Tree dict → ordered list using build_order
        if isinstance(curr_raw, dict):
            build_order = curr_bp.get("build_order", list(curr_raw.keys()))
            curr = [curr_raw[fid] for fid in build_order if fid in curr_raw]
        else:
            curr = list(curr_raw)

        if isinstance(prev_raw, dict):
            prev_build = prev_bp.get("build_order", list(prev_raw.keys()))
            prev = [prev_raw[fid] for fid in prev_build if fid in prev_raw]
        else:
            prev = list(prev_raw)

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
            features_raw = clean_blueprint.get("features", [])
            feature_hint = ""
            if features_raw:
                # Feature Tree: features is a dict {id → entry}
                # CSG-Tree:     features is a list of dicts
                if isinstance(features_raw, dict):
                    build_order = clean_blueprint.get("build_order", list(features_raw.keys()))
                    feature_types = [
                        features_raw.get(fid, {}).get("type", fid)
                        for fid in build_order
                    ]
                else:
                    feature_types = [f.get("type", "?") for f in features_raw]
                feature_hint = (
                    f"\n\nThis blueprint has {len(feature_types)} feature(s): {', '.join(feature_types)}.\n"
                    f"Build root first, then apply features in the listed order.\n"
                    f"⚠ Feature order is already correct — do NOT reorder (holes before slots)."
                )
            # If routed here from validator (placement error), inject the feedback
            validator_feedback = state.get("validator_feedback", "")
            validator_hint = (
                f"\n\n## ⚠ VALIDATOR FEEDBACK (placement error — fix the code, blueprint is correct)\n"
                f"{validator_feedback}\n"
                f"Fix the placement/offset code so the feature ends up at the correct position."
            ) if validator_feedback else ""

            prompt = (
                f"Translate this Blueprint into CadQuery Python code."
                f"{feature_hint}{notes_hint}{validator_hint}\n\n```json\n{blueprint_text}\n```"
            )

        # Enrich with relevant examples from RAG (multi-tag if Feature Tree)
        prompt = self._enrich(prompt, description, state)

        raw_response = self.call(prompt, system=SYSTEM_PROMPT)
        code = self._fix_imports(self._extractor.extract(raw_response))

        self.log.info("coder_generate_done", code_lines=code.count("\n") + 1)
        self._log_code_preview(code)
        return {"code": code}

    # ------------------------------------------------------------------
    # Skeleton-filling mode (Phase 1: Feature Tree pipeline)
    # ------------------------------------------------------------------

    def _fill_skeleton(self, state: PipelineState) -> dict:
        """Fill in a code skeleton generated by FunctionDecomposer.

        Each function stub (containing `pass`) is filled with correct
        CadQuery code based on the Feature Tree blueprint and the
        function's docstring.
        """
        skeleton = state.get("code_skeleton", "")
        blueprint = state.get("blueprint", {})
        description = blueprint.get("description", state.get("description", ""))
        change_desc = state.get("change_description", "")

        self.log.info("coder_fill_skeleton",
                      description=description[:60],
                      skeleton_lines=len(skeleton.splitlines()))

        clean_blueprint = {k: v for k, v in blueprint.items() if not k.startswith("_")}
        blueprint_text = json.dumps(clean_blueprint, indent=2)
        notes = clean_blueprint.get("notes", "")
        notes_hint = f"\n\nPLANNER NOTES: {notes}" if notes else ""

        review_issues = state.get("code_review_issues", "")
        current_code = state.get("code", "")

        if review_issues and current_code:
            # Code Review sent us back — fix specific issues in existing code
            prompt = (
                f"## Code Review Issues — fix ONLY these problems:\n{review_issues}\n\n"
                f"## Current Code (fix in place, keep working parts)\n"
                f"```python\n{current_code}\n```\n\n"
                f"## Feature Tree Blueprint (reference)\n```json\n{blueprint_text}\n```\n\n"
                f"Rules:\n"
                f"- Fix ONLY the listed issues — do not rewrite unaffected functions\n"
                f"- Keep ALL function signatures EXACTLY as given\n"
                f"- Use .faces(face).workplane(centerOption='CenterOfBoundBox') for face selection — NOT in cq.Workplane('XY')!\n"
                f"- Always .clean() after .union() and .cut()\n"
                f"- Keep cq.exporters.export(result, OUTPUT_PATH) at the end as-is"
                f"{notes_hint}"
            )
        else:
            # If routed here from validator (placement error), inject the feedback
            validator_feedback = state.get("validator_feedback", "")
            validator_hint = (
                f"\n## ⚠ VALIDATOR FEEDBACK (placement error — fix the code, blueprint is correct)\n"
                f"{validator_feedback}\n"
                f"Fix the placement/offset code so the feature ends up at the correct position.\n"
            ) if validator_feedback else ""

            prompt = (
                f"## Feature Tree Blueprint\n```json\n{blueprint_text}\n```\n\n"
                f"## Code Skeleton — fill in each function (replace `pass` with CadQuery code)\n"
                f"```python\n{skeleton}\n```\n"
                f"{validator_hint}\n"
                f"Rules:\n"
                f"- Keep ALL function signatures EXACTLY as given\n"
                f"- Each function docstring describes what it must do — follow it precisely\n"
                f"- Root function (make_*): create the base shape, return cq.Workplane\n"
                f"- Add functions (add_*): union the new shape onto body, return body\n"
                f"- Drill/cut functions: cut the feature from body, return body\n"
                f"- Use .faces(face).workplane(centerOption='CenterOfBoundBox') for face selection — NOT in cq.Workplane('XY')!\n"
                f"- Always .clean() after .union() and .cut()\n"
                f"- The final result variable is set in assemble() — do NOT add export here\n"
                f"- Keep cq.exporters.export(result, OUTPUT_PATH) at the end as-is"
                f"{notes_hint}"
            )

        # Modification Guard: if changed_features is set and previous_code exists,
        # tell the LLM to only regenerate the affected functions.
        changed_features = state.get("changed_features", [])
        previous_code = state.get("previous_code", "")
        if change_desc and changed_features and previous_code and not review_issues:
            changed_list = ", ".join(f'"{f}"' for f in changed_features)
            guard_section = (
                f"\n## Modification Guard — Partial Regeneration\n"
                f"Only regenerate functions for changed features: {changed_list}\n"
                f"For ALL other features: copy their function bodies EXACTLY from the reference code below — "
                f"do NOT modify any value, position, or parameter.\n"
                f"Always rewrite assemble() to match the current build_order.\n\n"
                f"## Reference code (previous working version)\n"
                f"```python\n{previous_code}\n```\n"
            )
            prompt = guard_section + prompt
        elif change_desc:
            prompt = f"## Change context\n{change_desc}\n\n" + prompt

        # Enrich with multi-tag RAG (always uses Feature Tree path here)
        prompt = self._enrich(prompt, description, state)

        raw_response = self.call(prompt, system=SYSTEM_PROMPT)
        code = self._fix_imports(self._extractor.extract(raw_response))

        self.log.info("coder_fill_skeleton_done", code_lines=code.count("\n") + 1)
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

        raw_response = self.call(prompt, system=SYSTEM_PROMPT)
        code = self._fix_imports(self._extractor.extract(raw_response))

        self.log.info("coder_fix_done", code_lines=code.count("\n") + 1)
        self._log_code_preview(code)
        return {"code": code}