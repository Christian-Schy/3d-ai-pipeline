# AGENTS.md

Operational guide for Codex and other coding agents working in this repo.

This file is the practical "how to work here" companion to `CLAUDE.md`.
`CLAUDE.md` explains the project vision and roadmap. This file explains the
engineering rules that keep the project modular, trainable, testable, and
commercially viable.

## Project North Star

Build a local, scalable Text-to-CAD pipeline that can turn natural language
into reliable 3D geometry:

```text
User text/image -> focused agents -> semantic blueprint
  -> deterministic resolver/checks -> deterministic/template codegen
  -> sandbox execution -> geometry/semantic validation -> STL
```

The project must become strong enough to have product potential. That means:

- reliable outputs, not impressive one-off demos
- clean architecture that can grow without collapsing
- measurable regressions through goldens and heatmaps
- local-model friendly prompts and agent tasks
- traceable decisions through ADRs, changelog, and commits

## Core Engineering Principles

### 1. Small agents beat overloaded agents

Every LLM agent must have one clear job and one clear output format.

If an agent starts doing multiple jobs, split it. Strong signs that an agent is
overloaded:

- prompt grows into a long checklist of unrelated responsibilities
- output schema mixes multiple conceptual objects
- runtime grows sharply with spec size
- failures are hard to attribute to one behavior
- DSPy training data would need conflicting examples

Preferred pattern:

```text
LLM: understand a small piece of language
Code: aggregate, calculate, validate, sort, transform
```

Examples already aligned with this principle:

- `Aktions-Splitter`: deterministic spec -> action phrases
- `Aktions-Klassifizierer`: one phrase -> type/side/hints
- `Normalizer/feature_definierer`: one classified action -> one feature
- `aktions_aggregator`: deterministic feature assembly

### 2. Determinism owns math and code whenever possible

Local models are useful for language understanding, but unreliable for exact
geometry math and code synthesis. Keep this boundary sharp:

LLMs should handle:

- natural language meaning
- ambiguity classification
- feature/part intent
- side/face wording
- semantic hints from user phrasing

Deterministic code should handle:

- coordinate math
- offsets, anchors, rotations, dimensions
- face selector mapping
- build order and parent wiring
- code templates for standard features
- geometry assertions and regression comparisons

For standard geometry, prefer templates and deterministic assemblers over
LLM-written CadQuery code. Complex geometry coders may come later, but the
standard path should stay template-first.

### 3. Keep the pipeline modular and scalable

The pipeline must allow new feature types without rewriting the whole system.
When adding capability, prefer a new narrow component over broadening an
existing one.

Good extension pattern:

```text
new vocabulary in prompt/schema
-> deterministic builder/parser support
-> resolver support
-> template/codegen support
-> validator/golden coverage
-> docs/changelog
```

Avoid:

- monolithic "planner does everything" prompts
- hidden fallback behavior without tests
- schema-breaking rewrites
- adding special cases deep inside unrelated modules

### 4. Schema stability is sacred

Blueprint data is training material. Preserve compatibility.

- Do not rename existing blueprint fields casually.
- Prefer additive optional fields.
- If a schema change is unavoidable, document it in an ADR.
- Keep semantic and resolved blueprint responsibilities separate.
- The LLM produces semantic intent; the resolver produces numeric placement.

## Current Architecture Map

Important entry points:

- `app.py` - Gradio UI only
- `api.py` - FastAPI wrapper only
- `main.py` - CLI wrapper only
- `src/graph/pipeline.py` - LangGraph topology and routing
- `src/graph/state.py` - shared `PipelineState`
- `src/graph/blueprint_schema.py` - semantic/resolved Pydantic schemas
- `src/graph/nodes/` - pipeline node functions
- `src/agents/` - LLM-facing agent classes
- `src/tools/` - deterministic tools
- `src/codegen/` - deterministic code generation/templates
- `data/prompts/` - prompt source
- `data/knowledge/` - RAG knowledge
- `tests/golden/` - full pipeline goldens
- `tests/golden/components/` - deterministic component goldens
- `docs/decisions/` - ADRs

The current interpreter path may be pass-through. Do not assume the name
"interpreter" means the LLM is active. Check `src/graph/nodes/input_nodes.py`
before changing behavior.

## Pipeline Design Rules

### Node boundaries

Each graph node should:

