# CadQuery Anti-Patterns — ★ Häufige Fehler erkennen
Tags: antipattern, fehler, häufig, erkennen, cadquery

## Anti-Patterns (Code MUSS korrigiert werden)

### 1. ❌ .clean() nach Boolean fehlt
```
body.union(tool)        ← FALSCH
body.union(tool).clean() ← RICHTIG
```
Suche nach: `.union(` ohne `.clean()` danach
Suche nach: `.cut(` ohne `.clean()` danach

### 2. ❌ >Z nach Union ohne NearestToPointSelector
```
body = base.union(steg).clean()
body.faces(">Z")        ← GEFÄHRLICH nach Union
```
Wenn Union im Code → alle danach folgenden `.faces(">Z")` prüfen

### 3. ❌ centerOption fehlt bei .workplane()
```
.workplane()                              ← FALSCH
.workplane(centerOption='CenterOfBoundBox') ← RICHTIG
```

### 4. ❌ Durchmesser/Radius verwechselt
```
.circle(diameter)  ← FALSCH, circle nimmt RADIUS
.circle(radius)    ← RICHTIG
.hole(diameter)    ← RICHTIG, hole nimmt DURCHMESSER
```

### 5. ❌ Fillet vor Boolean
Fillet/Chamfer muss NACH allen Union/Cut kommen

### 6. ❌ Mehrere Booleans ohne .clean()
```
body.union(a).union(b)  ← FALSCH
body.union(a).clean().union(b).clean()  ← RICHTIG
```

### 7. ❌ Variable nicht aktualisiert
```
add_steg(result)         ← FALSCH (Ergebnis verworfen)
result = add_steg(result) ← RICHTIG
```

## Warnung (kein FAIL, aber melden)
- Magic Numbers im Code (Maße ohne Konstante)
- Fehlende Docstrings
- Unnötiger Code (z.B. doppelter .clean())
