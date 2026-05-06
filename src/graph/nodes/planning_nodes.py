"""Planning nodes: 3-step chain (S0: feature_definierer + platzierer), blueprint_architect, blueprint_resolver, coordinate_validator, plan_validator, function_decomposer."""
from __future__ import annotations
import json
import time
import structlog

from src.graph.state import PipelineState
from src.agents.blueprint_architect import BlueprintArchitect
from src.agents.inventar_agent import InventarAgent
from src.agents.position_extractor_agent import PositionExtractorAgent
from src.agents.text_splitter_agent import TextSplitterAgent
from src.agents.normalizer_agent import NormalizerAgent
from src.agents.position_normalizer_agent import PositionNormalizerAgent
from src.agents.aktions_klassifizierer import AktionsKlassifizierer
from src.agents.assembly_agent import AssemblyAgent
from src.agents.pocket_child_placer import PocketChildPlacer
from src.agents.function_decomposer import FunctionDecomposerAgent
from src.agents.plan_validator import PlanValidatorAgent
from src.tools.aktions_aggregator import aggregate as aktions_aggregate
from src.tools.aktions_splitter import split_spec_into_aktionen
from src.tools.feature_builder import build_teil_definition
from src.tools.position_builder import build_position, build_orientation
from src.graph.feature_tree import FeatureTree
from ._registry import get_agent, get_raw_response
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

    agent = get_agent(InventarAgent)

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
    agent = get_agent(PositionExtractorAgent)
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

        positionen.append({
            "teil_id": teil_id,
            "is_root": teil_id == root_id,
            "placement_sentences": placement,
            "feature_sentences": labels["feature_sentences"],
        })

        log.info("position_extractor_teil_done",
                 teil=teil_id,
                 placement_count=len(placement),
                 feature_count=len(labels["feature_sentences"]))

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

    agent = get_agent(TextSplitterAgent)
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

    normalizer = get_agent(NormalizerAgent)
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

    position_normalizer = get_agent(PositionNormalizerAgent)
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

    agent = get_agent(PocketChildPlacer)
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


def assembly_node(state: PipelineState) -> dict:
    """Step 3: Assemble parts into a complete semantic blueprint.

    Deterministic: TeilDefinierer already attached parent + position + orientation
    via the PositionNormalizer. This step just merges everything into the final
    blueprint format. No LLM call needed.
    """
    teil_defs = state.get("teil_definitionen", [])
    _t0 = time.time()
    _step = len(state.get("agent_traces", [])) + 1

    if not teil_defs:
        log.warning("node_assembly_skipped", reason="no_teil_definitionen")
        return {"agent_traces": [_make_trace(
            agent="assembly", step=_step,
            input_data={}, output_data={"skipped": True},
            start_time=_t0,
        )]}

    # Single-part shortcut
    if len(teil_defs) == 1:
        blueprint = _single_part_blueprint(teil_defs[0])
        log.info("node_assembly_single_part", features=len(blueprint.get("features", {})))
        _trace = _make_trace(
            agent="assembly", step=_step,
            input_data={"teil_count": 1},
            output_data={"features": len(blueprint.get("features", {})), "mode": "single_part_shortcut"},
            start_time=_t0,
        )
        return {
            "blueprint": blueprint,
            "plan_valid": False,
            "plan_validation_issues": "",
            "coordinate_validation_issues": "",
            "validator_feedback": "",
            "agent_traces": [_trace],
        }

    # Multi-part: deterministic assembly from teil_defs (each has parent + position)
    blueprint = _deterministic_assembly(teil_defs)

    log.info("node_assembly_done_deterministic",
             features=len(blueprint.get("features", {})),
             build_order=blueprint.get("build_order", []))

    _trace = _make_trace(
        agent="assembly", step=_step,
        input_data={"teil_count": len(teil_defs)},
        output_data={
            "features": len(blueprint.get("features", {})),
            "build_order": blueprint.get("build_order", []),
            "mode": "deterministic",
        },
        start_time=_t0,
    )

    return {
        "blueprint": blueprint,
        "plan_valid": False,
        "plan_validation_issues": "",
        "coordinate_validation_issues": "",
        "validator_feedback": "",
        "agent_traces": [_trace],
    }


