# 99 - Normen-Audit und Pipeline-Luecken

Stand: 2026-05-18.

Dieses Dokument ist eine Arbeitsliste fuer die Konventions-Bibliothek. Es
zeigt, wo die aktuellen Docs bereits als Pipeline-Konvention brauchbar sind,
wo sie aber noch nicht den heutigen DIN/ISO-GPS-Stand oder eine vollstaendige
technische Zeichnungslogik abbilden.

Wichtig: Dieses Audit ersetzt keinen Normtext und keine zertifizierte
Normpruefung. DIN/ISO-Normen sind urheberrechtlich geschuetzt; hier werden nur
oeffentliche DIN-Media-Metadaten, Normtitel, Statushinweise und die lokale
Pipeline-Logik ausgewertet.

## Kurzurteil

Die vorhandenen Konventionen sind als erste Pipeline-Regeln nuetzlich, aber
sie entsprechen noch nicht vollstaendig den aktuellsten Anforderungen, die ein
Ingenieur aus einer normgerechten technischen Produktdokumentation erwarten
wuerde.

Der wichtigste Unterschied:

- Eine technische Zeichnung bemasst konkrete Geometrieelemente wie Kanten,
  Achsen, Mittelpunkte, Bezugsebenen, Bezugssysteme und Toleranzzonen.
- Die Pipeline nutzt derzeit vereinfachte Sprach-Konventionen wie
  `abstand_*`, `kante_*`, `versatz_*`, `alignment` und Feature-spezifische
  Defaults.

Diese Pipeline-Defaults koennen genau das treffen, was ein Konstrukteur meint,
duerfen aber nicht pauschal als DIN-Regel formuliert werden.

## Aktuelle Normanker fuer diese Bibliothek

Die Docs sollten diese Normen als Primaeranker verwenden:

| Thema | Aktueller Anker | Relevanz fuer Pipeline |
|---|---|---|
| Allgemeine Masseintragung | DIN EN ISO 129-1:2022-02 | Dimensionen und Toleranzen darstellen; ersetzt die alte DIN-406-Basis. |
| Darstellung, Ansichten, Schnitte | DIN EN ISO 128-1:2022-02, DIN EN ISO 128-2:2023-06, DIN EN ISO 128-3:2024-06 | Face-/Ansichtslogik, Schnitte fuer Bohrungen/Taschen/Innengeometrie. |
| Bezugssysteme / Datums | DIN EN ISO 5459:2025-12 | Datum A/B/C, Bezugssysteme, Bezugselemente, Lagebezug. |
| Form-/Richtungs-/Orts-/Lauftoleranzen | DIN EN ISO 1101:2017-09 | Positions-, Parallelitaets-, Rechtwinkligkeits- und andere GD&T-Angaben. |
| ISO-Passungen | DIN EN ISO 286-1:2019-09 und DIN EN ISO 286-2:2019-09 | Passungen wie H7/g6 fuer Bohrungen/Wellen. |
| Werkstueckkanten | DIN EN ISO 13715:2020-01 | Kanten mit unbestimmter Gestalt, Entgraten, Grat/Freistiche. |

Historische Normen in den aktuellen Docs sollten nur noch als historischer
Kontext genannt werden:

| Alte Referenz | Problem | Besser |
|---|---|---|
| DIN 406 / DIN 406-10 / DIN 406-11 | Zurueckgezogen; DIN Media verweist auf DIN EN ISO 129-1. | DIN EN ISO 129-1:2022-02 |
| DIN 406-12 | Zurueckgezogen; fuer Toleranzen nicht mehr alleiniger Anker. | DIN EN ISO 129-1, DIN EN ISO 14405-Reihe, DIN EN ISO 1101 |
| DIN 6 | Zurueckgezogen; durch ISO-128-/ISO-10209-/ISO-5456-nahe Normen ersetzt. | DIN EN ISO 128-Reihe |
| DIN 6784 | Zurueckgezogen; durch DIN ISO 13715 und spaeter DIN EN ISO 13715 ersetzt. | DIN EN ISO 13715:2020-01 |

## Lokale Dokumente mit Norm-Risiko

