"""
train_dspy.py — DSPy Prompt-Optimierung für die 3-Step Blueprint Chain + BA.

Aktive Agents (via data/dspy_training/agent_contracts.py):
    inventar, position_extractor, platzierer, feature_definierer, assembly
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
    project_traces, active_agents, CONTRACTS
)


# ── Daten laden ──────────────────────────────────────────────────

def load_manual_examples() -> list[dict]:
    """Kuratierte Beispiele aus examples.json laden (Legacy-Format)."""
    if not EXAMPLES_FILE.exists():
        return []
    return json.loads(EXAMPLES_FILE.read_text(encoding="utf-8"))


def load_traces() -> list[dict]:
    """Alle Pipeline-Traces laden (reference + sonnet batches)."""
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


def manual_to_agent_pairs(examples: list[dict], agent_name: str) -> list[dict]:
    """Konvertiere kuratierte Beispiele in Agent-Input/Output-Paare."""
    pairs = []
    for ex in examples:
        spec = ex["specification"]
        inv = ex["inventar"]
        teil_defs = ex["teil_definitionen"]
        bp = ex["blueprint"]

        if agent_name == "inventar":
            pairs.append({"input": {"specification": spec}, "output": inv, "feedback": "good"})

        elif agent_name == "feature_definierer":
            aktionen = inv.get("aktionen", [])
            aktionen_by_teil = {}
            for a in aktionen:
                aktionen_by_teil.setdefault(a.get("teil_id", ""), []).append(a)
            for teil_def in teil_defs:
                teil_id = teil_def["id"]
                teil_inv = next((t for t in inv["teile"] if t["id"] == teil_id), {})
                teil_akt = aktionen_by_teil.get(teil_id, [])
                pairs.append({
                    "input": {"teil": teil_inv, "aktionen": teil_akt, "specification": spec},
                    "output": teil_def,
                    "feedback": "good",
                })

        elif agent_name == "assembly":
            # Only multi-part examples need assembly
            if inv["teil_count"] > 1:
                pairs.append({
                    "input": {"inventar": inv, "teil_definitionen": teil_defs, "specification": spec},
                    "output": bp,
                    "feedback": "good",
                })

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
    print(f"\n{'Agent':<22} {'Traces':>8} {'Legacy':>8} {'Runs':>6} {'Gesamt':>8}")
    print("-" * 56)
    for agent in agents:
        t = traces_to_agent_pairs(traces, agent)
        m = manual_to_agent_pairs(manual, agent)
        r = [p for p in extract_run_examples(runs, agent, only_successful=True)
             if p.get("feedback") == "good"]
        active = "" if CONTRACTS.get(agent) and CONTRACTS[agent].active else " (legacy)"
        print(f"{agent+active:<22} {len(t):>8} {len(m):>8} {len(r):>6} "
              f"{len(t)+len(m)+len(r):>8}")


# ── DSPy Signatures ─────────────────────────────────────────────

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


class TeilDefiniererSignature(dspy.Signature):
    """Definiere EIN CAD-Teil mit allen seinen Features (Bohrungen, Nuten, Fasen etc.)
    als semantisches Blueprint. Berechne KEINE Offsets — beschreibe Positionen in Worten."""

    teil: str = dspy.InputField(
        desc="JSON-Objekt mit id, type, beschreibung, raw_params des Teils."
    )
    aktionen: str = dspy.InputField(
        desc="JSON-Liste der Aktionen auf diesem Teil, jeweils mit teil_id, seite, beschreibung."
    )
    specification: str = dspy.InputField(
        desc="Die Original-Spezifikation als Kontext."
    )
    teil_definition: str = dspy.OutputField(
        desc="JSON-Objekt mit id, type, params, orientation, features[{id, type, params, position, operation}]"
    )


class AssemblySignature(dspy.Signature):
    """Füge einzelne Teil-Definitionen zu einem vollständigen semantischen Blueprint zusammen.
    Bestimme Root, Parent-Beziehungen und Build-Order."""

    inventar: str = dspy.InputField(
        desc="JSON-Objekt mit teil_count, teile, aktionen."
    )
    teil_definitionen: str = dspy.InputField(
        desc="JSON-Liste aller Teil-Definitionen mit ihren Features."
    )
    specification: str = dspy.InputField(
        desc="Die Original-Spezifikation als Kontext."
    )
    blueprint: str = dspy.OutputField(
        desc="JSON-Objekt mit description, build_order, features (vollständiges semantisches Blueprint)."
    )


class PositionExtractorSignature(dspy.Signature):
    """Extrahiere aus einer Multi-Part-Spezifikation die Platzierungs-Sätze pro Kind-Teil.
    Root-Teil NIE eintragen. Pro Kind-Teil: teil_id, parent_hint (woran es sitzt),
    beschreibung (pre-digester Satz: Seite + Kontaktflaeche + Versatz/Winkel, ohne Rauschen)."""

    specification: str = dspy.InputField(
        desc="Die vollständige Multi-Part-Spezifikation in natürlicher Sprache."
    )
    teile: str = dspy.InputField(
        desc="JSON-Liste aller Teile (aus Inventar) mit id, type, raw_params."
    )
    positionen: str = dspy.OutputField(
        desc="JSON-Objekt {'positionen': [{teil_id, parent_hint, beschreibung}]} — "
             "nur fuer Kind-Teile (erstes Teil = Root, wird uebersprungen)."
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

class InventarModule(dspy.Module):
    def __init__(self):
        self.predict = dspy.Predict(InventarSignature)

    def forward(self, specification: str) -> dspy.Prediction:
        return self.predict(specification=specification)


class TeilDefiniererModule(dspy.Module):
    def __init__(self):
        self.predict = dspy.Predict(TeilDefiniererSignature)

    def forward(self, teil: str, aktionen: str, specification: str) -> dspy.Prediction:
        return self.predict(teil=teil, aktionen=aktionen, specification=specification)


class AssemblyModule(dspy.Module):
    def __init__(self):
        self.predict = dspy.Predict(AssemblySignature)

    def forward(self, inventar: str, teil_definitionen: str,
                specification: str) -> dspy.Prediction:
        return self.predict(
            inventar=inventar,
            teil_definitionen=teil_definitionen,
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

    def forward(self, specification: str, teile: str) -> dspy.Prediction:
        return self.predict(specification=specification, teile=teile)


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
        return None


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


def teil_definierer_metric(example, prediction, trace=None) -> float:
    """Bewerte Teil-Definition: Features korrekt gezählt + Typen stimmen."""
    try:
        expected = _parse_json_safe(getattr(example, "teil_definition", None))
        predicted = _parse_json_safe(getattr(prediction, "teil_definition", None))
        if not isinstance(predicted, dict) or not isinstance(expected, dict):
            return 0.0

        score = 0.0
        exp_feats = expected.get("features", [])
        pred_feats = predicted.get("features", [])
        if not isinstance(exp_feats, list):
            exp_feats = []
        if not isinstance(pred_feats, list):
            pred_feats = []
        if len(exp_feats) == len(pred_feats):
            score += 0.3
        exp_types = sorted(f.get("type", "") for f in exp_feats if isinstance(f, dict))
        pred_types = sorted(f.get("type", "") for f in pred_feats if isinstance(f, dict))
        if exp_types == pred_types:
            score += 0.3
        if predicted.get("orientation") == expected.get("orientation"):
            score += 0.2
        if predicted.get("params") == expected.get("params"):
            score += 0.2

        return score
    except Exception:
        return 0.0


def assembly_metric(example, prediction, trace=None) -> float:
    """Bewerte Assembly: build_order korrekt + Parent-Beziehungen stimmen."""
    try:
        expected = _parse_json_safe(getattr(example, "blueprint", None))
        predicted = _parse_json_safe(getattr(prediction, "blueprint", None))
        if not isinstance(predicted, dict) or not isinstance(expected, dict):
            return 0.0

        score = 0.0
        # Build-order Länge
        exp_bo = expected.get("build_order", [])
        pred_bo = predicted.get("build_order", [])
        if isinstance(exp_bo, list) and isinstance(pred_bo, list) and len(exp_bo) == len(pred_bo):
            score += 0.2
        # Feature-Count
        exp_feats = expected.get("features", {})
        pred_feats = predicted.get("features", {})
        if not isinstance(exp_feats, dict):
            exp_feats = {}
        if not isinstance(pred_feats, dict):
            pred_feats = {}
        if len(exp_feats) == len(pred_feats):
            score += 0.3
        # Parent-Beziehungen korrekt
        parent_match = 0
        for fid, feat in exp_feats.items():
            if isinstance(feat, dict) and fid in pred_feats and isinstance(pred_feats[fid], dict):
                if pred_feats[fid].get("parent") == feat.get("parent"):
                    parent_match += 1
        if exp_feats:
            score += 0.3 * (parent_match / len(exp_feats))
        # Root korrekt (erstes Element, parent=null)
        if isinstance(pred_bo, list) and isinstance(exp_bo, list) and pred_bo and exp_bo:
            if pred_bo[0] == exp_bo[0]:
                score += 0.2

        return score
    except Exception:
        return 0.0


def position_extractor_metric(example, prediction, trace=None) -> float:
    """Bewerte PositionExtractor: korrekte kind-teil-Liste + parent_hint.

    0.4 — Anzahl Positionen stimmt
    0.3 — teil_ids stimmen (Set-Gleichheit)
    0.2 — parent_hints stimmen (pro Eintrag)
    0.1 — beschreibung nicht leer
    """
    try:
        expected = _parse_json_safe(getattr(example, "positionen", None))
        predicted = _parse_json_safe(getattr(prediction, "positionen", None))
        if not isinstance(predicted, dict) or not isinstance(expected, dict):
            return 0.0
        exp_pos = expected.get("positionen", [])
        pred_pos = predicted.get("positionen", [])
        if not isinstance(exp_pos, list) or not isinstance(pred_pos, list):
            return 0.0

        score = 0.0
        if len(exp_pos) == len(pred_pos):
            score += 0.4

        exp_ids = {p.get("teil_id") for p in exp_pos if isinstance(p, dict)}
        pred_ids = {p.get("teil_id") for p in pred_pos if isinstance(p, dict)}
        if exp_ids and exp_ids == pred_ids:
            score += 0.3

        # parent_hint pro Eintrag
        exp_by_id = {p.get("teil_id"): p for p in exp_pos if isinstance(p, dict)}
        hint_matches = 0
        for p in pred_pos:
            if not isinstance(p, dict):
                continue
            e = exp_by_id.get(p.get("teil_id"))
            if e and p.get("parent_hint") == e.get("parent_hint"):
                hint_matches += 1
        if exp_pos:
            score += 0.2 * (hint_matches / len(exp_pos))

        if pred_pos and all(isinstance(p, dict) and p.get("beschreibung") for p in pred_pos):
            score += 0.1

        return score
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


# ── Beispiele konvertieren ───────────────────────────────────────

def to_dspy_examples(raw: list[dict], agent_name: str) -> list[dspy.Example]:
    """Konvertiere Agent-Input/Output-Paare in DSPy Examples."""
    examples = []

    for item in raw:
        inp = item["input"]
        out = item["output"]

        def _j(obj):
            return json.dumps(obj, ensure_ascii=False) if not isinstance(obj, str) else obj

        if agent_name == "inventar":
            ex = dspy.Example(
                specification=inp.get("specification", ""),
                inventar=_j(out),
            ).with_inputs("specification")

        elif agent_name == "feature_definierer":
            ex = dspy.Example(
                teil=_j(inp.get("teil", {})),
                aktionen=_j(inp.get("aktionen", [])),
                specification=inp.get("specification", ""),
                teil_definition=_j(out),
            ).with_inputs("teil", "aktionen", "specification")

        elif agent_name == "assembly":
            ex = dspy.Example(
                inventar=_j(inp.get("inventar", {})),
                teil_definitionen=_j(inp.get("teil_definitionen", [])),
                specification=inp.get("specification", ""),
                blueprint=_j(out),
            ).with_inputs("inventar", "teil_definitionen", "specification")

        elif agent_name == "blueprint_architect":
            ex = dspy.Example(
                specification=inp.get("specification", ""),
                blueprint=_j(out),
            ).with_inputs("specification")

        elif agent_name == "position_extractor":
            ex = dspy.Example(
                specification=inp.get("specification", ""),
                teile=_j(inp.get("teile", [])),
                positionen=_j(out),
            ).with_inputs("specification", "teile")

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
        else:
            continue

        examples.append(ex)

    return examples


# ── Training ─────────────────────────────────────────────────────

AGENT_CONFIG = {
    "inventar": {
        "module_cls": InventarModule,
        "metric": inventar_metric,
        "default_model": "qwen3.5:9b",
    },
    "position_extractor": {
        "module_cls": PositionExtractorModule,
        "metric": position_extractor_metric,
        "default_model": "qwen3.5:9b",
    },
    "platzierer": {
        "module_cls": PositionNormalizerModule,
        "metric": position_normalizer_metric,
        "default_model": "qwen3.5:9b",
    },
    "feature_definierer": {
        "module_cls": TeilDefiniererModule,
        "metric": teil_definierer_metric,
        "default_model": "qwen3.5:9b",
    },
    "assembly": {
        "module_cls": AssemblyModule,
        "metric": assembly_metric,
        "default_model": "qwen3.5:9b",
    },
    "blueprint_architect": {
        "module_cls": BlueprintArchitectModule,
        "metric": assembly_metric,  # same metric — evaluates blueprint quality
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
    run_pairs = extract_run_examples(runs, agent_name, only_successful=True)
    run_pairs = [p for p in run_pairs if p.get("feedback") == "good"]

    all_pairs = trace_pairs + manual_pairs + run_pairs

    print(f"\n{'='*60}")
    print(f"Training: {agent_name}  (source={source})")
    print(f"  Traces: {len(trace_pairs)}, Legacy: {len(manual_pairs)}, "
          f"Runs: {len(run_pairs)}, Gesamt: {len(all_pairs)}")
    print(f"{'='*60}")

    if not all_pairs:
        print(f"FEHLER: Keine Trainingsdaten für '{agent_name}'.")
        return

    examples = to_dspy_examples(all_pairs, agent_name)

    # Split: 80% train, 20% dev (min 1 dev)
    split = max(1, int(len(examples) * 0.8))
    trainset = examples[:split]
    devset = examples[split:] if len(examples) > split else examples[:1]

    print(f"  Train: {len(trainset)}, Dev: {len(devset)}")

    # DSPy LM konfigurieren (Ollama)
    model = model_name or config["default_model"]
    lm = dspy.LM(
        model=f"ollama_chat/{model}",
        api_base="http://localhost:11434",
        temperature=0.1,
        max_tokens=8000,
    )
    dspy.configure(lm=lm)
    print(f"  Modell: {model}")

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
