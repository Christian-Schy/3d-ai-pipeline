"""
src/agents/prompt_assembler.py — Builds focused Planner system prompts.

NOT a BaseAgent — no LLM call. Pure deterministic Python.

Takes the TaskClassification output and assembles a tailored system prompt
for the Planner by combining:
  1. A task-type-specific template (data/prompts/planner/template_*.md)
  2. Relevant rule snippets (data/knowledge/planner/rules/*.md)
  3. Optional RAG examples from PlannerRAG (max 2)
  4. Current geometry context (if requires_current_geometry=True)

Result: A 40-70 line system prompt instead of the 150-line monolithic SYSTEM_PROMPT.
Every line in the result is relevant to the specific task.
"""

from __future__ import annotations
import structlog
from pathlib import Path

log = structlog.get_logger()

# Directories — relative to project root
TEMPLATES_DIR = Path("data/prompts/planner")
RULES_DIR = Path("data/knowledge/planner/rules")

# Mapping from rag_category → rules file name
CATEGORY_TO_RULES_FILE = {
    "holes_single":      "rules_holes.md",
    "holes_multiple":    "rules_holes.md",
    "slots_grooves":     "rules_grooves.md",
    "boolean_ops":       "rules_boolean_order.md",
    "workplane_selection": "rules_workplane.md",
    "patterns_arrays":   "rules_patterns.md",
    "fillets_chamfers":  "rules_fillets.md",
    "primitives":        None,  # covered by templates
    "extrude_on_face":   None,
    "sketch_operations": None,
    "transforms":        None,
    "assemblies":        "rules_boolean_order.md",
}

# Mapping from planner_template → task-type-specific RAG examples file.
# The assembler queries this file first; falls back to global search if empty.
# None = no specific file → use global semantic search (template_complex covers all).
TEMPLATE_TO_EXAMPLES_FILE = {
    "template_simple":           "examples_simple.md",
    "template_boolean":          "examples_boolean.md",
    "template_feature_subtract": "examples_feature_subtract.md",
    "template_feature_add":      "examples_feature_add.md",
    "template_pattern":          "examples_feature_pattern.md",
    "template_modify":           "examples_modify.md",
    "template_complex":          None,  # search all examples globally
}

# Mapping from warning → inline rule text
WARNING_RULES = {
    "groove_surface_only": (
        "⚠ GROOVE DEPTH REQUIRED: This slot/groove stays ON the surface. "
        "Use cutBlind(-depth), NEVER cutThruAll(). "
        "Depth must be less than the solid's height."
    ),
    "multiple_holes_detected": (
        "⚠ MULTIPLE HOLES: Use hole_pattern with a positions list — "
        "NOT separate hole nodes. Positions are absolute from face center."
    ),
    "through_cut_needed": (
        "⚠ THROUGH-CUT: Set depth=null (not a fixed number) for a through-all hole or slot."
    ),
    "stacked_union_detected": (
        "⚠ STACKED UNION: Parts at different Z heights — "
        "for features on the BASE plate use face: \">Z[-2]\" not \">Z\"."
    ),
    "corner_positioning": (
        "⚠ CORNER POSITIONING: 'Xmm from edge' means offset = half_dim - X. "
        "Example: 20mm from edge on 200mm plate → offset = 100-20 = 80mm. "
        "Do NOT subtract hole radius."
    ),
    "corner_cut_detected": (
        "⚠ CORNER CUT: Use type 'corner_cut' — NOT polygon! "
        "Set corner_x=±half_x, corner_y=±half_y of the solid. "
        "x_leg and y_leg = cut depth along each axis."
    ),
}


