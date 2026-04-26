# Parent-Zuweisung — Feature-Hierarchie und Abhängigkeiten
Tags: parent, zuordnung, hierarchie, child, abhängigkeit, build_order

## Grundregel: Feature gehört zum NÄCHSTEN Teil

Ein Feature (Bohrung, Nut, Fase) gehört immer zum Teil, das direkt davor beschrieben wird.

## Parent-Erkennung aus Text

| Formulierung | Parent ist... |
|---|---|
| "Bohrung auf der Platte" | base (die Platte) |
| "Bohrung durch den Aufsatz" | aufsatz (NICHT Basis!) |
| "Nut oben auf dem Würfel" | base (der Würfel) |
| "Bohrung darin" / "darin eine Bohrung" | zuletzt genanntes Teil |
| "auf der 80×40 Seite" | Teil mit diesen Maßen |
| "auf der Basis" / "auf der Grundplatte" | base |
| "im Steg" | der Steg |

## WICHTIG: Zusammenbau vs. Feature-Zuordnung

FALSCH: "Platte mit Bohrung auf Basis" → Bohrung parent=base
RICHTIG: "Platte mit Bohrung auf Basis" → Bohrung parent=plate

Der Zusammenbau (Platte AUF Basis) bestimmt den Parent der PLATTE, nicht der Bohrung!

## Operation-Zuweisung

| Feature-Typ | Operation |
|---|---|
| Platte, Aufsatz, Boss, Steg | add |
| Bohrung, Nut, Tasche, Fase, Verrundung | subtract |
| Basis (erstes Teil) | add, parent=null |

## Build Order — 5 Phasen

```
Phase 1: BASE         → Grundkörper (parent=null)
Phase 2: BASE_CUTS    → Subtraktive auf Basis (VOR Union!)
Phase 3: ADDITIONS    → Additive Features (Union)
Phase 4: ADDITION_CUTS → Subtraktive auf additiven Features
Phase 5: FINISHING    → Fillet, Chamfer, Shell (IMMER zuletzt)
```

★ Parents IMMER vor Children in build_order!
★ Bohrungen auf Basis VOR Unions (Phase 2 vor 3) — danach ist >Z nicht mehr eindeutig

## Dimension Sanity Checks

- Bohrung-∅ < min(parent_breite, parent_länge)
- Bohrung-Tiefe ≤ parent_höhe (sonst depth=null → Durchgang)
- Lochkreis-Radius + Bohrung-Radius < parent_dim/2
- Eckbohrungen: inset > hole_diameter/2
- Tasche: breite < parent_breite, tiefe < parent_höhe
- Wandstärke: feature_breite - hole_diameter > 2mm
