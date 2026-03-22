# Face Selectors Combined — Selektoren kombinieren
Tags: kombiniert, combined, and, or, not, filter, mehrere_bedingungen, string_syntax

## Wann verwenden
- Ein einzelner Selektor ist nicht spezifisch genug
- Face muss mehrere Bedingungen erfüllen (z.B. oben UND rechts)
- Face soll ausgeschlossen werden

## CadQuery Code

```python
from cadquery.selectors import (
    NearestToPointSelector,
    DirectionNthSelector,
    InverseSelector,
    AndSelector,
    SumSelector  # = OR
)

# String-basierte Kombination
body.faces(">Z and #X")      # FALSCH — String-Syntax unterstützt KEIN and/or!

# RICHTIG: Selektor-Objekte kombinieren
from cadquery import selectors

# AND — Face muss BEIDE Bedingungen erfüllen
sel_top_and_large = AndSelector(
    selectors.DirectionSelector((0, 0, 1)),    # Normale zeigt nach oben
    selectors.AreaNthSelector(0)                # Größte Fläche
)
body.faces(sel_top_and_large)

# OR — Face muss EINE der Bedingungen erfüllen
sel_top_or_bottom = SumSelector(
    selectors.DirectionSelector((0, 0, 1)),     # Nach oben
    selectors.DirectionSelector((0, 0, -1))     # Oder nach unten
)
body.faces(sel_top_or_bottom)

# NOT — Alle Faces AUSSER...
sel_not_bottom = InverseSelector(
    selectors.DirectionSelector((0, 0, -1))     # Nicht nach unten
)
body.faces(sel_not_bottom)


# Praktisches Beispiel: Shell mit offenem Deckel
def shell_open_top(body: cq.Workplane, thickness: float) -> cq.Workplane:
    """Höhlt einen Körper aus, Deckel wird entfernt."""
    return body.shell(-thickness, body.faces(">Z").val())
```

## Häufige Fehler
1. **String-Syntax kann KEIN and/or**: `faces(">Z and >X")` funktioniert NICHT — Selektor-Objekte verwenden
2. **Import vergessen**: Selektoren aus `cadquery.selectors` importieren
3. **SumSelector = OR, nicht Addition**: Unintuitiver Name, ist aber logisches ODER
4. **InverseSelector auf einzelnen Selektor**: `InverseSelector(">Z")` geht nicht — Selektor-Objekt übergeben
