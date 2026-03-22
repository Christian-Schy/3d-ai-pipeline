# Build Order Rules — Reihenfolge der Feature-Erstellung
Tags: reihenfolge, build_order, sequenz, abfolge, planung

## Die 5 Phasen (immer in dieser Reihenfolge)

```
Phase 1: BASE         → Grundkörper erstellen
Phase 2: BASE_CUTS    → Subtraktive Features auf Basis (Bohrungen, Taschen)
Phase 3: ADDITIONS    → Additive Features (Union: Stege, Bosses, Stufen)
Phase 4: ADDITION_CUTS → Subtraktive Features auf additiven Features
Phase 5: FINISHING    → Fillet, Chamfer, Shell
```

## Warum diese Reihenfolge?

### Phase 2 VOR Phase 3:
- Nach Union (Phase 3) ist >Z auf der Basis nicht mehr eindeutig
- In Phase 2 ist >Z noch sicher → einfache Face-Selektion
- Eckbohrungen, zentrale Bohrungen etc. IMMER hier

### Phase 3 einzeln mit .clean():
- Jede Union einzeln: body = body.union(feature).clean()
- NICHT: body.union(a).union(b) ohne clean dazwischen

### Phase 4 NACH Phase 3:
- Features auf Steg/Boss brauchen NearestToPointSelector
- Erst wenn der Steg existiert, kann darauf gebohrt werden

### Phase 5 IMMER zuletzt:
- Fillet/Chamfer ändern Kanten
- Boolean-Ops nach Fillet können Fillets zerstören

## Beispiel Build Order
```
Beschreibung: Platte + 2 Stege + Eckbohrungen + Steg-Bohrung + Fillets

build_order: [
  "base",          ← Phase 1
  "corner_holes",  ← Phase 2 (auf Basis, VOR Union)
  "steg_links",    ← Phase 3
  "steg_rechts",   ← Phase 3
  "bohrung_steg_r",← Phase 4 (auf Steg, NACH Union)
  "fillets"        ← Phase 5
]
```

## Abhängigkeitsregel
Für jedes Feature gilt: build_order.index(parent) < build_order.index(child)
Parent muss IMMER vor Child kommen.
