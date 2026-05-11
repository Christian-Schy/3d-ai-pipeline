"""Planning node subset split out from planning_nodes.py."""
from __future__ import annotations
import time
import structlog

from src.graph.state import PipelineState
from src.agents.inventar_agent import InventarAgent
from src.agents.position_extractor_agent import PositionExtractorAgent
from src.agents.text_splitter_agent import TextSplitterAgent
from . import _registry
from ._tracing import _make_trace

log = structlog.get_logger()

# ══════════════════════════════════════════════════════════════════
# 3-Step Blueprint Chain (Phase A)
# ══════════════════════════════════════════════════════════════════

def inventar_node(state: PipelineState) -> dict:
    """Step 1: Extract parts inventory from the specification.

    Fresh runs: Step A only (teile list). The deterministic
    aktions_splitter_node and aktions_klassifizierer_node take over what
    the legacy Step B used to do — see ADR 0003.

    Retry from validator: legacy extract() with feedback so the model
    can correct the teile dimensions. Aktionen produced on retry are
    ignored downstream; the new chain re-derives them from the
    corrected teile + spec.
    """
    spec = state.get("specification", state.get("description", ""))
    _t0 = time.time()
    _step = len(state.get("agent_traces", [])) + 1

    retry_feedback = state.get("validator_feedback", "") or ""
    previous_inventar = state.get("inventar", {}) or {}
    is_retry = bool(previous_inventar and retry_feedback)

    agent = _registry.get_agent(InventarAgent)

    try:
        if is_retry:
            inventar = agent.extract(
                spec,
                retry_feedback=retry_feedback,
                previous_inventar=previous_inventar,
            )
        else:
            inventar = agent.extract_teile_only(spec)
    except Exception as e:
        log.error("node_inventar_failed", error=str(e)[:200])
        _trace = _make_trace(
            agent="inventar", step=_step,
            input_data={"specification": spec[:200]},
            output_data={"error": str(e)[:200]},
            start_time=_t0,
        )
        return {
            "inventar": {},
            "agent_traces": [_trace],
        }

    log.info("node_inventar_done",
             teil_count=inventar.get("teil_count", 0),
             aktionen=len(inventar.get("aktionen", [])))

    from src.config.loader import get_config as _gc
    _trace = _make_trace(
        agent="inventar", step=_step,
        input_data={"specification": spec},
        output_data=inventar,
        start_time=_t0,
        model=_gc().models.inventar,
        raw_response=getattr(agent, "_last_raw_response", None),
    )

    return {
        "inventar": inventar,
        "agent_traces": [_trace],
    }


def _relabel_features_on_self(
    teil_id: str,
    placement: list[str],
    feature: list[str],
) -> tuple[list[str], list[str], list[str]]:
    """Deterministischer Post-Filter fuer position_extractor.

    Hintergrund: Der LLM-Labeler klassifiziert manchmal Saetze wie
    "auf der platte oben eine 5mm bohrung 5 tief..." als placement statt
    als feature, weil sie eine Ortsangabe enthalten. Diese landen dann im
    joined pos_spec, den der Platzierer (offset-Step) bekommt — und das
    LLM extrahiert Werte aus dem Noise (run f93ae272, EF_kombo_basics).

    Regel — konservativ, nur bei eindeutigen Marker-Phrasen:
      * Satz beginnt mit "auf der/dem <teil_id>" oder "in der/dem <teil_id>"
        → das ist per Definition ein Feature AUF diesem Teil, gehoert in
        feature_sentences, nicht in placement_sentences.
      * Vergleich case-insensitive, nur am Satzanfang nach lstrip.
      * Nur gegen den eigenen `teil_id` gematcht — Parent-Verweise
        ("auf dem wuerfel" wenn man eine Platte platziert) bleiben in
        placement, weil sie das Anliegen-Verhaeltnis beschreiben.

    Returns: (neue_placement, neue_feature, verschobene_saetze).
    """
    prefixes = (
        f"auf der {teil_id}",
        f"auf dem {teil_id}",
        f"in der {teil_id}",
        f"in dem {teil_id}",
    )
    prefixes_lower = tuple(p.lower() for p in prefixes)
    new_placement: list[str] = []
    moved: list[str] = []
    for sent in placement:
        if any(sent.lower().lstrip().startswith(p) for p in prefixes_lower):
            moved.append(sent)
        else:
            new_placement.append(sent)
    return new_placement, list(feature) + moved, moved


