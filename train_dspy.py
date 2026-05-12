"""
train_dspy.py — DSPy Prompt-Optimierung für die 3-Step Blueprint Chain + BA.

Aktive Agents (via data/dspy_training/agent_contracts.py):
    inventar, position_extractor, platzierer_frame, platzierer_alignment,
    platzierer_anchor, platzierer_offset, normalizer
    (assembly_node ist deterministisch — kein LLM-Training)
Legacy (inaktiv, Training möglich):
    blueprint_architect

Quellen (additiv):
    --source traces  — Pipeline-Traces aus sonnet_traces.py + reference_traces.py
                        (via agent_contracts.project_traces) [DEFAULT]
    --source legacy  — alte examples.json (nur inventar/teil_def/assembly/BA)
    --source all     — beide kombiniert

Plus immer: feedback=good Runs aus data/sessions/runs.jsonl.

Verwendung:
    python train_dspy.py --stats                                # Statistik
    python train_dspy.py --all                                  # alle aktiven Agents
    python train_dspy.py --agent position_extractor             # einzeln
    python train_dspy.py --mode ba --model nemotron-cascade-2:30b
    python train_dspy.py --agent inventar --source all          # Traces + Legacy

Voraussetzungen:
    - pip install dspy
    - Ollama läuft lokal mit dem gewünschten Modell
"""

import argparse
import json
import random
import sys
from pathlib import Path

import dspy

# ── Pfade ────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent
RUNS_FILE = PROJECT_ROOT / "data" / "sessions" / "runs.jsonl"
EXAMPLES_FILE = PROJECT_ROOT / "data" / "dspy_training" / "examples.json"
OPTIMIZED_DIR = PROJECT_ROOT / "data" / "dspy_optimized"

# ── Trace-Quellen (Pipeline-Traces via agent_contracts) ──────────
sys.path.insert(0, str(PROJECT_ROOT / "data" / "dspy_training"))
from agent_contracts import (  # noqa: E402
    project_traces, active_agents, CONTRACTS,
    classifier_sub_agent_name_for_pair,
)


# ── Daten laden ──────────────────────────────────────────────────

def load_manual_examples() -> list[dict]:
    """Kuratierte Beispiele aus examples.json laden (Legacy-Format)."""
    if not EXAMPLES_FILE.exists():
        return []
    return json.loads(EXAMPLES_FILE.read_text(encoding="utf-8"))


def load_traces() -> list[dict]:
    """Alle Pipeline-Traces laden (reference + sonnet batches + labeler/platzierer)."""
    traces: list[dict] = []
    # Primär: Python-Module importieren, damit _pos/_norm-Helfer materialisiert sind
    try:
        from reference_traces import TRACES as REF_TRACES
        traces.extend(REF_TRACES)
    except Exception as e:
        print(f"WARN: reference_traces nicht ladbar: {e}")
    try:
        from sonnet_traces import TRACES as SONNET_TRACES
        traces.extend(SONNET_TRACES)
    except Exception as e:
        print(f"WARN: sonnet_traces nicht ladbar: {e}")
    # Hand-curated traces fuer den Labeler-Reshape + Anker-Vokabular (2026-05-04)
    try:
        from labeler_platzierer_traces import ALL_TRACES as LABELER_TRACES
        traces.extend(LABELER_TRACES)
    except Exception as e:
        print(f"WARN: labeler_platzierer_traces nicht ladbar: {e}")
    # Hand-curated variation pack for language variety (voice/user phrasing).
    try:
        from variation_traces import TRACES as VARIATION_TRACES
        traces.extend(VARIATION_TRACES)
    except Exception as e:
        print(f"WARN: variation_traces nicht ladbar: {e}")
    return traces


def traces_to_agent_pairs(traces: list[dict], agent_name: str) -> list[dict]:
    """Projiziere Traces auf Agent-Paare via agent_contracts-Adapter."""
    if not traces:
        return []
    pairs = project_traces(traces, agent_name)
    return [{**p, "feedback": "good"} for p in pairs]


def load_runs() -> list[dict]:
    """Alle Runs aus runs.jsonl laden."""
    if not RUNS_FILE.exists():
        return []
    runs = []
    for line in RUNS_FILE.read_text(encoding="utf-8").splitlines():
        try:
            runs.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return runs


def load_punctuation_seed() -> list[dict]:
    """Seed-Beispiele aus data/prompts/prompt_punctuation.py.

    Erste Trainingsrunde hat noch keine runs.jsonl Traces des Punctuation-Agents.
    Die statischen FEW_SHOT_EXAMPLES dienen als Anfangs-Set, damit das erste
    Training nicht leer laeuft.
    """
    try:
        sys.path.insert(0, str(PROJECT_ROOT))
        from src.utils.prompt_loader import load_prompt
        mod = load_prompt("prompt_punctuation.py")
        examples = getattr(mod, "FEW_SHOT_EXAMPLES", [])
    except Exception as e:
        print(f"WARN: punctuation seed nicht ladbar: {e}")
        return []
    return [
        {"input": {"specification": ex["input"]},
         "output": ex["output"],
         "feedback": "good"}
        for ex in examples
    ]


def load_aktions_klassifizierer_seed() -> list[dict]:
    """Hand-curated classifier bug/variation cases.

    `klassifizierer_traces.py` predates full trace projection and stores
    direct phrase-level examples. Keep it as seed material so the classifier
    can be trained without forcing those entries into whole-pipeline traces.
    """
    try:
        sys.path.insert(0, str(PROJECT_ROOT / "data" / "dspy_training"))
        from klassifizierer_traces import TRACES as KLASS_TRACES
    except Exception as e:
        print(f"WARN: klassifizierer seed nicht ladbar: {e}")
        return []
    pairs = []
    for ex in KLASS_TRACES:
        pairs.append({
            "input": {
                "phrase": ex.get("phrase", ""),
                "teil_type": ex.get("teil_type", "box"),
                "teil_params": ex.get("teil_params", {}),
                "parent_phrase": ex.get("parent_phrase", "(keine)"),
            },
            "output": ex.get("expected", {}),
            "feedback": "good",
        })
    return pairs


CLASSIFIER_SUB_AGENTS = {
    "hole_classifier",
    "pocket_classifier",
    "slot_classifier",
    "pattern_classifier",
    "edge_feature_classifier",
}


def filter_classifier_pairs_for_subagent(
    pairs: list[dict],
    agent_name: str,
) -> list[dict]:
    """Filter monolithic classifier pairs into one ADR-0006 sub-contract."""
    if agent_name not in CLASSIFIER_SUB_AGENTS:
        return pairs
    return [
        p for p in pairs
        if classifier_sub_agent_name_for_pair(p) == agent_name
    ]


def load_classifier_subagent_seed(agent_name: str) -> list[dict]:
    """Direct seed examples for ADR-0006 classifier sub-agents."""
    return filter_classifier_pairs_for_subagent(
        load_aktions_klassifizierer_seed(),
        agent_name,
    )


def load_normalizer_seed() -> list[dict]:
    """Direct seed examples for the Normalizer runtime short-form contract."""
    try:
        sys.path.insert(0, str(PROJECT_ROOT / "data" / "dspy_training"))
        from normalizer_traces import TRACES as NORMALIZER_TRACES
    except Exception as e:
        print(f"WARN: normalizer seed nicht ladbar: {e}")
        return []
    return [
        {
            "input": ex.get("input", {}),
            "output": ex.get("expected", ""),
            "feedback": "good",
        }
        for ex in NORMALIZER_TRACES
    ]


def manual_to_agent_pairs(examples: list[dict], agent_name: str) -> list[dict]:
    """Konvertiere kuratierte Legacy-Beispiele (examples.json) in Agent-Pairs.

    Das Legacy-Format hat keine pro-Aktion-Annotation, daher kann es nicht
    sinnvoll auf den fein-granularen `normalizer` projiziert werden. Nur
    inventar + blueprint_architect bekommen Pairs aus diesem Pfad.
    """
    pairs = []
    for ex in examples:
        spec = ex["specification"]
        inv = ex["inventar"]
        bp = ex["blueprint"]

        if agent_name == "inventar":
            pairs.append({"input": {"specification": spec}, "output": inv, "feedback": "good"})

        elif agent_name == "blueprint_architect":
            pairs.append({"input": {"specification": spec}, "output": bp, "feedback": "good"})

    return pairs


