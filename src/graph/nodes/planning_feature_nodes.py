"""Planning node subset split out from planning_nodes.py."""
from __future__ import annotations

import time

import structlog

from src.agents.normalizer_agent import NormalizerAgent
from src.agents.pocket_child_placer import PocketChildPlacer
from src.agents.position_normalizer_agent import PositionNormalizerAgent
from src.graph.state import PipelineState
from src.tools.position_builder import build_orientation, build_position

from . import _registry
from ._tracing import _make_trace

log = structlog.get_logger()

def feature_definierer_node(state: PipelineState) -> dict:
    """Stufe 3 of ADR 0003: per-classified-action feature definition.

    Reads:  state.aktions_klassifikationen, state.inventar.teile,
            state.specification (for context).
    Writes: state.aktions_features (raw SemanticFeatures with
            _teil_id / _phrase_idx / _parent_phrase_idx markers).

    Each classified action becomes exactly one SemanticFeature via
    NormalizerAgent.define_feature(klass, teil). The aggregator
    (aktions_aggregator_node) downstream consumes these into the final
    teil_definitionen[] structure.

    On retry from coordinate_validator: re-runs over the same
    klassifikationen (phrases are stable; only the LLM-derived feature
    details may change with feedback context).
    """
    inventar = state.get("inventar", {}) or {}
    klassifikationen = state.get("aktions_klassifikationen", []) or []
    spec = state.get("specification", state.get("description", ""))
    _t0 = time.time()
    _step = len(state.get("agent_traces", [])) + 1

    validation_hint = (
        state.get("coordinate_validation_issues", "")
        or state.get("validator_feedback", "")
        or ""
    )
    if validation_hint:
        log.info("node_feature_definierer_retry", hint=validation_hint[:120])

    if not inventar.get("teile"):
        log.warning("node_feature_definierer_skipped", reason="no_inventar")
        return {"aktions_features": [], "agent_traces": [_make_trace(
            agent="feature_definierer", step=_step,
            input_data={}, output_data={"skipped": True, "reason": "no_inventar"},
            start_time=_t0,
        )]}

    if not klassifikationen:
        log.warning("node_feature_definierer_skipped", reason="no_klassifikationen")
        return {"aktions_features": [], "agent_traces": [_make_trace(
            agent="feature_definierer", step=_step,
            input_data={"teile": len(inventar.get("teile", []))},
            output_data={"skipped": True, "reason": "no_klassifikationen"},
            start_time=_t0,
        )]}

    teile_by_id = {t["id"]: t for t in inventar.get("teile", []) if t.get("id")}
    teil_texte: dict[str, str] = state.get("teil_texte", {}) or {}

    spec_with_hint = spec
    if validation_hint:
        spec_with_hint = (
            f"{spec}\n\n"
            f"★ KORREKTUR-HINWEIS (vorheriger Versuch hatte Fehler):\n"
            f"{validation_hint}"
        )

    normalizer = _registry.get_agent(NormalizerAgent)
    features: list[dict] = []
    raw_responses: list[str] = []

    for klass in klassifikationen:
        teil_id = klass.get("teil_id", "")
        teil = teile_by_id.get(teil_id)
        if not teil:
            log.warning("feature_definierer_unknown_teil",
                        teil_id=teil_id, phrase=klass.get("beschreibung", "")[:60])
            continue

        feature_text = teil_texte.get(teil_id, spec_with_hint) or spec_with_hint

        try:
            feat = normalizer.define_feature(klass, teil, feature_text=feature_text)
        except Exception as e:
            log.error("feature_definierer_failed",
                      phrase=klass.get("beschreibung", "")[:80],
                      error=str(e)[:200])
            continue

        # define_feature returns None for sentinel typs (unbekannt /
        # ignorieren) so placement-only phrases like "vorne soll eine platte
        # hin mit 140x20x40" cannot fall through as phantom holes.
        if feat is None:
            log.info("feature_definierer_skip_sentinel",
                     teil=teil_id, phrase=klass.get("beschreibung", "")[:80])
            continue

        features.append(feat)
        raw = getattr(normalizer, "_last_raw_response", None)
        if raw:
            raw_responses.append(raw)
        log.info("feature_definierer_done",
                 teil=teil_id, typ=feat.get("type"),
                 phrase_idx=feat.get("_phrase_idx"))

    log.info("node_feature_definierer_done",
             features=len(features), of=len(klassifikationen))

    from src.config.loader import get_config as _gc
    return {
        "aktions_features": features,
        "agent_traces": [_make_trace(
            agent="feature_definierer", step=_step,
            input_data={"klassifikationen": len(klassifikationen),
                        "teile": len(teile_by_id)},
            output_data={"features": features},
            start_time=_t0,
            model=_gc().models.normalizer,
            raw_response="\n---\n".join(raw_responses) if raw_responses else None,
        )],
    }


