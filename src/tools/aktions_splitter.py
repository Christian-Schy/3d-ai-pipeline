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

# Part-declaration markers: dimension + part-keyword in any order. Used to
# distinguish "200mm wuerfel oben eine Bohrung ..." (strippable prefix) from
# "auf der rechten seite eine Bohrung ..." (already a feature phrase — must
# not be stripped, even though it ends with bare 'rechts' deep inside).
_PART_KEYWORDS = (
    r"wuerfel", r"würfel", r"wurfel",
    r"platte", r"zylinder", r"quader", r"kugel",
    r"box", r"teil", r"stueck", r"stück", r"stuck",
)
_PART_DECL_RE = re.compile(
    r"\b(?:" + "|".join(_PART_KEYWORDS) + r")\b",
    re.IGNORECASE,
)

# Feature keywords — if a segment lacks a bare side-keyword but mentions
# one of these, it is still a real feature phrase (the classifier can derive
# the side from descriptors like "auf der rechten seite"). Without this guard,
# segments like "auf der rechten seite eine bohrung von der linken kante 20mm
# entfernt von der oberen 30mm entfernt mit 20mm durchmesser 10 tief" would be
# silently dropped because none of oben/unten/rechts/links/vorne/hinten appear
# as a *bare* token.
#
# Plurals + compounds: each stem accepts a small enumerated suffix list so the
# regex catches "bohrungen", "taschen", "nuten", "fasen", "rundungen" plus
# loch-compounds "lochmuster", "lochkreis", "lochreihe", "lochbild" without
# matching unrelated words like "fasern" or "nutzbar".
_FEATURE_RE = re.compile(
    r"\b(?:"
    r"tasche(?:n)?"
    r"|bohrung(?:en)?"
    r"|nut(?:en)?"
    r"|fase(?:n)?"
    r"|rundung(?:en)?"
    r"|loch(?:muster|kreis|reihe|bild|er)?"
    r"|ausnehmung(?:en)?"
    r"|aush[oö]hlung(?:en)?"
    r"|ausfr[äa]sung(?:en)?"
    r"|aussparung(?:en)?"
    r")\b",
    re.IGNORECASE,
)

# Safety-net for missing punctuation between actions (Run-944d-Pattern).
# Voice-style input glues sentences without commas: "...20mm tiefe links
# soll eine nut...". Punctuation-Agent should catch this — but if it
# doesn't, the splitter falls back to inserting a comma when a typical
# action-end word is immediately followed by "<side> soll".
# Conservative: only triggers on the closed list of action-end words to
# avoid false positives in nested markers ("in der tasche oben ...") or
# part declarations ("100mm wuerfel oben ...").
_PARAM_END_WORDS = (
    "tiefe", "tief",
    "breite", "breit",
    "h[oö]he", "hoch",
    "durchmesser", "radius",
    "l[aä]nge", "lang",
    "kantenl[aä]nge",
    "hin",
    "versetzt", "rotiert", "gedreht",
)
_MISSING_COMMA_RE = re.compile(
    r"(\b(?:" + "|".join(_PARAM_END_WORDS) + r")\b)\s+"
    r"(\b(?:" + "|".join(_SIDE_KEYWORDS) + r")\s+soll\b)",
    re.IGNORECASE,
)

_PLACEMENT_CONTINUATION_RE = re.compile(
    r"^\s*(?:und\s+)?(?:\d+(?:[.,]\d+)?\s*mm\s+)?"
    r"(?:nach|um)\s+(?:oben|unten|rechts|links|vorne|hinten)\b"
    r".*\b(?:versetzt|verschoben)\b",
    re.IGNORECASE,
)

_CORNER_PREFIX_RE = re.compile(
    r"\b(?:obere|untere|rechte|linke)\s+"
    r"(?:rechte|linke|obere|untere)\s+ecke\b",
    re.IGNORECASE,
)

_SECTION_ANCHOR_PREFIX_RE = re.compile(
    r"^\s*(?:" + "|".join(_SIDE_KEYWORDS) + r")\s*:\s+.*\b(?:ecke|kante)\b",
    re.IGNORECASE,
)


def _insert_missing_commas(spec: str) -> str:
    """Insert a comma before '<side> soll' when the preceding word is a
    typical action-end token. Defensive against voice-style input where
    the user runs sentences together without punctuation.

    Example: '...20mm tiefe links soll eine nut...'
          → '...20mm tiefe, links soll eine nut...'

    See `tests/golden/components/SPLIT_run_944d_missing_comma_side_soll/`
    for the regression case.
    """
    return _MISSING_COMMA_RE.sub(r"\1, \2", spec)


def _is_placement_continuation(segment: str) -> bool:
    """True for comma fragments that only refine the previous feature."""
    return bool(_PLACEMENT_CONTINUATION_RE.search(segment or ""))


