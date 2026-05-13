"""
agent_contracts.py — Single Source of Truth fuer Agent-Trainings-Kontrakte.

Prinzip: Jedes Beispiel ist ein **Pipeline-Trace** (eine vollstaendige
Ground-Truth pro User-Text). Pro Agent projiziert ein Adapter aus dem Trace
genau das Input/Output-Paar, das dieser Agent lernen muss.

Folge: Wenn ein Agent gesplittet/gemerged wird, bleibt der Trace gueltig —
nur der Adapter muss nachgezogen werden. Neuer Agent? Adapter + Contract
eintragen, Trace um die neuen Felder erweitern, fertig.

Trace-Struktur (alle Felder optional ausser `specification`):
{
    "id": "einzigartig",
    "specification": "User-Text",
    "metadata": {"difficulty": "P0..P7", "category": ..., "sprachstil": ...},

    # Tier 1 — heutige Haupt-Kette
    "inventar": {teil_count, teile, aktionen},
    # position_extractor (Labeler, ab 2026-05-04): pro Teil ein Eintrag mit
    # zwei Satzlisten — placement (wo sitzt das Teil) vs feature (welche
    # Bohrungen/Taschen). Wird per-Teil getrennt trainiert.
    "position_extractor": {
        "positionen": [
            {"teil_id", "is_root", "placement_sentences", "feature_sentences"}
        ]
    },
    # position_normalizer (platzierer): pro Kind-Teil ein Eintrag. input_sentence
    # ist heute der zusammengejointe Klartext aus placement_sentences.
    "position_normalizer": [{teil_id, input_sentence, output}],
    "teil_definitionen": [{id, type, params, orientation, features}],
    "blueprint": {description, build_order, features},

    # Tier 2 — alte Kette (nur fuer Legacy-Training, wird nicht aktiv trainiert)
    # blueprint_architect nutzt denselben blueprint-Key

    # Phase B — Assertions (fuer deterministischen Validator)
    "assertions": {"expected_volume": float, "expected_bbox": [x,y,z],
                   "expected_feature_count": {type: n}},

    # Tier 3 — spaeter (Modification, ContourSpecifier, etc.)
    # "previous_blueprint": {...},
    # "modification_digest": "...",
    # "contour_paths": [...],
}
"""

from __future__ import annotations
import json
import re
from dataclasses import dataclass
from typing import Callable


# ══════════════════════════════════════════════════════════════════
# CONTRACT-REGISTRY
# ══════════════════════════════════════════════════════════════════

@dataclass
class AgentContract:
    """Definiert was ein Agent als Input/Output bekommt (DSPy-Signatur-Felder)."""
    name: str
    input_fields: list[str]     # Felder fuer dspy.Example (mit with_inputs)
    output_fields: list[str]    # Felder die der Agent produziert
    default_model: str
    active: bool = True          # false = existiert im Code, wird aber nicht trainiert


