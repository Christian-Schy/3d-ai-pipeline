"""
src/agents/demo_retriever.py — W6 (ADR 0014): hybrid KNN demo retrieval.

Ersetzt die fixen 8-16 BootstrapFewShot-Demos pro Klassifizierer durch
Retrieval: aus dem VOLLEN kuratierten Pool (`{agent}_demo_pool.json`,
erzeugt von scripts/build_classifier_demo_pools.py) werden pro Query die
K relevantesten Demos geholt.

Hybrid — zwei Sucharten, per Reciprocal Rank Fusion kombiniert:
  - dense  : sentence-transformers Embeddings (semantische Naehe;
             "Bohrung" ≈ "Loch", "von der Kante" ≈ "vom Rand").
  - BM25   : lexikalische Stichwort-Suche (exakte CAD-Fachwoerter;
             "rasterabstand", "taschen-kante", "entlang y-achse").
Beide decken gegenteilige Schwaechen ab. KEIN Cross-Encoder-Reranking —
das lohnt erst bei Pools mit Hunderten Kandidaten (ADR 0014 §14); die
Klassifizierer-Pools sind ~10-43 Demos gross.

Degradiert sauber: faellt sentence-transformers/numpy aus, laeuft die
Retrieval rein ueber BM25 weiter.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import structlog

log = structlog.get_logger()

DSPY_DIR = Path("data/dspy_optimized")

_RRF_K = 60          # Reciprocal-Rank-Fusion-Konstante (Standardwert)
_BM25_K1 = 1.5
_BM25_B = 0.75

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall((text or "").lower())


def _rank(scores: list[float]) -> list[int]:
    """Doc-Indizes nach Score absteigend sortiert."""
    return sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)


class _BM25:
    """Kompakter BM25Okapi-Index ueber eine feste Dokumentmenge."""

    def __init__(self, docs_tokens: list[list[str]]):
        self.docs = docs_tokens
        self.n = len(docs_tokens)
        self.avgdl = (sum(len(d) for d in docs_tokens) / self.n) if self.n else 0.0
        df: dict[str, int] = {}
        for toks in docs_tokens:
            for term in set(toks):
                df[term] = df.get(term, 0) + 1
        self.idf = {
            term: math.log(1 + (self.n - freq + 0.5) / (freq + 0.5))
            for term, freq in df.items()
        }
        self.tf = [{t: toks.count(t) for t in set(toks)} for toks in docs_tokens]

    def scores(self, query: str) -> list[float]:
        q = _tokenize(query)
        out: list[float] = []
        for i in range(self.n):
            dl = len(self.docs[i])
            score = 0.0
            for term in q:
                freq = self.tf[i].get(term, 0)
                if not freq:
                    continue
                idf = self.idf.get(term, 0.0)
                denom = freq + _BM25_K1 * (
                    1 - _BM25_B + _BM25_B * dl / (self.avgdl or 1)
                )
                score += idf * freq * (_BM25_K1 + 1) / denom
            out.append(score)
        return out


class DemoRetriever:
    """Hybrid (dense + BM25) KNN-Retrieval ueber den Demo-Pool eines Agenten."""

    def __init__(
        self,
        agent_name: str,
        input_fields: list[str],
        output_field: str,
    ) -> None:
        self.agent_name = agent_name
        self.input_fields = input_fields
        self.output_field = output_field

        path = DSPY_DIR / f"{agent_name}_demo_pool.json"
        self.demos: list[dict] = json.loads(path.read_text(encoding="utf-8"))
        self._phrases = [str(d.get("phrase", "")) for d in self.demos]
        self._bm25 = _BM25([_tokenize(p) for p in self._phrases])

        # Dense-Index wird lazy beim ersten retrieve() gebaut (Modell-Load).
        self._vectors = None      # numpy-Array | False (Dense deaktiviert)
        self._embed_fn = None

    # ── dense ──────────────────────────────────────────────────────────

    def _ensure_dense(self) -> None:
        if self._vectors is not None:
            return
        try:
            import numpy as np

            from src.rag.base_rag import get_embed_fn

            self._embed_fn = get_embed_fn()
            vecs = np.asarray(self._embed_fn(self._phrases), dtype="float32")
            norms = np.linalg.norm(vecs, axis=1, keepdims=True)
            self._vectors = vecs / np.clip(norms, 1e-8, None)
        except Exception as e:  # noqa: BLE001
            log.warning(
                "demo_retriever_dense_unavailable",
                agent=self.agent_name, error=str(e)[:200],
            )
            self._vectors = False

    def _dense_rank(self, query: str) -> list[int] | None:
        self._ensure_dense()
        if self._vectors is False:
            return None
        import numpy as np

        qv = np.asarray(self._embed_fn([query])[0], dtype="float32")
        qv = qv / max(float(np.linalg.norm(qv)), 1e-8)
        return _rank(list(self._vectors @ qv))

    # ── public ─────────────────────────────────────────────────────────

    def retrieve(self, query: str, k: int = 8) -> list[tuple[str, str]]:
        """Return up to k (user_msg, assistant_msg) demo pairs for the query."""
        n = len(self.demos)
        if n == 0:
            return []
        if n <= k:
            # Pool kleiner als k → alle Demos, kein Retrieval noetig.
            order = list(range(n))
        else:
            bm25_rank = _rank(self._bm25.scores(query))
            dense_rank = self._dense_rank(query)
            order = self._fuse(bm25_rank, dense_rank, k)
        return [self._as_pair(self.demos[i]) for i in order]

    @staticmethod
    def _fuse(
        bm25_rank: list[int],
        dense_rank: list[int] | None,
        k: int,
    ) -> list[int]:
        """Reciprocal Rank Fusion der beiden Ranglisten."""
        rrf: dict[int, float] = {}
        for rank, idx in enumerate(bm25_rank):
            rrf[idx] = rrf.get(idx, 0.0) + 1.0 / (_RRF_K + rank)
        if dense_rank is not None:
            for rank, idx in enumerate(dense_rank):
                rrf[idx] = rrf.get(idx, 0.0) + 1.0 / (_RRF_K + rank)
        return sorted(rrf, key=lambda i: rrf[i], reverse=True)[:k]

    def _as_pair(self, demo: dict) -> tuple[str, str]:
        parts = [
            f"{key}: {demo.get(key, '')}"
            for key in self.input_fields
            if demo.get(key, "")
        ]
        return "\n".join(parts), str(demo.get(self.output_field, ""))


# Modul-Cache: ein Retriever pro Agent (Pool-Embeddings nur einmal bauen).
_RETRIEVER_CACHE: dict[str, "DemoRetriever | None"] = {}


def get_demo_retriever(
    agent_name: str,
    input_fields: list[str],
    output_field: str,
) -> "DemoRetriever | None":
    """Cached DemoRetriever fuer einen Agenten, oder None ohne Pool-Datei."""
    if agent_name in _RETRIEVER_CACHE:
        return _RETRIEVER_CACHE[agent_name]

    pool_path = DSPY_DIR / f"{agent_name}_demo_pool.json"
    retriever: DemoRetriever | None = None
    if pool_path.exists():
        try:
            retriever = DemoRetriever(agent_name, input_fields, output_field)
        except Exception as e:  # noqa: BLE001
            log.warning("demo_retriever_build_failed",
                        agent=agent_name, error=str(e)[:200])
            retriever = None
    _RETRIEVER_CACHE[agent_name] = retriever
    return retriever