def extract_run_examples(runs: list[dict], agent_name: str,
                         only_successful: bool = True) -> list[dict]:
    """Extrahiert Input/Output-Paare für einen Agent aus runs.jsonl."""
    examples = []
    for run in runs:
        if only_successful and not run.get("success"):
            continue
        feedback = run.get("feedback", "")
        for trace in run.get("agent_traces", []):
            if trace.get("agent") != agent_name:
                continue
            inp = trace.get("input")
            out = trace.get("output")
            if not inp or not out:
                continue
            if isinstance(out, dict) and ("error" in out or out.get("skipped")):
                continue
            examples.append({"input": inp, "output": out, "feedback": feedback})
    return examples


def extract_aktions_klassifizierer_run_examples(
    runs: list[dict],
    only_successful: bool = True,
) -> list[dict]:
    """Expand logged classifier node traces into phrase-level examples.

    Live runs log `aktions_klassifizierer` as one node output containing
    `klassifikationen: [...]`. DSPy training needs one example per phrase,
    matching the actual agent call contract.
    """
    examples = []
    for run in runs:
        if only_successful and not run.get("success"):
            continue
        traces = run.get("agent_traces", []) or []
        inventar_trace = next(
            (t for t in traces if t.get("agent") == "inventar"),
            None,
        )
        classifier_trace = next(
            (t for t in traces if t.get("agent") == "aktions_klassifizierer"),
            None,
        )
        if not inventar_trace or not classifier_trace:
            continue
        inventar_out = inventar_trace.get("output") or {}
        klassifikationen = (classifier_trace.get("output") or {}).get(
            "klassifikationen", []
        )
        if not isinstance(klassifikationen, list):
            continue

        teile_by_id = {
            t.get("id"): t
            for t in inventar_out.get("teile", [])
            if isinstance(t, dict) and t.get("id")
        }
        by_idx: dict[tuple[str, int], dict] = {}
        for k in klassifikationen:
            if not isinstance(k, dict):
                continue
            teil_id = k.get("teil_id", "")
            teil = teile_by_id.get(teil_id, {})
            parent_phrase = "(keine)"
            parent_idx = k.get("parent_phrase_idx")
            if parent_idx is not None:
                parent = by_idx.get((teil_id, parent_idx))
                if parent:
                    parent_phrase = parent.get("beschreibung", "(keine)")

            examples.append({
                "input": {
                    "phrase": k.get("beschreibung", ""),
                    "teil_type": teil.get("type", "box"),
                    "teil_params": teil.get("raw_params", {}),
                    "parent_phrase": parent_phrase,
                },
                "output": {
                    "typ": k.get("typ", ""),
                    "seite": k.get("seite", ""),
                    "parameter_hints": k.get("parameter_hints", {}),
                },
                "feedback": run.get("feedback", ""),
            })
            by_idx[(teil_id, k.get("phrase_idx", 0))] = k
    return examples


def print_stats():
    """Zeigt Statistik über verfügbare Trainingsdaten (Traces + Legacy + Runs)."""
    manual = load_manual_examples()
    traces = load_traces()
    runs = load_runs()

    print(f"\n{'='*60}")
    print(f"PIPELINE-TRACES: {len(traces)}")
    print(f"LEGACY examples.json: {len(manual)}")
    print(f"RUNS (runs.jsonl): {len(runs)}")
    print(f"  Erfolgreich: {sum(1 for r in runs if r.get('success'))}")
    print(f"  Feedback=good: {sum(1 for r in runs if r.get('feedback') == 'good')}")

    agents = list(AGENT_CONFIG.keys())
    name_width = 34
    print(f"\n{'Agent':<{name_width}} {'Traces':>8} {'Legacy':>8} "
          f"{'Runs':>6} {'Seed':>6} {'Gesamt':>8}")
    print("-" * (name_width + 42))
    for agent in agents:
        t = traces_to_agent_pairs(traces, agent)
        m = manual_to_agent_pairs(manual, agent)
        if agent == "aktions_klassifizierer" or agent in CLASSIFIER_SUB_AGENTS:
            run_source = extract_aktions_klassifizierer_run_examples(
                runs, only_successful=True
            )
            if agent in CLASSIFIER_SUB_AGENTS:
                run_source = filter_classifier_pairs_for_subagent(
                    run_source, agent
                )
        else:
            run_source = extract_run_examples(runs, agent, only_successful=True)
        r = [p for p in run_source if p.get("feedback") == "good"]
        if agent == "punctuation":
            s = load_punctuation_seed()
        elif agent == "aktions_klassifizierer":
            s = load_aktions_klassifizierer_seed()
        elif agent in CLASSIFIER_SUB_AGENTS:
            s = load_classifier_subagent_seed(agent)
        elif agent == "normalizer":
            s = load_normalizer_seed()
        else:
            s = []
        active = (
            "" if CONTRACTS.get(agent) and CONTRACTS[agent].active
            else " (inactive)"
        )
        print(f"{agent+active:<{name_width}} {len(t):>8} {len(m):>8} {len(r):>6} "
              f"{len(s):>6} {len(t)+len(m)+len(r)+len(s):>8}")


# ── DSPy Signatures ─────────────────────────────────────────────

class PunctuationSignature(dspy.Signature):
    """Setze Kommas in eine CAD-Spezifikation an natuerlichen Trennstellen.
    KEIN Wort, KEINE Zahl, KEINE Einheit aendern — nur Kommas einfuegen.
    Trenne Bauteil von erster Aktion und aufeinanderfolgende Aktionen mit
    eigener Seitenangabe."""

    specification: str = dspy.InputField(
        desc="Roher Spezifikationstext (oft Voice-Input ohne Kommas)."
    )
    punctuated: str = dspy.OutputField(
        desc="Selber Text, nur mit Kommas an natuerlichen Trennstellen. "
             "Identische Wort-Sequenz wie der Input."
    )


class InventarSignature(dspy.Signature):
    """Extrahiere eine Stückliste (Inventar) aus einer CAD-Bauteilbeschreibung.
    Zähle die Körper (Bodies), liste ihre Namen, Typen und Rohdimensionen auf,
    und sammle alle Aktionen (Features) mit der zugehörigen Seite."""

    specification: str = dspy.InputField(
        desc="Die vollständige, eindeutige Bauteil-Spezifikation in natürlicher Sprache."
    )
    inventar: str = dspy.OutputField(
        desc="JSON-Objekt mit teil_count, teile[{id, type, beschreibung, raw_params}], "
             "aktionen[{teil_id, seite, beschreibung}]"
    )


class AktionsKlassifiziererSignature(dspy.Signature):
    """Klassifiziere EINE Aktions-Phrase in typ, seite und parameter_hints.

    Aufgabe bleibt eng: keine Feature-Struktur bauen, keine Offsets berechnen,
    keine strukturellen Splitter-Felder erfinden. Der Code reicht teil_id und
    phrase_idx separat durch.
    """

    phrase: str = dspy.InputField(
        desc="Eine einzelne Aktions-Phrase aus dem deterministischen Splitter."
    )
    teil_type: str = dspy.InputField(
        desc="Form des Host-Teils (box, cylinder, ...)."
    )
    teil_params: str = dspy.InputField(
        desc="JSON der Roh-Parameter des Host-Teils."
    )
    parent_phrase: str = dspy.InputField(
        desc="Parent-Phrase fuer nested Features, sonst '(keine)'."
    )
    klassifikation: str = dspy.OutputField(
        desc="JSON {typ, seite, parameter_hints}. parameter_hints enthaelt "
             "nur explizite Werte aus der Phrase; Zahlen plus optional "
             "richtung=x|y|z fuer Achsen."
    )


