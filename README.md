# 3D AI Pipeline

Local Text-to-CAD pipeline for turning natural language into reproducible CAD
geometry. The project combines small, focused LLM agents for language
understanding with deterministic blueprint resolution, template-based CadQuery
generation, sandboxed execution, and regression tests.

The goal is not a one-shot demo generator. The goal is a local pipeline that can
be measured, debugged, trained per component, and gradually expanded into a
reliable CAD automation tool.

## What It Does

Describe a part or small assembly in plain language:

```text
Platte 100x80x20mm. Oben eine zentrale Bohrung Ø10 durchgehend.
Rechts daneben ein Würfel 50mm, obere linke Ecke auf linker Kante,
10mm von oben, 10° gegen den Uhrzeigersinn gedreht.
```

The pipeline converts the request into a semantic blueprint, resolves numeric
placement deterministically, generates CadQuery code, executes it in a sandbox,
validates the result, and writes an STL.

## Design

The central boundary is simple:

- LLMs interpret language, classify intent, and produce structured semantic data.
- Deterministic code owns dimensions, offsets, face mapping, build order,
  template generation, and validation.

That keeps the standard path local-model friendly and makes failures easier to
attribute. A model may decide that a phrase describes a hole on the top face; it
does not calculate the final CAD offset by itself.

```text
Text or image
  -> focused agents
  -> semantic blueprint
  -> deterministic resolver and checks
  -> template/code generation
  -> sandboxed CadQuery execution
  -> geometry and semantic validation
  -> STL
```

## Current Architecture

```text
input
  -> interpreter / punctuation / visioner
  -> inventar
  -> aktions_splitter
  -> aktions_klassifizierer
  -> text_splitter
  -> position_extractor
  -> feature_definierer
  -> aktions_aggregator
  -> platzierer
  -> assembly
  -> pocket_child_placer
  -> blueprint_resolver
  -> coordinate_validator
  -> plan_validator
  -> function_decomposer
  -> coder / deterministic templates
  -> executor
  -> validator
```

Important architectural choices:

- Planning nodes are split by responsibility instead of living in one large
  graph module.
- Standard geometry is handled through deterministic builders, resolvers, and
  templates wherever possible.
- The semantic blueprint and resolved blueprint are kept separate so language
  outputs stay useful as training data.
- Component goldens and real-run heatmaps are used to catch regressions before
  prompt or architecture changes spread across the pipeline.

## Capabilities

Current Phase 1 focus:

- Boxes, plates, cylinders, holes, pockets, slots, grooves, chamfers, fillets,
  shells, and simple additive/subtractive feature combinations.
- Multi-part assemblies with parent/child placement, face vocabulary, anchors,
  edge distances, offsets, and rotations.
- Nested features such as holes inside pockets.
- Local Ollama model routing per agent.
- Gradio UI, FastAPI wrapper, CLI entry point, run logging, agent traces, and
  STL output.

Known limits:

- Complex freeform CAD operations such as lofts, sweeps, splines, and revolved
  profiles are future work.
- Vision input exists as a pipeline path, but text-first generation remains the
  primary target.
- Some realistic CAD phrasing still needs more golden coverage and targeted
  DSPy/prompt tuning.

## Tech Stack

- Orchestration: LangGraph
- Local models: Ollama
- CAD: CadQuery / OCCT
- Validation: trimesh plus deterministic blueprint checks
- UI: Gradio
- API: FastAPI
- RAG: ChromaDB and sentence-transformers
- Training and prompt optimization: DSPy
- Tests: pytest, component goldens, real-run golden scripts

## Setup

Python 3.12 is required. `uv` is recommended because the lockfile is included.

```bash
uv sync
```

Install the configured Ollama models, or adjust `config/config.yaml` to match
the models available on your machine.

```bash
ollama pull gemma4:26b
ollama pull qwen3.5:9b
ollama pull nemotron-cascade-2:30b
```

Start the UI:

```bash
uv run python app.py
```

Open:

```text
http://localhost:7860
```

Run the CLI:

```bash
uv run python main.py "Platte 100x80x20mm mit zentraler Bohrung Ø10"
```

Start the API:

```bash
uv run uvicorn api:app --host 0.0.0.0 --port 8000
```

Configuration lives in `config/config.yaml`, including model routing, Ollama
options, RAG paths, sandbox timeouts, UI settings, and error-loop behavior.

## Testing

Run the default test suite:

```bash
uv run pytest -q
```

Run deterministic component goldens:

```bash
uv run pytest -q tests/golden/components
```

Run selected real-run goldens when Ollama is available:

```bash
uv run python -m scripts.run_real_goldens --filter B_kombo --first-only --no-persist
```

The default pytest configuration skips tests marked `slow`.

## Repository Map

```text
app.py                         Gradio UI
api.py                         FastAPI wrapper
main.py                        CLI wrapper
config/config.yaml             central model and runtime configuration
src/graph/pipeline.py          LangGraph topology and routing
src/graph/state.py             shared pipeline state
src/graph/blueprint_schema.py  semantic and resolved blueprint schemas
src/graph/nodes/               graph node implementations
src/agents/                    LLM-facing agent classes
src/tools/                     deterministic parsing, resolving, validation
src/codegen/                   CadQuery templates and assembler
data/prompts/                  prompt sources
data/knowledge/                RAG knowledge
tests/golden/                  full pipeline and component goldens
docs/decisions/                architecture decision records
```

## Development Direction

Near-term engineering priorities:

- keep the Phase 1 blueprint schema stable
- strengthen deterministic splitter, resolver, validator, and template coverage
- expand component goldens and real-run heatmaps
- improve local-model reliability through per-agent prompts and DSPy examples
- avoid routing standard geometry through general-purpose code generation when a
  deterministic template can own it

Longer-term work includes connection features, richer assemblies, complex CAD
operations, stronger geometry assertions, and better image-to-blueprint support.

## License

MIT. See [LICENSE](LICENSE).