CONTRACTS: dict[str, AgentContract] = {
    "punctuation": AgentContract(
        name="punctuation",
        input_fields=["specification"],
        output_fields=["punctuated"],
        default_model="qwen3.5:9b",
    ),
    "inventar": AgentContract(
        name="inventar",
        input_fields=["specification"],
        output_fields=["inventar"],
        default_model="qwen3.5:9b",
    ),
    "aktions_klassifizierer": AgentContract(
        # Pro-Aktion-Mikro-Call (ADR 0003): nimmt EINE Phrase vom
        # deterministischen Aktions-Splitter und liefert {typ, seite,
        # parameter_hints}. Strukturelle Felder (teil_id, phrase_idx,
        # parent_phrase_idx) reicht der Aufrufer durch — das LLM
        # klassifiziert, der Code mergt. Kein aktives Training in
        # Stufe 2; der Adapter steht hier vorbereitet.
        name="aktions_klassifizierer",
        input_fields=["phrase", "teil_type", "teil_params", "parent_phrase"],
        output_fields=["klassifikation"],
        default_model="gemma4:26b",
        active=False,  # Rollback 2026-05-11 — Aktivierung brachte +B1 v2 aber
        # -EF (tasche pocket_edge) und -T_kombo (tasche params.y swap).
        # Vor naechstem Versuch: Tasche-Traces auditieren. Siehe Memory
        # project_klassifizierer_tasche_regress.md.
    ),
    "hole_classifier": AgentContract(
        # ADR 0006 Phase D: erster adoptierter typ-spezifischer Sub-Agent.
        # Isoliert einzelne Bohrungen von Tasche/Nut/Pattern; Runtime-Flag
        # classifier_subagents.hole_enabled ist nach gruenem B-Gate aktiv.
        name="hole_classifier",
        input_fields=["phrase", "teil_type", "teil_params", "parent_phrase"],
        output_fields=["klassifikation"],
        default_model="gemma4:26b",
    ),
    "pocket_classifier": AgentContract(
        # ADR 0006 Phase D: aktiviert 2026-05-12 mit erweitertem Trace-Set
        # (deren-X-kante Edge-to-Edge Demos zur Stabilisierung des T_kombo
        # Coin-Flip-Bugs).
        name="pocket_classifier",
        input_fields=["phrase", "teil_type", "teil_params", "parent_phrase"],
        output_fields=["klassifikation"],
        default_model="gemma4:26b",
    ),
    "slot_classifier": AgentContract(
        # ADR 0006 Phase D: aktiviert 2026-05-12 mit kante_oben/rechts/links
        # Demos (vorher nur kante_unten).
        name="slot_classifier",
        input_fields=["phrase", "teil_type", "teil_params", "parent_phrase"],
        output_fields=["klassifikation"],
        default_model="gemma4:26b",
    ),
    "pattern_classifier": AgentContract(
        # ADR 0006 Phase D: aktiviert 2026-05-12 mit Grid-Lochmuster und
        # Lochreihe-mit-ankerpunkt Demos (M_kombo Faelle).
        name="pattern_classifier",
        input_fields=["phrase", "teil_type", "teil_params", "parent_phrase"],
        output_fields=["klassifikation"],
        default_model="gemma4:26b",
    ),
    "edge_feature_classifier": AgentContract(
        # ADR 0006 Phase D: aktiviert 2026-05-12. 10 Demos genug fuer
        # einfache Fase/Rundung-Vokabular; nicht heatmap-kritisch.
        name="edge_feature_classifier",
        input_fields=["phrase", "teil_type", "teil_params", "parent_phrase"],
        output_fields=["klassifikation"],
        default_model="gemma4:26b",
    ),
    "position_extractor": AgentContract(
        # Per-Teil Labeler (ab 2026-05-04): bekommt EIN Teil-Text und labelt
        # die Saetze in placement_sentences vs feature_sentences. Ein Trainings-
        # Paar pro Teil pro Trace (also N_teile Paare pro Spec).
        # Output-Feld heisst "sentences" (NICHT "labels") — DSPy Example.labels
        # ist eine reservierte Methode und ueberschreibt das Feld.
        name="position_extractor",
        input_fields=["teil_id", "teil_text"],
        output_fields=["sentences"],
        default_model="gemma4:26b",
    ),
    "platzierer": AgentContract(
        # Legacy-Monolith. Der Runtime-Platzierer ist eine 4-Step-Kette; dieses
        # zusammengesetzte Ziel produziert Demos im falschen Format fuer die
        # Mini-Calls und wird deshalb nicht mehr aktiv trainiert.
        name="platzierer",
        input_fields=["teil_id", "teil_type", "teil_params", "alle_teile",
                      "specification", "position_sentence"],
        output_fields=["normalized_position"],
        default_model="qwen3.5:9b",
        active=False,
    ),
    "platzierer_frame": AgentContract(
        name="platzierer_frame",
        input_fields=["teil_id", "teil_type", "teil_params", "alle_teile",
                      "position_sentence"],
        output_fields=["frame"],
        default_model="gemma4:26b",
    ),
    "platzierer_alignment": AgentContract(
        name="platzierer_alignment",
        input_fields=["seite", "position_sentence"],
        output_fields=["alignment"],
        default_model="gemma4:26b",
    ),
    "platzierer_anchor": AgentContract(
        name="platzierer_anchor",
        input_fields=["teil_id", "teil_type", "teil_params", "parent",
                      "position_sentence"],
        output_fields=["anchor"],
        default_model="gemma4:26b",
    ),
    "platzierer_offset": AgentContract(
        name="platzierer_offset",
        input_fields=["position_sentence"],
        output_fields=["offset"],
        default_model="gemma4:26b",
    ),
    "normalizer": AgentContract(
        # 1 Aktion → 1 normalisierte Kurzform. Pipeline ruft
        # NormalizerAgent.normalize() pro Aktion auf; build_feature baut
        # daraus deterministisch das SemanticFeature. DSPy-Demos muessen
        # daher das Runtime-Format `typ:/seite:/parameter:` trainieren,
        # nicht das nachgelagerte Feature-JSON.
        name="normalizer",
        input_fields=["beschreibung", "seite", "teil_type", "teil_params",
                      "specification"],
        output_fields=["normalisierung"],
        default_model="qwen3.5:9b",
    ),
    # assembly_node ist deterministisch (kein LLM-Call). Kein Training-Target.
    # Legacy — nicht aktiv trainieren, Infrastruktur bleibt bestehen
    "blueprint_architect": AgentContract(
        name="blueprint_architect",
        input_fields=["specification"],
        output_fields=["blueprint"],
        default_model="nemotron-cascade-2:30b",
        active=False,  # Legacy: Modifications/Error-Loop-Pfad, kein neues Training
    ),
}


def active_agents() -> list[str]:
    """Liste der Agents, die aktuell trainiert werden sollen."""
    return [name for name, c in CONTRACTS.items() if c.active]


# ══════════════════════════════════════════════════════════════════
# ADAPTER — Trace → (input_dict, output_dict) pro Agent
# ══════════════════════════════════════════════════════════════════
#
# Jeder Adapter gibt eine LISTE von Paaren zurueck (ein Trace kann
# mehrere Trainings-Beispiele pro Agent liefern, z.B. bei teil_definierer
# und position_normalizer — ein Beispiel pro Teil).
#
# Signatur: adapter(trace: dict) -> list[{"input": {...}, "output": {...}}]
# Bei fehlenden Feldern im Trace gibt der Adapter [] zurueck (skip).

def _adapter_punctuation(trace: dict) -> list[dict]:
    """Trace-Adapter fuer Punctuation. Erwartet entweder:
      trace["punctuation"] = {"raw": "...", "punctuated": "..."}
    ODER (additiv): trace["raw_input"] + trace["specification"] werden als
    Paar interpretiert, wenn raw_input vorhanden und unterschiedlich.

    Standard-Trace-Annotation hat das Feld noch nicht — Adapter ist
    forward-kompatibel und gibt fuer alte Traces einfach [] zurueck.
    Hauptquelle bleibt runs.jsonl (live agent_traces).
    """
    p = trace.get("punctuation")
    if isinstance(p, dict) and p.get("raw") and p.get("punctuated"):
        return [{
            "input": {"specification": p["raw"]},
            "output": p["punctuated"],
        }]
    return []


def _adapter_inventar(trace: dict) -> list[dict]:
    inv = trace.get("inventar")
    spec = trace.get("specification")
    if not inv or not spec:
        return []
    return [{"input": {"specification": spec}, "output": inv}]