class HoleClassifierSignature(dspy.Signature):
    """Klassifiziere EINE Bohrungs-Phrase.

    Enger ADR-0006 Sub-Contract: typ muss bohrung sein. Keine Tasche/Nut/
    Pattern-Struktur bauen; nur seite und explizite Bohrungs-Hints.
    """

    phrase: str = dspy.InputField(desc="Eine einzelne Bohrungs-/Loch-Phrase.")
    teil_type: str = dspy.InputField(desc="Form des Host-Teils.")
    teil_params: str = dspy.InputField(desc="JSON der Host-Teil-Parameter.")
    parent_phrase: str = dspy.InputField(desc="Parent-Phrase, sonst '(keine)'.")
    klassifikation: str = dspy.OutputField(
        desc="JSON {typ:'bohrung', seite, parameter_hints}; erlaubte Hints: "
             "durchmesser, tiefe, abstand_*, versatz_*."
    )


class PocketClassifierSignature(dspy.Signature):
    """Klassifiziere EINE Taschen-/Ausnehmungs-Phrase."""

    phrase: str = dspy.InputField(desc="Eine einzelne Tasche/Ausnehmung-Phrase.")
    teil_type: str = dspy.InputField(desc="Form des Host-Teils.")
    teil_params: str = dspy.InputField(desc="JSON der Host-Teil-Parameter.")
    parent_phrase: str = dspy.InputField(desc="Parent-Phrase, sonst '(keine)'.")
    klassifikation: str = dspy.OutputField(
        desc="JSON {typ:'tasche', seite, parameter_hints}; erlaubte Hints: "
             "laenge, breite, tiefe, hoehe, rotation_deg, abstand_*, "
             "kante_*, versatz_*."
    )


class SlotClassifierSignature(dspy.Signature):
    """Klassifiziere EINE Nut-/Slot-Phrase."""

    phrase: str = dspy.InputField(desc="Eine einzelne Nut/Slot-Phrase.")
    teil_type: str = dspy.InputField(desc="Form des Host-Teils.")
    teil_params: str = dspy.InputField(desc="JSON der Host-Teil-Parameter.")
    parent_phrase: str = dspy.InputField(desc="Parent-Phrase, sonst '(keine)'.")
    klassifikation: str = dspy.OutputField(
        desc="JSON {typ:'nut', seite, parameter_hints}; erlaubte Hints: "
             "laenge, breite, tiefe, rotation_deg, richtung=x|y|z, "
             "abstand_*, kante_*, versatz_*."
    )


class PatternClassifierSignature(dspy.Signature):
    """Klassifiziere EINE Lochmuster-Phrase als Bohrungs-Familie."""

    phrase: str = dspy.InputField(desc="Eine einzelne Lochkreis/Eckbohrungen/Reihe-Phrase.")
    teil_type: str = dspy.InputField(desc="Form des Host-Teils.")
    teil_params: str = dspy.InputField(desc="JSON der Host-Teil-Parameter.")
    parent_phrase: str = dspy.InputField(desc="Parent-Phrase, sonst '(keine)'.")
    klassifikation: str = dspy.OutputField(
        desc="JSON {typ:'bohrung', seite, parameter_hints}; Pattern-Hints "
             "duerfen anzahl, kreis_durchmesser, abstand, abstand_kante, "
             "durchmesser, tiefe, richtung enthalten."
    )


class EdgeFeatureClassifierSignature(dspy.Signature):
    """Klassifiziere EINE Fase- oder Rundungs-Phrase."""

    phrase: str = dspy.InputField(desc="Eine einzelne Fase/Rundung-Phrase.")
    teil_type: str = dspy.InputField(desc="Form des Host-Teils.")
    teil_params: str = dspy.InputField(desc="JSON der Host-Teil-Parameter.")
    parent_phrase: str = dspy.InputField(desc="Parent-Phrase, sonst '(keine)'.")
    klassifikation: str = dspy.OutputField(
        desc="JSON {typ:'fase'|'rundung', seite, parameter_hints}; erlaubte "
             "Hints: groesse, radius, kantenlaenge."
    )


class NormalizerSignature(dspy.Signature):
    """Normalisiere EINE einzelne Aktion auf einem Teil zu EINER Kurzform.

    Kontext: Die Pipeline ruft den Normalizer pro Aktion auf (1 Aktion → 1 Feature).
    Die deterministische Aggregation aller Features zu einer teil_definition
    macht ein Code-Schritt (build_teil_definition), nicht das LLM.

    Aufgabe: Aus einem Beschreibungstext + Seite + Teil-Kontext einen sauberen
    fixed-vocabulary Kurztext erzeugen:
    typ, seite, position, optional richtung, parameter, notes.
    KEIN Feature-JSON bauen — build_feature macht das deterministisch.
    """

    beschreibung: str = dspy.InputField(
        desc="Aktions-Beschreibung in natuerlicher Sprache (z.B. 'Bohrung Ø10, 20mm von links, durchgehend')."
    )
    seite: str = dspy.InputField(
        desc="Seite des Teils ('oben', 'unten', 'rechts', 'links', 'vorne', 'hinten')."
    )
    teil_type: str = dspy.InputField(
        desc="Form des Teils ('box', 'cylinder', ...)."
    )
    teil_params: str = dspy.InputField(
        desc="JSON der Roh-Parameter des Teils (z.B. {x:100, y:80, z:20})."
    )
    specification: str = dspy.InputField(
        desc="Original-Spezifikation als Kontext."
    )
    normalisierung: str = dspy.OutputField(
        desc="Kurzform-Zeilen im Runtime-Format: typ, seite, position, "
             "optional richtung, parameter (key=wert, ...), notes. Kein JSON."
    )


class PositionExtractorSignature(dspy.Signature):
    """Per-Teil Labeler (ab 2026-05-04 Reshape).

    Eingabe: der Text EINES Teils (vom text_splitter vorgesplittet).
    Aufgabe: Saetze in zwei Listen trennen — placement (wo sitzt das Teil) vs
    feature (welche Bohrungen/Taschen). Originalwortlaut beibehalten."""

    teil_id: str = dspy.InputField(
        desc="ID des Teils das gelabelt wird (Kontext fuer das Modell)."
    )
    teil_text: str = dspy.InputField(
        desc="Per-Teil Text-Chunk vom TextSplitter — nur Saetze die zu diesem Teil gehoeren."
    )
    sentences: str = dspy.OutputField(
        desc="JSON {'placement_sentences': [...], 'feature_sentences': [...]} — "
             "Saetze des Teils getrennt nach Platzierung vs Feature. "
             "Saetze die nichts mit beidem zu tun haben weglassen."
    )


class PositionNormalizerSignature(dspy.Signature):
    """Normalisiere EINEN Platzierungs-Satz eines Kind-Teils in ein strukturiertes Dict.
    Felder: parent (teil_id), seite (aus Parent-Sicht), ausrichtung (centered/flush_*/anker),
    orientierung (standard/hochkant/liegend), anliegende_flaeche, abstand, winkel, anker, pre_rotation."""

    teil_id: str = dspy.InputField(desc="ID des zu platzierenden Kind-Teils.")
    teil_type: str = dspy.InputField(desc="Typ des Kind-Teils (box, cylinder, ...).")
    teil_params: str = dspy.InputField(desc="JSON der Roh-Parameter des Kind-Teils.")
    alle_teile: str = dspy.InputField(desc="JSON-Liste aller Teile (Kontext).")
    specification: str = dspy.InputField(desc="Original-Spezifikation als Kontext.")
    position_sentence: str = dspy.InputField(
        desc="Der pre-digester Platzierungs-Satz aus PositionExtractor."
    )
    normalized_position: str = dspy.OutputField(
        desc="JSON-Objekt mit {parent, seite, ausrichtung, orientierung, "
             "anliegende_flaeche, abstand, winkel, anker, pre_rotation, notes}."
    )