- read only the state fields it needs
- return only changed fields
- append an `agent_traces` entry when meaningful
- avoid direct calls into unrelated agents
- keep routing decisions outside heavy business logic

If a node grows large, split by responsibility. A node is too large when:

- it handles both extraction and aggregation
- it mutates several unrelated state groups
- tests need large fixtures to touch a small behavior
- errors cannot be attributed to one layer in heatmaps

### Routing

Routing functions must stay deterministic and explainable.

- No LLM calls in routing.
- Read limits from config, not hardcoded constants.
- Log route decisions with the reason.
- If a route intentionally ends early, preserve enough state for analysis.

Current important behavior:

- Template-mode codegen should fail fast on deterministic code/template bugs.
- `error_loop.disable_coder` can intentionally stop all Coder repair paths.
- If coder is disabled, standard/template coverage becomes even more important.

### State initialization

`PipelineState` must stay complete and consistent. Avoid duplicating large
initial-state dicts. Prefer a factory/helper when fresh and modify runs share
the same fields.

## Agent Design Rules

Every agent should have:

- a single responsibility
- a stable input contract
- a stable output contract
- dedicated prompt file(s)
- deterministic validation/parsing where possible
- isolated tests or golden cases
- trace logging suitable for future training
- a clear path to DSPy or other per-agent optimization

Do not let one agent own a whole workflow. An agent should be trainable on its
own. If training examples need unrelated labels, the agent is too broad.

### Prompt rules

Prompts should:

- define one task
- include the required output format
- avoid asking the model to calculate geometry offsets
- avoid asking the model to write standard CadQuery code
- include few-shot examples only for the agent's own task
- preserve original wording when downstream components need it

### Agent split rule

Split an agent when one of these becomes true:

- task has two different failure modes that need different tests
- prompt includes "also" or "zusaetzlich" for a second core job
- output includes two independent object types
- latency grows strongly with number of actions/features
- a future feature would add many special cases to the prompt

Do not split purely for architecture aesthetics. Split when the smaller jobs
are measurably easier to test, train, or reason about.

## Deterministic Tools And Templates

Templates are preferred for:

- boxes, plates, cylinders, spheres
- holes, counterbores, countersinks
- hole patterns
- slots/nuts
- rectangular pockets
- chamfers, fillets, shells
- standard unions/subtractions

For new standard features, implement the deterministic path first:

1. Extend normalized vocabulary if needed.
2. Extend `feature_builder`.
3. Extend semantic/resolved schema only additively.
4. Extend `blueprint_resolver`.
5. Extend `feature_classifier`.
6. Extend `codegen/templates.py` and/or `codegen/assembler.py`.
7. Add component goldens.
8. Add at least one pipeline/real-run golden variation when language is involved.

Only use LLM coders when geometry is genuinely complex or not yet templateable.
Even then, isolate complex coders by feature family later:

- contour coder
- revolve coder
- sweep/loft coder
- connector/joint coder

Do not route simple standard geometry into a general Coder if a template can
own it.

## Goldens And Regression Policy

Goldens are not optional. They are the safety net for commercial-quality
progress.

### Layer 1: Component goldens

Fast, deterministic, no LLM. Use for:

- splitter behavior
- resolver math
- assembler/codegen snippets
- coordinate validator behavior
- feature builder/aggregator behavior

Location:

```text
tests/golden/components/<scope>/
```

Every deterministic bug fix should get a component golden.

### Layer 2: Pipeline goldens

Slow, LLM-backed, used before major refactors/releases or when real runs fail.
Use text variations for the same semantic target.

Location:

```text
tests/golden/<slug>/
```

Pipeline goldens should compare the resolved blueprint with tolerances, not
unstable trace details.

### Real-run heatmaps

Use `scripts/run_real_goldens.py` to see which layer breaks across realistic
specs. Heatmaps should guide priorities.

When a heatmap shows repeated failures in one layer:

- fix the smallest deterministic layer first
- add a component golden
- rerun the relevant filtered heatmap
- then broaden to pipeline goldens

### Test-before-change rule

Before architecture pivots, DSPy training, or broad refactors:

1. Build/confirm regression baseline.
2. Run relevant component tests.
3. Run selected real goldens.
4. Only then change the architecture.

## Documentation Rules

Documentation is part of the implementation.

Use:

