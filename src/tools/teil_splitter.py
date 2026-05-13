"""src/tools/teil_splitter.py — Deterministic: spec → per-part declaration phrases.

ADR 0007. Inventar Step A (one-shot) loses parts and hallucinates param keys
on long multi-part specs (E_kombo: 11/13 plates + a bogus
'do_not_use_this_id_if_not_needed' key). The fix is to chunk the spec into
one phrase per part declaration so a focused micro-call sees only ONE part.

A part declaration = part keyword (wuerfel/platte/zylinder/quader/kugel/box)
WITH a dimension nearby ("100mm wuerfel", "platte 80x40x20", "Ø50 zylinder").
References like "der platte" / "des wuerfels" have no dimension and are NOT
declarations — they get appended to the current part's phrase as placement
context (the Step A micro-call ignores them).

100% deterministic, no LLM. Returns [] when no part declaration is found
(caller falls back to one-shot extraction).
"""
from __future__ import annotations

import re
from typing import List


_PART_KEYWORDS = (
    r"wuerfel", r"würfel", r"wurfel",
    r"platte", r"zylinder", r"quader", r"kugel", r"box",
)
_PART_KW_RE = re.compile(
    r"\b(?:" + "|".join(_PART_KEYWORDS) + r")\b", re.IGNORECASE
)

# Dimension patterns that mark a real declaration:
#   "80x40x20" / "80 x 40 x 20" / "60x40"   — boxes/plates
#   "100mm"                                  — cube size / cylinder height etc.
#   "Ø50" / "d50"                            — diameters
_DIM_RE = re.compile(
    r"\d+(?:[.,]\d+)?(?:\s*x\s*\d+(?:[.,]\d+)?){1,2}"   # 80x40x20 / 80 x 40
    r"|\d+(?:[.,]\d+)?\s*mm\b"                           # 100mm
    r"|[øØ]\s*\d+(?:[.,]\d+)?"                           # Ø50
    r"|\bd\s*\d+(?:[.,]\d+)?\b",                         # d50
    re.IGNORECASE,
)

# Feature keywords — if a segment mentions one AND the part keyword appears
# as a reference (preceded by a definite article), it's a feature phrase
# like "auf der platte oben eine 5mm bohrung", NOT a new part declaration.
_FEATURE_KW_RE = re.compile(
    r"\b(?:"
    r"bohrung(?:en)?|tasche(?:n)?|nut(?:en)?|fase(?:n)?|rundung(?:en)?"
    r"|loch(?:muster|kreis|reihe|bild|er)?"
    r"|ausnehmung(?:en)?|aush[oö]hlung(?:en)?|ausfr[äa]sung(?:en)?|aussparung(?:en)?"
    r")\b",
    re.IGNORECASE,
)
_DEF_ARTICLE_BEFORE_RE = re.compile(r"\b(?:der|des|die|dem|den)\s*$", re.IGNORECASE)

_TOP_LEVEL_SEP_RE = re.compile(r"[,;]")


def _is_part_declaration(segment: str) -> bool:
    """True if the segment introduces a NEW part: part keyword + dimension,
    where the part keyword is a DECLARATION not a REFERENCE.

    "100mm wuerfel"                              → True
    "vorne soll eine platte 80x40x20"            → True
    "100mm wuerfel mit bohrung oben"             → True (wuerfel is the base part)
    "die 80x40 seite liegt auf"                  → False (no part keyword)
    "obere rechte ecke der platte ..."           → False (part kw but no dimension)
    "10mm nach links versetzt"                   → False (dimension but no part kw)
    "auf der platte oben eine 5mm bohrung 5 tief"→ False ("platte" is a reference
                                                    behind a definite article and
                                                    the segment carries a feature)
    """
    m = _PART_KW_RE.search(segment)
    if not m or not _DIM_RE.search(segment):
        return False
    # Reference guard: when the segment also mentions a feature, and the
    # first part keyword sits behind a definite article (der/des/die/dem/den),
    # the dimension belongs to the feature, not to a new part.
    if _FEATURE_KW_RE.search(segment):
        prefix = segment[:m.start()]
        if _DEF_ARTICLE_BEFORE_RE.search(prefix):
            return False
    return True


def split_spec_into_teil_declarations(spec: str) -> List[str]:
    """Segment a spec into per-part declaration phrases.

    Each returned phrase starts with a part declaration. Comma fragments
    that are orientation / anchor / placement / feature continuations of
    the current part are appended to that part's phrase — never split
    mid-info (B3-v1 lesson). Leading non-declaration fragments (before any
    part) are dropped.

    Returns [] if no part declaration is found — caller should fall back
    to one-shot extraction.
    """
    if not spec:
        return []
    phrases: List[str] = []
    for raw_seg in _TOP_LEVEL_SEP_RE.split(spec):
        seg = raw_seg.strip()
        if not seg:
            continue
        if _is_part_declaration(seg):
            phrases.append(seg)
        elif phrases:
            phrases[-1] = f"{phrases[-1]}, {seg}"
        # else: leading fragment before any part declaration — drop.
    return phrases