class PlatziererFrameSignature(dspy.Signature):
    """Bestimme NUR Parent, Parent-Flaeche, Kind-Orientierung und Kontaktflaeche.
    Antworte als key:value Zeilen: parent, seite, orientierung, anliegende_flaeche."""

    teil_id: str = dspy.InputField(desc="ID des zu platzierenden Kind-Teils.")
    teil_type: str = dspy.InputField(desc="Typ des Kind-Teils.")
    teil_params: str = dspy.InputField(desc="JSON der Roh-Parameter des Kind-Teils.")
    alle_teile: str = dspy.InputField(desc="JSON-Liste aller Teile.")
    position_sentence: str = dspy.InputField(desc="Platzierungsbeschreibung.")
    frame: str = dspy.OutputField(
        desc="Vier Zeilen: parent: ..., seite: ..., orientierung: ..., anliegende_flaeche: ..."
    )


class PlatziererAlignmentSignature(dspy.Signature):
    """Bestimme NUR die 2D-Ausrichtung auf der bereits gewaehlten Parent-Flaeche.
    Antworte mit genau einer Zeile: ausrichtung: <keyword>.

    Grenzen:
    - versetzt/verschoben/von der Mitte -> von_mitte
    - X mm von Kante/Abstand zur Kante -> von_kanten
    - Anker-Sprache wie Ecke/Kante der Platte auf/von Ecke/Kante des Parents
      nicht als buendig klassifizieren; wenn keine weitere Ausrichtung da ist:
      zentriert. Anchor-Punkte macht ein anderer Agent.
    - nach aussen/Ueberstand an Kante -> buendig_rechts/links/oben/unten,
      an Ecke -> kombiniertes buendig_*.
    """

    seite: str = dspy.InputField(desc="Bereits gewaehlte Parent-Flaeche.")
    position_sentence: str = dspy.InputField(desc="Platzierungsbeschreibung.")
    alignment: str = dspy.OutputField(
        desc="Eine Zeile: ausrichtung: zentriert|buendig_*|von_kanten|von_mitte."
    )


class PlatziererAnchorSignature(dspy.Signature):
    """Bestimme NUR Ankerpunkte, wenn ein Kind-Punkt auf einem Parent-Punkt liegt.
    Antworte als key:value Zeilen: kind_punkt, eltern_punkt, optional eltern_abstand."""

    teil_id: str = dspy.InputField(desc="ID des Kind-Teils.")
    teil_type: str = dspy.InputField(desc="Typ des Kind-Teils.")
    teil_params: str = dspy.InputField(desc="JSON der Roh-Parameter des Kind-Teils.")
    parent: str = dspy.InputField(desc="Parent-Teil-ID.")
    position_sentence: str = dspy.InputField(desc="Platzierungsbeschreibung.")
    anchor: str = dspy.OutputField(
        desc="Zeilen: kind_punkt: ..., eltern_punkt: ..., optional eltern_abstand: richtung=wert."
    )


class PlatziererOffsetSignature(dspy.Signature):
    """Extrahiere NUR Winkel, Versatz, Kantenabstand und pre_rotation.
    Antworte mit key:value Zeilen; lasse Felder ohne Wert weg.

    Regeln:
    - "im Uhrzeigersinn"/CW = negativer winkel.
    - "gegen Uhrzeigersinn"/CCW = positiver winkel.
    - "versetzt", "verschoben", "von der Mitte ... nach ..." = versatz.
    - "X mm von [Kante] entfernt", "Abstand zur Kante" = kantenabstand.
    - Flaechenmasse wie "100x20 Seite liegt auf" ignorieren.
    """

    position_sentence: str = dspy.InputField(desc="Platzierungsbeschreibung.")
    offset: str = dspy.OutputField(
        desc="Zeilen fuer winkel, versatz, kantenabstand, pre_rotation. Leer wenn nichts genannt."
    )


class BlueprintArchitectSignature(dspy.Signature):
    """Erzeuge ein vollständiges semantisches Blueprint aus einer CAD-Bauteilbeschreibung.
    Identifiziere alle Teile, Features, Parent-Beziehungen und Build-Order in einem Schritt.
    Berechne KEINE Offsets — beschreibe Positionen in Worten (side, alignment, edge_distances).
    Antworte NUR mit JSON."""

    specification: str = dspy.InputField(
        desc="Die vollständige Bauteil-Spezifikation in natürlicher Sprache."
    )
    blueprint: str = dspy.OutputField(
        desc="JSON-Objekt mit description, build_order, features "
             "(jedes Feature hat type, params, parent, operation, position/orientation)."
    )


# ── DSPy Module ──────────────────────────────────────────────────

class PunctuationModule(dspy.Module):
    def __init__(self):
        self.predict = dspy.Predict(PunctuationSignature)

    def forward(self, specification: str) -> dspy.Prediction:
        return self.predict(specification=specification)


class InventarModule(dspy.Module):
    def __init__(self):
        self.predict = dspy.Predict(InventarSignature)

    def forward(self, specification: str) -> dspy.Prediction:
        return self.predict(specification=specification)


class AktionsKlassifiziererModule(dspy.Module):
    def __init__(self):
        self.predict = dspy.Predict(AktionsKlassifiziererSignature)

    def forward(self, phrase: str, teil_type: str,
                teil_params: str, parent_phrase: str) -> dspy.Prediction:
        return self.predict(
            phrase=phrase,
            teil_type=teil_type,
            teil_params=teil_params,
            parent_phrase=parent_phrase,
        )


class _ClassifierModule(dspy.Module):
    signature_cls = AktionsKlassifiziererSignature

    def __init__(self):
        self.predict = dspy.Predict(self.signature_cls)

    def forward(self, phrase: str, teil_type: str,
                teil_params: str, parent_phrase: str) -> dspy.Prediction:
        return self.predict(
            phrase=phrase,
            teil_type=teil_type,
            teil_params=teil_params,
            parent_phrase=parent_phrase,
        )


class HoleClassifierModule(_ClassifierModule):
    signature_cls = HoleClassifierSignature


class PocketClassifierModule(_ClassifierModule):
    signature_cls = PocketClassifierSignature


class SlotClassifierModule(_ClassifierModule):
    signature_cls = SlotClassifierSignature


class PatternClassifierModule(_ClassifierModule):
    signature_cls = PatternClassifierSignature


class EdgeFeatureClassifierModule(_ClassifierModule):
    signature_cls = EdgeFeatureClassifierSignature


class NormalizerModule(dspy.Module):
    def __init__(self):
        self.predict = dspy.Predict(NormalizerSignature)

    def forward(self, beschreibung: str, seite: str, teil_type: str,
                teil_params: str, specification: str) -> dspy.Prediction:
        return self.predict(
            beschreibung=beschreibung,
            seite=seite,
            teil_type=teil_type,
            teil_params=teil_params,
            specification=specification,
        )


class BlueprintArchitectModule(dspy.Module):
    def __init__(self):
        self.predict = dspy.ChainOfThought(BlueprintArchitectSignature)

    def forward(self, specification: str) -> dspy.Prediction:
        return self.predict(specification=specification)


class PositionExtractorModule(dspy.Module):
    def __init__(self):
        self.predict = dspy.Predict(PositionExtractorSignature)

    def forward(self, teil_id: str, teil_text: str) -> dspy.Prediction:
        return self.predict(teil_id=teil_id, teil_text=teil_text)


class PositionNormalizerModule(dspy.Module):
    def __init__(self):
        self.predict = dspy.Predict(PositionNormalizerSignature)

    def forward(self, teil_id: str, teil_type: str, teil_params: str,
                alle_teile: str, specification: str,
                position_sentence: str) -> dspy.Prediction:
        return self.predict(
            teil_id=teil_id, teil_type=teil_type, teil_params=teil_params,
            alle_teile=alle_teile, specification=specification,
            position_sentence=position_sentence,
        )