def _adapter_aktions_klassifizierer(trace: dict) -> list[dict]:
    """Eine Trainings-Probe pro AKTIONS-PHRASE (1 Phrase → 1 Klassifikation).

    Erwartet `trace["aktions_klassifizierer"]` als Liste von Pro-Phrase-
    Eintraegen, jeweils mit {phrase, teil_id, parent_phrase, output}.
    Forward-kompatibel: alte Traces ohne diese Annotation liefern [].
    """
    entries = trace.get("aktions_klassifizierer")
    inv = trace.get("inventar")
    spec = trace.get("specification")
    if not isinstance(entries, list) or not entries or not inv or not spec:
        return []

    teile_by_id = {t["id"]: t for t in inv.get("teile", [])}
    pairs = []
    for e in entries:
        teil = teile_by_id.get(e.get("teil_id", ""), {})
        pairs.append({
            "input": {
                "phrase": e.get("phrase", ""),
                "teil_type": teil.get("type", "box"),
                "teil_params": teil.get("raw_params", {}),
                "parent_phrase": e.get("parent_phrase", "(keine)"),
            },
            "output": e.get("output", {}),
        })
    return pairs


_CLASSIFIER_SUB_AGENTS = {
    "hole_classifier",
    "pocket_classifier",
    "slot_classifier",
    "pattern_classifier",
    "edge_feature_classifier",
}

_PATTERN_PHRASE_RE = re.compile(
    r"\b(?:"
    r"lochkreis|teilkreis|eckbohr\w*|bohrungsreihe|lochreihe|lochmuster|lochbild"
    r"|loecher\s+der\s+reihe|locher\s+der\s+reihe"
    r"|bohrungen\s+(?:in\s+einer\s+reihe|entlang)"
    r"|bohrungen\s+.*\b(?:abstand|achse)\b"
    r"|an\s+jeder\s+ecke"
    r")\b",
    re.IGNORECASE,
)


def classifier_sub_agent_name_for_pair(pair: dict) -> str | None:
    """Return the ADR-0006 sub-classifier target for one classifier pair.

    The source pair still uses the monolithic classifier output shape
    `{typ, seite, parameter_hints}`. Pattern phrases are detected from the
    input phrase because the monolith deliberately coarse-labels them as
    `bohrung`; the Normalizer later refines them to lochkreis/eckbohrungen/
    bohrungsreihe.
    """
    inp = pair.get("input") or {}
    out = pair.get("output") or {}
    phrase = str(inp.get("phrase") or "").lower()
    typ = str(out.get("typ") or "").lower()

    if typ == "bohrung" and _PATTERN_PHRASE_RE.search(phrase):
        return "pattern_classifier"
    if typ == "bohrung":
        return "hole_classifier"
    if typ == "tasche":
        return "pocket_classifier"
    if typ == "nut":
        return "slot_classifier"
    if typ in {"fase", "rundung"}:
        return "edge_feature_classifier"
    return None


def _filter_classifier_pairs(pairs: list[dict], sub_agent: str) -> list[dict]:
    return [
        p for p in pairs
        if classifier_sub_agent_name_for_pair(p) == sub_agent
    ]


def _adapter_hole_classifier(trace: dict) -> list[dict]:
    return _filter_classifier_pairs(
        _adapter_aktions_klassifizierer(trace), "hole_classifier"
    )


def _adapter_pocket_classifier(trace: dict) -> list[dict]:
    return _filter_classifier_pairs(
        _adapter_aktions_klassifizierer(trace), "pocket_classifier"
    )


def _adapter_slot_classifier(trace: dict) -> list[dict]:
    return _filter_classifier_pairs(
        _adapter_aktions_klassifizierer(trace), "slot_classifier"
    )


def _adapter_pattern_classifier(trace: dict) -> list[dict]:
    return _filter_classifier_pairs(
        _adapter_aktions_klassifizierer(trace), "pattern_classifier"
    )


def _adapter_edge_feature_classifier(trace: dict) -> list[dict]:
    return _filter_classifier_pairs(
        _adapter_aktions_klassifizierer(trace), "edge_feature_classifier"
    )


def _adapter_position_extractor(trace: dict) -> list[dict]:
    """Per-Teil Adapter (ab 2026-05-04 Labeler-Reshape).

    Trace muss `position_extractor.positionen[]` mit pro-Teil Listen liefern.
    Jeder Eintrag wird zu einem Trainings-Paar:
      input  = {teil_id, teil_text}   ← teil_text aus teil_texte oder spec
      output = {labels: {placement_sentences, feature_sentences}}
    """
    pe = trace.get("position_extractor")
    inv = trace.get("inventar")
    spec = trace.get("specification")
    if not pe or not inv or not spec:
        return []
    teile = inv.get("teile", [])
    if len(teile) < 2:
        return []  # single-part: kein labeler-Run

    teil_texte = trace.get("teil_texte", {}) or {}
    pairs = []
    for entry in pe.get("positionen", []):
        tid = entry.get("teil_id")
        if not tid:
            continue
        # Skip OLD-schema entries (parent_hint/beschreibung) — they cannot
        # be projected to the new labeler signature without re-annotation.
        if "placement_sentences" not in entry and "feature_sentences" not in entry:
            continue
        teil_text = teil_texte.get(tid, spec)
        sentences = {
            "placement_sentences": entry.get("placement_sentences", []),
            "feature_sentences": entry.get("feature_sentences", []),
        }
        pairs.append({
            "input": {"teil_id": tid, "teil_text": teil_text},
            "output": {"sentences": sentences},
        })
    return pairs


