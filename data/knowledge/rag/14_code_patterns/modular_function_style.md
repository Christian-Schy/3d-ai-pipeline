# Modular Function Style — ★ Code-Standard für den Coder
Tags: modular, style, standard, konvention, coder_referenz, template, coding_rules

## Wann verwenden
- IMMER — dies definiert wie JEDER generierte Code aussehen muss
- Referenz für den Coder-Prompt
- Referenz für den Code Review Agent

## Regeln

### MUSS-Regeln (Verstoß = Code wird abgelehnt)

1. **Eine Funktion pro Feature**
   - Nie mehrere Features in einer Funktion
   - Ausnahme: Parameter-Berechnung darf in der Funktion sein

2. **Funktions-Signatur**
   ```python
   # Basis-Funktion (kein Input)
   def make_base() -> cq.Workplane:

   # Feature-Funktion (Body rein, Body raus)
   def add_feature_name(body: cq.Workplane) -> cq.Workplane:

   # NIEMALS:
   def do_stuff():          # Kein Rückgabetyp
   def make(a, b, c, d):   # Zu viele Parameter — Konstanten nutzen
   ```

3. **Docstring in jeder Funktion**
   ```python
   def add_steg(body: cq.Workplane) -> cq.Workplane:
       """Rechteckiger Steg auf der rechten Seite.

       Feature: Box 10×80×20mm
       Parent: base, Face: >Z
       Position: Bündig rechts (X=45), auf Basis (Z=25)
       Boolean: Union
       """
   ```

4. **Parameter als Konstanten oben**
   ```python
   # RICHTIG:
   STEG_W = 10.0
   def add_steg(body):
       steg = cq.Workplane("XY").box(STEG_W, ...)

   # FALSCH:
   def add_steg(body):
       steg = cq.Workplane("XY").box(10, ...)  # Magic Number!
   ```

5. **assemble() Funktion**
   ```python
   def assemble() -> cq.Workplane:
       result = make_base()
       result = drill_holes(result)
       result = add_steg(result)
       return result

   result = assemble()
   cq.exporters.export(result, OUTPUT_PATH)
   ```

6. **.clean() nach jeder Boolean-Operation**
   ```python
   return body.union(steg).clean()    # RICHTIG
   return body.union(steg)            # FALSCH
   ```

7. **centerOption='CenterOfBoundBox'**
   ```python
   .workplane(centerOption='CenterOfBoundBox')    # RICHTIG
   .workplane()                                    # FALSCH (Default = ProjectedOrigin)
   ```

8. **NearestToPointSelector nach Union**
   ```python
   # Nach Union:
   body.faces(NearestToPointSelector((x, y, z)))   # RICHTIG
   body.faces(">Z")                                 # FALSCH (mehrdeutig)
   ```

### SOLL-Regeln (Best Practice)

1. **Aussagekräftige Namen**
   ```python
   # RICHTIG:
   def add_steg_rechts(body): ...
   def drill_flansch_bohrungen(body): ...

   # SCHLECHT:
   def feature1(body): ...
   def do_holes(body): ...
   ```

2. **Koordinaten vorberechnen**
   ```python
   # RICHTIG:
   steg_x = BASE_W / 2 - STEG_W / 2
   steg_z = BASE_H + STEG_H / 2
   steg = cq.Workplane("XY").box(...).translate((steg_x, 0, steg_z))

   # SCHLECHT:
   steg = cq.Workplane("XY").box(...).translate((45, 0, 27.5))
   ```

3. **Imports am Anfang**
   ```python
   import cadquery as cq
   from cadquery.selectors import NearestToPointSelector
   import math  # Nur wenn trigonometrische Funktionen gebraucht werden
   ```

4. **Build-Reihenfolge dokumentieren**
   ```python
   def assemble() -> cq.Workplane:
       """Build Order:
       1. make_base()              — Grundkörper
       2. drill_corner_holes()     — Subtraktiv auf Basis (VOR Union)
       3. add_steg()               — Additiv (Union)
       4. drill_steg_hole()        — Subtraktiv auf Feature (NACH Union)
       5. apply_fillets()          — Kosmetisch (AM ENDE)
       """
   ```

## Code-Struktur-Template

```python
import cadquery as cq
from cadquery.selectors import NearestToPointSelector
import math

OUTPUT_PATH = "output.stl"

# ============================================================
# PARAMETER
# ============================================================
# [Alle Maße hier als Konstanten]

# ============================================================
# FEATURE-FUNKTIONEN
# ============================================================

def make_base() -> cq.Workplane:
    """[Beschreibung]."""
    pass

def add_[feature](body: cq.Workplane) -> cq.Workplane:
    """[Beschreibung]."""
    pass

# ============================================================
# ASSEMBLY
# ============================================================

def assemble() -> cq.Workplane:
    """[Build Order dokumentieren]."""
    result = make_base()
    # result = add_xxx(result)
    return result

# ============================================================
# EXPORT
# ============================================================
result = assemble()
cq.exporters.export(result, OUTPUT_PATH)
```

## Anti-Patterns (SO NICHT)

```python
# ❌ MONOLITHISCH — Ein Block für alles
result = cq.Workplane("XY").box(100, 100, 20)
tool = cq.Workplane("XY").box(50, 50, 20).translate((25, -25, 40))
result = result.union(tool).clean()
result = (result.faces(">Z").workplane(centerOption='CenterOfBoundBox')
          .pushPoints([[30, -30], [-30, -30]]).hole(10)).clean()
cq.exporters.export(result, OUTPUT_PATH)

# ❌ MAGIC NUMBERS
result = cq.Workplane("XY").box(100, 100, 20)  # Was sind 100, 100, 20?

# ❌ KEINE FUNKTIONEN
# Alles in einem Script ohne Funktionen → nicht modifizierbar

# ❌ FALSCHE REIHENFOLGE
result = make_base()
result = add_steg(result)       # Union
result = drill_base_holes(result)  # Bohrung in Basis NACH Union → >Z trifft Steg!
```
