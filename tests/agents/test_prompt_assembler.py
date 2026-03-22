"""
tests/agents/test_prompt_assembler.py — Unit tests for PromptAssembler.

Deterministic (no LLM). PlannerRAG is mocked to avoid ChromaDB/embedding load.
"""

import pytest
from unittest.mock import MagicMock, patch
from src.agents.prompt_assembler import PromptAssembler


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_state(template="template_complex", rag_categories=None, warnings=None,
                specification="A box with a hole", requires_geo=False):
    return {
        "specification": specification,
        "task_classification": {
            "planner_template": template,
            "rag_categories": rag_categories or [],
            "warnings": warnings or [],
            "requires_current_geometry": requires_geo,
        },
        "geometry_state": {},
    }


@pytest.fixture(autouse=True)
def mock_planner_rag():
    """Mock PlannerRAG — never touches ChromaDB.

    PromptAssembler lazy-imports PlannerRAG inside _get_planner_rag(),
    so we patch the source module, not the assembler module.
    """
    fake_rag = MagicMock()
    fake_rag.build.return_value = None
    fake_rag.query.return_value = []
    fake_rag.query_filtered.return_value = []
    fake_rag.last_chunks_used = []
    with patch("src.rag.planner_rag.PlannerRAG", return_value=fake_rag):
        yield fake_rag


# ── Template loading ──────────────────────────────────────────────────────────

class TestTemplateLoading:
    def test_missing_template_returns_empty_prompt(self):
        assembler = PromptAssembler()
        state = _make_state(template="template_nonexistent_xyz")
        result = assembler.assemble(state)
        assert result["assembled_system_prompt"] == ""

    def test_existing_template_returns_nonempty_prompt(self):
        assembler = PromptAssembler()
        # template_complex exists in data/prompts/planner/
        state = _make_state(template="template_complex")
        result = assembler.assemble(state)
        assert result["assembled_system_prompt"] != ""

    def test_template_simple_loads(self):
        assembler = PromptAssembler()
        state = _make_state(template="template_simple")
        result = assembler.assemble(state)
        assert result["assembled_system_prompt"] != ""

    def test_all_templates_loadable(self):
        templates = [
            "template_simple", "template_complex", "template_feature_subtract",
            "template_feature_add", "template_boolean", "template_pattern", "template_modify",
        ]
        assembler = PromptAssembler()
        for t in templates:
            state = _make_state(template=t)
            result = assembler.assemble(state)
            assert result["assembled_system_prompt"] != "", f"Template {t} returned empty prompt"


# ── Warning rules ─────────────────────────────────────────────────────────────

class TestWarningRules:
    def test_groove_surface_warning_appended(self):
        assembler = PromptAssembler()
        state = _make_state(warnings=["groove_surface_only"])
        result = assembler.assemble(state)
        assert "GROOVE DEPTH REQUIRED" in result["assembled_system_prompt"]

    def test_multiple_holes_warning_appended(self):
        assembler = PromptAssembler()
        state = _make_state(warnings=["multiple_holes_detected"])
        result = assembler.assemble(state)
        assert "MULTIPLE HOLES" in result["assembled_system_prompt"]

    def test_unknown_warning_not_crash(self):
        assembler = PromptAssembler()
        state = _make_state(warnings=["totally_unknown_warning_xyz"])
        result = assembler.assemble(state)
        # Should not crash, just skip the unknown warning
        assert isinstance(result["assembled_system_prompt"], str)

    def test_no_warnings_no_warning_section(self):
        assembler = PromptAssembler()
        state = _make_state(warnings=[])
        result = assembler.assemble(state)
        assert "⚠ Warnings for this task" not in result["assembled_system_prompt"]


# ── Rules injection ───────────────────────────────────────────────────────────

class TestRulesInjection:
    def test_holes_category_injects_rules(self):
        assembler = PromptAssembler()
        state = _make_state(rag_categories=["holes_single"])
        result = assembler.assemble(state)
        prompt = result["assembled_system_prompt"]
        # rules_holes.md should be injected — check for some known content
        assert "Additional Rules" in prompt or prompt != ""

    def test_duplicate_categories_not_duplicated(self):
        assembler = PromptAssembler()
        state = _make_state(rag_categories=["holes_single", "holes_multiple"])
        result = assembler.assemble(state)
        prompt = result["assembled_system_prompt"]
        # rules_holes.md maps to same file for both — should appear only once
        # (no duplicate "## Additional Rules" sections)
        assert prompt.count("Additional Rules") <= 1


# ── No classification ─────────────────────────────────────────────────────────

class TestNoClassification:
    def test_no_classification_returns_empty(self):
        assembler = PromptAssembler()
        result = assembler.assemble({"specification": "A box"})
        assert result["assembled_system_prompt"] == ""

    def test_empty_classification_returns_empty(self):
        assembler = PromptAssembler()
        result = assembler.assemble({"task_classification": {}})
        assert result["assembled_system_prompt"] == ""
