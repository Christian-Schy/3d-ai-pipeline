"""
tests/agents/conftest.py — Session-scoped mocks für alle Agent-Tests.

sentence-transformers lädt ein 80MB Embedding-Modell beim ersten Import
von BaseRAG. Das macht jeden Test der einen Agent instantiiert langsam.

Fix: alle RAG-Klassen werden auf Session-Ebene durch MagicMocks ersetzt
bevor irgendein Test-Modul importiert wird. Das passiert einmalig und
gilt für die gesamte Test-Session.
"""

import pytest
from unittest.mock import MagicMock


def _make_fake_rag():
    fake = MagicMock()
    fake.return_value.query.return_value = ""
    fake.return_value.build.return_value = None
    # enrich_prompt must return a string — agents do `feedback in prompt`
    fake.return_value.enrich_prompt.side_effect = lambda prompt, desc: prompt
    return fake


@pytest.fixture(scope="session", autouse=True)
def mock_all_rag_classes():
    """Ersetzt alle RAG-Klassen session-weit — einmal, nicht per Test."""
    import unittest.mock as mock

    rag_paths = [
        # Note: src.rag.base_rag.BaseRAG is intentionally NOT mocked here.
        # Mocking the base class breaks tests/rag/ unit tests that need the real class.
        # We mock only the concrete subclasses used by agents.
        "src.rag.planner_rag.PlannerRAG",
        "src.rag.coder_rag.CoderRAG",
        "src.rag.interpreter_rag.InterpreterRAG",
        "src.agents.planner.PlannerRAG",
        "src.agents.coder.CoderRAG",
        "src.agents.interpreter.InterpreterRAG",
    ]

    patches = [mock.patch(path, _make_fake_rag()) for path in rag_paths]
    for p in patches:
        try:
            p.start()
        except AttributeError:
            pass  # Modul noch nicht importiert — kein Problem

    yield

    for p in patches:
        try:
            p.stop()
        except RuntimeError:
            pass