| Datei | Befund | Handlung |
|---|---|---|
| `10_masseintragung_din406.md` | Titel und Referenzen fuehren DIN 406 als aktive Grundlage. Zudem wird `edge-to-CENTER` fuer Pockets als Default gesetzt, was eher Pipeline-Konvention als Normregel ist. | Umbenennen/umschreiben auf ISO-129-orientierte Masseintragung; DIN 406 nur historisch nennen. |
| `20_bohrung_din.md` | Bohrung als point-like ist fuer CAD-Positionierung sinnvoll, aber technische Zeichnungen koennen Bohrungen ueber Achsen, Mittellinien, Lochbilder, Datums, Passungen, Gewinde, Senkungen und Toleranzen spezifizieren. | Bohrungs-Konvention in Basis-Geometrie und Engineering-Angaben splitten. |
| `21_nut_slot_din.md` | Slot-Length edge-to-EDGE und Width edge-to-CENTER ist plausibel, aber als DIN-Regel zu stark formuliert. Rotierte Slots fallen auf edge-to-CENTER zurueck. | **Konvention erledigt 2026-05-18:** auf Mittellinien-Bezug umgestellt (norm-treu, beide Achsen edge-to-center). Code-Migration + Slot-Golden-Rework + Endradien-Template + Restwandstaerke-Validator offen — siehe Nut/Slot-Sektion unten. |
| `22_tasche_din.md` | A1 edge-to-CENTER fuer Taschen ist nutzbar, aber nicht immer Konstrukteur-Default. A5 wird als A1 reduziert, obwohl eine technische Zeichnung auch Feature-Ecken und Bezugssysteme nutzen kann. | **Ueberprueft 2026-05-18:** Doc ist weitgehend in Ordnung. A5=A1 ist schon korrekt umgesetzt (deckt Schritt-1 Ecken-Regel). Feature-Ecke der Tasche → A2-dual ist sauber separiert. Norm-Verweise aktualisiert. Plan-Bucket-Punkte (Bodendetails, Datum, rotierte Kontur) bleiben — siehe Tasche-Sektion. |
| `24_pattern_din.md` | Grid/Linear A1 auf aeusserste Bohrung, Kreis A1 auf Pattern-Center ist praktikabel, aber nicht allgemein normativ. Startwinkel und Kind-Feature-Pruefung sind unvollstaendig. | **Ueberprueft 2026-05-18:** A1-Bezugspunkt pro Typ entspricht der ueblichen Drawing-Konvention (Teilkreis-Mitte / aeusserste Bohrung); ist als Default richtig. A5=A1 fuer Kreis ist schon korrekt umgesetzt. Norm-Verweise aktualisiert. Offen bleibt: `start_angle_deg`-Vokabular nicht implementiert, `coordinate_validator` prueft keine Kind-Bohrungen, Toleranzen pro Lochbild, gemischte Kind-Features (Slot/Tasche in Pattern). |
| `25_plate_din.md` | Plate-Stacking ist CAD-Assembly-/Mate-Logik, nicht klassische Einzelteil-Zeichnungsnorm. B1/C3 und Bottom-/Side-Stack sind noch lueckenhaft. | **Ueberprueft 2026-05-18:** A5-Sektion enthielt das alte Anker-Modell und produzierte ueberhaengende Plate-Platzierungen (P08). Auf Schritt-1-Regel (Ecke = A1) umgestellt + Ueberhang-Warnung + Empfehlung A2 (`kante_*`) fuer Eck-zu-Eck-Anlage. Plate-Golden-Rework: P08-aehnliche Eck-Specs auf `kante_*` umstellen. Offen bleibt: B1/C3-Coverage-Luecken, Bottom-Stack, echte Mate-Semantik (Cap 5.0), Feature-Zuordnung bei gestapelter Platte. |
| `26_edge_features_din.md` | DIN 6784 ist zurueckgezogen. ISO 13715 behandelt Kanten unbestimmter Gestalt; symmetrische 45-Grad-Fase per `C2` ist nur ein Teilfall. E2 und Innen-/Aussenkanten fehlen. | **Ueberprueft 2026-05-18:** Konzeptuelle Trennung eingezogen — definierte Fase/Rundung (ISO 129-1, Cx/Rx) ist der Scope dieses Docs; ISO 13715 (Kantenzustand fuer unbestimmte Kanten, Symbole `±`/`-`/`+`) ist eigene Capability und nicht implementiert (Plan-Bucket). Norm-Verweise aktualisiert. Offen: E2-Coverage, asymmetrische Fase (`C2×3`, ≠ 45°), Innen-/Aussenkanten-Filter, Reihenfolge-Validator (Fasen vor Rundungen). |
| `11_coverage_matrix.md` | Matrix enthaelt Widersprueche: Bohrung A5 als Pflicht, aber Feature-Doc sagt nicht anwendbar; Pattern A5 in Matrix aus, Feature-Doc testet A5; Plate C3 ist als Pflicht/TBD inkonsistent. | **Teilweise erledigt 2026-05-18:** A5 als Methode neu definiert (= A1 Ecken-Regel, kein eigenes Anker-Schema) — loest den `anker.md`-Widerspruch auf. Wording-Pool A5 + A5-Hinweise im Methoden-Block aktualisiert + Ueberhang-Hinweis fuer ausgedehnte Features. Offene Feinheiten: Feature-Table-Inkonsistenzen (Pattern A5 "—" trotz Kreis-A5=A1; Slot A5 "—" jetzt eigentlich = A1; Plate C3 vs Doc-TBD) — koennen mit dem Golden-Rework zusammen aufgeraeumt werden. |