def position_extractor_node(state: PipelineState) -> dict:
    """Step 1b: Per-teil Labeler — split each teil's text into placement vs.
    feature sentences.

    Runs AFTER text_splitter_node (which produces teil_texte = {teil_id: text}).
    For each teil, calls PositionExtractorAgent on that teil's chunk and gets
    back two lists:
      - placement_sentences: where the teil sits / how it is oriented
      - feature_sentences:   what holes / pockets / slots the teil has

    Downstream feature_definierer reads feature_sentences[teil_id] only,
    platzierer reads placement_sentences[teil_id] only — no cross-teil noise.

    Nach dem Labeler laeuft ein deterministischer Post-Filter
    (`_relabel_features_on_self`), der "auf der/dem <teil_id>"-Saetze in
    feature_sentences verschiebt. Faengt Mis-Splits des LLM-Labelers ab,
    die sonst zu Noise im Platzierer-Offset-Step fuehren.

    Skipped for single-part models (no placement, only features).
    """
    inventar = state.get("inventar", {})
    teil_texte: dict[str, str] = state.get("teil_texte", {}) or {}
    spec = state.get("specification", state.get("description", ""))
    _t0 = time.time()
    _step = len(state.get("agent_traces", [])) + 1

    teile = inventar.get("teile", [])
    if len(teile) < 2:
        log.info("node_position_extractor_skipped", reason="single_part")
        return {
            "position_extrakt": {"positionen": []},
            "agent_traces": [_make_trace(
                agent="position_extractor", step=_step,
                input_data={}, output_data={"skipped": True, "reason": "single_part"},
                start_time=_t0,
            )],
        }

    from src.config.loader import get_config as _gc
    agent = _registry.get_agent(PositionExtractorAgent)
    root_id = teile[0]["id"]
    positionen: list[dict] = []
    raw_responses: list[str] = []

    for teil in teile:
        teil_id = teil["id"]
        # Root teil: no placement, but features still possible (e.g. holes
        # in the base cube). Label its text too so feature_definierer can use
        # feature_sentences. Mark placement_sentences as empty for root.
        teil_text = teil_texte.get(teil_id, spec)
        try:
            labels = agent.label(teil_id, teil_text)
        except Exception as e:
            log.error("position_extractor_failed",
                      teil=teil_id, error=str(e)[:200])
            labels = {"placement_sentences": [], "feature_sentences": []}

        raw_responses.append(getattr(agent, "_last_raw_response", "") or "")

        # Root has no parent — strip placement sentences if any leaked through
        placement = labels["placement_sentences"] if teil_id != root_id else []
        feature_sents = labels["feature_sentences"]

        # Post-Filter: "auf der/dem <teil_id>"-Saetze sind per Definition
        # Features AUF dem Teil, gehoeren nicht in placement_sentences.
        # Faengt LLM-Mis-Splits ab (siehe Docstring von _relabel_features_on_self).
        placement, feature_sents, moved = _relabel_features_on_self(
            teil_id, placement, feature_sents
        )
        if moved:
            log.info("position_extractor_relabel_features_on_self",
                     teil=teil_id, moved_count=len(moved),
                     sample=moved[0][:80] if moved else "")

        positionen.append({
            "teil_id": teil_id,
            "is_root": teil_id == root_id,
            "placement_sentences": placement,
            "feature_sentences": feature_sents,
        })

        log.info("position_extractor_teil_done",
                 teil=teil_id,
                 placement_count=len(placement),
                 feature_count=len(feature_sents))

    result = {"positionen": positionen}

    log.info("node_position_extractor_done",
             teil_count=len(teile),
             total_placement=sum(len(p["placement_sentences"]) for p in positionen),
             total_feature=sum(len(p["feature_sentences"]) for p in positionen))

    _trace = _make_trace(
        agent="position_extractor", step=_step,
        input_data={"teile": [t["id"] for t in teile],
                    "teil_texte_lengths": {tid: len(txt)
                                            for tid, txt in teil_texte.items()}},
        output_data=result,
        start_time=_t0,
        model=_gc().models.position_extractor,
        raw_response="\n---\n".join(raw_responses) if raw_responses else None,
    )
    return {
        "position_extrakt": result,
        "agent_traces": [_trace],
    }


def text_splitter_node(state: PipelineState) -> dict:
    """Step 1a: Split spec into one focused text per part.

    Runs after inventar_node, before position_extractor_node.
    Gives the labeler (and all downstream agents) only the text that belongs
    to that specific part — no cross-teil noise. The labeler then splits
    each per-teil chunk into placement vs. feature sentences.
    Skipped for single-part models.
    """
    inventar = state.get("inventar", {})
    spec = state.get("specification", state.get("description", ""))
    _t0 = time.time()
    _step = len(state.get("agent_traces", [])) + 1

    teile = inventar.get("teile", [])
    if len(teile) < 2:
        log.info("node_text_splitter_skipped", reason="single_part")
        return {
            "teil_texte": {},
            "agent_traces": [_make_trace(
                agent="text_splitter", step=_step,
                input_data={}, output_data={"skipped": True, "reason": "single_part"},
                start_time=_t0,
            )],
        }

    agent = _registry.get_agent(TextSplitterAgent)
    try:
        teil_texte = agent.split(spec, teile)
    except Exception as e:
        log.error("node_text_splitter_failed", error=str(e)[:200])
        teil_texte = {}

    log.info("node_text_splitter_done",
             teil_count=len(teile),
             split_count=len(teil_texte))

    from src.config.loader import get_config as _gc
    _trace = _make_trace(
        agent="text_splitter", step=_step,
        input_data={"specification": spec, "teil_ids": [t["id"] for t in teile]},
        output_data={"teil_texte": teil_texte},
        start_time=_t0,
        model=getattr(_gc().models, "text_splitter",
                      getattr(_gc().models, "inventar", "")),
        raw_response=getattr(agent, "_last_raw_response", None),
    )
    return {
        "teil_texte": teil_texte,
        "agent_traces": [_trace],
    }


