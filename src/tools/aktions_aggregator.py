"""src/tools/aktions_aggregator.py — Stage 4 of the per-action chain.

Aggregates per-action SemanticFeatures (from NormalizerAgent.define_feature)
into the final teil_definitionen[] structure that the platzierer / blueprint
resolver consume. Pure deterministic step — no LLM.

Responsibilities (per ADR 0003):
  - Group features by their host teil (uses the _teil_id marker).
  - Order features within each teil by _phrase_idx (spec order).
  - Resolve `parent` for nested children: a feature with
    _parent_phrase_idx=K gets parent = the id of the feature at phrase_idx
    K within the same teil (typically a Pocket).
  - Strip the internal _teil_id / _phrase_idx / _parent_phrase_idx markers.
  - Derive teil orientation from the teil description (same heuristic as
    the legacy build_teil_definition).

Schema-compatible to today: the output `teil_definitionen[]` has the same
shape that downstream nodes already consume.
"""

from __future__ import annotations

from typing import Any, Dict, List

import structlog

log = structlog.get_logger()


_ORIENTATION_HOCHKANT = ("hochkant", "stehend", "aufrecht")
_ORIENTATION_FLACH = ("flach", "liegend")


def aggregate(
    features: List[Dict[str, Any]],
    teile: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Build teil_definitionen[] from per-action features and the teil list.

    Args:
        features: SemanticFeatures returned by
            NormalizerAgent.define_feature(). Each must carry _teil_id and
            _phrase_idx markers; nested children additionally carry
            _parent_phrase_idx.
        teile: Inventar Step A teile in spec order (id, type, raw_params,
            optional beschreibung).

    Returns:
        List of teil_definition dicts with shape:
            {id, type, params, orientation, features: [...]}
        Each feature is the input feature minus the internal markers, with
        `parent` rewritten to the parent-pocket's feature_id where the
        original phrase was nested.
    """
    by_teil: Dict[str, List[Dict[str, Any]]] = {}
    for feat in features:
        tid = feat.get("_teil_id") or feat.get("parent") or ""
        if not tid:
            log.warning("aktions_aggregator_feature_without_teil_id",
                        feature_id=feat.get("id"))
            continue
        by_teil.setdefault(tid, []).append(feat)

    teil_definitionen: List[Dict[str, Any]] = []
    for teil in teile:
        tid = teil["id"]
        raw = sorted(by_teil.get(tid, []),
                     key=lambda f: f.get("_phrase_idx", 0))

        feature_by_phrase_idx = {
            f.get("_phrase_idx"): f for f in raw if "_phrase_idx" in f
        }

        cleaned: List[Dict[str, Any]] = []
        for feat in raw:
            cleaned.append(_resolve_and_clean(
                feat, tid, feature_by_phrase_idx
            ))

        teil_definitionen.append({
            "id": tid,
            "type": teil.get("type", "box"),
            "params": teil.get("raw_params", {}),
            "orientation": _orientation_from_teil(teil),
            "features": cleaned,
        })

    return teil_definitionen


def _resolve_and_clean(
    feature: Dict[str, Any],
    teil_id: str,
    by_phrase_idx: Dict[Any, Dict[str, Any]],
) -> Dict[str, Any]:
    """Return a copy of `feature` with parent resolved and markers stripped."""
    out = dict(feature)
    parent_phrase_idx = out.get("_parent_phrase_idx")

    if parent_phrase_idx is not None:
        parent_feat = by_phrase_idx.get(parent_phrase_idx)
        if parent_feat is not None and parent_feat.get("id"):
            out["parent"] = parent_feat["id"]
        else:
            # Dangling reference — keep the teil_id default so the feature
            # still anchors to a valid host. Log so the issue stays visible.
            log.warning(
                "aktions_aggregator_dangling_parent",
                feature_id=out.get("id"),
                parent_phrase_idx=parent_phrase_idx,
                teil_id=teil_id,
            )
            out["parent"] = teil_id

    for marker in ("_teil_id", "_phrase_idx", "_parent_phrase_idx"):
        out.pop(marker, None)

    return out


def _orientation_from_teil(teil: Dict[str, Any]) -> str:
    """Heuristic copied from the legacy build_teil_definition: 'hochkant',
    'flach', or 'standard' based on teil.beschreibung keywords."""
    beschreibung = (teil.get("beschreibung") or "").lower()
    if any(kw in beschreibung for kw in _ORIENTATION_HOCHKANT):
        return "hochkant"
    if any(kw in beschreibung for kw in _ORIENTATION_FLACH):
        return "flach"
    return "standard"