## Positionierungsarten, die fuer Ingenieur-Wording fehlen

Diese Bezugsarten sollten langfristig in der Pipeline auftauchen, damit
Konstruktionen wirklich zeichnungsartig interpretierbar sind:

| Bezugsart | Beispiel-Wording | Pipeline-Status |
|---|---|---|
| Bauteilkante zu Feature-Mittelpunkt | "Bohrung 20 mm von links" | Teilweise aktiv als `abstand_*`. |
| Bauteilkante zu Feature-Kante | "linke Taschenkante 12 mm vom Rand" | Aktiv fuer Pocket/Slot/Plate, aber nicht ueberall sauber getestet. |
| Feature-Mittelpunkt zu Bauteilmitte | "10 mm aus Mitte nach rechts" | Aktiv als `versatz_*`. |
| Feature-Ecke zu Bauteil-Ecke | "obere rechte Ecke der Tasche 10 mm von oben und 20 mm von rechts" | Teilweise als A2/A5, aber begrifflich vermischt. |
| Feature zu Feature | "Bohrung 10 mm vom Taschenrand" | Geplant als A7 / Capability 6.0. |
| Achse / Mittellinie | "Nutachse 15 mm von der Bezugskante", "Bohrungsachse auf Mittellinie" | Nur implizit; keine eigenstaendige Schema-Semantik. |
| Datum A/B/C | "Position bezogen auf A und B" | Fehlt. Wichtig fuer ISO 5459 / ISO 1101. |
| Koordinatenbemassung / Baseline | "X=25, Y=40 ab Bezug A/B" | Fehlt als explizite Methode. |
| Kettenmass-Aufloesung | "erste Bohrung 10, weitere jeweils 20" | Dokumentiert als nicht implementiert. |
| Symmetrie / Gleichverteilung | "vier Bohrungen gleichmaessig verteilt" | Nur Pattern-Spezialfaelle; generisch fehlt. |
| Positions- und Formtoleranz | "Position Toleranzzone D0,1 zu A|B|C" | Fehlt. |
| Passung | "Bohrung D10 H7" | Fehlt. |
| Gewinde | "M6 durchgehend", "M8 Sackloch" | Fehlt. |
| Senkung / Absatzbohrung | "90 Grad Senkung", "Zylindersenkung fuer M6" | Fehlt. |
| Oberflaeche / Rauheit | "Ra 1,6 auf Dichtflaeche" | Fehlt. |

## Feature-spezifische Luecken

### Bohrung

Aktuell korrekt fuer einfache CAD-Geometrie:

- Face-Auswahl.
- Durchmesser.
- Tiefe.
- Mittelpunkt ueber Kantenabstand, Center-Versatz oder Zentrierung.

Noch nicht ausreichend fuer aktuelle Ingenieur-Erwartung:

- Gewinde, Passungen und Toleranzen.
- Durchgangsbohrung vs. Sackloch als normnahe Angabe.
- Senkungen, Zapfensenkungen, Kegelsenkungen, Stufenbohrungen.
- Achsen-/Mittellinienbezug statt nur Punktkoordinate.
- Positionsangaben zu Datum A/B/C.
- Lochbilder mit Startwinkel, Teilkreis und Toleranz.

### Tasche / Pocket

Aktuell korrekt fuer einfache rechteckige subtractive Features:

- Center-/Kanten-/Mitte-Bezuege.
- Rotation als CAD-Winkel.
- Warnung bei Ueberstand.

