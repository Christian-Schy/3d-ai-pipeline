# Plan fuer Sonnet: Golden-Test-Generierung aus Traces

**Ziel:** ~12-15 Regressions-Tests in `tests/golden/` aus den komplexesten Traces
in `sonnet_traces.py` ableiten. Goldens fangen Pipeline-Regressionen ab, wenn
DSPy die Prompts veraendert.

**Wichtig:** Du baust NICHT noch mehr Traces — die Coverage in
`sonnet_traces.py` (164 Traces) ist abgeschlossen. Du wandelst eine
**Auswahl der schwierigsten Traces** in Goldens um.

---

## 1. Wie ein Golden-Test aussieht

Pro Case ein Ordner `tests/golden/<slug>/` mit:

- `spec.txt` — die `trace["specification"]` (1:1 kopiert)
- `expected_blueprint.json` — das **resolved** Blueprint (face=">Z", numerische
  offsets) — KEIN semantic Blueprint
- `notes.md` — kurzer Header (Trace-ID, was getestet wird, kritische Felder)

Der Test-Harness (`tests/golden/test_golden_runs.py`) faehrt die Pipeline mit
`spec.txt` und vergleicht das Ergebnis gegen `expected_blueprint.json`.
Toleranzen: ±0.1mm Offset, ±0.01mm Params, ±0.01° Winkel.

---

## 2. Workflow pro Golden

### Schritt A — Trace auswaehlen
Aus `data/dspy_training/sonnet_traces.py::TRACES` einen Trace nehmen, der:
- **echtes Risiko-Niveau** abdeckt (P3+, P5 Anker, multi-feature, hochkant)
- **NICHT trivial** ist (P0 single-feature ist langweilig als Regressionstest)
- ein **klares assertion-Profil** hat (`expected_bbox`, `expected_feature_count`
  oder strukturelle Besonderheit wie Anker, Winkel, hochkant-Swap)

### Schritt B — Resolver auf das semantic Blueprint anwenden
```python
from src.tools.blueprint_resolver import resolve_blueprint
resolved = resolve_blueprint(trace["blueprint"])
```
Das ist deterministisch — keine LLM, keine Pipeline noetig. Output ist das
erwartete `expected_blueprint.json`.

### Schritt C — Files schreiben
```
tests/golden/<slug>/
    spec.txt                 ← trace["specification"]
    expected_blueprint.json  ← resolve_blueprint(trace["blueprint"])
    notes.md                 ← Header
```

`<slug>` = sprechender Kurzname, z.B. `wuerfel_p5_anchor_45ccw` oder
`platte_hochkant_oben_p2_bohrung`. Keine Sonderzeichen, snake_case.

### Schritt D — Validieren
```bash
.venv/bin/pytest tests/golden/ -v -k <slug>
```
Pipeline laeuft, vergleicht gegen die erzeugte `expected_blueprint.json`.
- **Test gruen** → Golden ist konsistent mit aktueller Pipeline. Speichern.
- **Test rot** → Diff zwischen Pipeline-Output und resolved-Trace anschauen:
  - Wenn Pipeline einen Bug hat: in `notes.md` als bekannten Fehler notieren,
    Golden trotzdem speichern (xfail oder als "Soll-Zustand"). Mir melden.
  - Wenn der Trace einen Annotations-Fehler hat: Trace fixen + neu rendern.

---

## 3. Auswahl-Kriterien (Welche Traces sind gute Goldens?)

**Pflicht-Sample (mindestens 1 pro Bereich):**

| Bereich | Trace-Kandidaten (beispielhaft) | Warum |
|---|---|---|
| **P5 Anker** | `t59_wuerfel_platte_p5_anchor_oben_links_umg`, `t62_wuerfel_platte_p5_winkel_45ccw_knapp` | Anker-Pfad ist die kritischste Logik in V2 |
| **P5 + Winkel** | `t62_wuerfel_platte_p5_winkel_45ccw_knapp`, `t63_quader_kleiner_wuerfel_p5_mitte_ecke_30cw_umg` | Pre-Rotation + Anker kombiniert |
| **3-Teil-Kette** | `t45_3teile_kette_umg`, `t64_3teil_kette_p3_p5_tech` | parent → kind → grosskind |
| **hochkant-Swap** | `t27_platte_hochkant_oben_p2_bohrung_ta`, `t107_platte_hochkant_4features_umg` | Y/Z-Tausch testet Resolver-Kern |
| **P4 Ueberstand** | `t44_platte_wuerfel_ueberstand_ta`, `t146_2teile_p4_ueberstand_vorne_umg` | overhang-Vokabular |
| **Multi-Feature mit Pattern** | `t68_wuerfel_5features_eckbohrungen_zentral_knapp`, `t82_platte_5features_ecken_fase_radius_nut_tech` | hole_pattern + chamfer + fillet kombiniert |
| **Zylinder-Stirn** | `t37_zylinder_3feat_ta`, `t152_zylinder_3feat_bohrung_lochkreis_tasche_ta` | hole_circle + Stirnseite |
| **Negativ/Default** | `t155_neg_bohrung_oben_rechts_ohne_abstand_p0_default_umg` | dokumentiert Default-Verhalten als Soll |

**Vermeiden:**
- T1-Single-Feature ohne Auffaelligkeiten (zu langweilig)
- Traces ohne `expected_*` assertions (kein Regressions-Anker)
- Negativ-Traces mit `[Klärungsbedarf]`-Notes (unscharfes Soll)

