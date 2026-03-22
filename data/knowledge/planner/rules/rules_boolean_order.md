# Boolean-Reihenfolge

## Pflicht-Reihenfolge (immer einhalten)
1. Basis erstellen (parent=null)
2. Subtraktionen auf Basis (BEVOR jede Union!)
3. Additionen (Union mit Basis oder anderen Teilen)
4. Subtraktionen auf additiven Features (NACH deren Union)
5. Fillet/Chamfer zuletzt

## Warum Subtraktion vor Union?
Nach einer Union ist face=">Z" mehrdeutig — es gibt mehrere gleich hohe Z-Flächen.
Bohrungen auf der Basis-Top-Face MÜSSEN vor der Union gesetzt werden.
Danach: NearestToPoint selector verwenden.

## Face-Selektion nach Union
- Vor Union: ">Z", ">X" etc. sicher
- NACH Union für Basis-Features: NearestToPoint([0, 0, basis_h])
- NACH Union für aufgesetzte Features: NearestToPoint([cx, cy, feature_top_z])

## Falsch-Beispiel (so NICHT):
build_order: ["base", "steg", "basis_hole"]  ← basis_hole NACH steg ist falsch!

## Richtig-Beispiel:
build_order: ["base", "basis_hole", "steg", "steg_hole"]
             Phase1   Phase2        Phase3   Phase4
