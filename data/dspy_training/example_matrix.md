# Example-Matrix: Slot-basierte Beschreibungs-Generierung

Dieses Dokument definiert die kombinatorische Basis, aus der Trainings- und
Golden-Beispiele erzeugt werden. Jedes Beispiel ist eine Kombination aus
Slot-Werten, optional mit mehreren Features hintereinander.

**Grundidee:** Ein einzelnes Feature hat endlich viele Beschreibungs-Aspekte.
Ist ein Feature vollstaendig beschrieben, ist die Beschreibung zu Ende. Komplexe
Teile entstehen, indem dieselbe Grund-Grammatik mehrfach hintereinander angewandt
wird. Das LLM muss nur EIN Feature sauber parsen koennen — den Rest loest Wiederholung.

---

## 1. Grund-Schema einer Beschreibung

```
<TEIL> [<GLOBAL-POS>] <FEATURE>* 

TEIL      = <FORM> <MASSE> [<ORIENTATION>]
FEATURE   = [<ANZAHL>] <F-TYP> <F-MASSE> <FACE> <POSITION> [<WINKEL>] [<TIEFE>]
```

Jeder Slot ist unabhaengig befuellbar. Nicht alle Kombinationen sind sinnvoll
(z.B. "diagonal" + "zentral" — diagonal hat keinen Bezug ohne Ecke).

---

## 2. Slot-Werte (Enumerationen)

### 2.1 FORM (Teil-Grundform)
- `box` / `quader` / `wuerfel` (wenn gleich)
- `platte` (impliziert duenne Dimension)
- `zylinder`
- `hohlzylinder` (spaeter)

### 2.2 MASSE
- Drei Zahlen: `100x100x20`, `50 50 50`, `Durchmesser 40 Hoehe 80`
- Benannt: `Breite 100 Tiefe 80 Hoehe 20`
- Gemischt: `Platte 100x100, 20mm dick`

### 2.3 ORIENTATION
- (leer / standard)
- `hochkant`
- `flach`
- `liegend`

### 2.4 ANZAHL (Feature-Multiplizitaet)
- 1 (Default, "eine Bohrung")
- N gleichmaessig: `4 Bohrungen im Quadrat 20x20`, `5er Lochkreis Ø40`
- N linear: `3 Bohrungen im Abstand 20mm`
- N-Muster: `4x4 Raster`, `3x2 Grid`

### 2.5 F-TYP
- `bohrung` (durchgehend, Default)
- `sackloch` / `bohrung X mm tief`
- `senkung` / `Senkbohrung`
- `gewinde` (Phase 2)
- `tasche` (eckig)
- `rund-tasche`
- `nut` (durchgehend vs. Laenge)
- `fase` (an Kante)
- `verrundung` / `radius` (an Kante)
- `lochkreis`
- `lochraster`

### 2.6 F-MASSE
- Bohrung: `Ø10`, `Durchmesser 10`, `M8`
- Tasche: `20x30`, `20x30x5 tief`
- Nut: `5x5`, `Breite 5 Tiefe 5`, `Breite 5 Tiefe 5 Laenge 40`
- Fase: `2mm`, `2x45°`
- Verrundung: `R3`, `Radius 3mm`

### 2.7 FACE (Flaechenwahl)
- **Quader/Platte**: `oben`, `unten`, `rechts`, `links`, `vorne`, `hinten`
- **Zylinder-Stirnseite**: `oben` / `unten`
- **Zylinder-Mantel**: ⚠️ **STUFE 2** — Resolver/Assembler unterstuetzen radiale
  Winkel-Platzierung aktuell nicht. Beispiele dazu werden in Stufe 2 ergaenzt.
  → In Stufe 1 nur Zylinder-Stirnseiten trainieren.

### 2.8 POSITION
Sortiert von einfach zu komplex:

**P0 — Zentral (Default, kein Slot-Wert noetig)**
- (weggelassen) / `zentral` / `mittig`

**P1 — Eine Achse, eine Kante**
- `20mm von links`
- `15mm von oben`
- `bündig rechts`

**P2 — Zwei Achsen (Ecke-Abstand)**
- `10mm von links, 15mm von oben`
- `jeweils 12,5mm von den Kanten`
- `obere rechte Ecke, 20mm von rechts, 20mm von oben`

**P3 — 2D-Richtung**
- `oben rechts` / `oben links` / `unten rechts` / `unten links`
- `in der oberen rechten Ecke`