def _deterministic_assembly(teil_defs: list[dict]) -> dict:
    """Merge teil_definitions into a complete semantic blueprint.

    Each teil_def already has parent + position + orientation (from
    PositionNormalizer + build_position + build_orientation). This function
    just combines all teile and their features into one features dict with
    proper build_order.

    No LLM needed — purely structural merging.
    """
    features = {}
    build_order = []

    # First pass: add all teile (root first, then others)
    roots = [t for t in teil_defs if t.get("parent") is None]
    children = [t for t in teil_defs if t.get("parent") is not None]

    # Topological ordering: parent before child
    ordered_teile = list(roots)
    remaining = list(children)
    while remaining:
        added_any = False
        for t in list(remaining):
            parent_id = t.get("parent")
            if parent_id in {o["id"] for o in ordered_teile}:
                ordered_teile.append(t)
                remaining.remove(t)
                added_any = True
        if not added_any:
            # Circular or orphaned — just append the rest to avoid infinite loop
            ordered_teile.extend(remaining)
            break

    # Build features dict + build_order
    for teil_def in ordered_teile:
        teil_id = teil_def["id"]
        is_root = teil_def.get("parent") is None

        # Add teil itself
        teil_feature = {
            "type": teil_def.get("type", "box"),
            "params": teil_def.get("params", {}),
            "orientation": teil_def.get("orientation", "standard"),
            "parent": teil_def.get("parent"),
            "operation": "add",
            "notes": "",
        }
        if not is_root and teil_def.get("position"):
            teil_feature["position"] = teil_def["position"]

        features[teil_id] = teil_feature
        build_order.append(teil_id)

        # Add this teil's features (expanded for multi-axis slots)
        expanded = _expand_multi_axis_slots(teil_def.get("features", []))
        for feat in expanded:
            feat_id = feat.get("id", f"feat_{teil_id}_{len(features)}")
            # Deduplicate: if another teil already used this id, prefix with parent
            if feat_id in features:
                feat_id = f"{teil_id}_{feat_id}"
            pos = feat.get("position", {
                "side": "oben", "alignment": "centered",
                "edge_distances": None, "angle_deg": 0, "notes": "",
            })
            # Merge feature-level notes into position.notes if position.notes is empty
            if not pos.get("notes") and feat.get("notes"):
                pos["notes"] = feat["notes"]
            features[feat_id] = {
                "type": feat.get("type", "hole_single"),
                "params": feat.get("params", {}),
                "parent": teil_id,
                "position": pos,
                "operation": feat.get("operation", "subtract"),
                "notes": feat.get("notes", ""),
            }
            build_order.append(feat_id)

    # Build description from teil_defs
    teil_names = [t["id"] for t in teil_defs]
    description = f"Baugruppe aus {len(teil_defs)} Teilen: {', '.join(teil_names)}"

    return {
        "description": description,
        "build_order": build_order,
        "features": features,
    }


def _expand_multi_axis_slots(features: list[dict]) -> list[dict]:
    """Split slot features with combined axis notes into separate features.

    "entlang X und Y" → two slots, one "entlang X" and one "entlang Y".
    This handles cases where the LLM merges two slots into one feature.
    """
    import re
    expanded = []
    for feat in features:
        notes = (feat.get("position") or {}).get("notes", "")
        notes_lower = notes.lower()
        ftype = feat.get("type", "")

        # Detect any two-axis combination: "X und Y", "Y und Z", "X und Z", etc.
        axis_match = re.findall(r"([xyz])", notes_lower)
        if ftype in ("slot", "groove") and len(axis_match) >= 2 and "und" in notes_lower:
            axes = [a.upper() for a in dict.fromkeys(axis_match)]  # unique, ordered
            for axis_label in axes:
                clone = json.loads(json.dumps(feat))  # deep copy
                clone["id"] = f"{feat.get('id', 'slot')}_{axis_label.lower()}"
                clone["position"]["notes"] = f"entlang {axis_label}"
                expanded.append(clone)
            log.info("expand_multi_axis_slot", original_id=feat.get("id"), split_into=len(axes))
        else:
            expanded.append(feat)

    # Fix perpendicular axis references: when two slots on the same face both
    # map to the same direction (because one axis is perpendicular to the face),
    # remap to the two actual on-face directions.
    expanded = _fix_slot_axis_per_face(expanded)

    return expanded


