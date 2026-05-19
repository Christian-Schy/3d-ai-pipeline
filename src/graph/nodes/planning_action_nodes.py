"""Planning node subset split out from planning_nodes.py."""
from __future__ import annotations

import re
import time

import structlog

from src.agents.aktions_klassifizierer import AktionsKlassifizierer
from src.agents.classifier_sub_agents import (
    CLASSIFIER_SUB_AGENT_CLASSES,
    AnchorClassifier,
)
from src.config.loader import get_config
from src.graph.state import PipelineState
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


# ADR 0009 — Pattern split: grid / circular / linear je eigener Sub-Agent.
_GRID_RE = re.compile(
    r"\b(?:lochmuster|raster|grid|eckbohr\w*|an\s+jeder\s+ecke)\b",
    re.IGNORECASE,
)
_GENERIC_LOCHBILD_RE = re.compile(r"\blochbild\b", re.IGNORECASE)
_CIRCULAR_RE = re.compile(
    r"\b(?:lochkreis|teilkreis|kreismuster)\b",
    re.IGNORECASE,
)
_LINEAR_RE = re.compile(
    r"\b(?:"
    r"bohrungsreihe|lochreihe"
    r"|loecher\s+der\s+reihe|locher\s+der\s+reihe"
    r"|reihe\s+aus"
    r"|bohrungen\s+(?:in\s+einer\s+reihe|entlang)"
    r"|bohrungen\s+.*\b(?:abstand|achse)\b"
    r")\b",
    re.IGNORECASE,
)
_HOLE_RE = re.compile(r"\b(?:bohrung(?:en)?|loch|loecher|locher)\b", re.IGNORECASE)
_POCKET_RE = re.compile(
    r"\b(?:tasche(?:n)?|ausnehmung(?:en)?|ausfraesung(?:en)?|aussparung(?:en)?)\b",
    re.IGNORECASE,
)
_SLOT_RE = re.compile(r"\bnut(?:en)?\b", re.IGNORECASE)
_EDGE_RE = re.compile(r"\b(?:fase(?:n)?|rundung(?:en)?|abrunden|radius)\b", re.IGNORECASE)
_LOCATIVE_PARENT_FEATURE_RE = re.compile(
    r"\bin\s+(?:der|die|dem|den|dieser|diese|diesem|diesen)\s+"
    r"(?:tasche(?:n)?|ausnehmung(?:en)?|ausfraesung(?:en)?|aussparung(?:en)?|nut(?:en)?)\b",
    re.IGNORECASE,
)

_SUBAGENT_FLAG = {
    "hole_classifier": "hole_enabled",
    "pocket_classifier": "pocket_enabled",
    "slot_classifier": "slot_enabled",
    "grid_classifier": "grid_enabled",
    "circular_classifier": "circular_enabled",
    "linear_classifier": "linear_enabled",
    "edge_feature_classifier": "edge_feature_enabled",
}


def _has_anchor_cue(phrase: str) -> bool:
    """Cheap early-out before the anchor micro-call (ADR 0014 W5b).

    An anchor is always phrased as "<feature-punkt> AUF <parent-punkt>"
    ("liegt auf der rechten Kante", "Ecke der Tasche auf Ecke des
    Wuerfels"). A phrase without the word "auf" cannot carry an anchor,
    so we skip the extra LLM call. This is routing, not interpretation
    (ADR 0014 §12 category) — the AnchorClassifier still makes the real
    decision for every phrase that passes the cue.
    """
    return " auf " in f" {(phrase or '').lower()} "


def detect_classifier_subagent(phrase: str) -> str | None:
    """Return the ADR-0006/0009 sub-classifier name for an unambiguous phrase.

    Pattern phrases (grid / circular / linear) are checked before generic
    holes because they naturally contain words like "bohrungen". If two real
    feature families remain in one phrase, return None so the monolithic
    fallback handles it.
    """
    text = _LOCATIVE_PARENT_FEATURE_RE.sub(" ", phrase or "")
    matches: list[str] = []

    linear = bool(_LINEAR_RE.search(text))

    if _GRID_RE.search(text) or (_GENERIC_LOCHBILD_RE.search(text) and not linear):
        matches.append("grid_classifier")
    if _CIRCULAR_RE.search(text):
        matches.append("circular_classifier")
    if linear:
        matches.append("linear_classifier")
    if not matches and _HOLE_RE.search(text):
        matches.append("hole_classifier")

    if _POCKET_RE.search(text):
        matches.append("pocket_classifier")
    if _SLOT_RE.search(text):
        matches.append("slot_classifier")
    if _EDGE_RE.search(text):
        matches.append("edge_feature_classifier")

    unique = list(dict.fromkeys(matches))
    return unique[0] if len(unique) == 1 else None