**Ziel:** 12-15 Goldens insgesamt, gleichmaessig verteilt ueber die obigen Bereiche.

---

## 4. Vorgehen — konkretes Skript-Skelett

```python
# scripts/build_goldens.py (du legst dieses an)
from pathlib import Path
import json, re, sys
sys.path.insert(0, "data/dspy_training")
sys.path.insert(0, ".")

from sonnet_traces import TRACES
from src.tools.blueprint_resolver import resolve_blueprint

GOLDEN_ROOT = Path("tests/golden")

# Auswahl: Liste von (trace_id, slug) Tupeln — du kuratierst diese
SELECTION = [
    ("t27_platte_hochkant_oben_p2_bohrung_ta",       "platte_hochkant_p2_bohrung"),
    ("t44_platte_wuerfel_ueberstand_ta",              "platte_wuerfel_p4_ueberstand"),
    ("t59_wuerfel_platte_p5_anchor_oben_links_umg",   "wuerfel_platte_p5_anchor"),
    ("t62_wuerfel_platte_p5_winkel_45ccw_knapp",      "wuerfel_platte_p5_45ccw"),
    # ... 8-11 weitere
]

trace_by_id = {t["id"]: t for t in TRACES}

for trace_id, slug in SELECTION:
    trace = trace_by_id.get(trace_id)
    if not trace:
        print(f"SKIP {trace_id}: nicht gefunden")
        continue
    case_dir = GOLDEN_ROOT / slug
    case_dir.mkdir(parents=True, exist_ok=True)

    (case_dir / "spec.txt").write_text(trace["specification"], encoding="utf-8")

    resolved = resolve_blueprint(trace["blueprint"])
    (case_dir / "expected_blueprint.json").write_text(
        json.dumps(resolved, ensure_ascii=False, indent=2), encoding="utf-8")

    notes = f"""# Golden Case: {slug}

**Quelle:** Trace `{trace_id}` aus sonnet_traces.py
**Difficulty:** {trace.get("metadata", {}).get("difficulty", "?")}
**Category:** {trace.get("metadata", {}).get("category", "?")}

## Was wird hier getestet?
<schreib einen Satz: was ist die kritische Eigenschaft dieses Cases>

## Bekannte Risiken
<falls bekannt: Pipeline-Bugs die diesen Test rot werden lassen koennen>
"""
    (case_dir / "notes.md").write_text(notes, encoding="utf-8")
    print(f"OK  {slug}")
```

Lauf:
```bash
.venv/bin/python scripts/build_goldens.py
.venv/bin/pytest tests/golden/ -v
```

---

## 5. Erwartete Probleme + Loesungswege

| Symptom | Vermutliche Ursache | Loesung |
|---|---|---|
| `resolve_blueprint` wirft `KeyError` | Trace hat exotisches Feature (`hole_pattern` mit unueblichem `pattern`-Wert) | Trace-Output anschauen, ggf. anderen Trace waehlen |
| Pipeline-Output != resolved-Trace bei Multi-Part | Pipeline-Bug bei Anker/Winkel | In `notes.md` festhalten, mir melden, Golden trotzdem speichern als Soll-Zustand |
| `placement.face` Diff | Trace hat side="vorne" mit alter Memory-Behauptung "wird ignoriert" | Resolver kennt vorne/hinten heute — Trace neu rendern, sollte passen |
| Diff in `params.x/y/z` bei hochkant | Resolver-Swap unterscheidet sich von Trace-Erwartung | Erwartung: hochkant → y/z tauschen, also bbox=[x, z_orig, y_orig]. Pruefen welche Konvention der Trace ansetzt |

---

## 6. Wann mich (Opus) einbeziehen

1. **Mehr als 3 Goldens scheitern** — entweder Pipeline hat Regression oder
   Resolver-Konvention im Trace stimmt nicht. Beides ist meine Entscheidung.
2. **xfail vs hard fail** — wenn ein Golden einen bekannten offenen Bug zeigt,
   muss ich entscheiden: jetzt fixen oder als xfail markieren bis Phase-1-Cleanup.
3. **Trace-Auswahl unklar** — wenn du mehr als 5 Kandidaten in einer Kategorie
   hast und nicht weisst welcher der "klar bessere" Golden ist.

**Nicht fuer mich:** slug-Naming, notes.md formulieren, Skript schreiben — du
kannst das alles selbst.

---

## 7. Checkliste pro Golden

Bevor du ihn als fertig markierst:

- [ ] Ordnername ist snake_case, sprechend
- [ ] `spec.txt` ist 1:1 aus `trace["specification"]` (kein Bearbeiten)
- [ ] `expected_blueprint.json` ist via `resolve_blueprint` erzeugt, nicht von Hand
- [ ] `notes.md` hat Trace-ID + 1 Satz Test-Zweck
- [ ] `.venv/bin/pytest tests/golden/ -v -k <slug>` lokal ausgefuehrt
- [ ] Bei rotem Test: Diff dokumentiert in `notes.md`

---

## 8. Ziel-Zahl + Abschluss

- **Min. 12, Max. 15** Goldens — quality > quantity
- Alle Bereiche aus Tabelle in Sektion 3 mindestens 1x abgedeckt
- Mind. 80% der Goldens gruen (Pipeline-Regression-Indikator akzeptabel)
- Wenn fertig: einmal `pytest tests/golden/ -v` laufen lassen, Output an mich
  zurueckmelden — ich review die Auswahl und entscheide ob wir Phase-1
  freigeben oder noch nachbessern.
