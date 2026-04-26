# Häufige Fehler — Bekannte Stolperfallen und Korrekturen
Tags: fehler, korrektur, falsch, richtig, warnung, stolperfalle

## 1. Muster als Einzelbohrungen

FALSCH: "4 Eckbohrungen" → 4× hole_single mit je eigener Position
RICHTIG: "4 Eckbohrungen" → 1× hole_pattern_grid mit count=4

★ IMMER konsolidieren: grid, circular, linear statt Einzelbohrungen!

## 2. flush_left / flush_right verwechselt

FALSCH: "linke Seite bündig" → alignment="flush_right"
RICHTIG: "linke Seite bündig" → alignment="flush_left"

Die Richtung im alignment entspricht der Richtung im Text!

## 3. Face bei "aufrecht" falsch

FALSCH: "aufrecht hinten" → face=">Z"
RICHTIG: "aufrecht hinten" → face=">Y"

Aufrecht = Kontaktfläche ist NICHT oben, sondern die Seite!

## 4. Parent falsch zugeordnet

FALSCH: "Bohrung durch den Aufsatz" → parent="base"
RICHTIG: "Bohrung durch den Aufsatz" → parent="aufsatz"

Feature gehört zum Teil, auf/in dem es beschrieben wird.

## 5. "von der Seite" vs. "von der Kante" — KRITISCH!

★★★ HÄUFIGSTER FEHLER — GENAU LESEN!

"von der linken SEITE" / "auf der linken Seite" / "links soll" = Face-Angabe → face="<X"
"von der linken KANTE Xmm" / "Xmm von links" = Offset-Angabe → offset auf aktueller Face

FALSCH: "15mm von der linken Kante" → face="<X"
RICHTIG: "15mm von der linken Kante" → offset_x = -(Dim/2 - 15) auf der AKTUELLEN Face

FALSCH: "von unten 10mm entfernt" → face="<Z"
RICHTIG: "von unten 10mm entfernt" → offset_y = -(Dim/2 - 10) auf der aktuellen Face

Schlüssel: Wenn eine DISTANZ ("Xmm") dabei steht → IMMER Offset, nie Face!

## 5b. Richtungswort VOR Feature = Face

"rechts soll eine Bohrung" → face=">X" (rechts = Face-Richtung)
"auf der linken Seite eine Bohrung" → face="<X"
"hinten eine Nut" → face=">Y"
"oben eine Tasche" → face=">Z"

Das Richtungswort DIREKT VOR dem Feature-Typ beschreibt die Face!
Erst DANACH kommen Positions-Angaben (Offsets) auf dieser Face.

## 5c. Rohdistanz statt Formel — HÄUFIGER FEHLER!

★★★ FALSCH: "20mm von rechter Kante" → offset_x = 20.0
★★★ RICHTIG: "20mm von rechter Kante" → offset_x = +(Dim/2 - 20)

Beispiel: Box 50×50×50, Bohrung auf >X Face, "10mm von Oberkante, 20mm von rechter Kante":
  >X Face Dimensionen: offset_x=Parent.y (50), offset_y=Parent.z (50)
  FALSCH:  offset_x=20.0, offset_y=10.0  ← Rohdistanzwerte!
  RICHTIG: offset_x=+(50/2-20)=+5.0, offset_y=+(50/2-10)=+15.0  ← Formel angewendet!

Die Formel ist IMMER: offset = ±(Dim/2 - Abstand_von_Kante)
Gilt für ALLE Faces (>Z, >X, <X, >Y, <Y) — nicht nur für >Z!

## 6. Offset-Vorzeichen falsch

| Position | offset_x | offset_y |
|---|---|---|
| rechts | + | |
| links | - | |
| hinten/oben | | + |
| vorne/unten | | - |

★ Vorzeichen aus Position ableiten, nicht raten!

## 7. depth=0 statt depth=null

FALSCH: Durchgangsbohrung → depth=0
RICHTIG: Durchgangsbohrung → depth=null

null = Durchgang, 0 = keine Tiefe (ungültig)

## 8. Nut ohne length

FALSCH: slot params = {"width": 5, "depth": 5}
RICHTIG: slot params = {"width": 5, "depth": 5, "length": null}

★ length MUSS immer im params stehen! null = volle Länge

## 9. Build-Order: Parent nach Child

FALSCH: build_order = ["hole_on_steg", "steg", "base"]
RICHTIG: build_order = ["base", "steg", "hole_on_steg"]

Parents IMMER vor ihren Children!

## 10. hole_pattern_linear statt circular

"4 Bohrungen in einer Reihe mit 20mm Abstand" → hole_pattern_linear
"4 Bohrungen auf einem Lochkreis" → hole_pattern_circular

Reihe ≠ Kreis! Auf Schlüsselwörter achten.