# Which global axes are visible on each face, and which is perpendicular
_FACE_AXES = {
    "oben":   ("X", "Y", "Z"),  # visible: X, Y; perp: Z
    "unten":  ("X", "Y", "Z"),
    "rechts": ("Y", "Z", "X"),  # visible: Y, Z; perp: X
    "links":  ("Y", "Z", "X"),
    "vorne":  ("X", "Z", "Y"),  # visible: X, Z; perp: Y
    "hinten": ("X", "Z", "Y"),
}


def _fix_slot_axis_per_face(features: list[dict]) -> list[dict]:
    """Fix axis notes on slots where the stated axis is perpendicular to the face.

    On face "rechts" (>X), the visible axes are Y and Z. If the LLM writes
    "entlang X" and "entlang Y", X is perpendicular and would be a duplicate.
    This function remaps the perpendicular axis to the other visible axis.
    """
    import re

    # Group slots by face (side)
    slots_by_side: dict[str, list[int]] = {}
    for i, feat in enumerate(features):
        if feat.get("type") not in ("slot", "groove"):
            continue
        side = (feat.get("position") or {}).get("side", "oben")
        slots_by_side.setdefault(side, []).append(i)

    for side, indices in slots_by_side.items():
        if side not in _FACE_AXES:
            continue
        axis1, axis2, perp = _FACE_AXES[side]

        for idx in indices:
            notes = (features[idx].get("position") or {}).get("notes", "")
            notes_lower = notes.lower()
            # Check if this slot references the perpendicular axis
            if f"entlang {perp.lower()}" in notes_lower or f"{perp.lower()}-achse" in notes_lower:
                # Determine which visible axis is NOT yet used by other slots on this face
                used_axes = set()
                for other_idx in indices:
                    if other_idx == idx:
                        continue
                    other_notes = (features[other_idx].get("position") or {}).get("notes", "").lower()
                    if f"entlang {axis1.lower()}" in other_notes or f"{axis1.lower()}-achse" in other_notes:
                        used_axes.add(axis1)
                    if f"entlang {axis2.lower()}" in other_notes or f"{axis2.lower()}-achse" in other_notes:
                        used_axes.add(axis2)

                # Assign the unused visible axis, or axis2 as default
                if axis1 not in used_axes:
                    new_axis = axis1
                elif axis2 not in used_axes:
                    new_axis = axis2
                else:
                    new_axis = axis2  # both used, default to second

                features[idx]["position"]["notes"] = f"entlang {new_axis}"
                log.info("fix_slot_perp_axis",
                         side=side, old=notes, new=f"entlang {new_axis}",
                         reason=f"{perp} is perpendicular to {side}")

    return features


def _single_part_blueprint(teil_def: dict) -> dict:
    """Build a complete blueprint from a single teil definition (no LLM needed)."""
    teil_id = teil_def["id"]
    features = {}

    # Root body
    features[teil_id] = {
        "type": teil_def.get("type", "box"),
        "params": teil_def.get("params", {}),
        "orientation": teil_def.get("orientation", "standard"),
        "parent": None,
        "operation": "add",
        "notes": "",
    }

    # Sub-features (holes, slots, etc.)
    # First expand multi-axis slots ("entlang X und Y" → 2 separate features)
    expanded_features = _expand_multi_axis_slots(teil_def.get("features", []))

    for feat in expanded_features:
        feat_id = feat.get("id", f"feat_{teil_id}")
        pos = feat.get("position", {
            "side": "oben", "alignment": "centered",
            "edge_distances": None, "angle_deg": 0, "notes": "",
        })
        # Merge feature-level notes into position.notes if position.notes is empty
        if not pos.get("notes") and feat.get("notes"):
            pos["notes"] = feat["notes"]
        features[feat_id] = {
            "type": feat.get("type", "hole_single"),
            "params": feat.get("params", {}),
            "parent": teil_id,
            "position": pos,
            "operation": feat.get("operation", "subtract"),
            "notes": feat.get("notes", ""),
        }

    build_order = [teil_id] + [f.get("id", f"feat_{teil_id}") for f in expanded_features]

    return {
        "description": f"{teil_def.get('type', 'box')} {teil_def.get('params', {})}",
        "build_order": build_order,
        "features": features,
    }


# ══════════════════════════════════════════════════════════════════
# Blueprint Architect (monolithisch — Fallback für Fix/Modify)
# ══════════════════════════════════════════════════════════════════

