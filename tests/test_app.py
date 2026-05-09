"""
tests/test_app.py — Tests for the Gradio UI callbacks and SessionState.

We test callback functions and session logic directly — no browser, no Gradio server.
The pipeline is fully mocked so no Ollama or RAG loads.
"""

import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def mock_pipeline_runner(monkeypatch):
    """Prevent real PipelineRunner from instantiating during import."""
    monkeypatch.setattr(
        "src.graph.pipeline.PipelineRunner.__init__",
        lambda self: None,
    )


# ---------------------------------------------------------------------------
# SessionState
# ---------------------------------------------------------------------------

class TestSessionState:
    """Tests for SessionState history management."""

    def make_session(self):
        from app import SessionState
        session = SessionState.__new__(SessionState)
        session.runner = MagicMock()
        session.last_result = None
        session.history = []
        session.last_run_id = ""
        session.pending_question = None
        session.user_answer = ""
        session.is_running = False
        import threading
        session.answer_event = threading.Event()
        return session

    def make_result(self, stl="/tmp/model_a.stl", description="A 30mm cube"):
        return {"stl_path": stl, "description": description, "blueprint": {}, "code": ""}

    def test_push_to_history_adds_entry(self):
        session = self.make_session()
        session.last_result = self.make_result()
        session.push_to_history()
        assert len(session.history) == 1

    def test_push_to_history_deduplicates_by_stl_path(self):
        """Calling push_to_history twice for the same stl_path adds only one entry."""
        session = self.make_session()
        session.last_result = self.make_result(stl="/tmp/same.stl")
        session.push_to_history()
        session.push_to_history()
        assert len(session.history) == 1

    def test_push_to_history_ignores_empty_last_result(self):
        session = self.make_session()
        session.last_result = None
        session.push_to_history()
        assert len(session.history) == 0

    def test_push_to_history_ignores_result_without_stl(self):
        session = self.make_session()
        session.last_result = {"stl_path": "", "description": "failed run"}
        session.push_to_history()
        assert len(session.history) == 0

    def test_get_history_choices_newest_first(self):
        """History choices are returned in reverse order (newest first)."""
        session = self.make_session()
        session.last_result = self.make_result("/tmp/a.stl", "Model A")
        session.push_to_history()
        session.last_result = self.make_result("/tmp/b.stl", "Model B")
        session.push_to_history()

        choices = session.get_history_choices()
        assert len(choices) == 2
        # [1] is newest (B), [2] is oldest (A)
        assert "Model B" in choices[0]
        assert "Model A" in choices[1]

    def test_get_history_choices_empty_when_no_history(self):
        session = self.make_session()
        assert session.get_history_choices() == []

    def test_restore_returns_correct_state(self):
        session = self.make_session()
        state_a = self.make_result("/tmp/a.stl", "Model A")
        state_b = self.make_result("/tmp/b.stl", "Model B")
        session.last_result = state_a
        session.push_to_history()
        session.last_result = state_b
        session.push_to_history()

        choices = session.get_history_choices()
        # choices[0] = newest = Model B
        restored = session.restore(choices[0])
        assert restored["stl_path"] == "/tmp/b.stl"

    def test_restore_returns_none_for_invalid_choice(self):
        session = self.make_session()
        assert session.restore("[1] Nonexistent") is None

    def test_history_capped_at_max(self):
        """History never exceeds MAX_HISTORY entries."""
        from app import SessionState
        session = self.make_session()
        for i in range(SessionState.MAX_HISTORY + 3):
            session.last_result = self.make_result(f"/tmp/model_{i}.stl", f"Model {i}")
            session.push_to_history()
        assert len(session.history) == SessionState.MAX_HISTORY

    def test_reset_for_new_run_clears_state(self):
        session = self.make_session()
        session.pending_question = "old question"
        session.user_answer = "old answer"
        session.reset_for_new_run()
        assert session.pending_question is None
        assert session.user_answer == ""
        assert session.is_running is True


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

class TestCallbacks:
    """Callback functions return correct gr.update() values."""

    def test_on_submit_empty_input_keeps_btn_interactive(self):
        from app import on_unified_submit, _session
        _session.last_result = None
        _session.pending_question = None
        chat_display, question_row, submit_btn, new_model_btn, desc_input = on_unified_submit("", None)
        assert submit_btn["interactive"] is True

    def test_on_submit_valid_starts_thread(self):
        from app import on_unified_submit, _session
        _session.is_running = False
        _session.last_result = None
        _session.pending_question = None
        _session.runner = MagicMock()

        with patch("threading.Thread") as mock_thread:
            mock_thread.return_value.start = MagicMock()
            chat_display, question_row, submit_btn, new_model_btn, desc_input = on_unified_submit("A 30mm cube", None)

        mock_thread.assert_called_once()
        assert submit_btn["interactive"] is False

    def test_on_submit_with_image_starts_thread(self):
        """Image path triggers same start-thread flow as text."""
        from app import on_unified_submit, _session
        _session.is_running = False
        _session.last_result = None
        _session.pending_question = None
        _session.runner = MagicMock()

        with patch("threading.Thread") as mock_thread:
            mock_thread.return_value.start = MagicMock()
            chat_display, question_row, submit_btn, new_model_btn, desc_input = on_unified_submit("", "/tmp/sketch.png")

        mock_thread.assert_called_once()

    def test_on_answer_submit_no_question_pending(self):
        from app import on_unified_submit, _session
        _session.pending_question = None
        _session.last_result = None
        _session.runner = MagicMock()
        with patch("threading.Thread") as mock_thread:
            mock_thread.return_value.start = MagicMock()
            result = on_unified_submit("30mm", None)
        assert result is not None

    def test_on_modify_without_previous_result_starts_generate(self):
        from app import on_unified_submit, _session
        _session.last_result = None
        _session.pending_question = None
        _session.runner = MagicMock()
        with patch("threading.Thread") as mock_thread:
            mock_thread.return_value.start = MagicMock()
            chat_display, question_row, submit_btn, new_model_btn, desc_input = on_unified_submit("Make it bigger", None)
        # No previous model — falls through to generate mode
        mock_thread.assert_called_once()

    def test_on_modify_empty_input_keeps_btn_interactive(self):
        from app import on_unified_submit, _session
        _session.last_result = None
        _session.pending_question = None
        chat_display, question_row, submit_btn, new_model_btn, desc_input = on_unified_submit("", None)
        assert submit_btn["interactive"] is True

    def test_on_restore_history_invalid_choice_returns_no_ops(self):
        from app import on_restore_history, _session
        _session.history = []
        result = on_restore_history("[1] Nonexistent Model")
        # Should return one no-op gr.update() per restore output.
        assert len(result) == 11

    def test_on_thumb_good_returns_update(self):
        from app import on_thumb_good, _session
        _session.last_run_id = ""  # no run — just check return value
        result = on_thumb_good()
        assert "👍" in result["value"]

    def test_on_thumb_bad_returns_update(self):
        from app import on_thumb_bad, _session
        _session.last_run_id = ""
        result = on_thumb_bad()
        assert "👎" in result["value"]