def _subagent_enabled(agent_name: str) -> bool:
    flag = _SUBAGENT_FLAG.get(agent_name)
    if not flag:
        return False
    return bool(getattr(get_config().classifier_subagents, flag, False))


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

    fallback_agent = _registry.get_agent(AktionsKlassifizierer)
    sub_agents: dict[str, object] = {}
    anchor_agent: AnchorClassifier | None = None
    route_counts = {"fallback": 0}
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

        route = "fallback"
        classifier = fallback_agent
        sub_agent_name = detect_classifier_subagent(p.get("phrase", ""))
        if sub_agent_name and _subagent_enabled(sub_agent_name):
            route = sub_agent_name
            if sub_agent_name not in sub_agents:
                sub_cls = CLASSIFIER_SUB_AGENT_CLASSES[sub_agent_name]
                sub_agents[sub_agent_name] = _registry.get_agent(sub_cls)
            classifier = sub_agents[sub_agent_name]
        elif sub_agent_name:
            route_counts[f"{sub_agent_name}_disabled"] = (
                route_counts.get(f"{sub_agent_name}_disabled", 0) + 1
            )
        else:
            route_counts["ambiguous_or_unknown"] = (
                route_counts.get("ambiguous_or_unknown", 0) + 1
            )

        try:
            k = classifier.classify(p, teil, parent_phrase=parent_phrase)
        except Exception as e:
            if classifier is not fallback_agent:
                log.warning(
                    "aktions_klassifizierer_subagent_failed_fallback",
                    sub_agent=route,
                    phrase=p.get("phrase", "")[:80],
                    error=str(e)[:200],
                )
                route = "fallback_after_subagent_error"
                try:
                    k = fallback_agent.classify(
                        p, teil, parent_phrase=parent_phrase
                    )
                except Exception as fallback_error:
                    log.error(
                        "aktions_klassifizierer_failed",
                        phrase=p.get("phrase", "")[:80],
                        error=str(fallback_error)[:200],
                    )
                    continue
            else:
                log.error("aktions_klassifizierer_failed",
                          phrase=p.get("phrase", "")[:80], error=str(e)[:200])
                continue
        route_counts[route] = route_counts.get(route, 0) + 1

        inherited_side = section_side_by_teil.get(teil_id)
        if inherited_side and k.get("seite") != inherited_side:
            log.info(
                "aktions_klassifizierer_section_side_override",
                phrase=p.get("phrase", "")[:80],
                original=k.get("seite"),
                inherited=inherited_side,
            )
            k["seite"] = inherited_side

        # W5b — Anker-Mikro-Klassifizierer. Eigener fokussierter Call statt
        # 6. Aufgabe im typ-Klassifizierer (ADR 0014 §13). Edge-Features
        # (fase/rundung) haben keinen Anker. Cue-gated, damit anker-freie
        # Phrasen den Extra-Call sparen.
        if (
            route != "edge_feature_classifier"
            and _has_anchor_cue(p.get("phrase", ""))
        ):
            if anchor_agent is None:
                anchor_agent = _registry.get_agent(AnchorClassifier)
            try:
                anchor_hints = anchor_agent.classify_anchor(p.get("phrase", ""))
            except Exception as e:  # noqa: BLE001
                log.warning("aktions_klassifizierer_anchor_failed",
                            phrase=p.get("phrase", "")[:80], error=str(e)[:200])
                anchor_hints = {}
            if anchor_hints:
                k.setdefault("parameter_hints", {}).update(anchor_hints)
                route_counts["anchor_hits"] = route_counts.get("anchor_hits", 0) + 1

        klassifikationen.append(k)
        by_idx_per_teil[(teil_id, p.get("phrase_idx"))] = k
        raw = getattr(classifier, "_last_raw_response", None)
        if raw:
            raw_responses.append(raw)

    log.info("node_aktions_klassifizierer_done",
             classified=len(klassifikationen), of=len(phrases))

    cfg = get_config()
    return {
        "aktions_klassifikationen": klassifikationen,
        "agent_traces": [_make_trace(
            agent="aktions_klassifizierer", step=_step,
            input_data={"phrase_count": len(phrases)},
            output_data={
                "klassifikationen": klassifikationen,
                "routes": route_counts,
            },
            start_time=_t0,
            model=getattr(cfg.models, "aktions_klassifizierer",
                          cfg.models.inventar),
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