class PlatziererFrameModule(dspy.Module):
    def __init__(self):
        self.predict = dspy.Predict(PlatziererFrameSignature)

    def forward(self, teil_id: str, teil_type: str, teil_params: str,
                alle_teile: str, position_sentence: str) -> dspy.Prediction:
        return self.predict(
            teil_id=teil_id,
            teil_type=teil_type,
            teil_params=teil_params,
            alle_teile=alle_teile,
            position_sentence=position_sentence,
        )


class PlatziererAlignmentModule(dspy.Module):
    def __init__(self):
        self.predict = dspy.Predict(PlatziererAlignmentSignature)

    def forward(self, seite: str, position_sentence: str) -> dspy.Prediction:
        return self.predict(seite=seite, position_sentence=position_sentence)


class PlatziererAnchorModule(dspy.Module):
    def __init__(self):
        self.predict = dspy.Predict(PlatziererAnchorSignature)

    def forward(self, teil_id: str, teil_type: str, teil_params: str,
                parent: str, position_sentence: str) -> dspy.Prediction:
        return self.predict(
            teil_id=teil_id,
            teil_type=teil_type,
            teil_params=teil_params,
            parent=parent,
            position_sentence=position_sentence,
        )


class PlatziererOffsetModule(dspy.Module):
    def __init__(self):
        self.predict = dspy.Predict(PlatziererOffsetSignature)

    def forward(self, position_sentence: str) -> dspy.Prediction:
        return self.predict(position_sentence=position_sentence)


# ── Metriken ─────────────────────────────────────────────────────

def _parse_json_safe(text) -> dict | list | None:
    """Versuche JSON zu parsen, auch wenn Markdown-Wrapper vorhanden.

    Handles non-string inputs gracefully (int, dict, list, None).
    """
    if text is None:
        return None
    if isinstance(text, (dict, list)):
        return text
    if isinstance(text, (int, float, bool)):
        return None
    if not isinstance(text, str):
        text = str(text)
    text = text.strip()
    if not text:
        return None
    if text.startswith("```"):
        lines = text.splitlines()
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    # Find first { or [ to handle preamble text
    for i, ch in enumerate(text):
        if ch in "{[":
            text = text[i:]
            break
    else:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Fallback: tolerate Python-repr-style output (single quotes, True/False/None).
    # Local LLMs sometimes drift into Python style despite JSON instructions.
    try:
        import ast
        parsed = ast.literal_eval(text)
        if isinstance(parsed, (dict, list)):
            return parsed
    except (ValueError, SyntaxError):
        pass
    return None


import re as _re_punct

def _word_tokens(text: str) -> list[str]:
    """Lowercase word tokens (Umlaut-aware) — used by punctuation_metric."""
    if not isinstance(text, str):
        text = str(text or "")
    return _re_punct.findall(r"\w+", text.lower(), flags=_re_punct.UNICODE)


def punctuation_metric(example, prediction, trace=None) -> float:
    """Bewerte Punctuation:
      0.5 — Wort-Sequenz IDENTISCH zum Input (hard requirement, sonst 0.0)
      0.4 — Komma-Set passt exakt zu Erwartung (Anzahl + Position via Token-Index)
      0.1 — Mindestens 1 Komma gesetzt wenn Erwartung > 0
    """
    try:
        in_text = getattr(example, "specification", "") or ""
        expected = getattr(example, "punctuated", "") or ""
        predicted = getattr(prediction, "punctuated", "") or ""

        in_tokens = _word_tokens(in_text)
        pred_tokens = _word_tokens(predicted)
        if in_tokens != pred_tokens:
            return 0.0  # hard fail: words must not change

        score = 0.5

        # Exact comma positions (relative to word index)
        def comma_positions(text: str) -> list[int]:
            positions: list[int] = []
            word_idx = -1
            in_word = False
            for ch in text:
                if ch.isalnum() or ch == "_":
                    if not in_word:
                        word_idx += 1
                        in_word = True
                else:
                    in_word = False
                    if ch == ",":
                        positions.append(word_idx)
            return positions

        exp_pos = comma_positions(expected)
        pred_pos = comma_positions(predicted)
        if exp_pos == pred_pos:
            score += 0.4
        elif set(exp_pos) & set(pred_pos):
            overlap = len(set(exp_pos) & set(pred_pos)) / max(len(exp_pos), 1)
            score += 0.4 * overlap

        if len(exp_pos) > 0 and len(pred_pos) > 0:
            score += 0.1
        return min(score, 1.0)
    except Exception:
        return 0.0


def inventar_metric(example, prediction, trace=None) -> float:
    """Bewerte Inventar-Qualität: teil_count korrekt + aktionen vollständig."""
    try:
        expected = _parse_json_safe(getattr(example, "inventar", None))
        predicted = _parse_json_safe(getattr(prediction, "inventar", None))
        if not isinstance(predicted, dict) or not isinstance(expected, dict):
            return 0.0

        score = 0.0
        if predicted.get("teil_count") == expected.get("teil_count"):
            score += 0.4
        exp_teile = expected.get("teile", [])
        pred_teile = predicted.get("teile", [])
        if isinstance(exp_teile, list) and isinstance(pred_teile, list):
            expected_ids = {t["id"] for t in exp_teile if isinstance(t, dict) and "id" in t}
            predicted_ids = {t["id"] for t in pred_teile if isinstance(t, dict) and "id" in t}
            if expected_ids == predicted_ids:
                score += 0.3
        exp_akt = expected.get("aktionen", [])
        pred_akt = predicted.get("aktionen", [])
        if isinstance(exp_akt, list) and isinstance(pred_akt, list):
            if len(exp_akt) == len(pred_akt):
                score += 0.2
            elif abs(len(exp_akt) - len(pred_akt)) <= 1:
                score += 0.1
            if pred_akt and all(isinstance(a, dict) and a.get("seite") for a in pred_akt):
                score += 0.1

        return score
    except Exception:
        return 0.0


def aktions_klassifizierer_metric(example, prediction, trace=None) -> float:
    """Bewerte phrase → {typ, seite, parameter_hints}.

    Weighting mirrors the agent contract:
      typ 0.25, seite 0.25, hint keys 0.25, hint values 0.25.
    """
    try:
        expected = _parse_json_safe(getattr(example, "klassifikation", None))
        predicted = _parse_json_safe(getattr(prediction, "klassifikation", None))
        if not isinstance(predicted, dict) or not isinstance(expected, dict):
            return 0.0

        score = 0.0
        if predicted.get("typ") == expected.get("typ"):
            score += 0.25
        if predicted.get("seite") == expected.get("seite"):
            score += 0.25

        exp_hints = expected.get("parameter_hints") or {}
        pred_hints = predicted.get("parameter_hints") or {}
        if isinstance(exp_hints, dict) and isinstance(pred_hints, dict):
            exp_keys = set(exp_hints)
            pred_keys = set(pred_hints)
            if exp_keys == pred_keys:
                score += 0.25
            elif exp_keys:
                score += 0.25 * (len(exp_keys & pred_keys) / len(exp_keys))
            if exp_keys:
                matches = sum(
                    1 for key in exp_keys
                    if key in pred_hints and pred_hints[key] == exp_hints[key]
                )
                score += 0.25 * (matches / len(exp_keys))
            elif not pred_keys:
                score += 0.25

        return score
    except Exception:
        return 0.0


def _parse_normalizer_shortform(text: str) -> dict:
    """Parse `typ:/seite:/parameter:` lines used by NormalizerAgent."""
    result = {
        "typ": "",
        "seite": "",
        "position": "",
        "richtung": "",
        "parameter": {},
        "notes": "",
    }
    for raw_line in str(text or "").strip().splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip()
        if key == "parameter":
            params = {}
            for part in value.split(","):
                part = part.strip()
                if "=" not in part:
                    continue
                p_key, _, p_value = part.partition("=")
                p_key = p_key.strip().lower()
                p_value = p_value.strip()
                if p_value.lower() in {"durch", "durchgaengig"}:
                    params[p_key] = "durch"
                else:
                    try:
                        params[p_key] = (
                            float(p_value) if "." in p_value else int(p_value)
                        )
                    except ValueError:
                        params[p_key] = p_value
            result["parameter"] = params
        elif key in result:
            result[key] = value.lower()
    return result