**P4 — Ueberstand / bündig**
- `bündig rechts`, `bündig mit oberer Kante`
- `steht 5mm rechts über`
- `ragt 10mm nach vorne hinaus`

**P5 — Anker (Ecke/Kante-auf-Kante)**
- `obere linke Ecke liegt auf der linken Kante`
- `obere rechte Ecke liegt auf der oberen Kante, 20mm von rechts`

**P6 — Relativ zu anderem Feature**
- `20mm rechts neben der ersten Bohrung`
- `zwischen Bohrung 1 und 2 zentriert`
- `gespiegelt zu Bohrung 1`

**P7 — Zylinder-Mantel speziell** ⚠️ **STUFE 2, nicht in Stufe 1 trainieren**
- `auf der rechten Seite, von oben gesehen um 30° versetzt`
- `gegenüberliegend` (180°)
- `auf halber Hoehe, 90° versetzt`

### 2.9 WINKEL
- (leer / 0°)
- `um 45° gedreht` (Default CW)
- `um 45° CCW gedreht` / `gegen den Uhrzeigersinn`
- `diagonal` (impliziert 45°)
- Bei Zylinder-Mantel: radialer Versatz in Grad (siehe P7)

### 2.10 TIEFE (nur bei Bohrungen/Taschen)
- (leer / durchgehend)
- `10mm tief`, `durchgehend`
- `halbe Materialstaerke`
- `durch alle Teile` (wenn Assembly)

### 2.11 SPRACHSTIL (orthogonale Achse — gleicher Inhalt, andere Form)
- **knapp-technisch**: `Bohrung Ø10, oben, 20mm v. links, 15mm v. vorne, 10mm tief`
- **technisch-ausfuehrlich**: `Auf der Oberseite eine Bohrung mit 10mm Durchmesser, 20mm von der linken und 15mm von der vorderen Kante entfernt, 10mm tief`
- **umgangssprachlich**: `oben rein eine Bohrung 10er, vom linken Rand 20 und von vorne 15 weg, 10mm tief`
- **knapp-fehlerhaft** (fuer Negativbeispiele): `Bohrung oben rechts`  ← unvollstaendig
- **mehrdeutig** (fuer Negativbeispiele): `Bohrung oben mittig rechts`  ← widerspruechlich

---

## 3. Generierungs-Regeln (welche Kombinationen gueltig sind)

| Kombination | Gueltig? | Kommentar |
|---|---|---|
| P0 + WINKEL | ❌ | zentral braucht keinen Winkel |
| P5 (Anker) + WINKEL | ✅ | Anker ist Drehpunkt |
| Zylinder + FACE=links/rechts/vorne/hinten | → P7 | wird zu Mantel mit Winkel |
| Tasche + TIEFE=(leer) | ✅ | Default = innen, endliche Tiefe |
| Nut + Laenge=(leer) | ✅ | Default = durchgehend in Richtungsachse |
| FORM=platte + P7 (Mantel) | ❌ | Platten haben keinen Mantel |
| lochkreis + P0 | ✅ | Lochkreis-Mittelpunkt zentral |
| P2 + ANZAHL=N | ✅ | "4 Bohrungen je 20mm v. Kanten" (Eck-Pattern) |

---

## 4. Worked Examples (aus der Matrix abgeleitet)

### Beispiel A: Einfachste Form (P0, 1 Feature)
Slots: `FORM=wuerfel`, `MASSE=50`, `F-TYP=bohrung`, `F-MASSE=Ø10`, `FACE=oben`, `POSITION=P0`, `TIEFE=durchgehend`
→ "50mm Wuerfel, oben zentrale Bohrung Ø10 durchgehend"

### Beispiel B: Zwei-Achsen-Eck (P2, 1 Feature)
Slots: `FORM=platte`, `MASSE=100x100x20`, `F-TYP=bohrung`, `F-MASSE=Ø10`, `FACE=oben`, `POSITION=P2(rechts 20, vorne 15)`, `TIEFE=durchgehend`
→ "100x100x20 Platte, oben eine Bohrung Ø10 20mm von rechts und 15mm von vorne entfernt"