def platzierer_node(state: PipelineState) -> dict:
    """Step 2b: Attach parent / position / orientation to each part.

    S0 (Modulare Trennung): Placement ONLY — no feature knowledge.
    Reads teil_definitionen (features-only from feature_definierer_node) and
    attaches parent + position + orientation via PositionNormalizerAgent.

    Input for PositionNormalizerAgent: position_extrakt[teil_id].placement_sentences
    (labeled placement-only sentences from per-teil chunk), never the full spec.
    """
    teil_defs = state.get("teil_definitionen", [])
    inventar = state.get("inventar", {})
    spec = state.get("specification", state.get("description", ""))
    _t0 = time.time()
    _step = len(state.get("agent_traces", [])) + 1

    if not teil_defs:
        log.warning("node_platzierer_skipped", reason="no_teil_definitionen")
        return {"agent_traces": [_make_trace(
            agent="platzierer", step=_step,
            input_data={}, output_data={"skipped": True},
            start_time=_t0,
        )]}

    # Single-part: no placement needed
    if len(teil_defs) == 1:
        teil_defs[0]["parent"] = None
        teil_defs[0]["position"] = None
        log.info("node_platzierer_single_part_skipped")
        return {
            "teil_definitionen": teil_defs,
            "agent_traces": [_make_trace(
                agent="platzierer", step=_step,
                input_data={"teil_count": 1},
                output_data={"skipped": True, "reason": "single_part"},
                start_time=_t0,
            )],
        }

    position_extrakt = state.get("position_extrakt", {})
    position_by_teil = {
        p["teil_id"]: p
        for p in position_extrakt.get("positionen", [])
        if p.get("teil_id")
    }

    teil_texte: dict[str, str] = state.get("teil_texte", {}) or {}
    all_teile = inventar.get("teile", [])
    root_teil_id = all_teile[0]["id"] if all_teile else (teil_defs[0]["id"] if teil_defs else "")

    position_normalizer = _registry.get_agent(PositionNormalizerAgent)
    traces = []
    updated_defs = []

    for idx, teil_def in enumerate(teil_defs):
        teil_id = teil_def["id"]
        is_root = (teil_id == root_teil_id)
        t_start = time.time()
        step_i = _step + len(traces)

        if is_root:
            teil_def["parent"] = None
            teil_def["position"] = None
            updated_defs.append(teil_def)
            traces.append(_make_trace(
                agent="platzierer", step=step_i,
                input_data={"teil_id": teil_id, "is_root": True},
                output_data={"parent": None, "position": None},
                start_time=t_start,
            ))
            continue

        # Priority: labeled placement_sentences > teil_texte chunk > full spec.
        # placement_sentences contains only the sentences about WHERE this teil
        # sits — no feature noise, no other-teil noise.
        pos_entry = position_by_teil.get(teil_id)
        placement_sentences = pos_entry.get("placement_sentences", []) if pos_entry else []
        if placement_sentences:
            pos_spec = " ".join(placement_sentences)
            log.info("platzierer_using_labeled_placement",
                     teil=teil_id, sentence_count=len(placement_sentences),
                     text=pos_spec[:80])
        elif teil_id in teil_texte:
            pos_spec = teil_texte[teil_id]
            log.info("platzierer_using_teil_text",
                     teil=teil_id, text=pos_spec[:80])
        else:
            pos_spec = spec

        # Get teil params for PositionNormalizerAgent (from inventar, not teil_def)
        inventar_teil = next((t for t in all_teile if t["id"] == teil_id), {})
        teil_params = inventar_teil.get("raw_params", teil_def.get("params", {}))
        teil_type = inventar_teil.get("type", teil_def.get("type", "box"))

        normalized_position = None
        position_raw = ""
        try:
            normalized_position = position_normalizer.normalize(
                teil_id=teil_id,
                teil_type=teil_type,
                teil_params=teil_params,
                alle_teile=all_teile,
                specification=pos_spec,
            )
            position_raw = getattr(position_normalizer, "_last_raw_response", "")
            log.info("platzierer_done",
                     teil=teil_id,
                     parent=normalized_position.get("parent"),
                     seite=normalized_position.get("seite"),
                     ausrichtung=normalized_position.get("ausrichtung"))
        except Exception as e:
            log.error("platzierer_failed", teil=teil_id, error=str(e)[:200])

        if normalized_position:
            teil_def["position"] = build_position(normalized_position)
            teil_def["parent"] = normalized_position.get("parent", root_teil_id)
            teil_def["orientation"] = build_orientation(
                normalized_position, teil_params
            )
        else:
            # Fallback: centered on top of root
            teil_def["parent"] = root_teil_id
            teil_def["position"] = {
                "side": "oben", "alignment": "centered",
                "edge_distances": None, "angle_deg": 0, "notes": "",
            }
            teil_def["orientation"] = "standard"

        updated_defs.append(teil_def)

        from src.config.loader import get_config as _gc
        _cfg = _gc()
        traces.append(_make_trace(
            agent="platzierer", step=step_i,
            input_data={"teil_id": teil_id, "pos_spec": pos_spec[:300]},
            output_data={
                "parent": teil_def.get("parent"),
                "position": teil_def.get("position"),
                "orientation": teil_def.get("orientation"),
                "normalized_position": normalized_position,
            },
            start_time=t_start,
            model=getattr(_cfg.models, "position_normalizer",
                          getattr(_cfg.models, "normalizer", "")),
            raw_response=position_raw or None,
        ))

    log.info("node_platzierer_done",
             teile=len(updated_defs),
             placed=sum(1 for d in updated_defs if d.get("parent") is not None))

    return {
        "teil_definitionen": updated_defs,
        "agent_traces": traces,
    }