def _normalizer_value_equal(left, right) -> bool:
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return abs(float(left) - float(right)) < 1e-6
    return str(left).strip().lower() == str(right).strip().lower()


def normalizer_metric(example, prediction, trace=None) -> float:
    """Bewerte Normalizer: 1 Aktion → 1 Runtime-Kurzform.

    Der Normalizer soll nur Sprachbedeutung in das feste Kurzform-Vokabular
    bringen. Feature-JSON, Operationen und Geometrie-Math gehoeren dem
    deterministischen `build_feature`-Pfad.
    """
    try:
        expected = _parse_normalizer_shortform(
            getattr(example, "normalisierung", "")
        )
        predicted = _parse_normalizer_shortform(
            getattr(prediction, "normalisierung", "")
        )
        if not expected.get("typ") or not predicted.get("typ"):
            return 0.0

        score = 0.0
        if predicted.get("typ") == expected.get("typ"):
            score += 0.25
        if predicted.get("seite") == expected.get("seite"):
            score += 0.15
        if predicted.get("position") == expected.get("position"):
            score += 0.10
        if predicted.get("richtung") == expected.get("richtung"):
            score += 0.10

        exp_params = expected.get("parameter") or {}
        pred_params = predicted.get("parameter") or {}
        if isinstance(exp_params, dict) and isinstance(pred_params, dict):
            exp_keys = set(exp_params.keys())
            pred_keys = set(pred_params.keys())
            if exp_keys == pred_keys:
                score += 0.20
            value_matches = sum(
                1 for k in exp_keys
                if k in pred_params
                and _normalizer_value_equal(pred_params[k], exp_params[k])
            )
            if exp_keys:
                score += 0.20 * (value_matches / len(exp_keys))
            else:
                score += 0.20

        return score
    except Exception:
        return 0.0


def position_extractor_metric(example, prediction, trace=None) -> float:
    """Bewerte Labeler: Bag-of-Sentences-Match auf placement_sentences und feature_sentences.

    Beide Listen werden als Mengen verglichen (Reihenfolge egal). Score:
      0.5 — placement_sentences-Set stimmt (Schnittmenge / max(|exp|,|pred|))
      0.5 — feature_sentences-Set stimmt (gleiche Logik)

    Toleranz: Whitespace/Case wird vor Vergleich normalisiert. Leere Listen
    auf beiden Seiten geben 1.0 fuer diese Haelfte (nichts erwartet, nichts
    geliefert = korrekt).
    """
    def _norm_sentence(s) -> str:
        return " ".join(str(s).strip().lower().split()) if isinstance(s, str) else ""

    def _set_match(exp_list, pred_list) -> float:
        exp = {_norm_sentence(s) for s in exp_list if _norm_sentence(s)}
        pred = {_norm_sentence(s) for s in pred_list if _norm_sentence(s)}
        if not exp and not pred:
            return 1.0
        if not exp or not pred:
            return 0.0
        intersect = len(exp & pred)
        union_size = max(len(exp), len(pred))
        return intersect / union_size if union_size else 0.0

    try:
        expected = _parse_json_safe(getattr(example, "sentences", None))
        predicted = _parse_json_safe(getattr(prediction, "sentences", None))
        if not isinstance(predicted, dict) or not isinstance(expected, dict):
            return 0.0

        place_score = _set_match(
            expected.get("placement_sentences", []),
            predicted.get("placement_sentences", []),
        )
        feat_score = _set_match(
            expected.get("feature_sentences", []),
            predicted.get("feature_sentences", []),
        )
        return 0.5 * place_score + 0.5 * feat_score
    except Exception:
        return 0.0


def position_normalizer_metric(example, prediction, trace=None) -> float:
    """Bewerte PositionNormalizer: strukturelle Felder des output-Dicts.

    Kritische Felder (feld-gewichtet):
      parent 0.15, seite 0.25, ausrichtung 0.2, orientierung 0.1,
      anliegende_flaeche 0.1, abstand 0.1, winkel 0.05, anker-Struktur 0.05.
    """
    try:
        expected = _parse_json_safe(getattr(example, "normalized_position", None))
        predicted = _parse_json_safe(getattr(prediction, "normalized_position", None))
        if not isinstance(predicted, dict) or not isinstance(expected, dict):
            return 0.0

        weights = {
            "parent": 0.15,
            "seite": 0.25,
            "ausrichtung": 0.2,
            "orientierung": 0.1,
            "anliegende_flaeche": 0.1,
        }
        score = 0.0
        for field, w in weights.items():
            if predicted.get(field) == expected.get(field):
                score += w

        # abstand: dict-Gleichheit (tolerant bei None vs {})
        exp_abs = expected.get("abstand") or {}
        pred_abs = predicted.get("abstand") or {}
        if exp_abs == pred_abs:
            score += 0.1

        # winkel: numerisch gleich
        if float(expected.get("winkel") or 0) == float(predicted.get("winkel") or 0):
            score += 0.05

        # anker: struktur + wichtige Felder
        exp_anker = expected.get("anker")
        pred_anker = predicted.get("anker")
        if exp_anker is None and pred_anker is None:
            score += 0.05
        elif isinstance(exp_anker, dict) and isinstance(pred_anker, dict):
            if (exp_anker.get("kind_punkt") == pred_anker.get("kind_punkt")
                    and exp_anker.get("eltern_punkt") == pred_anker.get("eltern_punkt")):
                score += 0.05

        return score
    except Exception:
        return 0.0


def _parse_kv_lines(text) -> dict[str, str]:
    if text is None:
        return {}
    if not isinstance(text, str):
        text = str(text)
    result: dict[str, str] = {}
    for line in text.strip().splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower().replace(" ", "_")
        value = value.strip()
        if key and value:
            result[key] = value
    return result


