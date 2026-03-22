"""
src/rag/base_rag.py — Shared ChromaDB logic for all RAG instances.

Every agent-specific RAG (CoderRAG, PlannerRAG, ...) inherits from here.
The common parts live once:
  - ChromaDB client setup
  - Embedding function (sentence-transformers, runs locally on CPU)
  - build(): load files from a knowledge dir → split → store as vectors
  - query(): find the most relevant chunks for a given description
  - enrich_prompt(): inject retrieved context into a prompt string

Subclasses only need to set:
  collection_name  — unique name in ChromaDB (e.g. "coder_knowledge")
  knowledge_dir    — where the .py / .md knowledge files live
"""

import hashlib
import os
import structlog
from pathlib import Path

# Prevent sentence-transformers from checking HuggingFace for updates at startup.
# The model is fully cached locally — no internet needed.
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_DATASETS_OFFLINE", "1")

import chromadb
from chromadb.utils import embedding_functions

log = structlog.get_logger()

# Runs locally on CPU — 80 MB, fast, good for technical text
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Fallback chunk count — used when no per-agent config is found
DEFAULT_N_RESULTS = 4

# Module-level cache — SentenceTransformer loads once, shared across all RAG instances.
# Without this, every RAG subclass instantiation triggers a fresh 80MB model load.
_cached_embed_fn: "embedding_functions.SentenceTransformerEmbeddingFunction | None" = None


def get_embed_fn() -> embedding_functions.SentenceTransformerEmbeddingFunction:
    """Return a cached ChromaDB embedding function.

    First call takes ~3-5s (model load). All subsequent calls are instant.
    Call this at app startup to pre-warm the model before the first user request.
    """
    global _cached_embed_fn
    if _cached_embed_fn is None:
        _cached_embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL
        )
    return _cached_embed_fn


