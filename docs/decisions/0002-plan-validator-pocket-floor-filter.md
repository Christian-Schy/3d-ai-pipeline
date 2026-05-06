# ADR 0002 — plan_validator filtert pocket_floor depth-Errors deterministisch

- **Datum:** 2026-05-05
- **Status:** superseded (2026-05-06)
- **Commit:** `ca15719`
- **Aufgehoben durch:** Bug-2-Fix in der ADR-0003-Stufe-5c-Iteration.
  Die Loesung "Regex-Filter auf LLM-Output" hat die Format-Drift des
  LLM nicht abgefangen (siehe Run 3db7d152: 7 false positives statt 1).
  Stattdessen wurde **Check 6** komplett aus dem plan_validator-Prompt
  entfernt — `coordinate_validator.run_coordinate_check` Check 2
  (depth_vs_material) macht den deterministischen Vergleich seit jeher
  korrekt und behandelt feature-in-feature (depth = pocket+material)
  bereits ueber `_resolve_root_parent_id`. Damit ist der Filter samt
  Regex obsolet und entfaellt.

## Kontext

Der `plan_validator` ist ein LLM-basierter Pre-Coder-Validator. Er
arbeitet eine Checkliste von 14 Pruefungen ab. Eine davon, **Check 6**,
prueft fuer subtractive Features (Bohrung, Nut, Tasche): "Ist das
Feature kleiner als sein Parent?".

Bei Bohrungen, die durch den Boden einer Tasche ins Material gehen,
liefert der Resolver bewusst eine erweiterte Tiefe:

```
depth_local        = 10  (User-Wert: "Bohrung 10mm tief in der Tasche")
parent_depth       = 10  (Tasche selbst 10mm tief)
depth (resolved)   = 20  (Bohrung muss durch Pocket-Boden + 10mm Material)
depth_reference_applied = "pocket_floor"
```

Der LLM-Validator versteht das nicht und meldet bei jeder solchen
Bohrung:

```
[ERROR] Feature 'hole_in_X' (depth 20) is larger than parent 'X' (depth 10)
```

Das routet die Pipeline zurueck zum feature_definierer, der die
Aktionsliste nicht aendern kann — der Re-Run produziert byte-identisch
dasselbe Ergebnis und lief in Run 965da548 weitere ~17s. Erst nach
Erschoepfung der Retries laeuft die Pipeline durch zum Executor, der
das Modell korrekt baut.

CLAUDE.md vermerkt das als bekannte LLM-Validator-Limitation:

> Validator (LLM): Sagt oft "valid" bei offensichtlichen Fehlern bzw.
> "invalid" bei korrekten Outputs. Wird durch deterministische
> Geometry Assertions ersetzt (Phase B).

## Entscheidung

Zwei sich ergaenzende Schritte:

1. **Prompt-Ausnahme** in `data/prompts/prompt_plan_validator.py` —
   eine Zeile ergaenzt, die dem LLM sagt, dass `depth_reference_applied
   = "pocket_floor"` eine zulaessige Ausnahme zu Check 6 ist. Das ist
   best-effort: lokale LLMs ignorieren Ausnahme-Klauseln oft.

2. **Deterministischer Post-Filter** im Agent
   (`src/agents/plan_validator.py`). Nach dem LLM-Call laeuft die
   Funktion `_drop_pocket_floor_depth_errors`:
   - Matcht Check-6-Errors per Regex auf Feature-ID
   - Lookup im Blueprint, ob das Feature
     `params.depth_reference_applied == "pocket_floor"` traegt
   - Wenn ja: Error wird verworfen
   - Wenn nach dem Filter keine ERROR-Severity-Eintraege mehr uebrig:
     `valid` wird auf True geflippt

## Verworfene Alternativen

1. **Check 6 ganz aus dem LLM-Prompt entfernen** und in einen
   deterministischen Pre-Validator umziehen. Korrekt im Sinne von
   "Rechnen = deterministisch", aber zu groesserer Refactor — mehrere
   andere Faelle (Slot-Tiefe, Tasche-Tiefe, Nut-Tiefe ohne pocket_floor)
   sind weiterhin LLM-Sache und im selben Prompt verflochten. Spaeterer
   Phase-B-Schritt.

2. **Pre-Filter:** Blueprint vor dem LLM-Call scrubben (z.B. depth
   durch depth_local ersetzen fuer pocket_floor-Features). Verworfen
   weil invasiv und der LLM dann nicht mehr das echte Blueprint sieht
   (riskiert, dass er andere Felder darauf bezieht).

3. **Prompt-Patch alleine:** nur die Ausnahme im Prompt, kein Post-
   Filter. Verworfen weil empirisch der LLM die Ausnahme oft ignoriert.
   Das Sicherheitsnetz aus Code ist robuster.

## Konsequenzen

**Positiv:**

- pocket-mit-Bohrung Specs laufen ohne Retry durch — ~17s Latenz pro
  betroffenem Run gespart.
- Echte Check-6-Verletzungen (z.B. eine `face`-referenzierte Bohrung,
  die wirklich ueber den Parent hinaus geht) bleiben erhalten — der
  Filter prueft `depth_reference_applied` strikt.
- Validator-Output behaelt Aussagekraft: er meldet jetzt nur noch
  echte Probleme, nicht Standard-False-Positives.

**Negativ / zu beachten:**

- Wenn der Resolver `depth_reference_applied` mal nicht setzt, fallen
  echte Bohrungen wieder in den Filter — wir verlieren die
  Schutzfunktion. Akzeptabel weil das Setzen des Felds bereits durch
  Tests in `tests/tools/` und durch
  `tests/agents/test_pocket_child_placer.py` abgedeckt ist.
- Der LLM-Validator bleibt grundsaetzlich unzuverlaessig fuer
  Rechenaufgaben. Phase B (deterministische Geometry Assertions)
  bleibt das Ziel — diese ADR ist Brueckentechnik.

## Tests

`tests/agents/test_plan_validator_pocket_floor.py` deckt ab:
- Filter dropt Check-6-Errors fuer pocket_floor-Bohrungen
- Filter behaelt Check-6-Errors fuer face-referenzierte Bohrungen
- Filter laesst andere Checks (1, 2, 8) unangetastet
- Verdict-Flip: nach Filter ohne ERROR-Severity wird is_valid=True
- Edge-Cases: doppelte Anfuehrungszeichen in Messages, fehlende
  Feature-ID, fehlendes depth_reference_applied-Feld
