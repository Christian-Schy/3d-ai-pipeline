# ADR 0011 — Slot Anfangs-/Endpunkt-Modell (anfang_*/ende_*)

- **Datum:** 2026-05-16
- **Status:** accepted
- **Vorgaenger-ADRs:** 0006 (Klassifizierer-Split), 0010 (A5-Anker-Hint)
- **Verwandt:** Memory `feedback_determinism_scope`,
  `feedback_richer_schema_not_rules`, `project_next_phase_plan` (Phase B),
  Golden `N_coverage` N04, Konvention 21

## Problem

N04 (Konvention 21) war deferred: "Nut 5x3, Anfangspunkt 20mm von linker
Kante, Endpunkt 80mm von linker Kante, von vorderer Kante 30mm" — die Nut
ist ueber zwei Endpunkte statt ueber `laenge` beschrieben. Der
`slot_classifier` hatte keine Endpunkt-Keys.

Die naheliegende Abkuerzung waere, den LLM `laenge = 80 - 20 = 60`
rechnen zu lassen. Das ist Arithmetik im LLM — gegen
`feedback_determinism_scope` (Rechnen ist deterministisch).

## Entscheidung

Analog ADR 0010 schema-getrieben, mit klarer Schicht-Trennung:

1. **Additive Klassifizierer-Hints** `anfang_<kante>` / `ende_<kante>`
   im `slot_classifier` (12 Zahlen-Keys fuer die 6 Kanten).
2. **Der LLM extrahiert** die zwei Endpunkt-Distanzen + die Bezugskante
   und leitet `richtung` aus den Punkten ab (zwei Punkte an derselben
   links/rechts-Kante → X, an vorderer/hinterer → Y). Das ist
   Textverstaendnis.
3. **Der Code rechnet.** `feature_builder._resolve_slot_endpoints`
   bildet `laenge = |ende - anfang|` und
   `abstand_<kante> = (anfang + ende) / 2` — der Mittelpunkt der beiden
   Endpunkte ist die Slot-Mittellinie (aktuelle Slot-Konvention 21).
   Reine Arithmetik, kein Sprachverstaendnis.

Die Endpunkt-Aufloesung sitzt im `feature_builder` (vor `_build_params`),
nicht im Resolver: same-edge-Endpunkte (`anfang_links` + `ende_links`)
brauchen keine Parent-Dimensionen, nur die zwei Zahlen.

## Konsequenzen

- N04 ist aktiv; N_coverage 12/12 vollstaendig.
- Schema additiv (Schema-Stabilitaet gewahrt).
- Konsistent mit ADR 0010: LLM = Textverstaendnis, Code = Arithmetik /
  geschlossenes Vokabular.

## Nachtrag 2026-05-18

Konvention 21 wurde von der frueheren per-Achse-Regel auf einheitlichen
Mittellinien-Bezug umgestellt. Die ADR-Entscheidung bleibt gleich
(Endpunkte extrahieren, Code rechnet), aber die abgeleitete
`abstand_*`-Semantik ist jetzt der Mittelwert statt `min(...)`.

## Grenzen / offen

- **Gegenueberliegende Endpunkte** ("Anfangspunkt 20 von links, Endpunkt
  30 von rechts") brauchen die Parent-Breite (`laenge = face_w - 20 -
  30`) und damit eine Aufloesung im Resolver, nicht im feature_builder.
  Nicht Teil der Konvention-21-N-Faelle — kein deferred Golden, sondern
  eine spaetere Wording-Erweiterung wenn ein Golden sie braucht.

## Verworfen

- **LLM rechnet die Laenge** — Arithmetik im Textverstaendnis-Layer,
  gegen `feedback_determinism_scope`.
