# ADR 0001 — pocket_child_placer macht nur Containment-Mapping, nicht Position-Parsing

- **Datum:** 2026-05-05
- **Status:** accepted
- **Commit:** `9393767`

## Kontext

Der `pocket_child_placer`-Agent laeuft nach Assembly und vor dem
blueprint_resolver. Seine Aufgabe ist eigentlich, Bohrungen, die in
Taschen sitzen sollen, dem richtigen Pocket-Parent zuzuordnen, damit
der Resolver sie im Pocket-Lokalframe platziert.

Bis 2026-05-05 hat der Agent jedoch **zwei** Aufgaben gleichzeitig
gehabt: er hat (a) das Containment erkannt ("welche Bohrung gehoert
in welche Tasche?") und gleichzeitig (b) die Position der Bohrung
**erneut** aus dem User-Text geparst. Das LLM hat den Position-Teil
falsch geparst — beobachtet in Run 965da548:

- User sagte: "in der Tasche um 15mm nach rechts versetzt und um 10mm
  nach oben versetzt eine 10mm bohrung"
- feature_definierer hatte das korrekt extrahiert:
  `center_offset: {top: 10, right: 15}`
- pocket_child_placer hat es neu geparst und nur `right: 15`
  uebernommen — die "10mm nach oben" ging verloren

Das resolved Blueprint zeigte daraufhin Hole 1 bei `(74.7721, 72.6047)`
statt der erwarteten `(73.0356, 82.4528)` — das Delta entspricht exakt
nur dem 15mm-Versatz rotiert um den Pocket-Winkel, der 10mm-Anteil
fehlte komplett.

Latenz dieses LLM-Calls: ca. 21s pro Run, weil das Output-Schema
verschachtelt war (volle Position-Struktur).

## Entscheidung

**Aufgaben-Trennung:** der `pocket_child_placer` macht ab jetzt **nur
noch Containment-Mapping**. Der LLM-Output ist eine schmale Liste:

```json
{ "assignments": [{"hole_feature_id": "...", "pocket_id": "..."}] }
```

Position, Params, Type — alles wird **deterministisch vom Upstream-
Feature** uebernommen, das der `feature_definierer` bereits korrekt
extrahiert hat. Der Agent clont das Feature, aendert nur `parent`
auf die Pocket-ID und benennt die ID auf `hole_in_<pocket>_<idx>` um.
`depth_reference` wird deterministisch auf `"pocket_floor"` gesetzt.

## Verworfene Alternativen

1. **Prompt-Patch im pocket_child_placer:** dem LLM via Prompt
   beibringen, "10mm nach oben" nicht zu vergessen. Wurde verworfen,
   weil der feature_definierer dieselbe Aufgabe schon korrekt
   erledigt — es ist Doppelarbeit, die nur Risiken bringt.

2. **Cross-Check zwischen beiden Agents:** beide parsen Position,
   bei Abweichung Fehler. Verworfen, weil bei Disagreement neue
   Komplexitaet entsteht und beide Agents auf demselben Modelltyp
   und denselben Text laufen — wenig unabhaengiger Gewinn.

3. **feature_definierer macht Containment mit:** Pocket-Liste an
   ihn weiterreichen, er entscheidet auch parent. Verworfen, weil
   das den feature_definierer ueberlaedt und die saubere Trennung
   "ein Agent, ein Job" bricht.

## Konsequenzen

**Positiv:**

- Bug 965da548 behoben — Hole 1 sitzt jetzt bei `(73.0356, 82.4528)`,
  beide Achsen-Versaetze ueberleben (verifiziert in Run 70d27d2f).
- Latenz des Agents: 21s -> 6.4s (3.3x), weil Output-Schema schmaler
  und LLM-Aufgabe einfacher ist.
- Deterministisches Durchreichen der Position folgt der Projekt-Regel
  "Textverstaendnis = LLM, Rechen/Code/Zusammenbau = deterministisch".

**Negativ / zu beachten:**

- Wenn der `feature_definierer` ein Position-Feld leer laesst, wird
  das leere Feld durchgereicht. Der Resolver faellt dann auf
  alignment-only zurueck. Akzeptabel im aktuellen Stand; falls das
  spaeter Probleme macht, koennte ein LLM-Fallback-Pfad nachgeruestet
  werden.
- Schema-Aenderung des LLM-Outputs (von verschachtelter Position zu
  schmalem Mapping) macht alte DSPy-Demos fuer diesen Agent
  inkompatibel. Aktuell hatte der Agent ohnehin keine optimierten
  DSPy-Artefakte — kein Verlust.

**Nicht in dieser Aenderung:**

- Bei seitlichen Pockets (Face `>X` / `<Y`) wertet der Resolver
  `center_offset` aktuell im Welt-`>Z`-Frame aus
  ([blueprint_resolver.py:1239](../../src/tools/blueprint_resolver.py#L1239)).
  Das ist eine separate, praeexistierende Limitation und bleibt fuer
  einen eigenen Fix offen.

## Tests

`tests/agents/test_pocket_child_placer.py` deckt 16 Faelle ab,
inklusive einer End-to-End-Regression auf der Spec aus Run 965da548:
feature_definierer-Output mit `center_offset {top:10, right:15}` ->
pocket_child_placer (LLM gemockt) -> blueprint_resolver -> finale
Offsets `(73.04, 82.45)` statt buggy `(74.77, 72.60)`.