def _parse_assignments(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for part in str(text or "").split(","):
        part = part.strip()
        if "=" not in part:
            continue
        key, _, value = part.partition("=")
        result[key.strip().lower()] = value.strip()
    return result


def _numeric_text_equal(a: str, b: str) -> bool:
    try:
        return abs(float(a) - float(b)) < 1e-6
    except (TypeError, ValueError):
        return str(a).strip().lower() == str(b).strip().lower()


def _assignment_match(exp: str, pred: str) -> float:
    exp_dict = _parse_assignments(exp)
    pred_dict = _parse_assignments(pred)
    if not exp_dict and not pred_dict:
        return 1.0
    if not exp_dict or not pred_dict:
        return 0.0
    exp_keys = set(exp_dict)
    pred_keys = set(pred_dict)
    key_score = len(exp_keys & pred_keys) / max(len(exp_keys), len(pred_keys), 1)
    value_matches = sum(
        1 for key in exp_keys & pred_keys
        if _numeric_text_equal(exp_dict[key], pred_dict[key])
    )
    value_score = value_matches / max(len(exp_keys), 1)
    return 0.5 * key_score + 0.5 * value_score


def platzierer_frame_metric(example, prediction, trace=None) -> float:
    expected = _parse_kv_lines(getattr(example, "frame", ""))
    predicted = _parse_kv_lines(getattr(prediction, "frame", ""))
    if not expected or not predicted:
        return 0.0
    fields = ("parent", "seite", "orientierung", "anliegende_flaeche")
    return sum(
        1 for field in fields
        if predicted.get(field) == expected.get(field)
    ) / len(fields)


def platzierer_alignment_metric(example, prediction, trace=None) -> float:
    expected = _parse_kv_lines(getattr(example, "alignment", ""))
    predicted = _parse_kv_lines(getattr(prediction, "alignment", ""))
    return 1.0 if predicted.get("ausrichtung") == expected.get("ausrichtung") else 0.0


def platzierer_anchor_metric(example, prediction, trace=None) -> float:
    expected = _parse_kv_lines(getattr(example, "anchor", ""))
    predicted = _parse_kv_lines(getattr(prediction, "anchor", ""))
    if not expected and not predicted:
        return 1.0
    if not expected or not predicted:
        return 0.0
    score = 0.0
    if predicted.get("kind_punkt") == expected.get("kind_punkt"):
        score += 0.4
    if predicted.get("eltern_punkt") == expected.get("eltern_punkt"):
        score += 0.4
    score += 0.2 * _assignment_match(
        expected.get("eltern_abstand", ""),
        predicted.get("eltern_abstand", ""),
    )
    return score


def platzierer_offset_metric(example, prediction, trace=None) -> float:
    expected = _parse_kv_lines(getattr(example, "offset", ""))
    predicted = _parse_kv_lines(getattr(prediction, "offset", ""))
    if not expected and not predicted:
        return 1.0
    fields = ("winkel", "versatz", "kantenabstand", "pre_rotation")
    score = 0.0
    for field in fields:
        exp_value = expected.get(field, "")
        pred_value = predicted.get(field, "")
        if field == "winkel":
            field_score = 1.0 if _numeric_text_equal(exp_value or "0", pred_value or "0") else 0.0
        else:
            field_score = _assignment_match(exp_value, pred_value)
        score += 0.25 * field_score
    return score


# ── Beispiele konvertieren ───────────────────────────────────────

def to_dspy_examples(raw: list[dict], agent_name: str) -> list[dspy.Example]:
    """Konvertiere Agent-Input/Output-Paare in DSPy Examples."""
    examples = []

    for item in raw:
        inp = item["input"]
        out = item["output"]

        def _j(obj):
            return json.dumps(obj, ensure_ascii=False) if not isinstance(obj, str) else obj

        if agent_name == "punctuation":
            # output is a plain string (the punctuated spec), not JSON
            out_text = out if isinstance(out, str) else str(out)
            ex = dspy.Example(
                specification=inp.get("specification", ""),
                punctuated=out_text,
            ).with_inputs("specification")

        elif agent_name == "inventar":
            ex = dspy.Example(
                specification=inp.get("specification", ""),
                inventar=_j(out),
            ).with_inputs("specification")

        elif agent_name == "aktions_klassifizierer" or agent_name in CLASSIFIER_SUB_AGENTS:
            ex = dspy.Example(
                phrase=inp.get("phrase", ""),
                teil_type=inp.get("teil_type", "box"),
                teil_params=_j(inp.get("teil_params", {})),
                parent_phrase=inp.get("parent_phrase", "(keine)"),
                klassifikation=_j(out),
            ).with_inputs("phrase", "teil_type", "teil_params",
                          "parent_phrase")

        elif agent_name == "normalizer":
            out_text = out if isinstance(out, str) else out.get("normalisierung", "")
            ex = dspy.Example(
                beschreibung=inp.get("beschreibung", ""),
                seite=inp.get("seite", "oben"),
                teil_type=inp.get("teil_type", "box"),
                teil_params=_j(inp.get("teil_params", {})),
                specification=inp.get("specification", ""),
                normalisierung=out_text,
            ).with_inputs("beschreibung", "seite", "teil_type",
                          "teil_params", "specification")

        elif agent_name == "blueprint_architect":
            ex = dspy.Example(
                specification=inp.get("specification", ""),
                blueprint=_j(out),
            ).with_inputs("specification")

        elif agent_name == "position_extractor":
            # New per-teil labeler: input = teil_id + teil_text, output = sentences
            # (renamed from "labels" because DSPy Example.labels is a reserved method)
            sent = out.get("sentences") if isinstance(out, dict) and "sentences" in out else \
                   out.get("labels") if isinstance(out, dict) and "labels" in out else \
                   out
            ex = dspy.Example(
                teil_id=inp.get("teil_id", ""),
                teil_text=inp.get("teil_text", ""),
                sentences=_j(sent if isinstance(sent, dict) else {}),
            ).with_inputs("teil_id", "teil_text")

        elif agent_name == "platzierer":
            ex = dspy.Example(
                teil_id=inp.get("teil_id", ""),
                teil_type=inp.get("teil_type", "box"),
                teil_params=_j(inp.get("teil_params", {})),
                alle_teile=_j(inp.get("alle_teile", [])),
                specification=inp.get("specification", ""),
                position_sentence=inp.get("position_sentence", ""),
                normalized_position=_j(out),
            ).with_inputs("teil_id", "teil_type", "teil_params",
                          "alle_teile", "specification", "position_sentence")

        elif agent_name == "platzierer_frame":
            ex = dspy.Example(
                teil_id=inp.get("teil_id", ""),
                teil_type=inp.get("teil_type", "box"),
                teil_params=_j(inp.get("teil_params", {})),
                alle_teile=_j(inp.get("alle_teile", [])),
                position_sentence=inp.get("position_sentence", ""),
                frame=out if isinstance(out, str) else str(out),
            ).with_inputs("teil_id", "teil_type", "teil_params",
                          "alle_teile", "position_sentence")

        elif agent_name == "platzierer_alignment":
            ex = dspy.Example(
                seite=inp.get("seite", "oben"),
                position_sentence=inp.get("position_sentence", ""),
                alignment=out if isinstance(out, str) else str(out),
            ).with_inputs("seite", "position_sentence")

        elif agent_name == "platzierer_anchor":
            ex = dspy.Example(
                teil_id=inp.get("teil_id", ""),
                teil_type=inp.get("teil_type", "box"),
                teil_params=_j(inp.get("teil_params", {})),
                parent=inp.get("parent", ""),
                position_sentence=inp.get("position_sentence", ""),
                anchor=out if isinstance(out, str) else str(out),
            ).with_inputs("teil_id", "teil_type", "teil_params",
                          "parent", "position_sentence")

        elif agent_name == "platzierer_offset":
            ex = dspy.Example(
                position_sentence=inp.get("position_sentence", ""),
                offset=out if isinstance(out, str) else str(out),
            ).with_inputs("position_sentence")
        else:
            continue

        examples.append(ex)

    return examples


# ── Training ─────────────────────────────────────────────────────

AGENT_CONFIG = {
    "punctuation": {
        "module_cls": PunctuationModule,
        "metric": punctuation_metric,
        "default_model": "qwen3.5:9b",
    },
    "inventar": {
        "module_cls": InventarModule,
        "metric": inventar_metric,
        "default_model": "qwen3.5:9b",
    },
    "aktions_klassifizierer": {
        "module_cls": AktionsKlassifiziererModule,
        "metric": aktions_klassifizierer_metric,
        "default_model": "gemma4:26b",
    },
    "hole_classifier": {
        "module_cls": HoleClassifierModule,
        "metric": aktions_klassifizierer_metric,
        "default_model": "gemma4:26b",
    },
    "pocket_classifier": {
        "module_cls": PocketClassifierModule,
        "metric": aktions_klassifizierer_metric,
        "default_model": "gemma4:26b",
    },
    "slot_classifier": {
        "module_cls": SlotClassifierModule,
        "metric": aktions_klassifizierer_metric,
        "default_model": "gemma4:26b",
    },
    "pattern_classifier": {
        "module_cls": PatternClassifierModule,
        "metric": aktions_klassifizierer_metric,
        "default_model": "gemma4:26b",
    },
    "edge_feature_classifier": {
        "module_cls": EdgeFeatureClassifierModule,
        "metric": aktions_klassifizierer_metric,
        "default_model": "gemma4:26b",
    },
    "position_extractor": {
        "module_cls": PositionExtractorModule,
        "metric": position_extractor_metric,
        "default_model": "gemma4:26b",
    },
    "platzierer_frame": {
        "module_cls": PlatziererFrameModule,
        "metric": platzierer_frame_metric,
        "default_model": "gemma4:26b",
    },
    "platzierer_alignment": {
        "module_cls": PlatziererAlignmentModule,
        "metric": platzierer_alignment_metric,
        "default_model": "gemma4:26b",
    },
    "platzierer_anchor": {
        "module_cls": PlatziererAnchorModule,
        "metric": platzierer_anchor_metric,
        "default_model": "gemma4:26b",
    },
    "platzierer_offset": {
        "module_cls": PlatziererOffsetModule,
        "metric": platzierer_offset_metric,
        "default_model": "gemma4:26b",
    },
    "normalizer": {
        "module_cls": NormalizerModule,
        "metric": normalizer_metric,
        "default_model": "gemma4:26b",
    },
    # assembly: Pipeline-Schritt ist deterministisch (kein LLM-Call), kein Training-Target.
    "blueprint_architect": {
        "module_cls": BlueprintArchitectModule,
        # Pragmatic: Blueprint Architect ist Legacy-Pfad, eigene Metric waere overengineering.
        # Nutzen normalizer_metric als grobe feature-basierte Bewertung.
        "metric": normalizer_metric,
        "default_model": "nemotron-cascade-2:30b",
    },
}


def train_agent(agent_name: str,
                model_name: str | None = None,
                max_bootstrapped: int = 4,
                max_labeled: int = 8,
                source: str = "traces"):
    """Trainiere/optimiere Prompts für einen Agent mit DSPy BootstrapFewShot.

    source: 'traces' (default) | 'legacy' | 'all'
    """

    config = AGENT_CONFIG.get(agent_name)
    if not config:
        print(f"FEHLER: Unbekannter Agent '{agent_name}'. Verfügbar: {list(AGENT_CONFIG)}")
        return

    # Daten laden je nach Quelle
    trace_pairs: list[dict] = []
    manual_pairs: list[dict] = []
    if source in ("traces", "all"):
        traces = load_traces()
        trace_pairs = traces_to_agent_pairs(traces, agent_name)
    if source in ("legacy", "all"):
        manual = load_manual_examples()
        manual_pairs = manual_to_agent_pairs(manual, agent_name)

    runs = load_runs()
    if agent_name == "aktions_klassifizierer" or agent_name in CLASSIFIER_SUB_AGENTS:
        run_pairs = extract_aktions_klassifizierer_run_examples(
            runs, only_successful=True
        )
        if agent_name in CLASSIFIER_SUB_AGENTS:
            run_pairs = filter_classifier_pairs_for_subagent(
                run_pairs, agent_name
            )
    else:
        run_pairs = extract_run_examples(runs, agent_name, only_successful=True)
    run_pairs = [p for p in run_pairs if p.get("feedback") == "good"]

    seed_pairs: list[dict] = []
    if agent_name == "punctuation":
        seed_pairs = load_punctuation_seed()
    elif agent_name == "aktions_klassifizierer":
        seed_pairs = load_aktions_klassifizierer_seed()
    elif agent_name in CLASSIFIER_SUB_AGENTS:
        seed_pairs = load_classifier_subagent_seed(agent_name)
    elif agent_name == "normalizer":
        seed_pairs = load_normalizer_seed()

    all_pairs = trace_pairs + manual_pairs + run_pairs + seed_pairs

    print(f"\n{'='*60}")
    print(f"Training: {agent_name}  (source={source})")
    print(f"  Traces: {len(trace_pairs)}, Legacy: {len(manual_pairs)}, "
          f"Runs: {len(run_pairs)}, Seed: {len(seed_pairs)}, "
          f"Gesamt: {len(all_pairs)}")
    print(f"{'='*60}")

    if not all_pairs:
        print(f"FEHLER: Keine Trainingsdaten für '{agent_name}'.")
        return

    examples = to_dspy_examples(all_pairs, agent_name)
    # Curated trace files are often grouped by category/difficulty. A plain
    # tail split can put a whole failure mode (e.g. "nach aussen"/ueberstand)
    # only into dev, so the optimizer never sees a demo for it. Keep the split
    # deterministic, but shuffle before slicing.
    rng = random.Random(42)
    rng.shuffle(examples)

    # Split: 80% train, 20% dev (min 1 dev)
    split = max(1, int(len(examples) * 0.8))
    trainset = examples[:split]
    devset = examples[split:] if len(examples) > split else examples[:1]

    print(f"  Train: {len(trainset)}, Dev: {len(devset)}")

    # DSPy LM konfigurieren (Ollama)
    model = model_name or config["default_model"]
    # extra_body.think=False disables reasoning_content for gemma/qwen/etc.,
    # otherwise the model fills the reasoning channel and leaves the text channel
    # empty under DSPy's default ChatAdapter. Mirrors the Pipeline's call_json()
    # which sets think via agent_options.
    lm = dspy.LM(
        model=f"ollama_chat/{model}",
        api_base="http://localhost:11434",
        temperature=0.1,
        max_tokens=3000,
        extra_body={"think": False},
    )
    # JSONAdapter forces structured JSON output instead of DSPy's free-form
    # [[ ## field ## ]] markers — much more reliable for local models that
    # otherwise drift into reasoning loops without producing parseable text.
    dspy.configure(lm=lm, adapter=dspy.JSONAdapter())
    print(f"  Modell: {model}  (think=False, JSONAdapter, max_tokens=3000)")

    # Modul und Optimierer
    module = config["module_cls"]()
    metric = config["metric"]

    optimizer = dspy.BootstrapFewShot(
        metric=metric,
        max_bootstrapped_demos=max_bootstrapped,
        max_labeled_demos=max_labeled,
    )

    print(f"\n  Starte Optimierung...")
    try:
        optimized = optimizer.compile(module, trainset=trainset)
    except Exception as e:
        print(f"  FEHLER bei Optimierung: {e}")
        import traceback
        traceback.print_exc()
        return

    # Evaluiere auf devset
    if devset:
        scores = []
        for ex in devset:
            try:
                pred = optimized(**{k: getattr(ex, k) for k in ex.inputs().keys()})
                score = metric(ex, pred)
                scores.append(score)
                print(f"    dev example score: {score:.2f}")
            except Exception as eval_err:
                print(f"    dev example error: {eval_err}")
                scores.append(0.0)
        avg = sum(scores) / len(scores) if scores else 0.0
        print(f"\n  Dev-Score: {avg:.2f} ({len(scores)} Beispiele)")

    # Speichern
    OPTIMIZED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OPTIMIZED_DIR / f"{agent_name}_optimized.json"
    optimized.save(str(out_path))
    print(f"  Gespeichert: {out_path}")

    return optimized


# ── Main ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="DSPy Prompt-Training: Pipeline-Traces → optimierte Prompts.")
    parser.add_argument("--agent", type=str,
                        help=f"Einzelnen Agent trainieren. Verfügbar: {list(AGENT_CONFIG)}")
    parser.add_argument("--all", action="store_true",
                        help="Alle aktiven Agents trainieren (ohne blueprint_architect/legacy)")
    parser.add_argument("--mode", type=str, choices=["ba"],
                        help="'ba' = Legacy Blueprint Architect (monolithisch)")
    parser.add_argument("--source", type=str, choices=["traces", "legacy", "all"],
                        default="traces",
                        help="Datenquelle: traces (default) | legacy examples.json | all")
    parser.add_argument("--stats", action="store_true",
                        help="Trainingsdaten-Statistik anzeigen")
    parser.add_argument("--model", type=str, default=None,
                        help="Modell überschreiben (z.B. nemotron-cascade-2:30b)")
    parser.add_argument("--max-bootstrapped", type=int, default=4,
                        help="Max bootstrapped demos (default: 4)")
    parser.add_argument("--max-labeled", type=int, default=8,
                        help="Max labeled demos (default: 8)")
    args = parser.parse_args()

    if args.stats:
        print_stats()
        return

    if args.mode == "ba":
        train_agent("blueprint_architect", args.model,
                    args.max_bootstrapped, args.max_labeled, source=args.source)
        return

    if args.all:
        for agent in active_agents():
            train_agent(agent, args.model,
                        args.max_bootstrapped, args.max_labeled, source=args.source)
        return

    if args.agent:
        train_agent(args.agent, args.model,
                    args.max_bootstrapped, args.max_labeled, source=args.source)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
