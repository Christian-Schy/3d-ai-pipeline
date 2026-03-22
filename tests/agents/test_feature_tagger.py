"""
tests/agents/test_feature_tagger.py — Unit tests for FeatureTaggerAgent.

LLM and RAG are mocked.
"""

import pytest
from unittest.mock import MagicMock, patch


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_agent():
    """Create FeatureTaggerAgent with mocked RAG."""
    with patch("src.agents.feature_tagger.FeatureTaggerRAG") as MockRAG:
        fake_rag = MagicMock()
        fake_rag.return_value.build.return_value = None
        fake_rag.return_value.enrich_prompt.side_effect = lambda prompt, desc: prompt
        MockRAG.return_value = fake_rag.return_value
        from src.agents.feature_tagger import FeatureTaggerAgent
        agent = FeatureTaggerAgent()
        agent._rag = fake_rag.return_value
        agent._rag_ready = True
        return agent


def _mock_call_json(agent, return_value: dict):
    agent.call_json = MagicMock(return_value=return_value)


# ── rag_queries from features[].rag_tags ─────────────────────────────────────

class TestRagQueriesFromFeatureTags:
    """Regression: rag_queries must be collected from features[].rag_tags, not top-level rag_queries."""

    def test_rag_queries_collected_from_feature_tags(self):
        agent = _make_agent()
        _mock_call_json(agent, {
            "features": [
                {"id": "base", "type": "box", "rag_tags": ["box_primitive", "basic_shape"]},
                {"id": "hole", "type": "hole", "rag_tags": ["hole_through", "drilling"]},
            ],
            "dependencies": [],
            "task_classification": {
                "task_type": "complex_multi_step",
                "difficulty": "low",
                "requires_current_geometry": False,
                "rag_categories": ["holes_single"],
                "planner_template": "template_feature_subtract",
                "warnings": [],
            },
        })
        result = agent.tag({"specification": "Box with a through hole"})
        rag_queries = result["feature_tree"]["rag_queries"]
        assert "box_primitive" in rag_queries
        assert "basic_shape" in rag_queries
        assert "hole_through" in rag_queries
        assert "drilling" in rag_queries

    def test_rag_queries_deduplicated(self):
        agent = _make_agent()
        _mock_call_json(agent, {
            "features": [
                {"id": "base", "type": "box", "rag_tags": ["primitive", "box"]},
                {"id": "hole", "type": "hole", "rag_tags": ["primitive", "hole"]},
            ],
            "dependencies": [],
            "task_classification": {
                "task_type": "simple_primitive",
                "difficulty": "low",
                "requires_current_geometry": False,
                "rag_categories": [],
                "planner_template": "template_simple",
                "warnings": [],
            },
        })
        result = agent.tag({"specification": "A box"})
        rag_queries = result["feature_tree"]["rag_queries"]
        # "primitive" appears in both features — must be deduplicated
        assert rag_queries.count("primitive") == 1

    def test_top_level_rag_queries_used_if_present(self):
        """If LLM outputs top-level rag_queries, use those directly."""
        agent = _make_agent()
        _mock_call_json(agent, {
            "features": [
                {"id": "base", "type": "box", "rag_tags": ["box_primitive"]},
            ],
            "rag_queries": ["explicit_query_1", "explicit_query_2"],
            "dependencies": [],
            "task_classification": {
                "task_type": "simple_primitive",
                "difficulty": "low",
                "requires_current_geometry": False,
                "rag_categories": [],
                "planner_template": "template_simple",
                "warnings": [],
            },
        })
        result = agent.tag({"specification": "A box"})
        rag_queries = result["feature_tree"]["rag_queries"]
        # Top-level takes priority
        assert "explicit_query_1" in rag_queries
        assert "explicit_query_2" in rag_queries


# ── task_classification output ────────────────────────────────────────────────

class TestTaskClassificationOutput:
    def test_task_classification_fields_present(self):
        agent = _make_agent()
        _mock_call_json(agent, {
            "features": [{"id": "base", "type": "box", "rag_tags": []}],
            "dependencies": [],
            "task_classification": {
                "task_type": "simple_primitive",
                "difficulty": "low",
                "requires_current_geometry": False,
                "rag_categories": ["primitives"],
                "planner_template": "template_simple",
                "warnings": [],
            },
        })
        result = agent.tag({"specification": "A box"})
        tc = result["task_classification"]
        assert "task_type" in tc
        assert "planner_template" in tc
        assert "rag_categories" in tc
        assert "warnings" in tc

    def test_feature_tree_output_keys(self):
        agent = _make_agent()
        _mock_call_json(agent, {
            "features": [],
            "dependencies": [],
            "task_classification": {
                "task_type": "complex_multi_step",
                "difficulty": "high",
                "requires_current_geometry": False,
                "rag_categories": [],
                "planner_template": "template_complex",
                "warnings": [],
            },
        })
        result = agent.tag({"specification": "Something complex"})
        assert "feature_tree" in result
        assert "features_identified" in result["feature_tree"]
        assert "dependencies" in result["feature_tree"]
        assert "rag_queries" in result["feature_tree"]


# ── interpreter_features hint ─────────────────────────────────────────────────

class TestInterpreterFeaturesHint:
    def test_interpreter_features_included_in_prompt(self):
        agent = _make_agent()
        captured_prompt = []

        def mock_call_json(prompt, system=None):
            captured_prompt.append(prompt)
            return {
                "features": [{"id": "base", "type": "box", "rag_tags": []}],
                "dependencies": [],
                "task_classification": {
                    "task_type": "simple_primitive", "difficulty": "low",
                    "requires_current_geometry": False, "rag_categories": [],
                    "planner_template": "template_simple", "warnings": [],
                },
            }

        agent.call_json = mock_call_json
        state = {
            "specification": "A box",
            "interpreter_features": [
                "base: Box 50×50×20mm, Parent=none",
                "hole: ∅10mm, Parent=base, Face=+Z, Offset=(0,0)",
            ],
        }
        agent.tag(state)
        assert captured_prompt, "call_json was never called"
        prompt = captured_prompt[0]
        assert "Interpreter pre-analysis" in prompt
        assert "base: Box 50×50×20mm" in prompt

    def test_no_hint_if_interpreter_features_empty(self):
        agent = _make_agent()
        captured_prompt = []

        def mock_call_json(prompt, system=None):
            captured_prompt.append(prompt)
            return {
                "features": [],
                "dependencies": [],
                "task_classification": {
                    "task_type": "simple_primitive", "difficulty": "low",
                    "requires_current_geometry": False, "rag_categories": [],
                    "planner_template": "template_simple", "warnings": [],
                },
            }

        agent.call_json = mock_call_json
        agent.tag({"specification": "A box", "interpreter_features": []})
        assert "Interpreter pre-analysis" not in captured_prompt[0]


# ── Fallback on LLM error ─────────────────────────────────────────────────────

class TestFallback:
    def test_fallback_on_connection_error(self):
        agent = _make_agent()
        agent.call_json = MagicMock(side_effect=ConnectionRefusedError("Ollama not running"))
        result = agent.tag({"specification": "A box"})
        assert "feature_tree" in result
        assert "task_classification" in result
        # Fallback defaults to complex template
        assert result["task_classification"]["planner_template"] == "template_complex"

    def test_fallback_on_value_error(self):
        agent = _make_agent()
        agent.call_json = MagicMock(side_effect=ValueError("Bad JSON"))
        result = agent.tag({"specification": "Something"})
        assert result["feature_tree"]["rag_queries"] == []
