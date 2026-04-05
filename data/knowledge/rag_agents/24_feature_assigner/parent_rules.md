# Parent-Zuweisung — Wer gehört zu wem?
Tags: parent, zuordnung, bohrung, nut, aufsatz, feature, teil

## Grundregel: Feature gehört zum NÄCHSTEN Teil

Ein Feature (Bohrung, Nut, Fase) gehört immer zum Teil, das direkt davor oder dabei beschrieben wird.

## Parent-Erkennung aus Text

| Formulierung | Parent ist... |
|---|---|
| "Bohrung auf der Platte" | plate |
| "Bohrung durch den Aufsatz" | pad/aufsatz |
| "Nut oben auf dem Würfel" | base (der Würfel) |
| "Bohrung darin" / "darin eine Bohrung" | das zuletzt genannte Teil |
| "auf der 80×40 Seite" | das Teil mit 80×40 Maßen |
| "auf der Basis" / "auf der Grundplatte" | base |

## WICHTIG: Nicht verwechseln

FALSCH: "Platte mit Bohrung auf Basis" → Bohrung parent=base
RICHTIG: "Platte mit Bohrung auf Basis" → Bohrung parent=plate (die Bohrung ist IN der Platte)

Der Zusammenbau (Platte AUF Basis) bestimmt den parent der PLATTE, nicht der Bohrung.

## Operation-Zuweisung

| Feature-Typ | Operation |
|---|---|
| Platte, Aufsatz, Boss, Steg, Zylinder | add |
| Bohrung, Nut, Tasche, Fase, Verrundung | subtract |
| Basis (erstes Teil) | add, parent=null |

## Params-Extraktion

Übernimm Maße WÖRTLICH aus der Spezifikation:
- "20×80×40" → {"x": 20, "y": 80, "z": 40}
- "∅10mm durchgehend" → {"diameter": 10, "depth": null}
- "∅10mm 29mm tief" → {"diameter": 10, "depth": 29}
- "Nut 5×5" → {"width": 5, "depth": 5}
- "Nut 5×5 entlang Y 30mm lang" → {"width": 5, "depth": 5, "length": 30}
