# Implicit Placement — ★ "darin", "darauf", "daneben" auflösen
Tags: implizit, darin, darauf, daneben, relativ, bezug, interpretation, placement

## Wann verwenden
- User beschreibt Position relativ zu einem Feature, nicht absolut
- Interpreter muss "darin" in konkrete Face + Position umwandeln
- ★ Kritisch für korrektes geometrisches Verständnis

## Auflösungsregeln

### "darin" / "im" / "in dem"
**Bedeutung**: Feature INNERHALB eines anderen Features
**Typisch**: Bohrung in einem Steg, Tasche in einem Boss

```
User: "im Steg eine Bohrung"
→ Parent: Steg
→ Face: abhängig von Kontext
  - Wenn Steg vertikal: Bohrung von oben (>Z des Stegs)
  - Wenn "seitlich darin": Bohrung von der Seite (>X/<X des Stegs)
→ Position: zentriert im Steg (default)
```

### "darauf" / "drauf" / "oben drauf"
**Bedeutung**: Feature AUF der Oberseite eines anderen Features
**Typisch**: Boss auf einer Platte, Steg auf einer Stufe

```
User: "auf den Steg drauf einen Boss"
→ Parent: Steg
→ Face: >Z des Stegs (Oberseite)
→ Position: zentriert auf Steg (default)
```

### "daneben" / "neben"
**Bedeutung**: Feature NEBEN einem anderen Feature, auf gleicher Basis
**Typisch**: Zweiter Boss neben dem ersten, Bohrung neben der Tasche

```
User: "neben dem Boss eine Bohrung"
→ Parent: Basis (NICHT der Boss!)
→ Face: gleiche Face wie der Boss (meist >Z der Basis)
→ Position: versetzt vom Boss
```

### "auf der rechten/linken/vorderen/hinteren Seite" (oben drauf, Top-Face)
**Bedeutung**: Feature AUF DER TOP-FACE, aber SEITLICH positioniert
**★ ACHTUNG**: "auf der rechten Seite" ≠ Seitenfläche! Es ist die TOP-FACE mit einem Offset!

```
User: "oben auf der rechten Seite ein Block"
→ Parent: Basis-Körper
→ Face: >Z (OBERSEITE, NICHT Seitenfläche!)
→ Position: flush_right → offset_x = +parent_W/2 - feature_W/2

User: "auf der linken Seite oben ein Aufsatz"
→ Face: >Z, Position: flush_left → offset_x = -(parent_W/2 - feature_W/2)

User: "auf der rechten hinteren Ecke"
→ Face: >Z, Position: offset_x = +parent_W/2 - feature_W/2, offset_y = +parent_L/2 - feature_L/2
```

### "von der Seite" / "seitlich"
**Bedeutung**: Feature auf einer Seitenfläche (nicht oben drauf!)
**Welche Seite?**: Kontext → "von rechts" = >X, "von links" = <X

```
User: "von der rechten Seite eine Bohrung"
→ Parent: der Körper an dieser Stelle
→ Face: >X (Seitenfläche)
→ Position: zentriert auf der Seitenfläche (Y/Z-Mitte)
```

### "gegenüber" / "auf der anderen Seite"
**Bedeutung**: Gespiegeltes Feature
```
User: "gegenüber auch eine Bohrung"
→ Gleiche Parameter wie Referenz-Feature
→ Position: gespiegelt (X → -X, oder Y → -Y)
```

### "am Rand" / "an der Kante"
**Bedeutung**: Feature bündig am Rand platziert
```
User: "am Rand eine Bohrung"
→ Position: offset = parent_dimension/2 - feature_radius - small_margin
```

### "zentral" / "mittig" / "in der Mitte"
**Bedeutung**: Geometrische Mitte des Parents
```
User: "zentral darin eine Bohrung"
→ offset_x = 0, offset_y = 0 relativ zum Parent-Zentrum
```

## Auflösungs-Algorithmus für den Interpreter

```
1. IDENTIFIZIERE das Referenz-Feature (worauf bezieht sich "darin"?)
2. BESTIMME die Beziehung (darin/darauf/daneben/seitlich)
3. LEITE die Face ab:
   - "darin" + vertikal → >Z des Features
   - "darin" + "seitlich" → >X oder <X des Features
   - "darauf" → >Z des Features
   - "daneben" → >Z der Basis
   - "seitlich" → >X/<X/>Y/<Y
4. LEITE die Position ab:
   - "zentral/mittig" → (0, 0) relativ zum Feature
   - "am Rand" → offset zum Rand
   - Keine Angabe → zentriert (default)
5. FORMULIERE explizit:
   "Bohrung ∅10 IN Steg, Face: >Z des Stegs, Position: zentriert"
```

### "Nut entlang der Y-Achse" / "entlang der X-Achse"
**Bedeutung**: Die Nut läuft über die GESAMTE Breite/Länge des Parents in dieser Richtung.
**★ KRITISCH**: "entlang der Y-Achse" = Nut-Länge = volle Y-Dimension des Parents. Die 5×5 Angabe beschreibt nur Querschnitt (Breite × Tiefe), NICHT die Länge!
**Position**: Offset in der Richtung QUER zur Nut-Achse. "Entlang Y, zentriert in X" → offset_x=0, offset_y=0, length=parent_Y
**★ Nie**: Nut an gleicher Position wie Bohrung platzieren (Nut würde im Bohrloch verschwinden!)

```
User: "Nut oben entlang der Y-Achse von 5×5"
→ Type: slot/groove
→ Face: >Z (Oberseite)
→ Breite (X): 5mm, Tiefe (Z): 5mm
→ Länge (Y): VOLLE Y-Dimension des Parents (z.B. 30mm für 30×30×30 Würfel)
→ Position: zentriert auf Oberseite (Offset X=0, Y=0)
→ Params: width=5, depth=5, length=30

User: "Nut entlang der X-Achse 4mm tief 8mm breit"
→ Länge (X): VOLLE X-Dimension des Parents
→ Breite (Y): 8mm, Tiefe: 4mm
```

## Beispiele

| User-Input | Aufgelöst |
|-----------|-----------|
| "in der Platte ein Loch" | Bohrung in Basis, >Z, zentriert |
| "im Steg eine Bohrung" | Bohrung im Steg, >Z des Stegs, zentriert |
| "von rechts in den Steg bohren" | Bohrung im Steg, >X des Stegs, Y/Z-zentriert |
| "drauf einen Boss" | Boss auf letztem Feature, >Z, zentriert |
| "neben der Bohrung noch eine" | Bohrung in Basis, >Z, versetzt von erster |
| "seitlich eine Nut" | Nut auf Seitenfläche, >X oder >Y |
| "unten drunter eine Tasche" | Tasche in Unterseite, <Z, zentriert |
| "am Rand 4 Löcher" | 4 Bohrungen, Eckpositionen, >Z, mit Inset |
| "Nut entlang der Y-Achse 5×5" | Nut auf >Z, Länge=parent_Y, Breite=5, Tiefe=5, Offset=(0,0) |
