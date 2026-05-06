"""src/tools/aktions_splitter.py — Deterministic splitter for action phrases.

Splits the cleaned user specification into individual action phrases — one
per intended geometry feature (Tasche, Bohrung, Nut, Fase, Rundung). Detects
nesting markers ("in der Tasche eine Bohrung ...") and links child phrases
to their parent via parent_phrase_idx.

Replaces the monolithic Inventar Step B LLM call with deterministic text
segmentation. See docs/decisions/0003-inventar-feature-definierer-pro-aktion.md.

Pure text-segmentation along clear markers — no interpretation, no LLM.
The Aktions-Klassifizierer (Stufe 2) handles understanding what the phrase
means; this module only cuts the spec into pieces.

Output schema per phrase:
    {
        "phrase":            str,        # original substring of spec
        "teil_id":           str,        # id from Inventar Step A
        "phrase_idx":        int,        # 0-based, per teil
        "parent_phrase_idx": int | None, # set on nested children
    }
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional


# Side keywords mark the start of a top-level action within a comma segment.
# Matched as bare words only — adjective forms ("rechten", "linken",
# "oberen", "unteren") are descriptors inside a phrase, not split markers.
_SIDE_KEYWORDS = ("oben", "unten", "rechts", "links", "vorne", "hinten")
_SIDE_RE = re.compile(
    r"\b(?:" + "|".join(_SIDE_KEYWORDS) + r")\b",
    re.IGNORECASE,
)

# Nesting markers signal "this phrase belongs inside the previous parent".
# Covers "in der Tasche", "in der Ausnehmung", "darin", "innerhalb".
_NESTED_RE = re.compile(
    r"\b(?:in\s+der\s+(?:tasche|ausnehmung)|darin|innerhalb)\b",
    re.IGNORECASE,
)


def split_spec_into_aktionen(
    specification: str,
    teile: List[Dict],
) -> List[Dict]:
    """Segment a cleaned user spec into action phrases per teil.

    Args:
        specification: Cleaned user spec (post-punctuation_agent).
        teile: Inventar Step A output. Each dict needs at least an "id".

    Returns:
        Action-phrase list in spec order. Empty list on empty inputs.
    """
    if not specification or not teile:
        return []

    teil_ids = [t["id"] for t in teile]
    counters: Dict[str, int] = {tid: 0 for tid in teil_ids}
    last_teil = teil_ids[0]
    aktionen: List[Dict] = []

    for raw_segment in _comma_split(specification):
        seg_teil = _assign_teil_id(raw_segment, teil_ids, last_teil)
        seg = _strip_part_declaration(raw_segment)
        if not seg:
            continue

        parent_text, children = _split_at_nested_markers(seg)
        parent_idx: Optional[int]

        if parent_text:
            parent_idx = counters[seg_teil]
            aktionen.append({
                "phrase": parent_text,
                "teil_id": seg_teil,
                "phrase_idx": parent_idx,
                "parent_phrase_idx": None,
            })
            counters[seg_teil] += 1
        else:
            # Segment opens directly with "in der Tasche ..." — no fresh
            # parent in this segment, so link to the most recent parent of
            # the same teil. Falls back to None if there isn't one yet.
            parent_idx = _last_parent_idx(aktionen, seg_teil)

        for child_text in children:
            aktionen.append({
                "phrase": child_text,
                "teil_id": seg_teil,
                "phrase_idx": counters[seg_teil],
                "parent_phrase_idx": parent_idx,
            })
            counters[seg_teil] += 1

        last_teil = seg_teil

    return aktionen


def _comma_split(spec: str) -> List[str]:
    """Top-level comma-separated segments. Empty/whitespace-only segments
    are dropped — handles ',,' and trailing ',' gracefully."""
    return [s.strip() for s in spec.split(",") if s.strip()]


def _strip_part_declaration(segment: str) -> str:
    """Strip a leading part-declaration (e.g. '200mm wuerfel') by cutting
    everything before the first bare side keyword. If no side keyword is
    present, the segment is treated as a pure part declaration and dropped
    by returning ''."""
    m = _SIDE_RE.search(segment)
    if m is None:
        return ""
    return segment[m.start():].strip()


def _split_at_nested_markers(segment: str) -> tuple[str, List[str]]:
    """Return (parent_text, [child_text, ...]).

    parent_text is the part before the first nested marker (may be empty).
    Each child entry begins at a nested marker and runs up to the next.
    """
    matches = list(_NESTED_RE.finditer(segment))
    if not matches:
        return segment.strip(), []

    parent_text = segment[:matches[0].start()].strip()
    children: List[str] = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(segment)
        children.append(segment[m.start():end].strip())
    return parent_text, children


def _assign_teil_id(
    segment: str,
    teil_ids: List[str],
    last_teil: str,
) -> str:
    """Pick the teil this segment talks about. Single-part: trivial.
    Multi-part: substring match on teil-id; otherwise carry the last seen
    teil forward (positional context).
    """
    if len(teil_ids) == 1:
        return teil_ids[0]
    seg_lower = segment.lower()
    for tid in teil_ids:
        if tid.lower() in seg_lower:
            return tid
    return last_teil


def _last_parent_idx(aktionen: List[Dict], teil_id: str) -> Optional[int]:
    """phrase_idx of the most recent parent (parent_phrase_idx is None) for
    the given teil. Returns None if no parent exists yet."""
    for entry in reversed(aktionen):
        if entry["teil_id"] == teil_id and entry["parent_phrase_idx"] is None:
            return entry["phrase_idx"]
    return None