Noch offen:

- Zeichnungslogik fuer Bodenflaeche, Tiefe, Radius/Freistich, Innenkanten.
- Datum-/Achsenbezuege.
- Positionstoleranzen und Flaechenqualitaet.
- Rotierte Tasche nahe Rand mit exakter Konturpruefung statt bbox-Approximation.

### Nut / Slot

**Konvention beschlossen 2026-05-18:** Mittellinien-Bezug auf beiden
Achsen (norm-treu nach ISO 129-1, analog zur Bohrungs-Achse). Loest die
fruehere per-Achse-Regel ab (Length=edge-to-EDGE, Width=edge-to-CENTER).
Details: [`21_nut_slot_din.md`](21_nut_slot_din.md).

Aktuell gut:

- Explizite Achsrichtung.
- Anfangs-/Endpunkt-Phrasen (self-contained).
- `kante_*`/`pocket_edge_distances` bleibt als bewusste Opt-in-Methode
  fuer Restwandstaerken-/Endkanten-Bemassung.

Erledigt 2026-05-18 (Paket 1):

- ✅ **Resolver-Code-Migration:** Slot-per-Achse-Branch in
  `_compute_offsets` entfernt → Slot-`abstand_*` ist edge-to-CENTER auf
  beiden Achsen, wie bei `hole_single`.
- ✅ **Feature-Builder-Code-Migration:** `_resolve_slot_endpoints` auf
  `abstand_<kante> = (anfang + ende) / 2` umgestellt.
- ✅ **Resolver-Component-Goldens umgerechnet:** V2 `slot_top_y_edge`,
  N_coverage N01-N12, N_kombo Slot-Cases auf Mittellinien-Bezug. Inputs
  wo noetig nachgezogen (n04 endpoints: `left:20`→`left:50`;
  N_kombo `nut_ecke_oben_rechts` input `top:10`→`top:25` zur
  Geometrie-Validitaet). 303/303 Tests gruen.

Noch offen:

- **Pipeline-Goldens-Heatmap unter Mittellinien-Regel verifizieren**
  (Ollama, separate Sitzung). Spec-Texte (D1/D2 in `21_nut_slot_din.md`
  und in `tests/golden/components/.../pipeline/specs.txt`) sind
  grossteils weiter gueltig, mehrdeutige Stellen werden mit dem
  Heatmap-Lauf re-verifiziert.
- **Endradien fehlen im Slot-Template:** Eine normgerechte Nut/Langloch
  hat halbrunde Enden (`R = Breite/2`). Das Template erzeugt heute nur
  den rechteckigen Schnitt — muss um die zwei Endradien ergaenzt
  werden.
- **Validator-Flag Restwandstaerke:** Sobald Endradien existieren,
  pruefen ob Slot-Aussenkontur einen Mindestabstand zur Bauteilkante
  einhaelt (heute nur per-bbox-Approximation in
  `coordinate_validator`).

Weiterhin offen (Engineering-Plan, eigene Capability):

- Werkzeugdurchmesser-/Passungs-/Funktionstoleranz-Angabe fuer Nuten.
- Bezugssysteme (Datum A/B/C, ISO 5459) als Bezugspunkt der Slot-
  Position (statt Bauteilkante).

### Pattern

Aktuell gut:

- Grid, Linear-Reihe, Teilkreis.
- Anzahl, Abstand, Teilkreis-Durchmesser.

Noch offen:

- Erste Bohrung / Startwinkel ist dokumentiert, aber nicht implementiert.
- Randabstand kann aeusserste Bohrung oder Pattern-Center meinen; das muss
  im Schema explizit werden.
- Kind-Bohrungen werden nicht vollstaendig gegen Bauteilgrenzen validiert.
- Toleranzen pro Lochbild fehlen.

### Plate / Assembly

Aktuell gut:

- Praktische Stack- und Side-by-Side-Beschreibung fuer CAD-Assemblies.

Normrisiko:

- Das ist keine reine technische Zeichnungsnorm, sondern Assembly-/Mate-
  Semantik.
- Fuer eine ingenieurnahe Umsetzung braucht es Bezugsebenen, Kontaktflaechen,
  Ausrichtung, Fixierung und ggf. Baugruppenbeziehungen als eigene Konzepte.

### Edge Features

Aktuell gut:

