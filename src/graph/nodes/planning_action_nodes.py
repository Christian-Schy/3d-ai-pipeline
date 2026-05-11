"""Planning node subset split out from planning_nodes.py."""
from __future__ import annotations
import re
import time
import structlog

from src.graph.state import PipelineState
from src.agents.aktions_klassifizierer import AktionsKlassifizierer
from src.tools.aktions_aggregator import aggregate as aktions_aggregate
from src.tools.aktions_splitter import split_spec_into_aktionen
from . import _registry
from ._tracing import _make_trace

log = structlog.get_logger()

# ══════════════════════════════════════════════════════════════════
# Per-Action Chain (ADR 0003) — wired in Stufe 5b, additive in 5a
# ══════════════════════════════════════════════════════════════════

_SECTION_SIDE_RE = re.compile(
    r"^\s*(oben|unten|rechts|links|vorne|hinten)\b"
    r"(?:\s*\([^)]*\))?\s*:",
    re.IGNORECASE,
)


def _section_side_from_phrase(phrase: str) -> str | None:
    """Return the face side from section headers like 'rechts (...): ...'."""
    match = _SECTION_SIDE_RE.match(phrase or "")
    if not match:
        return None
    return match.group(1).lower()

def aktions_splitter_node(state: PipelineState) -> dict:
    """Stufe 1 of ADR 0003 — deterministic spec → action phrases.

    Reads:  state.specification, state.inventar.teile
    Writes: state.aktions_phrases  ([{phrase, teil_id, phrase_idx,
            parent_phrase_idx}])

    Replaces the buggy Inventar Step B verklumpung. No LLM.
    """
    _t0 = time.time()
    _step = len(state.get("agent_traces", [])) + 1

    spec = state.get("specification", state.get("description", ""))
    inventar = state.get("inventar", {}) or {}
    teile = inventar.get("teile", []) or []

    if not spec or not teile:
        log.warning("node_aktions_splitter_skipped",
                    has_spec=bool(spec), teile=len(teile))
        return {
            "aktions_phrases": [],
            "agent_traces": [_make_trace(
                agent="aktions_splitter", step=_step,
                input_data={"spec_chars": len(spec), "teil_count": len(teile)},
                output_data={"phrases": [], "skipped": True},
                start_time=_t0,
            )],
        }

    phrases = split_spec_into_aktionen(spec, teile)

    log.info(
        "node_aktions_splitter_done",
        phrases=len(phrases),
        nested=sum(1 for p in phrases if p.get("parent_phrase_idx") is not None),
    )

    return {
        "aktions_phrases": phrases,
        "agent_traces": [_make_trace(
            agent="aktions_splitter", step=_step,
            input_data={"specification": spec[:300], "teil_count": len(teile)},
            output_data={"phrases": phrases},
            start_time=_t0,
        )],
    }


def aktions_klassifizierer_node(state: PipelineState) -> dict:
    """Stufe 2 of ADR 0003 — per-phrase classification.

    Reads:  state.aktions_phrases, state.inventar.teile
    Writes: state.aktions_klassifikationen

    One small LLM call per phrase. For nested children, the parent's
    original phrase text is passed as context so the classifier can
    inherit the seite when the child phrase doesn't state one.
    """
    _t0 = time.time()
    _step = len(state.get("agent_traces", [])) + 1

    phrases = state.get("aktions_phrases", []) or []
    inventar = state.get("inventar", {}) or {}
    teile_by_id = {t["id"]: t for t in inventar.get("teile", []) if t.get("id")}

    if not phrases:
        log.warning("node_aktions_klassifizierer_skipped", reason="no_phrases")
        return {
            "aktions_klassifikationen": [],
            "agent_traces": [_make_trace(
                agent="aktions_klassifizierer", step=_step,
                input_data={"phrase_count": 0},
                output_data={"klassifikationen": [], "skipped": True},
                start_time=_t0,
            )],
        }

    agent = _registry.get_agent(AktionsKlassifizierer)
    klassifikationen: list[dict] = []
    raw_responses: list[str] = []
    by_idx_per_teil: dict[tuple[str, int], dict] = {}
    section_side_by_teil: dict[str, str] = {}

    for p in phrases:
        teil_id = p.get("teil_id", "")
        teil = teile_by_id.get(teil_id)
        if not teil:
            log.warning("aktions_klassifizierer_unknown_teil",
                        teil_id=teil_id, phrase=p.get("phrase", "")[:60])
            continue

        parent_phrase = None
        parent_idx = p.get("parent_phrase_idx")
        if parent_idx is not None:
            parent = by_idx_per_teil.get((teil_id, parent_idx))
            if parent is not None:
                parent_phrase = parent.get("beschreibung")

        section_side = _section_side_from_phrase(p.get("phrase", ""))
        if section_side:
            section_side_by_teil[teil_id] = section_side

        try:
            k = agent.classify(p, teil, parent_phrase=parent_phrase)
        except Exception as e:
            log.error("aktions_klassifizierer_failed",
                      phrase=p.get("phrase", "")[:80], error=str(e)[:200])
            continue

        inherited_side = section_side_by_teil.get(teil_id)
        if inherited_side and k.get("seite") != inherited_side:
            log.info(
                "aktions_klassifizierer_section_side_override",
                phrase=p.get("phrase", "")[:80],
                original=k.get("seite"),
                inherited=inherited_side,
            )
            k["seite"] = inherited_side

        klassifikationen.append(k)
        by_idx_per_teil[(teil_id, p.get("phrase_idx"))] = k
        raw = getattr(agent, "_last_raw_response", None)
        if raw:
            raw_responses.append(raw)

    log.info("node_aktions_klassifizierer_done",
             classified=len(klassifikationen), of=len(phrases))

    from src.config.loader import get_config as _gc
    return {
        "aktions_klassifikationen": klassifikationen,
        "agent_traces": [_make_trace(
            agent="aktions_klassifizierer", step=_step,
            input_data={"phrase_count": len(phrases)},
            output_data={"klassifikationen": klassifikationen},
            start_time=_t0,
            model=getattr(_gc().models, "aktions_klassifizierer",
                           _gc().models.inventar),
            raw_response="\n---\n".join(raw_responses) if raw_responses else None,
        )],
    }


def aktions_aggregator_node(state: PipelineState) -> dict:
    """Stufe 4 of ADR 0003 — features → teil_definitionen[].

    Reads:  state.aktions_features, state.inventar.teile
    Writes: state.teil_definitionen

    Pure deterministic step. Resolves nested children's `parent` to the
    parent pocket's feature_id and strips internal markers.
    """
    _t0 = time.time()
    _step = len(state.get("agent_traces", [])) + 1

    features = state.get("aktions_features", []) or []
    inventar = state.get("inventar", {}) or {}
    teile = inventar.get("teile", []) or []

    teil_definitionen = aktions_aggregate(features, teile)

    log.info("node_aktions_aggregator_done",
             features_in=len(features),
             teil_definitionen=len(teil_definitionen))

    return {
        "teil_definitionen": teil_definitionen,
        "agent_traces": [_make_trace(
            agent="aktions_aggregator", step=_step,
            input_data={"feature_count": len(features), "teil_count": len(teile)},
            output_data={"teil_definitionen": teil_definitionen},
            start_time=_t0,
        )],
    }