- `README.md` for user-facing overview
- `CLAUDE.md` for vision, roadmap, current architecture notes
- `AGENTS.md` for operational coding-agent instructions
- `CHANGELOG.md` for meaningful chronological changes
- `docs/decisions/` for architecture decisions
- source `STRUKTUR` headers in core files

When editing these core files, keep their `STRUKTUR` header current:

- `src/graph/pipeline.py`
- `src/graph/state.py`
- `src/graph/blueprint_schema.py`
- `src/codegen/assembler.py`
- `src/codegen/templates.py`

For larger changes, write or update an ADR. ADRs should explain context,
decision, rejected alternatives, and consequences. They should not be daily
bug reports.

## Commit Policy

Commit regularly after coherent, tested slices.

A good commit:

- contains one conceptual change
- includes related tests/goldens/docs
- does not mix unrelated cleanup with behavior changes
- mentions whether tests were run
- keeps generated/session noise out unless intentionally needed

Before committing:

```text
git status -sb
run relevant tests
review diff
update CHANGELOG.md when the change is meaningful
update ADR/docs when architecture changed
```

If the working tree already has unrelated user changes, do not revert them and
do not fold them into your commit.

## Code Quality Bar

Write code as if this repo will be maintained by a team.

Rules:

- prefer small modules with explicit ownership
- prefer typed structures/Pydantic models over loose dicts when contracts harden
- no magic model names or tunables in code; use config
- no broad refactors during bug fixes
- avoid hidden behavior in comments-only logic
- keep logging useful for tracing failures
- keep deterministic functions separately testable
- design for new feature types to plug in without rewiring everything

Avoid:

- giant prompts
- giant node functions
- stringly typed geometry math without tests
- silent fallbacks that mask data loss
- untested changes to resolver/assembler behavior
- LLM calls where a rule-based transform is enough

## UI/API Boundaries

`app.py`, `api.py`, and `main.py` should remain thin adapters.

They may:

- call `PipelineRunner`
- display state/results
- collect feedback
- save session metadata through existing tools

They should not:

- import individual agents directly
- run model logic
- contain geometry logic
- duplicate pipeline decisions

If UI code grows, split UI helpers rather than adding more logic to `app.py`.

## Session Data And Training

Runs and traces are valuable training material.

Keep:

- `agent_traces`
- raw/parsed agent outputs
- failure layer attribution
- good/bad run pairing when available
- task IDs or labels when the UI provides them

For training:

- train per agent, not globally
- do not train on unstable schemas
- pair failures with later successes when possible
- prefer clear reward signals from geometry assertions/goldens
- avoid mixing data from old and new agent contracts without adapters

## Current Priority Snapshot

As of the latest local inspection:

- build the regression baseline before big pivots
- keep Phase 1 schema stable
- strengthen component goldens and real-run heatmaps
- fix deterministic splitter/resolver/codegen failures before prompt tuning
- grow template coverage for standard geometry
- keep `disable_coder` implications visible when Coder repair is off

Known near-term improvement candidates:

- splitter support for `lochmuster`, `lochkreis`, `lochreihe`, `bohrungen`
- UI test drift around history restore/output arity
- shared state factory for `PipelineRunner.run()` and `modify()`
- clearer template-only/fail-fast reporting in heatmaps
- more component goldens for feature matrix B/M/N/T/E/EF/NEST

## Commercial Quality Checklist

For any new user-visible capability, ask:

- Can the user phrase it in at least 2-3 realistic ways?
- Does a component golden cover deterministic behavior?
- Does a pipeline golden or heatmap spec cover language behavior?
- Is the output blueprint stable enough for training?
- Can the failure be attributed to one layer?
- Is the feature modular enough to extend later?
- Does it avoid relying on local models for exact math?
- Is it documented in the right place?

## Open Decisions To Clarify With The User

Ask for clarification when these affect implementation:

- how often to auto-commit during long sessions
- whether commits should be made without explicit per-commit approval
- what the first commercial target is: local desktop tool, API service, SaaS,
  plugin, or internal workflow tool
- which quality gate defines "Phase 1 sealed"
- whether future specialist-fan-out should wait strictly for green baseline
  or can be prototyped behind a flag

Default until clarified:

- commit after coherent tested milestones, not after every tiny edit
- do not break existing schema fields
- do not pivot architecture before regression coverage exists
- prefer deterministic/template implementation for standard geometry
