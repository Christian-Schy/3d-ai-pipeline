# Golden Test Cases

Regressions-Tests: jeder Ordner hier = ein eingefrorener Pipeline-Run.

## Wie funktioniert es?

```
tests/golden/
  01_wuerfel_6_features/
    spec.txt                ← roher Input-Text
    expected_blueprint.json ← resolved Blueprint (Referenz)
    notes.md                ← was wird hier getestet, warum ist das ein Edge-Case
```

`pytest tests/golden/` fährt die Pipeline für jeden Case und vergleicht
das resolved Blueprint gegen expected_blueprint.json.

**Was verglichen wird:**
- `placement.face` — exakt (`>Z`, `<X` etc.)
- `placement.alignment` — exakt (`centered`, `flush_right_top` etc.)
- `placement.offset_x/y` — ±0.1 mm Toleranz
- `placement.angle_deg` — ±0.01 Grad Toleranz
- `params` (x/y/z/Maße) — ±0.01 mm Toleranz
- Feature-Typen und -Anzahl — exakt

**Was ignoriert wird:** `notes`, `description`, Timestamps, `stl_path`, `run_id`

## Neuen Golden Case anlegen

### Option A — CLI (empfohlen)
```bash
python -m scripts.save_golden <run_id> --slug "01_wuerfel_6_features" --note "Würfel mit vielen Features auf unterschiedlichen Seiten"
```

### Option B — UI
Im Ergebnis-Tab auf "Als Golden speichern" klicken, Slug eingeben.

### Option C — Manuell
```
mkdir tests/golden/mein_case/
echo "dein spec text" > tests/golden/mein_case/spec.txt
# expected_blueprint.json aus einem guten Run kopieren (runs.jsonl)
```

## Tests ausführen

```bash
# Schnelle Tests inkl. Component-Goldens, ohne LLM-Pipeline-Goldens
uv run pytest -q

# Nur echte Pipeline-Goldens mit Ollama/LLMs
uv run pytest -q -m slow tests/golden/test_golden_runs.py

# Bestimmte Pipeline-Goldens
uv run pytest -q -m slow tests/golden/test_golden_runs.py -k "wuerfel"

# Schnelle Unit-Tests ohne irgendeinen Golden-Ordner
uv run pytest -q --ignore=tests/golden
```

`pyproject.toml` setzt standardmaessig `-m not slow`, damit ein
versehentliches `pytest` keine echten Modell-Runs startet. Pipeline-Goldens
muessen deshalb explizit mit `-m slow` gestartet werden.

## Capability Ladder fuer komplexe Standard-Teile

Die Baseline waechst bewusst stufenweise. Komplexe Kombi-Teile bleiben als
Zielbild sichtbar, werden aber erst als harte Gates genutzt, wenn die
darunterliegenden Levels stabil sind.

| Level | Ziel | Harte Gate-Quelle |
|-------|------|-------------------|
| 1 | Einzel-Features: Bohrung, Tasche, Nut, einfache Extrusion | Component-Goldens + erste Pipeline-Variante |
| 2 | Mehrere Features auf einem Grundkoerper | Heatmap `--filter B,N,T` |
| 3 | Nested Features, besonders Bohrungen in Taschen | Heatmap `--filter NEST` |
| 4 | Extrusionen mit Features | Heatmap `--filter E,EF` |
| 5 | grosse Kombi-Teile mit vielen Feature-Varianten | Stress-/Zielbild, erst spaeter blockierend |

Echte User-Formulierungen aus `data/sessions/runs.jsonl` sollen bevorzugt
als `pipeline/specs.txt`-Varianten aufgenommen werden.

## Wenn ein Test rot wird

1. Schau dir den Diff an — welche Felder weichen ab?
2. Ist es LLM-Varianz (kleine Abweichung beim gleichen Spec)? → Toleranz in notes.md dokumentieren
3. Ist es eine echte Regression (Face falsch, Offset falsch)? → Bug finden und fixen, DANN Test wieder grün
4. War das alte expected_blueprint falsch (Fehler im alten Run)? → expected_blueprint.json updaten und in notes.md dokumentieren warum

## Coverage-Ziel

| # | Beschreibung | Slug |
|---|---|---|
| 1 | 1 Teil mit vielen Features (Bohrungen, Nuten, versch. Positionen) | |
| 2 | Mehrere Extrusionen (3+ Teile) | |
| 3 | Extrusionen + Features kombiniert | |
| 4 | Anchor-Platzierung | |
| 5 | Rotation (angle_deg) | |
| 6 | Edge-Case: face-Wort im Kontext eines anderen Teils | |
