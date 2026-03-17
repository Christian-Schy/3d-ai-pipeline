"""
tests/rag/test_base_rag.py — Tests for BaseRAG logic.

No real ChromaDB, no sentence-transformers — all external deps mocked.
Focus: the _built flag, dedup logic, and chunking.
"""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path


@pytest.fixture()
def fake_rag(tmp_path):
    """Return a BaseRAG instance with all external deps mocked.

    - chromadb.PersistentClient → MagicMock
    - sentence-transformers embedding function → MagicMock
    """
    with patch("src.rag.base_rag.chromadb.PersistentClient") as mock_client_cls, \
         patch("src.rag.base_rag.get_embed_fn") as mock_embed:

        mock_embed.return_value = MagicMock()

        mock_collection = MagicMock()
        mock_collection.count.return_value = 0
        mock_collection.get.return_value = {"ids": []}

        mock_client = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_client_cls.return_value = mock_client

        from src.rag.base_rag import BaseRAG

        rag = BaseRAG(db_path=str(tmp_path / "rag_db"))
        rag._collection = mock_collection
        yield rag, mock_collection


class TestBuiltFlag:
    """_built flag prevents double-build when knowledge_dir is empty."""

    def test_initially_false(self, fake_rag):
        rag, _ = fake_rag
        assert rag._built is False

    def test_set_to_true_after_build(self, fake_rag, tmp_path):
        rag, collection = fake_rag
        # Create an empty knowledge dir so build() doesn't raise
        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        rag.knowledge_dir = str(knowledge_dir)

        rag.build()
        assert rag._built is True

    def test_query_does_not_call_build_when_already_built(self, fake_rag):
        rag, collection = fake_rag
        rag._built = True
        collection.count.return_value = 0  # empty but already built

        with patch.object(rag, "build") as mock_build:
            rag.query("some description")
            mock_build.assert_not_called()

    def test_query_calls_build_when_not_built_and_empty(self, fake_rag, tmp_path):
        rag, collection = fake_rag
        rag._built = False
        collection.count.return_value = 0

        # build() is called — it may raise, but what matters is the call happened
        with patch.object(rag, "build") as mock_build:
            rag.query("some description")
            mock_build.assert_called_once()

    def test_query_skips_build_when_collection_has_chunks(self, fake_rag):
        """If collection already has chunks, build() is never triggered."""
        rag, collection = fake_rag
        rag._built = False
        collection.count.return_value = 5  # already populated

        collection.query.return_value = {
            "documents": [["chunk text"]],
            "metadatas": [[{"source": "test.md"}]],
            "distances": [[0.1]],
        }

        with patch.object(rag, "build") as mock_build:
            rag.query("description")
            mock_build.assert_not_called()


class TestChunking:
    """_split_into_chunks splits correctly for .md and .py files."""

    def get_rag(self, tmp_path):
        with patch("src.rag.base_rag.chromadb.PersistentClient"), \
             patch("src.rag.base_rag.get_embed_fn"):
            from src.rag.base_rag import BaseRAG
            rag = BaseRAG.__new__(BaseRAG)
            rag.collection_name = "test"
            rag.log = MagicMock()
            return rag

    def test_md_split_by_headers(self, tmp_path):
        rag = self.get_rag(tmp_path)
        content = "# Intro\nsome text\n## Section A\ncontent A\n## Section B\ncontent B"
        file_path = tmp_path / "test.md"
        file_path.write_text(content)
        chunks = rag._split_into_chunks(content, file_path)
        # Each ## section becomes a chunk
        assert len(chunks) >= 2
        texts = [c[0] for c in chunks]
        assert any("Section A" in t for t in texts)
        assert any("Section B" in t for t in texts)

    def test_py_split_by_blank_lines(self, tmp_path):
        rag = self.get_rag(tmp_path)
        content = (
            "def foo():\n    \"\"\"Does something useful here.\"\"\"\n    pass\n\n\n"
            "def bar():\n    \"\"\"Returns a meaningful result.\"\"\"\n    return 42\n\n\n"
            "class Baz:\n    \"\"\"A class with some real content.\"\"\"\n    x = 1\n"
        )
        file_path = tmp_path / "test.py"
        file_path.write_text(content)
        chunks = rag._split_into_chunks(content, file_path)
        assert len(chunks) == 3

    def test_short_py_blocks_skipped(self, tmp_path):
        """Blocks shorter than 30 chars are skipped (noise filter)."""
        rag = self.get_rag(tmp_path)
        content = "x = 1\n\n\ndef longer_function():\n    return 'something useful here'\n"
        file_path = tmp_path / "test.py"
        file_path.write_text(content)
        chunks = rag._split_into_chunks(content, file_path)
        texts = [c[0] for c in chunks]
        assert not any(t == "x = 1" for t in texts)

    def test_chunk_ids_are_stable(self, tmp_path):
        """Same file + index always produces the same chunk ID."""
        rag = self.get_rag(tmp_path)
        content = "## Section\nsome content"
        file_path = tmp_path / "test.md"
        chunks1 = rag._split_into_chunks(content, file_path)
        chunks2 = rag._split_into_chunks(content, file_path)
        ids1 = [c[1] for c in chunks1]
        ids2 = [c[1] for c in chunks2]
        assert ids1 == ids2

    def test_md_chunk_type_is_documentation(self, tmp_path):
        rag = self.get_rag(tmp_path)
        content = "## Example\nsome docs"
        file_path = tmp_path / "example.md"
        chunks = rag._split_into_chunks(content, file_path)
        assert all(c[2]["type"] == "documentation" for c in chunks)

    def test_py_chunk_type_is_code_example(self, tmp_path):
        rag = self.get_rag(tmp_path)
        content = "def my_function():\n    return 'hello world from function'\n"
        file_path = tmp_path / "example.py"
        chunks = rag._split_into_chunks(content, file_path)
        assert all(c[2]["type"] == "code_example" for c in chunks)
