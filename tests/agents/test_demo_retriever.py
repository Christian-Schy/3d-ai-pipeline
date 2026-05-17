"""Unit tests for the W6 hybrid demo retriever (ADR 0014).

Covers the deterministic core — tokenisation, BM25 scoring, RRF fusion,
pair formatting — without touching Ollama or the embedding model. The
dense + fusion path with n > k is exercised by the live agent_regression
suite instead.
"""

from __future__ import annotations

from src.agents.demo_retriever import (
    DemoRetriever,
    _BM25,
    _tokenize,
    get_demo_retriever,
)


def test_tokenize_lowercases_and_splits():
    assert _tokenize("Oben eine Tasche 30x20x10!") == [
        "oben", "eine", "tasche", "30x20x10",
    ]
    assert _tokenize("") == []
    assert _tokenize(None) == []


def test_bm25_ranks_term_overlap_higher():
    docs = [
        _tokenize("oben eine tasche von linker kante"),
        _tokenize("oben eine bohrung zentral"),
        _tokenize("die obere taschen-kante vom rand"),
    ]
    bm25 = _BM25(docs)
    scores = bm25.scores("taschen kante vom rand")
    # doc 2 shares the most query terms → highest score
    assert scores[2] > scores[0]
    assert scores[2] > scores[1]
    # doc 1 (no overlap with 'taschen/kante/rand') scores ~0
    assert scores[1] == 0.0


def test_bm25_empty_pool():
    bm25 = _BM25([])
    assert bm25.scores("anything") == []


def test_fuse_combines_rankings_via_rrf():
    # bm25 ranks doc 3 first, dense ranks doc 1 first; doc 2 is rank-2 in
    # both; doc 0 is last in both.
    bm25_rank = [3, 2, 1, 0]
    dense_rank = [1, 2, 3, 0]
    fused = DemoRetriever._fuse(bm25_rank, dense_rank, k=3)
    assert len(fused) == 3
    # RRF rewards being #1 in ANY list more than being #2 in both — so a
    # list-leader (doc 3 or doc 1) wins over the always-second doc 2.
    assert fused[0] in (1, 3)
    # doc 0 is last in both → must not be in the top-3.
    assert 0 not in fused


def test_fuse_bm25_only_when_dense_missing():
    bm25_rank = [5, 4, 3, 2, 1, 0]
    fused = DemoRetriever._fuse(bm25_rank, None, k=3)
    assert fused == [5, 4, 3]


def test_retrieve_small_pool_returns_all_as_pairs():
    """A pool with n <= k skips retrieval entirely — all demos, formatted
    as (user_msg, assistant_msg) pairs. Uses the real circular pool (9)."""
    r = get_demo_retriever(
        "circular_classifier",
        ["phrase", "teil_type", "teil_params", "parent_phrase"],
        "klassifikation",
    )
    assert r is not None, "circular_classifier_demo_pool.json should exist"
    pairs = r.retrieve("oben ein lochkreis", k=20)  # k > pool size
    assert len(pairs) == len(r.demos)
    for user_msg, assistant_msg in pairs:
        assert "phrase:" in user_msg
        assert assistant_msg  # the klassifikation JSON string


def test_get_demo_retriever_unknown_agent_returns_none():
    assert get_demo_retriever("does_not_exist_classifier", [], "") is None
