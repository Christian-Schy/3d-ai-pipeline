"""
scripts/build_classifier_demo_pools.py — W6 (ADR 0014).

Extrahiert pro typ-Klassifizierer den VOLLEN Demo-Pool aus den kuratierten
`klassifizierer_traces.py` und schreibt ihn als `{agent}_demo_pool.json`
nach data/dspy_optimized/.

Hintergrund: BootstrapFewShot backt nur 8-16 fixe Demos in
`{agent}_optimized.json`. W6 stellt auf KNN-Retrieval um — dafuer muss der
GANZE Pool zur Inferenzzeit verfuegbar sein. Der DemoRetriever
(src/agents/demo_retriever.py) liest diese Pool-Dateien und holt pro Query
die relevantesten K Demos (hybrid: dense + BM25).

Trainings-Artefakt → Datei. Der Runtime-Code importiert KEINE
Trainings-Module; er liest nur die hier erzeugten JSONs.

Aufruf:  python scripts/build_classifier_demo_pools.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DSPY_TRAINING = PROJECT_ROOT / "data" / "dspy_training"
OUT_DIR = PROJECT_ROOT / "data" / "dspy_optimized"

sys.path.insert(0, str(DSPY_TRAINING))

# Sub-Klassifizierer, die einen Pool bekommen. anchor_classifier hat (noch)
# keine kuratierten Traces — kommt, sobald Anker-Demos existieren.
SUB_AGENTS = (
    "hole_classifier",
    "pocket_classifier",
    "slot_classifier",
    "grid_classifier",
    "circular_classifier",
    "linear_classifier",
    "edge_feature_classifier",
)


def _trace_to_demo(trace: dict) -> dict:
    """One klassifizierer_traces entry → one demo dict.

    Demo-Format spiegelt `{agent}_optimized.json`: die Klassifizierer-
    Eingabefelder + `klassifikation` als JSON-String. So kann der
    DemoRetriever die Demos genauso in (user_msg, assistant_msg) wandeln
    wie BaseAgent._load_dspy_demos es fuer die alten Demos tut.
    """
    expected = trace.get("expected", {}) or {}
    return {
        "phrase": trace.get("phrase", ""),
        "teil_type": trace.get("teil_type", "box"),
        "teil_params": trace.get("teil_params", {}),
        "parent_phrase": trace.get("parent_phrase", "(keine)"),
        "klassifikation": json.dumps(expected, ensure_ascii=False),
    }


def main() -> None:
    from klassifizierer_traces import TRACES
    from agent_contracts import classifier_sub_agent_name_for_pair

    # klassifizierer_traces → Pair-Form, die classifier_sub_agent_name_for_pair erwartet.
    pairs = [
        {
            "input": {"phrase": t.get("phrase", "")},
            "output": t.get("expected", {}) or {},
            "_trace": t,
        }
        for t in TRACES
    ]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"klassifizierer_traces: {len(TRACES)} Eintraege\n")

    total = 0
    for agent in SUB_AGENTS:
        pool = [
            _trace_to_demo(p["_trace"])
            for p in pairs
            if classifier_sub_agent_name_for_pair(p) == agent
        ]
        out_path = OUT_DIR / f"{agent}_demo_pool.json"
        out_path.write_text(
            json.dumps(pool, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        total += len(pool)
        print(f"  {agent:26s} {len(pool):3d} Demos → {out_path.name}")

    # Mehrdeutige Pattern-Phrasen (grid+circular o.ae.) routen auf None.
    unrouted = sum(
        1 for p in pairs if classifier_sub_agent_name_for_pair(p) is None
    )
    print(f"\n  Pool gesamt: {total}  (nicht zugeordnet: {unrouted})")


if __name__ == "__main__":
    main()
