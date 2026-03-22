# Dimension Sanity Checks — Passt Feature auf Parent?
Tags: dimension, prüfung, sanity, grenzen, plausibilität

## Prüfregeln (VOR dem Coder anwenden)

### 1. Feature ≤ Parent
- Feature-Breite ≤ Parent-Breite
- Feature-Länge ≤ Parent-Länge
- Ausnahme: Feature darf überstehen wenn gewollt (z.B. Flansch)

### 2. Bohrungen
- hole_diameter < min(parent_w, parent_l)
- hole_depth ≤ parent_height (sonst Durchgangsbohrung)
- hole_diameter > 0 (kein Null-Durchmesser)

### 3. Lochkreis
- circle_radius + hole_radius < min(parent_w, parent_l) / 2
- n_holes ≥ 2 (sonst ist es eine Einzelbohrung)
- circle_diameter > hole_diameter

### 4. Eckbohrungen
- inset > hole_diameter / 2 (Loch nicht am Rand abgeschnitten)
- inset < min(parent_w, parent_l) / 2 (Loch nicht außerhalb)

### 5. Tasche
- pocket_width < parent_width
- pocket_length < parent_length
- pocket_depth < parent_height (sonst Durchgangsschnitt)

### 6. Z-Stacking
- Gesamthöhe = Summe aller gestapelten Features
- Prüfe ob Gesamthöhe plausibel für das Bauteil

### 7. Wandstärke
- Bei Bohrung in Feature: feature_breite - hole_diameter > 2mm (min. Wandstärke)
- Bei Tasche: parent_höhe - tasche_tiefe > 1mm (Boden nicht zu dünn)

## Wenn Prüfung fehlschlägt
→ Warnung an Planner mit konkretem Fehler
→ Planner soll Dimensionen anpassen oder Rückfrage stellen
