"""FunctionDecomposerAgent — classifies a blueprint and dispatches code-gen.

Three modes (decided by ``classify_blueprint``):
  - ``template``: every feature is template-able → emit final code, skip Coder.
  - ``mixed``: some templates + some complex features. Two sub-strategies:
      * ratio of standard ≥ 80% → still emit pure template, skip the few
        complex features (cheaper than waking the Coder for a tiny minority).
      * otherwise → emit templates as a stub, let Coder fill complex bits.
  - ``llm``: all features are complex → emit a per-function skeleton for Coder.
    Tiny-spec safety net: if there are ≤3 features the classification is
    almost certainly wrong, fall back to a template emission so the executor
    fails loud rather than the Coder timing out on a long prompt.
"""

import structlog

from src.codegen.assembler import generate_code as generate_template_code
from src.codegen.feature_classifier import classify_blueprint, get_complex_features
from src.graph.feature_tree import FeatureTree
from src.graph.state import PipelineState

from .skeleton import generate_skeleton


# Above this fraction of standard features we prefer pure-template emission
# over mixed-mode (Coder timeouts cost more than skipping the complex few).
_MIXED_TO_TEMPLATE_RATIO = 0.8

# Tiny specs classified as all-complex are almost always Inventar
# misclassifications (e.g. "bohrung_durch" instead of "hole_single").
_TINY_SPEC_THRESHOLD = 3


class FunctionDecomposerAgent:
    """Generates a Python skeleton (or final code) from a Feature Tree blueprint.

    Rule-based — no LLM call. Reads ``state.blueprint`` and writes either
    ``state.code`` (template mode) or ``state.code_skeleton`` (skeleton mode).

    If the blueprint is not a Feature Tree, returns empty skeleton so the
    Coder falls back to legacy CSG-Tree code generation.
    """

    name = "function_decomposer"

    def __init__(self):
        self.log = structlog.get_logger().bind(agent=self.name)

    def decompose(self, state: PipelineState) -> dict:
        blueprint = state.get("blueprint", {})

        if not FeatureTree.is_feature_tree(blueprint):
            self.log.info(
                "function_decomposer_skipped",
                reason="not_feature_tree",
                keys=list(blueprint.keys())[:5],
            )
            return {"code_skeleton": "", "generation_mode": "llm"}

        mode = classify_blueprint(blueprint)
        if mode == "template":
            return self._handle_template(blueprint)
        if mode == "mixed":
            return self._handle_mixed(blueprint)
        return self._handle_llm(blueprint)

    # ── mode handlers ────────────────────────────────────────────

    def _handle_template(self, blueprint: dict) -> dict:
        code = generate_template_code(blueprint)
        self.log.info(
            "function_decomposer_template",
            features=len(blueprint.get("build_order", [])),
            code_lines=len(code.splitlines()),
        )
        return {"code": code, "code_skeleton": "", "generation_mode": "template"}

    def _handle_mixed(self, blueprint: dict) -> dict:
        n_total, n_standard, n_complex, ratio = _feature_split(blueprint)

        if ratio >= _MIXED_TO_TEMPLATE_RATIO:
            code = generate_template_code(blueprint)
            self.log.info(
                "function_decomposer_mixed_to_template",
                features=n_total,
                standard=n_standard,
                complex_skipped=n_complex,
                ratio=round(ratio, 2),
            )
            return {"code": code, "code_skeleton": "", "generation_mode": "template"}

        code_with_stubs = generate_template_code(blueprint)
        self.log.info(
            "function_decomposer_mixed",
            features=n_total,
            standard=n_standard,
            complex=n_complex,
            skeleton_lines=len(code_with_stubs.splitlines()),
        )
        return {"code_skeleton": code_with_stubs, "generation_mode": "mixed"}

    def _handle_llm(self, blueprint: dict) -> dict:
        build_order = blueprint.get("build_order", [])
        n_total = len(build_order)

        if n_total <= 1:
            self.log.info(
                "function_decomposer_skipped",
                reason="single_feature",
                features=n_total,
            )
            return {"code_skeleton": "", "generation_mode": "llm"}

        if n_total <= _TINY_SPEC_THRESHOLD:
            n_complex = len(get_complex_features(blueprint))
            code = generate_template_code(blueprint)
            self.log.warning(
                "function_decomposer_llm_to_template_fallback",
                reason="small_spec_treated_as_complex_likely_misclass",
                features=n_total,
                complex=n_complex,
                code_lines=len(code.splitlines()),
            )
            return {"code": code, "code_skeleton": "", "generation_mode": "template"}

        skeleton = generate_skeleton(blueprint)
        if skeleton:
            self.log.info(
                "function_decomposer_done",
                features=n_total,
                skeleton_lines=len(skeleton.splitlines()),
            )
        else:
            self.log.warning("function_decomposer_empty_skeleton")
        return {"code_skeleton": skeleton, "generation_mode": "llm"}


def _feature_split(blueprint: dict) -> tuple[int, int, int, float]:
    """Return (total, standard, complex, standard_ratio) feature counts."""
    n_total = len(blueprint.get("build_order", []))
    n_complex = len(get_complex_features(blueprint))
    n_standard = n_total - n_complex
    ratio = n_standard / max(n_total, 1)
    return n_total, n_standard, n_complex, ratio