def _adapter_position_normalizer(trace: dict) -> list[dict]:
    """Eine Trainings-Probe pro Kind-Teil.

    `position_sentence` wird aus dem Trace gewonnen, in dieser Reihenfolge:
      1. position_normalizer[i].input_sentence (manuell annotiert)
      2. position_extractor.positionen[teil_id].placement_sentences (joined)
         — automatisch konsistent mit der Live-Pipeline ab 2026-05-04
    """
    pn_list = trace.get("position_normalizer")
    inv = trace.get("inventar")
    spec = trace.get("specification")
    if not pn_list or not inv or not spec:
        return []
    alle_teile = inv.get("teile", [])
    teile_by_id = {t["id"]: t for t in alle_teile}

    # Lookup placement_sentences from position_extractor (new schema)
    pe = trace.get("position_extractor", {})
    placement_by_teil = {
        e.get("teil_id"): e.get("placement_sentences", [])
        for e in pe.get("positionen", [])
        if e.get("teil_id")
    }

    pairs = []
    for entry in pn_list:
        tid = entry.get("teil_id")
        teil = teile_by_id.get(tid, {})
        # Prefer explicit input_sentence; otherwise derive from labeled placement
        sent = entry.get("input_sentence")
        if not sent:
            sent = " ".join(placement_by_teil.get(tid, []))
        pairs.append({
            "input": {
                "teil_id": tid,
                "teil_type": teil.get("type", "box"),
                "teil_params": teil.get("raw_params", {}),
                "alle_teile": alle_teile,
                "specification": spec,
                "position_sentence": sent,
            },
            "output": entry.get("output", {}),
        })
    return pairs


_CURRENT_PLATZIERER_AUSRICHTUNGEN = {
    "zentriert",
    "buendig_oben",
    "buendig_unten",
    "buendig_rechts",
    "buendig_links",
    "buendig_oben_rechts",
    "buendig_oben_links",
    "buendig_unten_rechts",
    "buendig_unten_links",
    "von_kanten",
    "von_mitte",
}

_DIRECTION_ORDER = ("oben", "unten", "rechts", "links", "vorne", "hinten")

_DIRECTION_CANON = {
    "oben": "oben", "top": "oben", "up": "oben",
    "unten": "unten", "bottom": "unten", "down": "unten",
    "rechts": "rechts", "right": "rechts",
    "links": "links", "left": "links",
    "vorne": "vorne", "front": "vorne", "forward": "vorne",
    "hinten": "hinten", "back": "hinten", "backward": "hinten",
}

_POINT_CANON = {
    "center": "center", "zentrum": "center", "mitte": "center",
    "mittelpunkt": "center",
    "top_left": "top_left", "oben_links": "top_left",
    "top_right": "top_right", "oben_rechts": "top_right",
    "bottom_left": "bottom_left", "unten_links": "bottom_left",
    "bottom_right": "bottom_right", "unten_rechts": "bottom_right",
    "top_edge": "top_edge", "obere_kante": "top_edge", "oberkante": "top_edge",
    "bottom_edge": "bottom_edge", "untere_kante": "bottom_edge", "unterkante": "bottom_edge",
    "left_edge": "left_edge", "linke_kante": "left_edge",
    "right_edge": "right_edge", "rechte_kante": "right_edge",
    "top_edge_left": "top_edge_left",
    "top_edge_right": "top_edge_right",
    "bottom_edge_left": "bottom_edge_left",
    "bottom_edge_right": "bottom_edge_right",
    "left_edge_top": "left_edge_top",
    "left_edge_bottom": "left_edge_bottom",
    "right_edge_top": "right_edge_top",
    "right_edge_bottom": "right_edge_bottom",
}


def _fmt_num(value) -> str:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return str(value)
    return str(int(f)) if abs(f - int(f)) < 1e-6 else str(f)


def _current_platzierer_pairs(trace: dict) -> list[dict]:
    """Return only current-schema normalized-position pairs.

    Older sonnet traces use runtime-incompatible labels such as "centered",
    "flush_top", "anker" and dict-style anchors. Keep those out of the split
    training targets until they are re-rendered into the current vocabulary.
    """
    pairs = []
    for pair in _adapter_position_normalizer(trace):
        out = pair.get("output") or {}
        if not isinstance(out, dict):
            continue
        if out.get("ausrichtung") not in _CURRENT_PLATZIERER_AUSRICHTUNGEN:
            continue
        anker = out.get("anker", "")
        if anker is not None and not isinstance(anker, str):
            continue
        pairs.append(pair)
    return pairs


def _format_kv_lines(values: dict[str, object]) -> str:
    lines = []
    for key, value in values.items():
        if value is None:
            continue
        if isinstance(value, dict):
            if not value:
                continue
            value = _format_assignments(value)
        text = str(value).strip()
        if text:
            lines.append(f"{key}: {text}")
    return "\n".join(lines)


def _format_assignments(values: dict) -> str:
    parts = []
    for key, value in values.items():
        parts.append(f"{key}={_fmt_num(value)}")
    return ", ".join(parts)


def _format_direction_assignments(values: dict[str, object]) -> str:
    ordered = {
        direction: values[direction]
        for direction in _DIRECTION_ORDER
        if direction in values
    }
    for key, value in values.items():
        if key not in ordered:
            ordered[key] = value
    return _format_assignments(ordered)


def _contact_orientation(output: dict) -> str:
    face = str(output.get("anliegende_flaeche") or "keine").lower()
    orientierung = str(output.get("orientierung") or "standard").lower()
    if face and face != "keine":
        return orientierung if orientierung.endswith("_liegt_auf") else f"{face}_liegt_auf"
    return orientierung


def _canonical_point(point: object) -> str:
    raw = str(point or "").strip().lower().replace(" ", "_")
    return _POINT_CANON.get(raw, raw)


