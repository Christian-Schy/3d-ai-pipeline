"""
tests/agents/test_interpreter.py — Tests for the Interpreter agent and dialog loop.

Performance rule: no real RAG, no real Ollama.
  - InterpreterAgent._rag is mocked at fixture level → no ChromaDB, no model load
  - call_json is mocked per test → no Ollama needed
  - Total test time should be < 2 seconds
"""

import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Fixture: patch RAG so no ChromaDB or sentence-transformers loads
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def no_rag(monkeypatch):
    """Prevent any RAG from loading during interpreter tests."""
    monkeypatch.setattr(
        "src.agents.interpreter.InterpreterRAG",
        lambda: MagicMock(_rag_ready=True, build=MagicMock(), enrich_prompt=lambda p, d: p),
    )


def make_state(description="A 30mm cube", messages=None):
    return {
        "description": description,
        "messages": messages or [],
        "specification": "",
        "is_complete": False,
    }


# ---------------------------------------------------------------------------
# InterpreterAgent unit tests
# ---------------------------------------------------------------------------

class TestInterpreterAgent:

    def test_complete_request_returns_spec(self):
        from src.agents.interpreter import InterpreterAgent
        agent = InterpreterAgent()
        with patch.object(agent, "call_json", return_value={
            "is_complete": True,
            "question": "",
            "specification": "Cube 30x30x30mm, solid, no holes.",
        }):
            result = agent.process(make_state("A 30mm cube"))
        assert result["is_complete"] is True
        assert result["specification"] == "Cube 30x30x30mm, solid, no holes."

    def test_vague_request_returns_question(self):
        from src.agents.interpreter import InterpreterAgent
        agent = InterpreterAgent()
        with patch.object(agent, "call_json", return_value={
            "is_complete": False,
            "question": "What dimensions should the box have (L x W x H in mm)?",
            "specification": "",
        }):
            result = agent.process(make_state("a box"))
        assert result["is_complete"] is False
        assert len(result["question"]) > 0

    def test_fallback_on_ollama_error(self):
        """If Ollama is down: treat description as complete."""
        from src.agents.interpreter import InterpreterAgent
        agent = InterpreterAgent()
        with patch.object(agent, "call_json", side_effect=ConnectionRefusedError("down")):
            result = agent.process(make_state("A bracket with two holes"))
        assert result["is_complete"] is True
        assert result["specification"] == "A bracket with two holes"

    def test_format_history_empty(self):
        from src.agents.interpreter import InterpreterAgent
        agent = InterpreterAgent()
        assert agent._format_history([]) == ""

    def test_format_history_with_messages(self):
        from langchain_core.messages import AIMessage, HumanMessage
        from src.agents.interpreter import InterpreterAgent
        agent = InterpreterAgent()
        messages = [
            AIMessage(content="What dimensions?"),
            HumanMessage(content="30x20x10mm"),
        ]
        history = agent._format_history(messages)
        assert "30x20x10mm" in history
        assert "What dimensions?" in history

    def test_missing_spec_key_doesnt_crash(self):
        from src.agents.interpreter import InterpreterAgent
        agent = InterpreterAgent()
        with patch.object(agent, "call_json", return_value={"is_complete": True}):
            result = agent.process(make_state("test"))
        assert result["is_complete"] is True
        assert isinstance(result["specification"], str)


# ---------------------------------------------------------------------------
# PipelineRunner dialog loop tests (graph is fully mocked)
# ---------------------------------------------------------------------------

class TestPipelineRunnerDialog:

    def test_run_no_interrupts(self):
        """Simple description completes without dialog."""
        from src.graph.pipeline import PipelineRunner
        runner = PipelineRunner()
        mock_pipeline = MagicMock()
        mock_pipeline.invoke.return_value = {
            "stl_path": "/tmp/test.stl",
            "execution_error": "", "validation_error": "",
            "validator_feedback": "", "attempts": 0, "semantic_attempts": 0,
        }
        mock_pipeline.get_state.return_value = MagicMock(tasks=[])
        runner._pipeline = mock_pipeline

        state = runner.run("A 30mm cube", ask_user=None)
        assert state["stl_path"] == "/tmp/test.stl"
        mock_pipeline.invoke.assert_called_once()

    def test_ask_user_called_on_interrupt(self):
        """ask_user callback fires when graph is interrupted."""
        from src.graph.pipeline import PipelineRunner
        runner = PipelineRunner()
        mock_pipeline = MagicMock()

        mock_pipeline.invoke.side_effect = [
            {"stl_path": "", "execution_error": ""},
            {"stl_path": "/tmp/done.stl", "execution_error": "",
             "validation_error": "", "validator_feedback": "",
             "attempts": 0, "semantic_attempts": 0},
        ]
        interrupted_task = MagicMock()
        interrupted_task.interrupts = [MagicMock(value="What dimensions?")]
        mock_pipeline.get_state.side_effect = [
            MagicMock(tasks=[interrupted_task]),
            MagicMock(tasks=[interrupted_task]),
            MagicMock(tasks=[]),
        ]

        ask_user = MagicMock(return_value="30x30x30mm")
        runner._pipeline = mock_pipeline
        state = runner.run("a box", ask_user=ask_user)

        ask_user.assert_called_once_with("What dimensions?")
        assert state["stl_path"] == "/tmp/done.stl"