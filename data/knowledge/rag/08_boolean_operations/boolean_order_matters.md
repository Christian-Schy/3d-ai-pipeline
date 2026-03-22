# Boolean Order Matters — Reihenfolge bei Booleans
Tags: reihenfolge, order, abfolge, zuerst, danach, boolean_sequenz, face_tracking

## Wann verwenden
- Mehrere Booleans hintereinander
- Face-Selektoren verhalten sich unerwartet nach Booleans
- Planung der Build-Reihenfolge im Feature Tree

## Das Problem

```python
# Reihenfolge 1: Erst Union, dann Bohrung
base = cq.Workplane("XY").box(100, 100, 20, centered=(True, True, False))
steg = cq.Workplane("XY").box(20, 50, 30).translate((40, 0, 35))
body = base.union(steg).clean()
# >Z trifft jetzt STEG-Top (Z=50), nicht Basis-Top (Z=20)!

# Reihenfolge 2: Erst Bohrung, dann Union
base = cq.Workplane("XY").box(100, 100, 20, centered=(True, True, False))
base = base.faces(">Z").workplane(centerOption='CenterOfBoundBox').hole(10)
# >Z trifft sicher Basis-Top (Z=20) — Steg existiert noch nicht
steg = cq.Workplane("XY").box(20, 50, 30).translate((40, 0, 35))
body = base.union(steg).clean()
```

## Empfohlene Reihenfolge

```
1. Basis-Körper erstellen
2. Features auf der Basis (Bohrungen, Taschen) — BEVOR Aufsätze kommen
3. Aufsätze/Stege via Union hinzufügen
4. Features auf den Aufsätzen (Bohrungen im Steg)
5. Fillets und Chamfers IMMER als LETZTES
```

## Regeln

```python
# REGEL 1: Subtraktive Features vor additiven
# → Bohrungen in Basis BEVOR Steg aufgesetzt wird

# REGEL 2: Fillets/Chamfers immer am Ende
# → Fillet verändert Kanten, spätere Booleans können Fillet zerstören

# REGEL 3: .clean() nach JEDER Boolean-Operation
# → Nie zwei Booleans ohne .clean() dazwischen

# REGEL 4: Face-Selektoren SOFORT nach der Operation verwenden
# → Nicht eine Union machen und 3 Schritte später face selektieren
```

## Häufige Fehler
1. **★★★ Fillet vor Boolean**: Fillet + danach Union = Fillet kann zerstört werden
2. **Bohrung nach Union**: Face-Selektor trifft falsche Face → besser vorher bohren
3. **Zwei Unions ohne .clean()**: Kann zu Non-Manifold führen
4. **Cut vor Union**: Wenn das Cut-Tool auch den zukünftigen Union-Partner schneidet → unerwartete Geometrie