- Fase und Rundung als templatebare Operation.
- Auswahl vieler einfacher Wuerfelkanten.

Noch offen:

- DIN EN ISO 13715 fuer unbestimmte Kanten sauber von definierter Fase/Rundung
  trennen.
- E2 "horizontale Kanten" testen.
- Aussenkanten vs. Innenkanten nach Taschen/Slots unterscheiden.
- Asymmetrische Fasen und Winkel ungleich 45 Grad.

## Empfohlene naechste Schritte

**Stand 2026-05-18 — Walkthrough-Paket abgeschlossen.** Konventions-Bibliothek
(10-26) auf ISO 129-1 / aktuelle Anker umgestellt; A5/Eck-Phrase einheitlich
als A1 (Ecken-Regel) aufgeloest; Slot auf Mittellinien-Bezug (Code+Goldens
migriert, 325/325 Tests gruen).

Roadmap fuer die naechsten Capability-Schritte → siehe
[`98_engineering_plan.md`](98_engineering_plan.md):

1. **Cap 1.0 Quick-Wins** (Slot-Endradien + Restwandstaerke-Validator,
   Pattern `start_angle_deg`, NEST `hole_classifier`-Fix, Pipeline-Goldens-
   Heatmap-Verifikation, Tasche-rotiert exakte Konturpruefung).
2. **Cap 2.0 Modifications** in Templates ueberfuehren (kein Coder).
3. **Cap 4.0 Connections** — Senkungen, Gewinde, Stufenbohrungen
   (`98_engineering_plan.md` §Cap 4.0).
4. **Cap 6.0 + 7.0** Datum + GD&T + Passungen + ISO 13715 Kantenzustand —
   B2B-Verkaufstreiber.
5. **Cap 8.0** STEP-Export mit PMI (parallel zu 7.0).

Erledigte Punkte aus diesem Audit (Walkthrough):

- ✅ README + Feature-Doc-Referenzen normativ aktualisiert (DIN 406, DIN 6,
  DIN 6784 als historisch markiert).
- ✅ `11_coverage_matrix.md` A5-Widerspruch geloest (A5 = A1 Ecken-Regel).
- ✅ A5/Eck-Phrase einheitlich aufgeloest in `10`, `20`, `22`, `24`, `25`, `26`.
- ✅ Slot-Konvention auf Mittellinien-Bezug — Code + Resolver-Component-
  Goldens migriert (Paket 1).

Offen aus diesem Audit:

- Matrix-Feinheiten: Feature-Table A5-Spalte harmonisieren
  (Pattern/Slot "—" → ✓(=A1)); Plate C3 vs Doc-TBD-Abgleich.
- Neue Matrix "Zeichnungs-Bezugsarten" mit Datum/Feature-zu-Feature →
  kommt mit Cap 6.0 (siehe `98_engineering_plan.md` §Cap 6.0).
- Pipeline-Goldens-Heatmap unter Mittellinien-Regel verifizieren
  (Ollama).

## Quellen

- DIN EN ISO 129-1:2022-02, DIN Media:
  https://www.dinmedia.de/de/norm/din-en-iso-129-1/333197796
- DIN 406-10:1992-12, zurueckgezogen, DIN Media:
  https://www.dinmedia.de/de/norm/din-406-10/1990706
- DIN EN ISO 128-1:2022-02, DIN Media:
  https://www.dinmedia.de/de/norm/din-en-iso-128-1/320738895
- DIN EN ISO 128-3:2024-06, DIN Media:
  https://www.dinmedia.de/de/norm/din-en-iso-128-3/359489181
- DIN 6:1956-10, zurueckgezogen, DIN Media:
  https://www.dinmedia.de/de/norm/din-6/7378761
- DIN EN ISO 5459:2025-12, DIN Media:
  https://www.dinmedia.de/de/norm/din-en-iso-5459/385519058
- DIN EN ISO 1101:2017-09, DIN Media:
  https://www.dinmedia.de/de/norm/din-en-iso-1101/258479779
- DIN EN ISO 286-1:2019-09, DIN Media:
  https://www.dinmedia.de/de/norm/din-en-iso-286-1/306462393
- DIN EN ISO 13715:2020-01, DIN Media:
  https://www.dinmedia.de/de/norm/din-en-iso-13715/314070606
- DIN 6784:1982-02, zurueckgezogen, DIN Media:
  https://www.dinmedia.de/de/norm/din-6784/939910