def _parse_anchor(output: dict) -> dict | None:
    anker = output.get("anker")
    if isinstance(anker, str) and "_auf_" in anker:
        child, _, parent = anker.partition("_auf_")
        return {
            "kind_punkt": _canonical_point(child),
            "eltern_punkt": _canonical_point(parent),
        }
    if isinstance(anker, dict):
        child = anker.get("kind_punkt") or anker.get("child_point")
        parent = anker.get("eltern_punkt") or anker.get("parent_point")
        if child or parent:
            result = {
                "kind_punkt": _canonical_point(child),
                "eltern_punkt": _canonical_point(parent),
            }
            eltern_abstand = anker.get("eltern_abstand")
            if isinstance(eltern_abstand, dict) and eltern_abstand:
                result["eltern_abstand"] = {
                    _DIRECTION_CANON.get(str(k).lower(), str(k).lower()): v
                    for k, v in eltern_abstand.items()
                }
            return result
    return None


def _canonical_offset_parts(output: dict) -> dict[str, dict[str, object]]:
    result = {"versatz": {}, "kantenabstand": {}, "pre_rotation": {}}
    abstand = output.get("abstand") or {}
    if isinstance(abstand, dict):
        for raw_key, value in abstand.items():
            key = str(raw_key).lower()
            if key.startswith("versatz_"):
                direction = _DIRECTION_CANON.get(key.removeprefix("versatz_"))
                if direction:
                    result["versatz"][direction] = value
            elif key.startswith("abstand_"):
                direction = _DIRECTION_CANON.get(key.removeprefix("abstand_"))
                if direction:
                    result["kantenabstand"][direction] = value

    pre_rotation = output.get("pre_rotation") or {}
    if isinstance(pre_rotation, dict):
        for axis in ("x", "y", "z"):
            value = pre_rotation.get(axis)
            if value not in (None, "", 0, 0.0):
                result["pre_rotation"][axis] = value

    return result


def _adapter_platzierer_frame(trace: dict) -> list[dict]:
    pairs = []
    for pair in _current_platzierer_pairs(trace):
        inp = pair["input"]
        out = pair["output"]
        pairs.append({
            "input": {
                "teil_id": inp.get("teil_id", ""),
                "teil_type": inp.get("teil_type", "box"),
                "teil_params": inp.get("teil_params", {}),
                "alle_teile": inp.get("alle_teile", []),
                "position_sentence": inp.get("position_sentence", ""),
            },
            "output": _format_kv_lines({
                "parent": out.get("parent"),
                "seite": out.get("seite"),
                "orientierung": _contact_orientation(out),
                "anliegende_flaeche": out.get("anliegende_flaeche", "keine"),
            }),
        })
    return pairs


def _adapter_platzierer_alignment(trace: dict) -> list[dict]:
    pairs = []
    for pair in _current_platzierer_pairs(trace):
        inp = pair["input"]
        out = pair["output"]
        ausrichtung = out.get("ausrichtung", "zentriert")
        pairs.append({
            "input": {
                "seite": out.get("seite", "oben"),
                "position_sentence": inp.get("position_sentence", ""),
            },
            "output": f"ausrichtung: {ausrichtung}",
        })
    return pairs


def _adapter_platzierer_anchor(trace: dict) -> list[dict]:
    pairs = []
    for pair in _current_platzierer_pairs(trace):
        inp = pair["input"]
        out = pair["output"]
        anchor = _parse_anchor(out)
        if not anchor:
            continue
        pairs.append({
            "input": {
                "teil_id": inp.get("teil_id", ""),
                "teil_type": inp.get("teil_type", "box"),
                "teil_params": inp.get("teil_params", {}),
                "parent": out.get("parent", ""),
                "position_sentence": inp.get("position_sentence", ""),
            },
            "output": _format_kv_lines(anchor),
        })
    return pairs


def _adapter_platzierer_offset(trace: dict) -> list[dict]:
    pairs = []
    for pair in _current_platzierer_pairs(trace):
        inp = pair["input"]
        out = pair["output"]
        parts = _canonical_offset_parts(out)
        sentence = inp.get("position_sentence", "")
        sentence_l = sentence.lower()
        if _parse_anchor(out) and (" von " in f" {sentence_l} " or "entfernt" in sentence_l):
            # The final normalized_position often stores anchor-qualified
            # distances as versatz_* because position_builder can consume both
            # vocabularies in anchor mode. The Offset mini-call's own contract
            # is text-local, though: "von links/von oben entfernt" is
            # kantenabstand. Convert the derived labels back to that contract.
            inverse = {
                "oben": "unten",
                "unten": "oben",
                "rechts": "links",
                "links": "rechts",
                "vorne": "hinten",
                "hinten": "vorne",
            }
            converted = {}
            for direction, value in parts["versatz"].items():
                converted[inverse.get(direction, direction)] = value
            if converted:
                parts["kantenabstand"].update(converted)
                parts["versatz"] = {}
        output = {
            "winkel": _fmt_num(out.get("winkel"))
            if float(out.get("winkel") or 0) != 0.0 else "",
            "versatz": _format_direction_assignments(parts["versatz"]),
            "kantenabstand": _format_direction_assignments(parts["kantenabstand"]),
            "pre_rotation": _format_assignments(parts["pre_rotation"]),
        }
        pairs.append({
            "input": {
                "position_sentence": inp.get("position_sentence", ""),
            },
            "output": _format_kv_lines(output),
        })
    return pairs


_NORMALIZER_FEATURE_TYPE_TO_TYP = {
    "hole_single": "bohrung",
    "hole": "bohrung",
    "hole_pattern_circular": "lochkreis",
    "hole_circle": "lochkreis",
    "hole_pattern_grid": "eckbohrungen",
    "hole_pattern": "eckbohrungen",
    "hole_pattern_linear": "bohrungsreihe",
    "slot": "nut",
    "pocket_rect": "tasche",
    "pocket": "tasche",
    "chamfer": "fase",
    "fillet": "rundung",
    "shell": "aushoelung",
}