class PromptAssembler:
    """Builds focused Planner system prompts from templates + rules + RAG.

    Usage:
        assembler = PromptAssembler()
        result = assembler.assemble(state)
        # result["assembled_system_prompt"] is a string ready for PlannerAgent
    """

    def __init__(self):
        self._planner_rag = None  # lazy init

    def _get_planner_rag(self):
        if self._planner_rag is None:
            from src.rag.planner_rag import PlannerRAG
            self._planner_rag = PlannerRAG()
            try:
                self._planner_rag.build()
            except FileNotFoundError:
                pass
        return self._planner_rag

    def assemble(self, state: dict) -> dict:
        """Assemble the focused system prompt for the Planner.

        Reads task_classification from state.
        Returns {"assembled_system_prompt": str}.
        """
        classification = state.get("task_classification", {})
        specification = state.get("specification") or state.get("description", "")
        geometry_state = state.get("geometry_state", {})

        if not classification:
            log.warning("prompt_assembler_no_classification")
            return {"assembled_system_prompt": ""}

        template_name = classification.get("planner_template", "template_complex")
        rag_categories = classification.get("rag_categories", [])
        warnings = classification.get("warnings", [])
        requires_geo = classification.get("requires_current_geometry", False)

        # 1. Load base template
        system_prompt = self._load_template(template_name)
        if not system_prompt:
            log.warning("prompt_assembler_template_missing", template=template_name)
            return {"assembled_system_prompt": ""}

        # 2. Append warning rules (inline — highest priority)
        if warnings:
            warning_lines = ["\n## ⚠ Warnings for this task"]
            for w in warnings:
                rule = WARNING_RULES.get(w)
                if rule:
                    warning_lines.append(f"- {rule}")
            system_prompt += "\n" + "\n".join(warning_lines)

        # 3. Append relevant rule snippets
        rules_text = self._load_rules(rag_categories)
        if rules_text:
            system_prompt += "\n\n## Additional Rules\n" + rules_text

        # 4. Append geometry context if needed
        if requires_geo and geometry_state:
            from src.graph.geometry_state import GeometryState
            try:
                geo = GeometryState.model_validate(geometry_state)
                system_prompt += geo.format_for_prompt()
            except Exception:
                pass

        # 5. Append RAG examples (max 2, optional) — task-type-specific first
        rag_text = self._query_rag(specification, rag_categories, n=2, template=template_name)
        if rag_text:
            system_prompt += "\n\n## Reference Examples\n" + rag_text

        prompt_len = len(system_prompt.split("\n"))
        log.info("prompt_assembler_done",
                 template=template_name,
                 warnings=len(warnings),
                 rag_categories=rag_categories,
                 lines=prompt_len)

        return {"assembled_system_prompt": system_prompt}

    def _load_template(self, template_name: str) -> str:
        """Load a template file from data/prompts/planner/."""
        path = TEMPLATES_DIR / f"{template_name}.md"
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
        log.warning("prompt_assembler_template_not_found", path=str(path))
        return ""

    def _load_rules(self, rag_categories: list[str]) -> str:
        """Load and deduplicate rule files for the given categories."""
        seen_files: set[str] = set()
        rule_sections: list[str] = []

        for category in rag_categories:
            filename = CATEGORY_TO_RULES_FILE.get(category)
            if not filename or filename in seen_files:
                continue
            seen_files.add(filename)

            path = RULES_DIR / filename
            if path.exists():
                content = path.read_text(encoding="utf-8").strip()
                if content:
                    rule_sections.append(content)
            else:
                log.debug("prompt_assembler_rules_not_found", file=filename)

        return "\n\n".join(rule_sections)

    def _query_rag(self, specification: str, rag_categories: list[str],
                   n: int = 2, template: str = "") -> str:
        """Query PlannerRAG for examples relevant to the specification.

        Strategy:
        1. If a task-type-specific examples file exists for this template,
           query that file first (filtered by source).
        2. If no results from the specific file, fall back to global search.
        3. template_complex has no specific file → always global search.
        """
        if not specification:
            return ""
        try:
            rag = self._get_planner_rag()

            # Attempt task-type-specific query first
            source_file = TEMPLATE_TO_EXAMPLES_FILE.get(template)
            chunks = []
            if source_file:
                chunks = rag.query_filtered(specification, n_results=n, source=source_file)
                if chunks:
                    log.debug("prompt_assembler_rag_specific",
                              template=template, source=source_file, n=len(chunks))

            # Fallback: global semantic search
            if not chunks:
                chunks = rag.query(specification, n_results=n)

            if not chunks:
                return ""

            parts = []
            for i, chunk in enumerate(chunks):
                parts.append(f"### Example {i+1} (from {chunk['source']}):\n```\n{chunk['text']}\n```")
            return "\n\n".join(parts)
        except Exception as e:
            log.debug("prompt_assembler_rag_failed", error=str(e))
            return ""
