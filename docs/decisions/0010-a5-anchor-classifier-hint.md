# ADR 0010 — A5-Anker als Klassifizierer-Hint (anker_ecke)

- **Datum:** 2026-05-16
- **Status:** ZURUECKGEZOGEN 2026-05-17 — siehe Nachtrag unten
- **Ersetzt durch:** keine eigene ADR; A5 ist konventionell A1 bzw. A2

## Nachtrag (2026-05-17) — warum zurueckgezogen

Der Heatmap-Lauf nach Adoption zeigte: das `anker_ecke`-Schema war
ueberfluessig und schaedlich. A5 ("in der Ecke + Versatz") ist **kein
eigener Fall**:

- Eine Ecke nennt zwei Kanten. Der Versatz bemasst — nach der
  Default-Konvention 22 (A1, edge-to-CENTER) — das Tasche-ZENTRUM von
  genau diesen zwei Kanten. "In der oberen rechten Ecke, 22 nach links,
  18 nach unten" ist schlicht `abstand_rechts:22, abstand_oben:18` = A1.
- Nur wenn die Phrase die **Taschen-Kante** explizit nennt, gilt A2
  (`kante_*`). Das deckt T06/T02 ab, nicht T08.

Das `anker_ecke`-Schema hat zudem aktiv Schaden angerichtet: der Prompt
griff auch bei "obere rechte Ecke **der Tasche**" (T_kombo t10,
child-corner-to-edge) und verbog die Anker-Semantik bestehender
Goldens. `position.anchor` mit `child_point=corner` aenderte das
Verhalten frueherer T_kombo-Faelle.

Konsequenz: `anker_ecke` (Klassifizierer-Hint, Prompt, `_clean_hints`-
Zweig, `_apply_phrase_anchor`-Schema-Pfad, `_RECT_ANCHOR_TYPES`) wurde
vollstaendig revertiert. T08 ist ein A1-Fall (`abstand_*`). Analog M09
(Kreis-Pattern A5 = A1). **Regel: A5 = A1 (Default) bzw. A2 (bei
explizit genannter Feature-Kante) — nie ein eigenes Schema.**

Der historische Inhalt der ADR bleibt unten als Kontext stehen.

---

## (Historisch — verworfener Ansatz)
- **Vorgaenger-ADRs:** 0006 (Klassifizierer-Split), 0008 (Capability-Matrix)
- **Verwandt:** Memory `feedback_richer_schema_not_rules`,
  `feedback_determinism_scope`, `feedback_no_silent_deferrals`,
  `project_next_phase_plan` (Phase B), Golden `T_coverage` T08

## Problem

T08 (Konvention 22, A5 Pocket-Anker) war deferred: "in der oberen
rechten Ecke, 8mm nach links und 6mm nach unten versetzt" — eine Tasche
sitzt in einer Bauteil-Face-Ecke mit Inset. Der `pocket_classifier`
hatte kein Feld dafuer.

Der Resolver kann A5 laengst (`position.anchor` mit
`{child_point, parent_point, offset}` → `_apply_anchor`). Es gab nur
keinen Pfad von der deutschen Phrase dorthin: der bestehende
`_infer_phrase_anchor` ist ein deutscher Regex und matchte die
flektierte Form ("oberen rechten Ecke", Dativ) nicht.

Der erste Reflex war, den Regex um Inflektions-Varianten zu erweitern.
Das ist Textverstaendnis im Code — genau das, was
`feedback_determinism_scope` / `feedback_richer_schema_not_rules`
ausschliessen.

## Entscheidung

A5-Anker schema-getrieben loesen, nicht per Regex:

1. **Additiver Klassifizierer-Hint** `anker_ecke` im `pocket_classifier`
   — geschlossenes 4-Wert-Vokabular: `top_right` | `top_left` |
   `bottom_right` | `bottom_left`.
2. **Der LLM macht das Textverstaendnis.** Der Prompt lehrt die
   Zuordnung; alle deutschen Wording-Varianten (Dativ/Nominativ/
   Kurzform/Synonyme) werden ueber Demos abgedeckt — nicht ueber
   Code-Regex.
3. **Der Code macht nur Token→Geometrie-Mapping.** `_apply_phrase_anchor`
   liest `anker_ecke` aus den Parametern und baut
   `position.anchor = {child_point: anker_ecke, parent_point: anker_ecke,
   offset: {<dir>: versatz_<dir>}}`. Geschlossenes Vokabular → reines
   deterministisches Mapping, kein Sprachverstaendnis.
4. **`_infer_phrase_anchor` bleibt unveraendert** als Legacy-Fallback
   fuer Wordings ohne Klassifizierer-Hint. Wird nicht erweitert.

`child_point = parent_point = anker_ecke`: die CAD-Konvention fuer
"in der Ecke" ist Feature-Ecke an Bauteil-Face-Ecke. Fuer point-like
Features (Bohrung-/Pattern-Center, child_w/h = 0) faellt das geometrisch
auf den Center-Anker zurueck — derselbe Hint ist also auch fuer M09
(`circular_classifier`) wiederverwendbar.

## Konsequenzen

- T08 ist aktiv; T_coverage 12/12 vollstaendig.
- `anker_ecke` ist additiv (Schema-Stabilitaet gewahrt) und der erste
  String-Hint neben `richtung`. `_clean_hints` validiert ihn gegen das
  geschlossene Vokabular; OOV-Tokens werden verworfen.
- Wiederverwendbar fuer M09 (Pattern-Kreis A5) — gleicher Hint im
  `circular_classifier`.
- Kein neuer Regex, keine Inflektions-Pflege im Code.

## Verworfen

- **`_infer_phrase_anchor`-Regex um Inflektionen erweitern** — deutsche
  Grammatik im Code, gegen `feedback_determinism_scope`. Jede neue
  Wording-Variante haette einen Code-Edit erzwungen statt einer Demo.
- **Eigenes `anchor`-Objekt im Klassifizierer-Output** statt eines
  flachen Hints — groesserer Schema-Eingriff; der flache `anker_ecke`
  + bestehende `versatz_*` reichen.