_NORMALIZER_UNSUPPORTED_FEATURE_TYPES = {
    # Current prompt/feature_builder vocabulary has no deterministic template
    # for these yet. Keep them out of normalizer training until the standard
    # path supports them end-to-end.
    "hole_counterbore",
    "hole_countersink",
}

_EN_TO_DE_DIRECTION = {
    "top": "oben",
    "bottom": "unten",
    "right": "rechts",
    "left": "links",
    "front": "vorne",
    "back": "hinten",
}

_ALIGNMENT_TO_POSITION = {
    "centered": "zentriert",
    "custom": "von_kanten",
    "top_right": "oben-rechts",
    "top_left": "oben-links",
    "bottom_right": "unten-rechts",
    "bottom_left": "unten-links",
    "flush_right": "rechts",
    "flush_left": "links",
    "flush_top": "oben",
    "flush_bottom": "unten",
    "all_edges": "zentriert",
    "corner_4": "von_kanten",
    "von_kanten": "von_kanten",
}


def _normalizer_has_through_word(text: str) -> bool:
    return bool(re.search(r"\bdurch(?:gehend|gaengig)?\b", text.lower()))


def _normalizer_depth(params: dict, description: str) -> object | None:
    value = params.get("depth")
    if isinstance(value, str) and value.lower() in {"through", "durch"}:
        return "durch"
    if _normalizer_has_through_word(description):
        return "durch"
    return value


def _normalizer_position(position: dict) -> str:
    if position.get("center_offset"):
        return "von_mitte"
    if position.get("edge_distances") or position.get("pocket_edge_distances"):
        return "von_kanten"
    alignment = str(position.get("alignment") or "centered").lower()
    return _ALIGNMENT_TO_POSITION.get(alignment, "zentriert")


def _normalizer_add_distance_params(
    params: dict[str, object],
    position: dict,
) -> None:
    for source_key, prefix in (
        ("edge_distances", "abstand"),
        ("center_offset", "versatz"),
        ("pocket_edge_distances", "kante"),
    ):
        values = position.get(source_key)
        if not isinstance(values, dict):
            continue
        for direction, value in values.items():
            de = _EN_TO_DE_DIRECTION.get(str(direction).lower())
            if de:
                params[f"{prefix}_{de}"] = value


def _normalizer_direction(feature: dict) -> str:
    params = feature.get("params") or {}
    raw = params.get("direction")
    if str(raw).lower() in {"x", "y", "z"}:
        return str(raw).lower()
    notes = ((feature.get("position") or {}).get("notes") or "")
    match = re.search(r"entlang\s+([xyz])\b", str(notes), re.IGNORECASE)
    return match.group(1).lower() if match else ""


def _feature_to_normalizer_shortform(pair_input: dict, feature: dict) -> str | None:
    """Project current SemanticFeature labels back to Normalizer runtime text.

    Historical traces store the post-build feature JSON, but the actual
    Normalizer LLM only emits fixed-vocabulary key/value lines. This adapter
    keeps the training contract aligned with runtime while still reusing the
    curated trace corpus.
    """
    if isinstance(feature, str):
        return feature
    if not isinstance(feature, dict):
        return None

    feature_type = str(feature.get("type") or "")
    if feature_type in _NORMALIZER_UNSUPPORTED_FEATURE_TYPES:
        return None
    typ = _NORMALIZER_FEATURE_TYPE_TO_TYP.get(feature_type)
    if not typ:
        return None

    params_in = feature.get("params") or {}
    position = feature.get("position") or {}
    description = str(pair_input.get("beschreibung") or "")
    params: dict[str, object] = {}

    if typ == "bohrung":
        diameter = params_in.get("diameter", params_in.get("d"))
        if diameter is not None:
            params["durchmesser"] = diameter
        depth = _normalizer_depth(params_in, description)
        if depth is not None:
            params["tiefe"] = depth
    elif typ == "lochkreis":
        diameter = params_in.get("bolt_circle_diameter")
        if diameter is None and params_in.get("bolt_circle_radius") is not None:
            diameter = params_in["bolt_circle_radius"] * 2
        if diameter is not None:
            params["kreis_durchmesser"] = diameter
        if params_in.get("count") is not None:
            params["anzahl"] = params_in["count"]
        hole_diameter = params_in.get("hole_diameter", params_in.get("diameter"))
        if hole_diameter is not None:
            params["bohr_durchmesser"] = hole_diameter
        depth = _normalizer_depth(params_in, description)
        if depth is not None:
            params["tiefe"] = depth
    elif typ == "eckbohrungen":
        count = params_in.get("count")
        if count is None and params_in.get("count_x") and params_in.get("count_y"):
            count = params_in["count_x"] * params_in["count_y"]
        if count is None and params_in.get("rows") and params_in.get("cols"):
            count = params_in["rows"] * params_in["cols"]
        if count is not None:
            params["anzahl"] = count
        inset = params_in.get("inset", params_in.get("edge_distance"))
        if inset is not None:
            params["abstand_kante"] = inset
        hole_diameter = params_in.get("hole_diameter", params_in.get("diameter"))
        if hole_diameter is not None:
            params["bohr_durchmesser"] = hole_diameter
        depth = _normalizer_depth(params_in, description)
        if depth is not None:
            params["tiefe"] = depth
    elif typ == "bohrungsreihe":
        if params_in.get("count") is not None:
            params["anzahl"] = params_in["count"]
        if params_in.get("spacing") is not None:
            params["abstand"] = params_in["spacing"]
        hole_diameter = params_in.get("hole_diameter", params_in.get("diameter"))
        if hole_diameter is not None:
            params["bohr_durchmesser"] = hole_diameter
        depth = _normalizer_depth(params_in, description)
        if depth is not None:
            params["tiefe"] = depth
    elif typ == "nut":
        if params_in.get("width") is not None:
            params["breite"] = params_in["width"]
        if params_in.get("depth") is not None:
            params["tiefe"] = params_in["depth"]
        if params_in.get("length") is not None:
            params["laenge"] = params_in["length"]
    elif typ == "tasche":
        laenge = params_in.get("x", params_in.get("length", params_in.get("width")))
        breite = params_in.get("y", params_in.get("height"))
        if laenge is not None:
            params["laenge"] = laenge
        if breite is not None:
            params["breite"] = breite
        if params_in.get("depth") is not None:
            params["tiefe"] = params_in["depth"]
    elif typ == "fase":
        if params_in.get("size") is not None:
            params["groesse"] = params_in["size"]
        if params_in.get("edge_selector") is not None:
            params["kanten"] = params_in["edge_selector"]
    elif typ == "rundung":
        radius = params_in.get("radius", params_in.get("size"))
        if radius is not None:
            params["radius"] = radius
        if params_in.get("edge_selector") is not None:
            params["kanten"] = params_in["edge_selector"]
    elif typ == "aushoelung":
        thickness = params_in.get("thickness")
        if thickness is not None:
            params["dicke"] = thickness

    _normalizer_add_distance_params(params, position)

    angle = position.get("angle_deg")
    if isinstance(angle, (int, float)) and float(angle) != 0.0 and typ != "nut":
        params["drehung"] = angle

    lines = [
        f"typ: {typ}",
        f"seite: {position.get('side') or pair_input.get('seite', 'oben')}",
        f"position: {_normalizer_position(position)}",
    ]
    direction = _normalizer_direction(feature)
    if direction:
        lines.append(f"richtung: {direction}")
    if params:
        lines.append(f"parameter: {_format_assignments(params)}")
    notes = position.get("notes")
    if notes:
        lines.append(f"notes: {notes}")
    return "\n".join(lines)