def _is_pre_feature_anchor_prefix(segment: str) -> bool:
    """True for comma fragments that introduce an anchor for the next feature.

    Example from B_kombo_additive_anchor:
      "oben: obere rechte ecke der oberseite, 20mm nach unten ..."

    The comma is not an action boundary there. The first fragment has no
    feature keyword, but carries the corner anchor needed by the next
    bohrung phrase.
    """
    if not segment or _FEATURE_RE.search(segment):
        return False
    return bool(
        _SECTION_ANCHOR_PREFIX_RE.search(segment)
        or _CORNER_PREFIX_RE.search(segment)
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

    specification = _insert_missing_commas(specification)

    teil_ids = [t["id"] for t in teile]
    counters: Dict[str, int] = {tid: 0 for tid in teil_ids}
    last_teil = teil_ids[0]
    aktionen: List[Dict] = []
    last_action_idx: Optional[int] = None
    last_segment_was_action = False
    pending_anchor_prefix = ""

    for raw_segment in _comma_split(specification):
        current_segment = raw_segment
        if pending_anchor_prefix:
            current_segment = f"{pending_anchor_prefix}, {raw_segment.strip()}"
            pending_anchor_prefix = ""

        seg_teil = _assign_teil_id(current_segment, teil_ids, last_teil)
        seg = _strip_part_declaration(current_segment)
        if not seg:
            if (
                last_segment_was_action
                and last_action_idx is not None
                and _is_placement_continuation(current_segment)
            ):
                aktionen[last_action_idx]["phrase"] = (
                    f"{aktionen[last_action_idx]['phrase']}, {current_segment.strip()}"
                )
            elif _is_pre_feature_anchor_prefix(current_segment):
                pending_anchor_prefix = current_segment.strip()
                last_segment_was_action = False
            else:
                last_segment_was_action = False
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
            last_action_idx = len(aktionen) - 1
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
            last_action_idx = len(aktionen) - 1
            counters[seg_teil] += 1

        last_teil = seg_teil
        last_segment_was_action = True

    return aktionen


_TOP_LEVEL_SEP_RE = re.compile(r"[,;]")


def _comma_split(spec: str) -> List[str]:
    """Top-level segment-separated chunks. Splits on both ',' and ';' —
    semicolons are a stylistic alternative for separating feature actions
    (User-Spec aus B_kombo_asymmetric_multiface). Empty/whitespace-only
    segments are dropped, handles ',,' / ';;' / trailing ','/';' gracefully.
    """
    return [s.strip() for s in _TOP_LEVEL_SEP_RE.split(spec) if s.strip()]


def _strip_part_declaration(segment: str) -> str:
    """Strip a leading part-declaration; drop segments that aren't actions.

    A segment is an ACTION only if it mentions a feature keyword
    (tasche/bohrung/nut/fase/rundung/loch/...). Everything else is dropped
    before the classifier sees it:
      - Pure part declarations: '200mm wuerfel', 'platte 140x20x40'
      - Side-led part declarations: 'vorne soll eine platte hin mit 140x20x40'
      - Orientation/placement descriptions: 'die 140x20 seite liegt auf
        davon die rechte untere ecke auf der rechten kante 10mm nach oben'
    These would otherwise be misclassified as taschen by the LLM
    (Bug A from runs 8a170a03 / dc21d2ab).

    Remaining cases — segment HAS a feature keyword:
    1. Bare side-keyword AND a part-keyword sits before it
       ('200mm wuerfel oben eine bohrung'): strip the prefix.
    2. Bare side-keyword present but no part-keyword in the prefix
       ('auf der rechten seite eine nut ... nach rechts versetzt'):
       the side-keyword is just an internal direction marker.
       Keep the whole segment.
    3. No bare side-keyword ('auf der rechten seite eine bohrung ...'):
       keep the whole segment — classifier infers side from descriptors.
    """
    if not _FEATURE_RE.search(segment):
        return ""
    m = _SIDE_RE.search(segment)
    if m is None:
        return segment.strip()
    prefix = segment[:m.start()]
    if _PART_DECL_RE.search(prefix):
        return segment[m.start():].strip()
    return segment.strip()


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
    Multi-part: substring match on teil-id; otherwise default to the
    BASE teil (teil_ids[0]) — actions belong to the base unless the user
    explicitly names another part.

    Bug D from runs 8a170a03 / dc21d2ab: 'auf der rechten seite eine
    bohrung ...' phrases used to inherit last_teil (which could be a
    later-declared platte). Per user rule, ambiguous side-led phrases
    belong to the base teil. last_teil is kept in the signature for
    backward compatibility but no longer consulted here — nested-marker
    children inherit teil_id from their parent at the caller level.
    """
    if len(teil_ids) == 1:
        return teil_ids[0]
    seg_lower = segment.lower()
    for tid in teil_ids:
        if tid.lower() in seg_lower:
            return tid
    return teil_ids[0]


def _last_parent_idx(aktionen: List[Dict], teil_id: str) -> Optional[int]:
    """phrase_idx of the most recent parent (parent_phrase_idx is None) for
    the given teil. Returns None if no parent exists yet."""
    for entry in reversed(aktionen):
        if entry["teil_id"] == teil_id and entry["parent_phrase_idx"] is None:
            return entry["phrase_idx"]
    return None