class BaseRAG:
    """Foundation for all agent-specific RAG instances.

    Handles ChromaDB setup, file ingestion, vector search, and
    prompt enrichment. Subclasses configure collection_name,
    knowledge_dir, and agent_name — no other overrides needed.
    """

    collection_name: str = "base_knowledge"
    knowledge_dir: str = "data/knowledge/base"
    # Set in subclasses to look up per-agent n_results from config.
    # e.g. "planner" → cfg.rag.n_results.planner
    agent_name: str = ""

    def __init__(self, db_path: str = "data/rag_db"):
        self._db_path = Path(db_path)
        self._db_path.mkdir(parents=True, exist_ok=True)
        self.last_chunks_used: list[str] = []  # updated after each enrich_prompt() call

        self._client = chromadb.PersistentClient(path=str(self._db_path))

        # Shared embedding function — loaded once, reused across all RAG instances
        self._embed_fn = get_embed_fn()

        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=self._embed_fn,
            metadata={"hnsw:space": "cosine"},
        )

        # Per-agent n_results from config — falls back to DEFAULT_N_RESULTS
        from src.config.loader import get_config
        cfg_n = get_config().rag.n_results
        self._n_results: int = (
            getattr(cfg_n, self.agent_name, None) or DEFAULT_N_RESULTS
            if self.agent_name else DEFAULT_N_RESULTS
        )

        # Tracks whether build() has been called at least once.
        # Prevents query() from re-triggering build() when knowledge_dir is empty
        # but _ensure_rag() already called build() and found nothing.
        self._built: bool = False

        self.log = structlog.get_logger().bind(rag=self.collection_name)
        self.log.info("rag_initialized",
                      existing_chunks=self._collection.count(),
                      n_results=self._n_results)

    # ------------------------------------------------------------------
    # Building the vector database
    # ------------------------------------------------------------------

    def build(self, force_rebuild: bool = False) -> int:
        """Load all knowledge files and store them as vectors.

        Skips chunks that haven't changed (stable ID based on filename+index).
        Call this once at startup — subsequent calls are fast (nothing to add).

        Returns the total chunk count after building.
        """
        if force_rebuild:
            self.log.info("rag_rebuild_forced")
            self._client.delete_collection(self.collection_name)
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                embedding_function=self._embed_fn,
                metadata={"hnsw:space": "cosine"},
            )

        knowledge_path = Path(self.knowledge_dir)
        if not knowledge_path.exists():
            self.log.error("rag_knowledge_dir_missing", path=str(knowledge_path))
            raise FileNotFoundError(
                f"Knowledge directory not found: {knowledge_path}\n"
                f"Create it and add .py / .md knowledge files."
            )

        files_processed = 0
        chunks_added = 0

        for file_path in sorted(knowledge_path.rglob("*")):
            if file_path.suffix not in (".py", ".md") or file_path.is_dir():
                continue

            content = file_path.read_text(encoding="utf-8")
            chunks = self._split_into_chunks(content, file_path)

            for chunk_text, chunk_id, metadata in chunks:
                if self._chunk_exists(chunk_id):
                    continue
                self._collection.add(
                    documents=[chunk_text],
                    ids=[chunk_id],
                    metadatas=[metadata],
                )
                chunks_added += 1

            files_processed += 1

        total = self._collection.count()
        self._built = True
        self.log.info("rag_build_complete",
                      files=files_processed,
                      new_chunks=chunks_added,
                      total_chunks=total)
        return total

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def query(self, description: str, n_results: int = 0) -> list[dict]:
        """Find the most relevant chunks for a description.

        Returns list of dicts: {'text': ..., 'source': ..., 'distance': ...}
        Lower distance = more similar. Typical range: 0.0 (identical) – 2.0 (unrelated).
        """
        if self._collection.count() == 0 and not self._built:
            # Lazy build — only if build() hasn't been called yet.
            # Prevents double-build when knowledge_dir is empty.
            self.log.warning("rag_empty_building_now")
            self.build()

        effective_n = n_results if n_results > 0 else self._n_results
        n = min(effective_n, self._collection.count())
        if n == 0:
            return []

        results = self._collection.query(
            query_texts=[description],
            n_results=n,
        )

        chunks = [
            {
                "text": doc,
                "source": results["metadatas"][0][i].get("source", "unknown"),
                "distance": results["distances"][0][i],
            }
            for i, doc in enumerate(results["documents"][0])
        ]

        self.log.info("rag_query",
                      description=description[:60],
                      results=len(chunks),
                      top_distance=round(chunks[0]["distance"], 3) if chunks else None)
        return chunks

    def query_filtered(self, description: str, n_results: int = 0, source: str = "") -> list[dict]:
        """Like query() but restricts results to a specific source file.

        Args:
            description: The query text.
            n_results:   Max chunks to return (0 = use per-agent default).
            source:      Filename to filter by (e.g. "examples_feature_subtract.md").
                         If empty, falls back to unfiltered query().

        Returns:
            Same format as query(): list of {'text', 'source', 'distance'}.
            Returns [] if no matching chunks found — caller should fall back.
        """
        if not source:
            return self.query(description, n_results)

        if self._collection.count() == 0 and not self._built:
            self.log.warning("rag_empty_building_now")
            self.build()

        effective_n = n_results if n_results > 0 else self._n_results
        where = {"source": source}

        # Count available docs for this source to avoid ChromaDB error (n > available)
        try:
            matching = self._collection.get(where=where)
            available = len(matching["ids"])
        except Exception:
            available = 0

        n = min(effective_n, available)
        if n == 0:
            return []

        results = self._collection.query(
            query_texts=[description],
            n_results=n,
            where=where,
        )

        chunks = [
            {
                "text": doc,
                "source": results["metadatas"][0][i].get("source", "unknown"),
                "distance": results["distances"][0][i],
            }
            for i, doc in enumerate(results["documents"][0])
        ]

        self.log.info("rag_query_filtered",
                      source=source,
                      description=description[:60],
                      results=len(chunks))
        return chunks

    def enrich_prompt(self, prompt: str, description: str) -> str:
        """Inject retrieved context into a prompt string.

        Inserts a '## Relevant Reference' section right before the blueprint
        block (looks for 'blueprint:' in the prompt, case-insensitive).
        Falls back to prepending if no blueprint marker found.

        After each call, self.last_chunks_used is updated with the source
        names of injected chunks (empty list if no chunks were retrieved).
        This is the main entry point used by agents.
        """
        chunks = self.query(description)
        self.last_chunks_used = list(dict.fromkeys(c["source"] for c in chunks))
        if not chunks:
            return prompt

        context_parts = ["\n## Relevant Reference\n"]
        context_parts.append(
            "The following examples are relevant to this task. "
            "Use them as reference — adapt to the specific blueprint.\n"
        )
        for i, chunk in enumerate(chunks):
            context_parts.append(f"\n### Reference {i + 1} (from {chunk['source']}):\n")
            context_parts.append(f"```\n{chunk['text']}\n```\n")

        context = "\n".join(context_parts)

        # Insert context before the blueprint section if present
        lower = prompt.lower()
        if "blueprint:" in lower:
            split_at = lower.find("blueprint:")
            insert_at = prompt.find("\n\n", split_at)
            if insert_at > 0:
                enriched = prompt[:insert_at] + "\n\n" + context + "\n" + prompt[insert_at:]
            else:
                enriched = prompt + "\n\n" + context
        else:
            enriched = context + "\n\n" + prompt

        self.log.info("rag_prompt_enriched",
                      original_len=len(prompt),
                      enriched_len=len(enriched),
                      chunks_injected=len(chunks))
        return enriched

    def add_example(
        self,
        doc_text: str,
        doc_id: str = "",
        metadata: dict | None = None,
    ) -> bool:
        """Add a single document to the collection (used for auto-learning).

        Skips silently if the document already exists (idempotent).
        Returns True if added, False if already present or empty.
        """
        if not doc_text.strip():
            return False
        if not doc_id:
            doc_id = hashlib.md5(doc_text.encode()).hexdigest()
        if self._chunk_exists(doc_id):
            return False
        self._collection.add(
            documents=[doc_text],
            ids=[doc_id],
            metadatas=[metadata or {"source": "auto_learned.py", "type": "auto_learned"}],
        )
        self.log.info("rag_example_added", doc_id=doc_id[:8])
        return True

    @property
    def chunk_count(self) -> int:
        return self._collection.count()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _split_into_chunks(
        self, content: str, file_path: Path
    ) -> list[tuple[str, str, dict]]:
        """Split file content into indexable chunks.

        .md  → split by '## ' headers (each section = one chunk)
        .py  → split by triple blank lines (each logical block = one chunk)
        """
        chunks = []
        source_name = file_path.name

        if file_path.suffix == ".md":
            sections = content.split("\n## ")
            for i, section in enumerate(sections):
                text = section.strip()
                if not text:
                    continue
                chunk_id = self._make_id(file_path, text)
                chunks.append((text, chunk_id, {
                    "source": source_name,
                    "type": "documentation",
                    "index": i,
                }))
        else:  # .py
            blocks = content.split("\n\n\n")
            for i, block in enumerate(blocks):
                text = block.strip()
                if len(text) < 30:
                    continue
                chunk_id = self._make_id(file_path, text)
                chunks.append((text, chunk_id, {
                    "source": source_name,
                    "type": "code_example",
                    "index": i,
                }))

        return chunks

    def _make_id(self, file_path: Path, chunk_text: str) -> str:
        """Content-hash ID: changes when chunk text changes → auto re-embed."""
        raw = f"{self.collection_name}_{file_path.name}_{chunk_text}"
        return hashlib.md5(raw.encode()).hexdigest()

    def _chunk_exists(self, chunk_id: str) -> bool:
        try:
            result = self._collection.get(ids=[chunk_id])
            return len(result["ids"]) > 0
        except Exception:
            return False