def blueprint_architect_node(state: PipelineState) -> dict:
    """Generate a complete Feature Tree Blueprint in a single LLM call.

    Replaces the Häppchen chain (Feature Tagger → Feature Assigner →
    Feature Position Assigner → Part Position Assigner → Blueprint Assembler).

    Handles three modes:
      - Fresh:  spec → new blueprint
      - Modify: spec + change_description + previous_blueprint → updated blueprint
      - Fix:    spec + validation errors + broken blueprint → corrected blueprint
    """
    spec = state.get("specification", state.get("description", ""))
    change_desc = state.get("change_description", "")
    prev_blueprint = state.get("blueprint", {}) or state.get("previous_blueprint", {})
    validation_issues = (
        state.get("coordinate_validation_issues", "")
        or state.get("plan_validation_issues", "")
        or state.get("validator_feedback", "")
    )

    _t0 = time.time()
    _step = len(state.get("agent_traces", [])) + 1
    architect = get_agent(BlueprintArchitect)

    try:
        # Mode selection
        if validation_issues and prev_blueprint:
            # Fix mode: re-route after validation failure
            log.info("node_blueprint_architect", mode="fix",
                     issues=validation_issues[:80])
            result = architect.fix(spec, prev_blueprint, validation_issues)
        elif change_desc and prev_blueprint:
            # Modify mode: apply changes to existing blueprint
            log.info("node_blueprint_architect", mode="modify",
                     change=change_desc[:80])
            result = architect.modify(spec, change_desc, prev_blueprint)
        else:
            # Fresh mode: generate from scratch
            log.info("node_blueprint_architect", mode="fresh",
                     spec=spec[:80])
            result = architect.generate(spec)

        blueprint = result["blueprint"]
        rag_chunks = result.get("rag_chunks_used", [])

    except ValueError as e:
        log.error("node_blueprint_architect_failed", error=str(e)[:200])
        _trace = _make_trace(
            agent="blueprint_architect", step=_step,
            input_data={"specification": spec},
            output_data={"error": str(e)[:200]},
            start_time=_t0,
        )
        return {
            "blueprint": prev_blueprint or {},
            "plan_valid": False,
            "plan_validation_issues": f"Blueprint Architect error: {str(e)[:150]}",
            "agent_traces": [_trace],
        }

    from src.config.loader import get_config as _gc
    _trace = _make_trace(
        agent="blueprint_architect", step=_step,
        input_data={"specification": spec, "mode": "fix" if validation_issues else ("modify" if change_desc else "fresh")},
        output_data={
            "build_order": blueprint.get("build_order", []),
            "features": len(blueprint.get("features", {})),
        },
        start_time=_t0,
        model=_gc().models.blueprint_architect,
        rag_chunks_used=rag_chunks,
        raw_response=getattr(architect, "_last_raw_response", None),
    )

    return {
        "blueprint": blueprint,
        "plan_valid": False,  # let validators run
        "plan_validation_issues": "",
        "coordinate_validation_issues": "",
        "validator_feedback": "",
        "agent_traces": [_trace],
    }


def blueprint_resolver_node(state: PipelineState) -> dict:
    """Deterministic: convert semantic blueprint → resolved blueprint.

    Handles orientation resolution (hochkant → dimension swap),
    face calculation (rechts → >X), and offset computation
    (flush_right → numeric offset). No LLM needed.

    Sits between blueprint_architect and coordinate_validator.
    If the blueprint is already resolved (legacy format), passes through.
    """
    blueprint = state.get("blueprint", {})
    _t0 = time.time()
    _step = len(state.get("agent_traces", [])) + 1

    if not blueprint or not blueprint.get("features"):
        return {"agent_traces": [_make_trace(
            agent="blueprint_resolver", step=_step,
            input_data={}, output_data={"skipped": True, "reason": "no_blueprint"},
            start_time=_t0,
        )]}

    from src.tools.blueprint_resolver import resolve_blueprint

    # resolve_blueprint handles all cases internally:
    # - Semantic format → full resolution (orientation + face + offsets)
    # - Already-resolved legacy → passthrough
    # - Mixed fix-mode → orientation resolution only, keep existing placement
    resolved = resolve_blueprint(blueprint)

    # Log what changed
    changes = []
    for fid, feat in resolved.get("features", {}).items():
        orig = blueprint.get("features", {}).get(fid, {})
        orig_params = orig.get("params", {})
        new_params = feat.get("params", {})
        if orig_params != new_params:
            changes.append(f"{fid}: params changed (orientation resolved)")
        placement = feat.get("placement")
        if placement and (placement.get("offset_x", 0) != 0 or placement.get("offset_y", 0) != 0):
            changes.append(f"{fid}: offsets computed ({placement['offset_x']}, {placement['offset_y']})")

    log.info("node_blueprint_resolver",
             features=len(resolved.get("features", {})),
             changes=len(changes))

    _trace = _make_trace(
        agent="blueprint_resolver", step=_step,
        input_data={"build_order": blueprint.get("build_order", [])},
        output_data={
            "features_resolved": len(resolved.get("features", {})),
            "changes": changes[:10],  # limit trace size
        },
        start_time=_t0,
    )

    return {
        "blueprint": resolved,
        "agent_traces": [_trace],
    }


