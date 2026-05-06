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
        active=False,  # Aktivieren in Stufe 7 (DSPy-Re-Training).
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
        # intern 4 mini-calls (frame/alignment/anchor/offset); hier als EIN
        # Contract, da Ground-Truth als zusammengesetztes Output annotiert wird.
        # Split in 4 Sub-Contracts ist spaeter additiv moeglich.
        name="platzierer",
        input_fields=["teil_id", "teil_type", "teil_params", "alle_teile",
                      "specification", "position_sentence"],
        output_fields=["normalized_position"],
        default_model="qwen3.5:9b",
    ),
    "normalizer": AgentContract(
        # 1 Aktion → 1 Feature. Pipeline ruft NormalizerAgent pro Aktion auf
        # (siehe feature_definierer_node: for aktion in teil_aktionen: normalizer.normalize(...))
        # Die deterministische Aggregation zu einer teil_definition macht build_teil_definition,
        # nicht das LLM. Daher trainieren wir hier den fein-granularen Schritt.
        name="normalizer",
        input_fields=["beschreibung", "seite", "teil_type", "teil_params",
                      "specification"],
        output_fields=["feature"],
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
            out.append({
                "input": {
                    "beschreibung": inp.get("beschreibung", ""),
                    "seite": inp.get("seite", "oben"),
                    "teil_type": inp.get("teil_type", "box"),
                    "teil_params": inp.get("teil_params", {}),
                    "specification": inp.get("specification",
                                             trace.get("specification", "")),
                },
                "output": p.get("output", {}),
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
            pairs.append({
                "input": {
                    "beschreibung": aktion.get("beschreibung", ""),
                    "seite": aktion.get("seite", "oben"),
                    "teil_type": teil.get("type", "box"),
                    "teil_params": teil.get("raw_params", {}),
                    "specification": spec,
                },
                "output": feature,
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
    "position_extractor": _adapter_position_extractor,
    "platzierer": _adapter_position_normalizer,
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
