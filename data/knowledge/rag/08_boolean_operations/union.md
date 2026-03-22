# Union — Körper vereinigen
Tags: union, vereinigen, zusammenfügen, addieren, verbinden, kombinieren, add

## Wann verwenden
- Zwei Körper zu einem zusammenfügen
- Steg/Boss/Aufsatz auf Basis aufsetzen
- Mehrere Teile zu einem Solid verschmelzen

## CadQuery Code (modulare Funktion)

```python
def unite_bodies(target: cq.Workplane, tool: cq.Workplane) -> cq.Workplane:
    """Vereinigt zwei Körper. Target + Tool = Ergebnis.

    WICHTIG: Immer .clean() nach union!
    """
    return target.union(tool).clean()


def add_feature_on_body(body: cq.Workplane, feature: cq.Workplane) -> cq.Workplane:
    """Fügt ein Feature (Steg, Boss) auf einen Körper.

    Typischer Ablauf:
    1. Feature als separaten Body erstellen
    2. An richtige Position verschieben (.translate)
    3. Mit Body vereinigen (.union)
    4. Aufräumen (.clean)
    """
    return body.union(feature).clean()


# Beispiel: Platte + Steg
def example_plate_with_steg():
    base = cq.Workplane("XY").box(100, 100, 20, centered=(True, True, False))
    steg = (cq.Workplane("XY")
            .box(10, 100, 20)
            .translate((45, 0, 30)))  # Oben rechts
    return base.union(steg).clean()
```

## Parameter-Referenz
| Parameter | Typ | Beschreibung | Default |
|-----------|-----|--------------|---------|
| toUnion | Workplane/Shape | Körper der hinzugefügt wird | — |
| clean | bool | Automatisch aufräumen | True |
| glue | bool | Schnelle Union ohne Schnittlinien | False |
| tol | float | Toleranz | None |

## Häufige Fehler
1. **★★★ .clean() vergessen**: Ohne `.clean()` können interne Flächen bleiben → Probleme bei Face-Selektion und STL-Export
2. **★★ Face-Selektion nach Union**: `>Z` trifft nach Union die HÖCHSTE Face — oft unerwartet → siehe face_selectors_after_union.md
3. **Körper überlappen nicht**: Union von nicht-überlappenden Körpern ergibt ein Multi-Solid → problematisch für STL
4. **Reihenfolge beachten**: `a.union(b)` behält die Workplane von `a` — wichtig für nachfolgende Operationen

## Komposition
- Immer: `body.union(feature).clean()` — clean nicht vergessen
- Feature muss den Body berühren oder überlappen
- Nach Union: Face-Selektoren prüfen (siehe face_selectors_after_union.md)
