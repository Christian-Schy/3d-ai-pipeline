# Diagonale und Winkel-Positionierung
Tags: diagonal, winkel, angle, schräg, gedreht, rotation, 45grad, position

## Diagonale Positionierung (Zukunftsfeature)

Aktuell werden Teile nur achsenparallel positioniert (0/90/180/270 Grad).
Diagonale/schräge Positionierung ist für zukünftige Versionen geplant.

## Workarounds für diagonale Anforderungen

### "Platte diagonal auf die Ecke"
-> Nicht direkt möglich. Best-effort: alignment="centered"
-> Warnung im Output: "Diagonale Positionierung nicht unterstützt"

### "Teil im 45-Grad-Winkel"
-> rotation_deg: 45 (Feld existiert, wird aber vom Coder noch nicht unterstützt)
-> Hinweis: orientation_hint="45 Grad gedreht" weitergeben für spätere Verarbeitung

## Face-Hint bei schrägen Beschreibungen

Wenn die Spec eine Fläche beschreibt die nicht direkt einer Achsen-Face entspricht:
-> face_hint wörtlich übernehmen
-> face auf beste Annäherung setzen (>Z, >X etc.)

## Künftige Erweiterung: rotation_deg

Geplantes Feld für Rotation um die Face-Normale:
- rotation_deg: 0 = keine Rotation (Standard)
- rotation_deg: 45 = 45 Grad im Uhrzeigersinn
- rotation_deg: 90 = 90 Grad (= andere Alignment-Richtung)

Bis dahin: orientation_hint nutzen um Rotationswünsche durchzureichen.