def function_decomposer_node(state: PipelineState) -> dict:
    """Generate a Python skeleton from the Feature Tree blueprint.

    Rule-based (no LLM). Runs between plan_validator and coder.
    Writes code_skeleton to state — Coder reads it to fill in function bodies.
    If blueprint is not Feature Tree format, writes empty skeleton and Coder
    falls back to legacy CSG-Tree mode.
    """
    blueprint = state.get("blueprint", {})
    _t0 = time.time()
    _step = len(state.get("agent_traces", [])) + 1

    if FeatureTree.is_feature_tree(blueprint):
        log.info("node_function_decomposer",
                 build_order=blueprint.get("build_order", []),
                 features=len(blueprint.get("features", {})))
    else:
        log.info("node_function_decomposer_skipped", reason="not_feature_tree")

    result = get_agent(FunctionDecomposerAgent).decompose(state)

    mode = result.get("generation_mode", "llm")
    _trace = _make_trace(
        agent="function_decomposer", step=_step,
        input_data={"build_order": blueprint.get("build_order", [])},
        output_data={
            "generation_mode": mode,
            "code_lines": len(result.get("code", "").splitlines()),
            "skeleton_lines": len(result.get("code_skeleton", "").splitlines()),
        },
        start_time=_t0,
    )
    result["agent_traces"] = [_trace]
    return result


def coordinate_validator_node(state: PipelineState) -> dict:
    """Rule-based coordinate and dimension check after the Planner.

    Runs deterministically — no LLM needed. Checks that feature dimensions
    are physically plausible (fits in parent, depth ≤ material, bolt circle
    geometry, wall thickness). Skips CSG-Tree blueprints.

    Returns coordinate_validation_issues (str). Empty = all passed.
    On ERROR-severity issues: routes back to Planner. WARNINGs pass through.
    """
    blueprint = state.get("blueprint", {})
    _t0 = time.time()
    _step = len(state.get("agent_traces", [])) + 1

    if not blueprint:
        return {"coordinate_validation_issues": "", "coordinate_valid": True}

    from src.tools.coordinate_validator import run_coordinate_check, format_issues_for_planner
    issues = run_coordinate_check(blueprint)

    errors = [i for i in issues if i.severity == "ERROR"]
    warnings = [i for i in issues if i.severity == "WARNING"]

    _trace = _make_trace(
        agent="coordinate_validator", step=_step,
        input_data={"build_order": blueprint.get("build_order", [])},
        output_data={"errors": len(errors), "warnings": len(warnings)},
        start_time=_t0,
    )

    if errors:
        attempts = state.get("coordinate_validation_attempts", 0) + 1
        log.warning("node_coordinate_validator_failed",
                    errors=len(errors), warnings=len(warnings),
                    attempt=attempts)
        issues_text = format_issues_for_planner(issues)
        return {
            "coordinate_validation_issues": issues_text,
            "coordinate_valid": False,
            "coordinate_validation_attempts": attempts,
            "agent_traces": [_trace],
        }

    if warnings:
        log.info("node_coordinate_validator_warnings", warnings=len(warnings))

    log.info("node_coordinate_validator_ok",
             features=len(blueprint.get("build_order", [])))
    return {
        "coordinate_validation_issues": "",
        "coordinate_valid": True,
        "agent_traces": [_trace],
    }