def _adapter_normalizer(trace: dict) -> list[dict]:
    """Eine Trainings-Probe pro AKTION (1 Aktion → 1 Feature).

    Quelle (in dieser Reihenfolge):
      1. trace["normalizer_pairs"]: explizite Paare (handgepflegt) — werden
         direkt durchgereicht, ueberschreiben die Index-Paarung.
      2. teil_definitionen[].features  zip  inventar.aktionen[teil_id]
         (klassische Annotation mit beidseitiger Liste).

    Pipeline-Realitaet (planning_nodes.feature_definierer_node):
        for aktion in teil_aktionen:
            norm = normalizer.normalize(beschreibung, seite, feature_spec)
    """
    # Variant 1: explicit hand-curated pairs
    explicit = trace.get("normalizer_pairs")
    if isinstance(explicit, list) and explicit:
        out = []
        for p in explicit:
            inp = p.get("input") or {}
            pair_input = {
                "beschreibung": inp.get("beschreibung", ""),
                "seite": inp.get("seite", "oben"),
                "teil_type": inp.get("teil_type", "box"),
                "teil_params": inp.get("teil_params", {}),
                "specification": inp.get("specification",
                                         trace.get("specification", "")),
            }
            normalisierung = _feature_to_normalizer_shortform(
                pair_input,
                p.get("output", {}),
            )
            if not normalisierung:
                continue
            out.append({
                "input": pair_input,
                "output": normalisierung,
            })
        return out

    # Variant 2: zip teil_definitionen[].features with inventar.aktionen
    teil_defs = trace.get("teil_definitionen") or []
    inv = trace.get("inventar")
    spec = trace.get("specification")
    if not teil_defs or not inv or not spec:
        return []
    aktionen = inv.get("aktionen", [])
    aktionen_by_teil: dict[str, list] = {}
    for a in aktionen:
        aktionen_by_teil.setdefault(a.get("teil_id", ""), []).append(a)
    teile_by_id = {t["id"]: t for t in inv.get("teile", [])}

    pairs = []
    for td in teil_defs:
        tid = td["id"]
        teil = teile_by_id.get(tid, {})
        td_aktionen = aktionen_by_teil.get(tid, [])
        td_features = td.get("features", [])
        # Index-pair action with feature; skip if either side is empty
        for aktion, feature in zip(td_aktionen, td_features):
            pair_input = {
                "beschreibung": aktion.get("beschreibung", ""),
                "seite": aktion.get("seite", "oben"),
                "teil_type": teil.get("type", "box"),
                "teil_params": teil.get("raw_params", {}),
                "specification": spec,
            }
            normalisierung = _feature_to_normalizer_shortform(pair_input, feature)
            if not normalisierung:
                continue
            pairs.append({
                "input": pair_input,
                "output": normalisierung,
            })
    return pairs


def _adapter_blueprint_architect(trace: dict) -> list[dict]:
    """Legacy — nicht aktiv, aber Adapter bleibt fuer optionales Training."""
    bp = trace.get("blueprint")
    spec = trace.get("specification")
    if not bp or not spec:
        return []
    return [{"input": {"specification": spec}, "output": bp}]


