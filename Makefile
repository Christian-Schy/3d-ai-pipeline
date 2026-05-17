# 3D AI Pipeline V2 — Developer Makefile
#
# Konventionen:
#   - Verwendet `.venv/bin/python` direkt (kein activate noetig).
#   - `make audit` ist der Senior-Profi-Code-Health-Check (siehe ADR 0008
#     Done-Review-Checkliste).
#   - Targets sind nicht-destruktiv ausser explizit anders dokumentiert.

PY := .venv/bin/python
SRC := src
TESTS := tests

.PHONY: help test test-tools test-golden audit \
        lint format types complexity duplicates dead-code size-audit \
        goldens-real goldens-real-filter \
        install-dev clean

help:
	@echo "Targets:"
	@echo "  make test            — Unit + Component-Goldens (schnell, kein LLM)"
	@echo "  make test-tools      — Nur tests/tools/ (deterministische Logik)"
	@echo "  make test-golden     — Nur tests/golden/ (Component-Goldens, schnell)"
	@echo "  make goldens-real    — Alle 18 Real-Pipeline-Goldens (dauert ~25 min, braucht Ollama)"
	@echo ""
	@echo "Code-Health (siehe ADR 0008):"
	@echo "  make audit           — Komplettes Audit (lint + types + complexity + duplicates + dead-code + size)"
	@echo "  make lint            — Ruff Lint (E/F/I/B/UP/SIM)"
	@echo "  make format          — Ruff Auto-Formatter (modifying!)"
	@echo "  make types           — Mypy (strict fuer src/tools, src/graph/blueprint_schema)"
	@echo "  make complexity      — Radon Cyclomatic-Complexity (Funktionen >C-Level flag)"
	@echo "  make duplicates      — Pylint duplicate-code (>20 Zeilen)"
	@echo "  make dead-code       — Vulture (unused funcs/imports)"
	@echo "  make size-audit      — Datei-Groesse-Report (>500 LOC flag)"
	@echo ""
	@echo "Setup:"
	@echo "  make install-dev     — Audit-Tooling installieren (ruff/mypy/radon/vulture)"

# ─── Tests ──────────────────────────────────────────────────────────────

test: test-tools test-golden

test-tools:
	$(PY) -m pytest $(TESTS)/tools -q

test-golden:
	$(PY) -m pytest $(TESTS)/golden -q

goldens-real:
	$(PY) -m scripts.run_real_goldens

goldens-real-filter:
	@if [ -z "$(F)" ]; then echo "Usage: make goldens-real-filter F=<filter>"; exit 1; fi
	$(PY) -m scripts.run_real_goldens --filter $(F)

# ─── Agent-Regression (Layer 0.5: per-Agent live LLM cases) ──────────────
# Needs Ollama. Excluded from default pytest run via pyproject.toml addopts.
# Faster than `goldens-real` (5 min/agent vs 25 min full heatmap),
# catches prompt-vs-demo drift before it ever reaches the pipeline.

agent-regression:
	$(PY) -m pytest $(TESTS)/agent_regression -m agent_regression -v

agent-regression-filter:
	@if [ -z "$(F)" ]; then echo "Usage: make agent-regression-filter F=<test-id-substring>"; exit 1; fi
	$(PY) -m pytest $(TESTS)/agent_regression -m agent_regression -v -k $(F)

# Reproduzierbare Train+Validate-Schleife pro Agent.
# - max_labeled = 16 (statt 8 default) → 12 labeled + 4 bootstrapped = 16 Demos
#   im Inferenz-Prompt (~37% statt 19% Coverage bei ~43 pocket-Demos).
#   Konservativ unter num_ctx=4096; bei Bedarf weiter hoch + num_ctx bumpen.
# - BootstrapFewShot ist intern bereits seed-fixed (random.Random(0));
#   Train/Dev-Split nutzt seed 42 (train_dspy.py).
# - Nach Training laeuft die Agent-Regression-Suite fuer den Agent automatisch.
retrain-validate:
	@if [ -z "$(A)" ]; then echo "Usage: make retrain-validate A=<agent>  (z.B. A=pocket_classifier)"; exit 1; fi
	@echo "─── retrain $(A) (max_labeled=16) ───"
	$(PY) train_dspy.py --agent $(A) --max-labeled 16
	@echo
	@echo "─── validate via agent-regression-suite ───"
	$(PY) -m pytest $(TESTS)/agent_regression -m agent_regression -v -k $$(echo $(A) | sed 's/_classifier//')

# ─── Code-Health Audit ──────────────────────────────────────────────────

audit: lint types complexity duplicates dead-code size-audit
	@echo ""
	@echo "─── Audit summary ────────────────────────────────────────────"
	@echo "Alle Checks gelaufen. Pruefe oben fuer Findings."

lint:
	@echo "─── ruff lint ────────────────────────────────────────────────"
	$(PY) -m ruff check $(SRC) || true

format:
	@echo "─── ruff format (modifying) ──────────────────────────────────"
	$(PY) -m ruff format $(SRC)

types:
	@echo "─── mypy (strict fuer src/tools + src/graph/{blueprint_schema,state}) ──"
	$(PY) -m mypy $(SRC) || true

complexity:
	@echo "─── radon CC (Funktionen mit Komplexitaet >= C) ──────────────"
	$(PY) -m radon cc -nc -s $(SRC) || true
	@echo ""
	@echo "Schwelle: A=einfach, B=ok, C=ok-aber-pruefen, D-F=Refactor-Kandidat."

duplicates:
	@echo "─── duplicates: Funktions-Signaturen/Bloecke ueber Dateien ────"
	@$(PY) -c "import subprocess,sys; \
		r=subprocess.run(['$(PY)','-m','pylint','--disable=all','--enable=duplicate-code','--min-similarity-lines=20','-r','y','$(SRC)'], capture_output=True,text=True); \
		print(r.stdout); print(r.stderr,file=sys.stderr)" || true
	@echo "(Falls pylint nicht installiert: pip install pylint, oder ignoriere — vulture+radon decken viel ab.)"

dead-code:
	@echo "─── vulture (unused funcs/imports/variables) ─────────────────"
	$(PY) -m vulture $(SRC) || true

size-audit:
	@echo "─── Datei-Groesse-Report (Schwelle 500 LOC) ──────────────────"
	@find $(SRC) -name '*.py' -not -path '*/__pycache__/*' \
		| xargs wc -l 2>/dev/null \
		| sort -rn \
		| awk 'NR==1 {next} $$1 > 500 {print "  ⚠ " $$0; over++} END {if (over==0) print "  Alle Dateien <= 500 LOC."}'

# ─── Setup ──────────────────────────────────────────────────────────────

install-dev:
	uv sync --group dev

clean:
	find . -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name '.mypy_cache' -prune -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name '.ruff_cache' -prune -exec rm -rf {} + 2>/dev/null || true