def plan_validator_node(state: PipelineState) -> dict:
    """Validate the Blueprint before the expensive Coder runs.

    First runs a fast deterministic quick_check (feature count + depth consistency).
    If that passes, runs the LLM Plan-Validator for geometric logic errors.
    On failure, routes back to Planner (max config.plan_validator.max_retries).

    In Häppchen mode (specialized agents produced the blueprint), the LLM validator
    is skipped — the specialized agents already validated structure and positions.
    Only the deterministic quick_check runs (for Feature Tree: skipped entirely).
    """
    blueprint = state.get("blueprint", {})
    spec = state.get("specification") or state.get("description", "")
    _t0 = time.time()
    _step = len(state.get("agent_traces", [])) + 1

    # Fast deterministic check: does blueprint contain all features from spec?
    # Runs always — even on patches, to catch missing features or wrong depth values.
    # Skip for Feature Tree blueprints: quick_check is CSG-Tree specific.
    if blueprint and spec and not FeatureTree.is_feature_tree(blueprint):
        try:
            from src.tools.geometry_precheck import quick_check
            quick_issues = quick_check(blueprint, spec)
            if quick_issues:
                issues_text = " | ".join(i["message"] for i in quick_issues)
                attempts = state.get("plan_validation_attempts", 0) + 1
                log.warning("node_plan_validator_quick_fail",
                            issues=issues_text[:120], attempt=attempts)
                _trace = _make_trace(
                    agent="plan_validator", step=_step,
                    input_data={"blueprint": blueprint},
                    output_data={"is_valid": False, "issues": issues_text, "source": "quick_check"},
                    start_time=_t0,
                )
                return {
                    "plan_valid": False,
                    "plan_validation_issues": f"Blueprint is missing features or has wrong depth values: {issues_text}",
                    "plan_validation_attempts": attempts,
                    "agent_traces": [_trace],
                }
        except Exception as _qc_err:
            log.warning("node_plan_validator_quick_check_failed", error=str(_qc_err))

    # Skip LLM plan_validator for non-additive patch modifications.
    # A pure value/position change on a previously-validated blueprint cannot introduce
    # structural errors — the quick_check above is sufficient.
    # LLM still runs for: fresh blueprints, additive changes, revisions after validator feedback.
    change_desc = state.get("change_description", "")
    is_additive = state.get("is_additive", False)
    validator_feedback = state.get("validator_feedback", "")
    if (change_desc
            and not is_additive
            and not validator_feedback
            and state.get("plan_validation_attempts", 0) == 0):
        log.info("node_plan_validator_skipped",
                 reason="non_additive_patch", change=change_desc[:60])
        _trace = _make_trace(
            agent="plan_validator", step=_step,
            input_data={"blueprint": blueprint},
            output_data={"is_valid": True, "source": "skipped_non_additive_patch"},
            start_time=_t0,
        )
        return {"plan_valid": True, "agent_traces": [_trace]}

    log.info("node_plan_validator",
             blueprint_desc=blueprint.get("description", "")[:60],
             attempt=state.get("plan_validation_attempts", 0))
    result = get_agent(PlanValidatorAgent).validate(state)
    from src.config.loader import get_config as _gc
    _trace = _make_trace(
        agent="plan_validator", step=_step,
        input_data={"blueprint": blueprint},
        output_data={"is_valid": result.get("plan_valid", False),
                     "issues": result.get("plan_validation_issues", "")},
        start_time=_t0, model=_gc().models.plan_validator,
        raw_response=get_raw_response(PlanValidatorAgent),
    )
    result["agent_traces"] = [_trace]
    return result


# ══════════════════════════════════════════════════════════════════
# Per-Action Chain (ADR 0003) — wired in Stufe 5b, additive in 5a
# ══════════════════════════════════════════════════════════════════

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

    agent = get_agent(AktionsKlassifizierer)
    klassifikationen: list[dict] = []
    raw_responses: list[str] = []
    by_idx_per_teil: dict[tuple[str, int], dict] = {}

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

        try:
            k = agent.classify(p, teil, parent_phrase=parent_phrase)
        except Exception as e:
            log.error("aktions_klassifizierer_failed",
                      phrase=p.get("phrase", "")[:80], error=str(e)[:200])
            continue

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