### Beispiel C: Anker + Winkel (P5 + WINKEL)
Slots: `FORM=platte`, `MASSE=100x100x20`, `F-TYP=tasche`, `F-MASSE=30x30x5`, `FACE=oben`, `POSITION=P5(obere linke Ecke auf linker Kante, 10mm v. oben)`, `WINKEL=45° CCW`
→ "Platte 100x100x20, auf der Oberseite eine Tasche 30x30x5 tief, die obere linke Ecke liegt auf der linken Kante 10mm von oben entfernt, 45° gegen den Uhrzeigersinn gedreht"

### Beispiel D: Zylinder-Mantel (P7)
Slots: `FORM=zylinder`, `MASSE=Ø40 H80`, `F-TYP=bohrung`, `F-MASSE=Ø8`, `FACE=Mantel`, `POSITION=P7(halbe Hoehe, 30° von oben gesehen)`, `TIEFE=10`
→ "Zylinder Ø40 Hoehe 80, auf dem Mantel auf halber Hoehe, von oben gesehen um 30° versetzt, eine Bohrung Ø8, 10mm tief"

### Beispiel E: Mehrere Features hintereinander (Komplexitaet durch Wiederholung)
→ "100x100x20 Platte. Oben eine Bohrung Ø10 zentral. Oben 4 Bohrungen Ø5 je 15mm von den Kanten. Rechts eine Tasche 30x20x5 tief zentral. Vorne eine Nut 5x5 durchgehend entlang der X-Achse."

### Beispiel F: Assembly (2 Teile)
→ "Wuerfel 50mm. Rechts daneben eine Platte 40x40x20 hochkant, obere linke Ecke auf linker Kante, 10mm von oben, 10° CCW gedreht."

---

## 5. Negativbeispiele (mit einbeziehen!)

| Beschreibung | Erwartetes Verhalten |
|---|---|
| "Bohrung oben rechts" (ohne Abstaende) | LLM nimmt Default: Eck-Abstand = halbe Materialstaerke ODER Rueckfrage |
| "Bohrung oben mittig rechts" | Mehrdeutig → Rueckfrage |
| "Bohrung auf der 20x100-Flaeche" nach "hochkant" | LLM muss Roh-Face vs. globale Face unterscheiden |
| "Bohrung durch alle Teile" bei 1-Teil-Specification | Tiefe = Materialdicke, kein Fehler |

---

## 6. Minimal-Paare (Trainingswert hoch)

| A | B | Unterschied |
|---|---|---|
| "10mm von oben" | "10mm oberhalb" | (A) innerhalb Face, (B) ausserhalb Teil (Ueberstand) |
| "bündig rechts" | "rechts anliegend" | semantisch gleich — beide zu P4(0 Offset) |
| "45° gedreht" | "diagonal" | gleich (45° CW) |
| "um 45° CCW" | "um -45°" | gleich |
| "obere Ecke auf Kante" | "obere Kante auf Ecke" | unterschiedlicher Anker-Punkt |

---

## 7. Target-Coverage (wann ist die Matrix "abgedeckt"?)

Coverage-Ziel fuer Stufe 1:
- Jede FORM mindestens einmal
- Jede FACE mindestens einmal pro FORM
- Jede POSITION-Klasse (P0–P7) mindestens 3x in unterschiedlichen Kontexten
- Jeder F-TYP mit mindestens P0, P2, P5 kombiniert
- Jeder SPRACHSTIL mindestens 10x
- Mindestens 20 Mehr-Feature-Beispiele (≥3 Features hintereinander)
- Mindestens 10 Negativ- und 10 Minimal-Paar-Beispiele

Grobe Schaetzung: **150–250 Beispiele** decken die Matrix sauber ab.

---

## 8. Nutzung

**Siehe [SONNET_PLAN.md](SONNET_PLAN.md) fuer den konkreten Workflow.**

Kurzversion:
1. Sonnet (oder andere LLM) erzeugt **komplette Pipeline-Traces** — nicht nur Texte,
   sondern auch die Ground-Truth pro Agent (inventar, teil_def, blueprint, ...)
2. Traces werden in `reference_traces.py` oder einer neuen Datei angehaengt
3. `agent_contracts.py` projiziert pro Agent automatisch die Trainings-Paare
4. `train_dspy.py` trainiert auf dem vergroesserten Trainset
5. Optimierte Prompts landen in `data/dspy_optimized/*.json`

**Wichtig:** Sonnet annotiert den ganzen Trace. Damit sind Agent-Splits/Merges
spaeter ohne Re-Annotation moeglich.
