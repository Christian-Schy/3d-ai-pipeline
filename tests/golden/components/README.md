# Component-Goldens

Schnelle deterministische Regressions-Tests fuer einzelne Pipeline-Stufen.
Im Gegensatz zu den Pipeline-Goldens (`tests/golden/<slug>/`) laufen diese
**ohne LLM** in Millisekunden.

## Was wird getestet?

Pro Feature ein Ordner mit Sub-Tests fuer einzelne deterministische
Stufen (resolver, splitter, assembler):

```
tests/golden/components/
  <FEATURE-ID>_<beschreibung>/
    resolver/                       ← Resolver-Mathe (semantic → resolved)
      input_semantic.json
      expected_resolved.json
    splitter/                       ← aktions_splitter (spec → phrases)
      spec.txt
      expected_phrases.json
    assembler/                      ← (optional) cadquery-Snippet
      input_resolved.json
      expected_code_lines.txt
```

Jede Sub-Stufe ist optional. Pro Feature reicht oft `resolver/` allein,
weil dort die meisten Bugs sitzen.

## Pattern fuer Feature-IDs

Aus ADR 0005 (Feature-Matrix):
- `B1` bis `B4` — Bohrungen
- `M1` bis `M3` — Lochmuster
- `N1`, `N2` — Nuten
- `T1` bis `T4` — Taschen
- `E1` bis `E5` — Extrusionen
- `EF1` bis `EF3` — Features auf Extrusionen
- `NEST1`, `NEST2` — verschachtelte Features

## Tests laufen lassen

```bash
# Alle Component-Goldens
pytest tests/golden/components/

# Nur eine Feature-Familie
pytest tests/golden/components/ -k "B1"

# Nur eine Stufe
pytest tests/golden/components/ -k "resolver"
```

## Neuen Component-Golden anlegen

Beispiel: B3 (Bohrung Mischung Versatz + Abstand) als Resolver-Golden.

1. Ordner anlegen:
   ```
   tests/golden/components/B3_bohrung_mix_axes/resolver/
   ```

2. **input_semantic.json** anlegen — das semantic Blueprint, das ein
   normaler Pipeline-Lauf produzieren WUERDE. Beispiel-Form siehe
   `B1_bohrung_versatz_mitte/resolver/input_semantic.json`.

3. **expected_resolved.json** anlegen — was der `blueprint_resolver`
   daraus erzeugen muss. Berechnung der `placement.offset_x/y` per Hand
   nachvollziehen (siehe Resolver-Doku im Code).

4. Test laeuft automatisch via `_test_resolver_components.py` —
   Discovery sucht alle `<scope>/resolver/` Ordner.

## Wenn ein Test rot wird

1. Schau dir `pytest -v` Output an — welche Felder weichen ab?
2. Echte Regression in Resolver/Splitter? → Bug fixen, Test wieder gruen.
3. Geaenderte Konvention (bewusst)? → `expected_*.json` updaten und
   Aenderung in CHANGELOG dokumentieren.

## Beziehung zu Pipeline-Goldens

| Aspekt | Component-Golden | Pipeline-Golden (`tests/golden/<slug>/`) |
|--------|------------------|----------------------------------|
| LLM | Nein | Ja |
| Speed | <1s | 30-300s |
| Deckung | Deterministische Tools | End-to-End inkl. Sprachverstaendnis |
| Wann laufen | Auf jedem Commit | Vor Releases / Architektur-Aenderungen |
| Skalierung | Beliebig viele | Begrenzt durch LLM-Kosten |
