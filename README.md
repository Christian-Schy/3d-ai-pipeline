# 3D AI Pipeline

> **Text → 3D-Modell.** Natürliche Sprache → semantisches Blueprint → CadQuery-Code → STL.
> Lokale LLMs (9b–30b) statt Cloud, deterministische Tools für Geometrie, KI nur für Sprachverstehen.

---

## Was es macht

Du beschreibst ein Bauteil in natürlicher Sprache:

> *"Platte 100x80x20mm. Oben eine zentrale Bohrung Ø10 durchgehend.
> Rechts daneben ein Würfel 50mm, obere linke Ecke auf linker Kante,
> 10mm von oben, 10° gegen den Uhrzeigersinn gedreht."*

Die Pipeline produziert daraus ein STL, das du direkt drucken oder weiterverarbeiten kannst.

---

## Architektur

### Pipeline-Flow

```
Text → Interpreter ─┐
                    ↓
          ┌─ Inventar (Stückliste + Aktionen)
          ├─ PositionExtractor (wo sitzt jedes Kind-Teil?)
3-Step    ├─ TextSplitter (Spec → ein Text pro Teil)
Blueprint ├─ FeatureDefinierer (Features pro Teil)
Chain     ├─ Platzierer (Anker/Rotation/Punkt-auf-Kante)
          └─ Assembly (vollständiges Blueprint)
                    ↓
          BlueprintResolver (deterministisch: semantic → resolved)
                    ↓
          CoordinateValidator → PlanValidator (LLM)
                    ↓
          FunctionDecomposer → Coder → Executor (CadQuery sandbox)
                    ↓
          GeometryPrecheck → Validator → STL
```

### Kern-Designentscheidung: KI für Sprache, Code für Mathe

**Semantisches Blueprint** (LLM erzeugt):
```python
{"orientation": "hochkant",
 "position": {"side": "oben", "alignment": "centered",
              "edge_distances": {"left": 20, "front": 15}}}
```

**Resolved Blueprint** (Resolver berechnet deterministisch):
```python
{"placement": {"face": ">Z", "offset_x": -30.0, "offset_y": -25.0}}
```

Die KI muss keine Offsets rechnen, keine Face-IDs erzeugen, keine Dimensions-Swaps machen.
Sie übersetzt natürliche Sprache in strukturiertes Vokabular — den Rest macht deterministischer Code.
Resultat: kleine Modelle (9b–26b) reichen, große (30b+) sind nur Fallback.

### Multi-Agent-Trennung

Statt eines monolithischen "GPT-baut-mir-CAD"-Prompts gibt es 10 spezialisierte Agents.
Jeder hat genau **eine** Aufgabe mit **einem** Ausgabeformat.
Vorteile:

- Kleine Modelle bewältigen einzelne Schritte, scheitern an Mega-Prompts
- Fehler isolierbar: welcher Agent hat versagt?
- Pro-Teil skalierbar: 3 Teile = 3 Calls, 20 Teile = 20 Calls
- Trainierbar pro Agent (DSPy-basiert)

---

## Stufenplan

| Stufe | Status | Inhalt |
|---|---|---|
| **1 — Primitive Assembly** | ★ aktuell | Boxen, Zylinder, Bohrungen, Taschen, Nuten, Fasen, Mehrteilige Assemblies (P0–P5 Position-Vokabular) |
| 2 — Verbindungen | geplant | Verschraubungen, Scharniere, Clips — `connection`-Feature bohrt automatisch beide Seiten |
| 3 — Komplexe Formen | geplant | Loft, Sweep, Revolution, Spline, Freiform-Konturen |
| 4 — Vision + Parametrik | geplant | Bild/Skizze → Maße schätzen → Blueprint, bewegliche Mehrteile-Mechanismen |

---

## Tech-Stack

- **LLM-Orchestration:** [LangGraph](https://github.com/langchain-ai/langgraph) (Stateful Multi-Agent-Graph)
- **Lokale Modelle:** [Ollama](https://ollama.com) — qwen3.5 (9b/35b), gemma4:26b, nemotron-cascade-2:30b
- **Geometrie:** [CadQuery](https://github.com/CadQuery/cadquery) (OCCT-basiert)
- **STL-Validierung:** [trimesh](https://github.com/mikedh/trimesh)
- **UI:** [Gradio](https://gradio.app) — 3D-Viewer + Live-Logs + Agent-Traces
- **RAG:** ChromaDB + sentence-transformers
- **Prompt-Optimierung:** DSPy mit 167 annotierten Pipeline-Traces

---

## Hardware

Entwickelt auf:
- NVIDIA 5060 Ti 16GB VRAM
- 64GB RAM DDR5
- AMD Ryzen 7 7800X3D

Reicht für komfortable 26b-Modelle. 35b möglich. 70b langsam aber machbar.

---

## Setup

```bash
# Dependencies (uv empfohlen, pip funktioniert auch)
uv sync

# Ollama-Modelle ziehen
ollama pull gemma4:26b
ollama pull nemotron-cascade-2:30b   # für Coder-Fallback
ollama pull qwen3.5:9b               # für schnelle Agents

# UI starten
uv run app.py
# → http://localhost:7860
```

Konfiguration in `config/config.yaml` — Model-Routing, Temperatur, RAG, Sandbox-Timeouts.

---

## Trainings-Daten + Goldens

```
data/dspy_training/
  sonnet_traces.py        — 164 annotierte Pipeline-Traces (P0–P5, Single + Multi-Part)
  reference_traces.py     — 3 hand-kuratierte Referenzbeispiele
  agent_contracts.py      — Adapter: Trace → per-Agent Trainings-Paare
  SONNET_PLAN.md          — wie weitere Traces annotiert werden
  SONNET_GOLDEN_PLAN.md   — wie aus Traces Golden-Tests werden

tests/golden/             — 13+ deterministische Regressionstests
scripts/build_goldens.py  — Goldens aus Traces neu erzeugen

train_dspy.py             — DSPy-Optimierung pro Agent
                            (inventar, position_extractor, platzierer,
                             feature_definierer, assembly)
```

---

## Projektstatus

**Phase 1 ist near-complete.** Funktionierende Multi-Part-Assemblies mit P5-Anker-Vokabular
("obere linke Ecke auf linker Kante, 10mm versetzt, 10° gedreht"). Erfolgsrate auf
einfachen bis mittleren Specs ~70%, je nach Sprachstil.

**Bekannte Lücken:**
- Zylinder-Mantel-Bohrungen (P7) → Stufe 2
- Konturen/Freiform → Stufe 3
- Vision/Bild-Input → Stufe 4
- DSPy-Optimierung läuft, finale Prompts noch in Tuning

---

## Zur Entstehung

Das Projekt ist aus zwei Gründen entstanden. Zum einen weil ich denke, dass sich mit LLMs sehr viel bauen und automatisieren lässt; besonders faszinierend finde ich, dass das mittlerweile auch komplett lokal funktioniert. Zum anderen nutze ich es als Übung: ich arbeite seit etwa zwei Monaten dran und versuche, alles so sauber und durchdacht wie möglich umzusetzen. Der Anspruch ist hoch, das fordert mich, und es macht mir Spaß.

Pull Requests, Issues und Diskussionen sind willkommen.

---

## License

MIT — siehe [LICENSE](LICENSE).
