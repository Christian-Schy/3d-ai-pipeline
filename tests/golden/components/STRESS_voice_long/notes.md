# STRESS_voice_long

Splitter-Component-STRESS-Golden: lange Voice-style Spec mit 15 Aktionen
auf 2 Teilen (Wuerfel + Platte), komma-getrennt, Umgangssprache
("mach mir", "oben drauf kommt", "noch eine", "in dieser tasche"), mit
allen Cap-1.0-Feature-Typen plus einem NEST-Hint und einem
Lochkreis-Startwinkel.

## Was hier wirklich getestet wird

- `split_spec_into_aktionen(spec, teile)` muss aus dem komma-getrennten
  Run-on-Satz korrekt 15 Aktions-Phrasen ableiten.
- Die Teil-Deklarationen (`mach mir einen würfel ...`,
  `oben drauf kommt eine platte ...`) werden gedroppt — sie sind nicht
  Aktionen, sondern Inventar-Material.
- Multi-Part-Routing: Phrasen ohne Teil-Cue gehen an `wuerfel` (Aktionen
  0-11); Phrasen mit `auf der platte ...` werden korrekt `platte`
  zugewiesen (Aktionen 12-14).
- `parent_phrase_idx` ist hier durchgaengig `null` — der Splitter
  encodet keine Feature-Hierarchie. NEST (`in dieser tasche zentral eine
  5mm bohrung`) wird als Aktion 4 auf wuerfel emittiert; der spaeter
  laufende `pocket_child_placer` setzt die Tasche → Bohrung-Verbindung
  ueber die "in der tasche"-Cue im Text.

## Bewusst NICHT abgedeckt

- LLM-Agenten downstream (Klassifizierer, position_extractor,
  feature_definierer) — die haben L0.5-Suiten in `tests/agent_regression/`.
- Punctuation-Setzung (rohes Voice ohne Kommas) — diese Spec hat
  bereits Kommas, weil der Splitter rule-based an Kommas teilt. Der
  Punctuation-Pre-Step (LLM) ist ein eigener Pipeline-Schritt vor dem
  Splitter; er liesse sich separat per Real-Run testen, GPU-Zeit.
- Voll-Pipeline-Real-Run gegen Ollama (Resolver + Codegen + Validator)
  — das ist Cov-5+ Material.

## Befund beim Bauen

Splitter handhabt 15 Aktionen + 2 Teile auf einen Wurf korrekt. Kein
besonderer Stress-Befund — der rule-based Splitter ist deterministisch
und skaliert linear mit der Komma-Anzahl. Der wahre voice-Stress liegt
**vor** dem Splitter im Punctuation-Agent (Komma-Setzung bei rohem
Voice-Text), das ist ein separater LLM-Test.