def pocket_child_placer_node(state: PipelineState) -> dict:
    """Step 3.5: Inject hole-in-pocket features after assembly.

    Reads state.specification + state.blueprint, finds pockets that the
    user wants to drill into, and adds new SemanticFeature entries with
    parent set to the pocket ID. The resolver's
    _resolve_feature_in_feature pathway handles the local-frame math.

    No-op when:
      - The spec does not mention "in der Tasche" (or synonyms)
      - The blueprint has no pocket_rect / pocket_round / cutout features
    Either skips the LLM call entirely (no token cost).
    """
    blueprint = state.get("blueprint") or {}
    spec = state.get("specification") or state.get("description") or ""
    _t0 = time.time()
    _step = len(state.get("agent_traces", [])) + 1

    if not blueprint or not spec:
        return {"agent_traces": [_make_trace(
            agent="pocket_child_placer", step=_step,
            input_data={}, output_data={"skipped": True, "reason": "no_blueprint_or_spec"},
            start_time=_t0,
        )]}

    agent = _registry.get_agent(PocketChildPlacer)
    try:
        result = agent.extract(spec, blueprint)
    except Exception as e:
        log.warning("node_pocket_child_failed", error=str(e)[:200])
        return {"agent_traces": [_make_trace(
            agent="pocket_child_placer", step=_step,
            input_data={"spec_len": len(spec)},
            output_data={"error": str(e)[:200]},
            start_time=_t0,
        )]}

    features_to_add = result.get("features_to_add") or {}
    feature_ids_to_remove = result.get("feature_ids_to_remove") or []
    if not features_to_add:
        return {"agent_traces": [_make_trace(
            agent="pocket_child_placer", step=_step,
            input_data={"spec_len": len(spec), "pockets": _count_pockets(blueprint)},
            output_data={"added": 0},
            start_time=_t0,
        )]}

    # Merge into blueprint: append new features, drop upstream duplicates,
    # rebuild build_order minus removed IDs (resolver re-topo-sorts anyway).
    new_features = dict(blueprint.get("features") or {})
    for rid in feature_ids_to_remove:
        new_features.pop(rid, None)
    for fid, feat in features_to_add.items():
        new_features[fid] = feat

    new_build_order = [
        fid for fid in (blueprint.get("build_order") or [])
        if fid not in feature_ids_to_remove
    ]
    for fid in features_to_add:
        if fid not in new_build_order:
            new_build_order.append(fid)

    new_blueprint = dict(blueprint)
    new_blueprint["features"] = new_features
    new_blueprint["build_order"] = new_build_order

    log.info("node_pocket_child_added",
             count=len(features_to_add),
             ids=list(features_to_add.keys()),
             removed=feature_ids_to_remove)

    return {
        "blueprint": new_blueprint,
        "agent_traces": [_make_trace(
            agent="pocket_child_placer", step=_step,
            input_data={"spec_len": len(spec), "pockets": _count_pockets(blueprint)},
            output_data={"added": len(features_to_add),
                         "ids": list(features_to_add.keys()),
                         "removed": feature_ids_to_remove},
            start_time=_t0,
        )],
    }


def _count_pockets(blueprint: dict) -> int:
    """Count pocket-typed subtractive features in the blueprint."""
    features = blueprint.get("features") or {}
    if not isinstance(features, dict):
        return 0
    count = 0
    for feat in features.values():
        if not isinstance(feat, dict):
            continue
        if (feat.get("type") or "").lower() in ("pocket_rect", "pocket_round", "cutout"):
            if (feat.get("operation") or "add").lower() == "subtract":
                count += 1
    return count


