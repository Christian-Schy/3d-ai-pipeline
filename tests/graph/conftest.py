"""
tests/graph/conftest.py — Stub agents for graph/pipeline smoke tests.

All agents are patched via the get_agent() registry and _get_sandbox_instance()
in execution_nodes so that no Ollama, RAG, or filesystem writes happen.
"""

import pytest
from unittest.mock import MagicMock


def _make_interpreter_stub():
    """Stub: marks spec as complete on first call."""
    stub = MagicMock()
    stub.process.return_value = {
        "specification": "A 30mm cube with flat top",
        "messages": [],
        "is_complete": True,
        "interpreter_features": [],
    }
    stub._format_history = MagicMock(return_value="")
    stub._rag = None
    return stub


def _make_planner_stub():
    stub = MagicMock()
    stub.run.return_value = {
        "blueprint": {
            "description": "30mm cube",
            "root": {"type": "box", "x": 30.0, "y": 30.0, "z": 30.0},
        }
    }
    stub._rag = None
    return stub


def _make_coder_stub():
    stub = MagicMock()
    stub.run.return_value = {
        "code": (
            "import cadquery as cq\n"
            "result = cq.Workplane('XY').box(30, 30, 30)\n"
        )
    }
    stub._rag = None
    return stub


def _make_validator_stub():
    """Stub: always approves — sets validator_feedback to empty.

    stats must be a real dict (not MagicMock) — LangGraph serializes state
    via msgpack and cannot handle MagicMock objects.
    """
    result = MagicMock()
    result.ok = True
    result.feedback = ""
    result.stats = {}   # real dict, not MagicMock
    stub = MagicMock()
    stub.check.return_value = result
    return stub


def _make_sandbox_stub():
    stub = MagicMock()
    run_result = MagicMock()
    run_result.success = True
    run_result.error = ""
    stub.run.return_value = run_result
    return stub


def _make_code_fixer_stub():
    stub = MagicMock()
    stub.diagnose.return_value = {"fix_plan": "stub fix plan"}
    return stub


def _make_mod_interp_stub():
    stub = MagicMock()
    stub.classify.return_value = {
        "is_modification": False,
        "is_additive": False,
        "change_description": "",
        "changed_features": [],
        "reasoning": "stub",
    }
    return stub


def _make_feature_tagger_stub():
    stub = MagicMock()
    stub.tag.return_value = {
        "feature_tree": {
            "features_identified": [],
            "dependencies": [],
            "rag_queries": [],
        },
        "task_classification": {
            "task_type": "primitive_single",
            "difficulty": "low",
            "requires_current_geometry": False,
            "rag_categories": [],
            "planner_template": "template_simple",
            "warnings": [],
        },
    }
    return stub


def _make_function_decomposer_stub():
    stub = MagicMock()
    stub.decompose.return_value = {"code_skeleton": ""}
    return stub


def _make_prompt_asm_stub():
    stub = MagicMock()
    stub.assemble.return_value = {"assembled_system_prompt": ""}
    stub._planner_rag = None
    return stub


def _make_plan_val_stub():
    stub = MagicMock()
    stub.validate.return_value = {"plan_valid": True, "plan_validation_issues": ""}
    return stub


@pytest.fixture(autouse=True)
def stub_all_nodes(monkeypatch):
    """Replace every agent via the get_agent() registry with stubs.

    Also patches _get_sandbox_instance() in execution_nodes.
    Runs for every test in tests/graph/ — keeps smoke tests fast
    and independent of Ollama / RAG / sandbox.
    """
    from src.agents.interpreter import InterpreterAgent
    from src.agents.planner import PlannerAgent
    from src.agents.coder import CoderAgent
    from src.agents.validator import ValidatorAgent
    from src.agents.code_fixer import CodeFixerAgent
    from src.agents.modification_interpreter import ModificationInterpreterAgent
    from src.agents.feature_tagger import FeatureTaggerAgent
    from src.agents.function_decomposer import FunctionDecomposerAgent
    from src.agents.prompt_assembler import PromptAssembler
    from src.agents.plan_validator import PlanValidatorAgent

    # Build a class→stub mapping
    _stubs = {
        InterpreterAgent: _make_interpreter_stub(),
        PlannerAgent: _make_planner_stub(),
        CoderAgent: _make_coder_stub(),
        ValidatorAgent: _make_validator_stub(),
        CodeFixerAgent: _make_code_fixer_stub(),
        ModificationInterpreterAgent: _make_mod_interp_stub(),
        FeatureTaggerAgent: _make_feature_tagger_stub(),
        FunctionDecomposerAgent: _make_function_decomposer_stub(),
        PromptAssembler: _make_prompt_asm_stub(),
        PlanValidatorAgent: _make_plan_val_stub(),
    }

    def _fake_get_agent(agent_class):
        return _stubs.get(agent_class, MagicMock())

    import src.graph.nodes._registry as registry
    monkeypatch.setattr(registry, "get_agent", _fake_get_agent)

    # Also patch each node submodule that imported get_agent at module level
    import src.graph.nodes.input_nodes as inp
    import src.graph.nodes.planning_nodes as plan
    import src.graph.nodes.execution_nodes as exec_
    import src.graph.nodes.validation_nodes as val

    monkeypatch.setattr(inp, "get_agent", _fake_get_agent)
    monkeypatch.setattr(plan, "get_agent", _fake_get_agent)
    monkeypatch.setattr(exec_, "get_agent", _fake_get_agent)
    monkeypatch.setattr(val, "get_agent", _fake_get_agent)

    # Patch sandbox — it's not managed by get_agent
    monkeypatch.setattr(exec_, "_get_sandbox_instance", _make_sandbox_stub)