ADAPTERS: dict[str, Callable[[dict], list[dict]]] = {
    "punctuation": _adapter_punctuation,
    "inventar": _adapter_inventar,
    "aktions_klassifizierer": _adapter_aktions_klassifizierer,
    "hole_classifier": _adapter_hole_classifier,
    "pocket_classifier": _adapter_pocket_classifier,
    "slot_classifier": _adapter_slot_classifier,
    "pattern_classifier": _adapter_pattern_classifier,
    "edge_feature_classifier": _adapter_edge_feature_classifier,
    "position_extractor": _adapter_position_extractor,
    "platzierer": _adapter_position_normalizer,
    "platzierer_frame": _adapter_platzierer_frame,
    "platzierer_alignment": _adapter_platzierer_alignment,
    "platzierer_anchor": _adapter_platzierer_anchor,
    "platzierer_offset": _adapter_platzierer_offset,
    "normalizer": _adapter_normalizer,
    "blueprint_architect": _adapter_blueprint_architect,
}


def project_trace(trace: dict, agent_name: str) -> list[dict]:
    """Projiziere einen Trace auf Trainings-Paare fuer einen bestimmten Agent."""
    adapter = ADAPTERS.get(agent_name)
    if adapter is None:
        raise ValueError(f"Unbekannter Agent: {agent_name}. Bekannt: {list(ADAPTERS)}")
    return adapter(trace)


def project_traces(traces: list[dict], agent_name: str) -> list[dict]:
    """Projiziere eine Liste von Traces auf alle Trainings-Paare eines Agents."""
    pairs = []
    for t in traces:
        pairs.extend(project_trace(t, agent_name))
    return pairs


# ══════════════════════════════════════════════════════════════════
# TRACE-VALIDIERUNG (Sanity-Checks vor dem Training)
# ══════════════════════════════════════════════════════════════════

def validate_trace(trace: dict) -> list[str]:
    """Pruefe strukturelle Konsistenz eines Trace. Gibt Liste von Fehlern zurueck."""
    errors = []

    if "specification" not in trace or not trace["specification"]:
        errors.append("specification fehlt oder leer")
    if "id" not in trace:
        errors.append("id fehlt")

    inv = trace.get("inventar")
    teil_defs = trace.get("teil_definitionen") or []

    if inv:
        teil_ids_inv = {t["id"] for t in inv.get("teile", []) if isinstance(t, dict)}
        teil_ids_def = {t["id"] for t in teil_defs if isinstance(t, dict)}
        if inv.get("teil_count") != len(teil_ids_inv):
            errors.append(f"teil_count={inv.get('teil_count')} != len(teile)={len(teil_ids_inv)}")
        if teil_defs and teil_ids_inv != teil_ids_def:
            errors.append(f"teile-IDs in inventar vs teil_definitionen weichen ab: "
                          f"{teil_ids_inv} vs {teil_ids_def}")
        # aktionen referenzieren valide teile
        for a in inv.get("aktionen", []):
            if a.get("teil_id") not in teil_ids_inv:
                errors.append(f"aktion referenziert unbekannten teil_id={a.get('teil_id')}")

    # position_extractor nur sinnvoll bei multi-part
    pe = trace.get("position_extractor")
    if pe and inv and inv.get("teil_count", 0) < 2:
        errors.append("position_extractor gesetzt, aber teil_count < 2")

    # position_normalizer: kind-teile sollten Einträge haben bei multi-part
    pn = trace.get("position_normalizer")
    if pn and inv:
        teile = inv.get("teile", [])
        if teile:
            child_ids = {t["id"] for t in teile[1:]}  # erste = root, rest = kinder
            normalized_ids = {e.get("teil_id") for e in pn}
            missing = child_ids - normalized_ids
            if missing:
                errors.append(f"position_normalizer fehlt fuer kind-teile: {missing}")

    # blueprint: features-Dict enthaelt alle teile + features
    bp = trace.get("blueprint")
    if bp and teil_defs:
        bp_features = bp.get("features", {})
        for td in teil_defs:
            if td["id"] not in bp_features:
                errors.append(f"blueprint features fehlt teil '{td['id']}'")

    return errors


def validate_all(traces: list[dict]) -> dict[str, list[str]]:
    """Pruefe alle Traces. Gibt Mapping id → Fehler zurueck (nur mit Fehlern)."""
    result = {}
    for t in traces:
        errs = validate_trace(t)
        if errs:
            result[t.get("id", "<no-id>")] = errs
    return result


# ══════════════════════════════════════════════════════════════════
# STATS
# ══════════════════════════════════════════════════════════════════

def coverage_report(traces: list[dict]) -> dict:
    """Zeige Coverage nach Kategorie, Schwierigkeit, Sprachstil."""
    by_difficulty: dict[str, int] = {}
    by_category: dict[str, int] = {}
    by_sprachstil: dict[str, int] = {}
    by_agent: dict[str, int] = {}

    for t in traces:
        md = t.get("metadata", {})
        by_difficulty[md.get("difficulty", "?")] = by_difficulty.get(md.get("difficulty", "?"), 0) + 1
        by_category[md.get("category", "?")] = by_category.get(md.get("category", "?"), 0) + 1
        by_sprachstil[md.get("sprachstil", "?")] = by_sprachstil.get(md.get("sprachstil", "?"), 0) + 1

        for agent in CONTRACTS:
            pairs = project_trace(t, agent)
            if pairs:
                by_agent[agent] = by_agent.get(agent, 0) + len(pairs)

    return {
        "total_traces": len(traces),
        "by_difficulty": by_difficulty,
        "by_category": by_category,
        "by_sprachstil": by_sprachstil,
        "training_pairs_per_agent": by_agent,
    }


if __name__ == "__main__":
    # Quick self-test: leerer Trace → keine Paare, keine Fehler
    empty = {"id": "test", "specification": "test"}
    for name in CONTRACTS:
        pairs = project_trace(empty, name)
        assert pairs == [], f"{name} sollte [] liefern"
    print("agent_contracts.py — self-test ok")
    print(f"Registered agents: {list(CONTRACTS)}")
    print(f"Active agents:     {active_agents()}")
