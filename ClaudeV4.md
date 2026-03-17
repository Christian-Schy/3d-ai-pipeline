# 3D AI Pipeline V2 — Verbesserungsplan

## 1. Architektur-Überblick (Neue Pipeline)

```
User Input (Text/Bild)
    │
    ▼
┌──────────────┐
│  Interpreter  │  (qwen3.5:9b) — Zwei Modi: Initial / Modifikation
│  (bestehend)  │  Versteht Absicht, stellt Rückfragen
└──────┬───────┘
       │
       ▼
┌──────────────────┐
│  Task-Classifier  │  (qwen3.5:9b) — NEU
│                    │  Klassifiziert Task-Typ, Schwierigkeit, wählt RAG-Chunks
└──────┬─────────────┘
       │
       ▼
┌──────────────────┐
│  Prompt-Assembler │  (Deterministisch, KEIN LLM)
│                    │  Baut Planner-Prompt aus Templates + RAG zusammen
└──────┬─────────────┘
       │
       ▼
┌──────────────┐
│   Planner     │  (qwen3.5:27b) — Bekommt jetzt fokussierten, kurzen Prompt
│  (bestehend)  │  Erzeugt CSG-Tree mit expliziten Parametern
└──────┬───────┘
       │
       ▼
┌──────────────────┐
│  Plan-Validator   │  (qwen3.5:9b) — NEU
│                    │  Prüft CSG-Tree auf Logik, Maße, fehlende Parameter
└──────┬─────────────┘
       │
       ▼
┌──────────────┐
│    Coder      │  (qwen3-coder:30b) — Bekommt validierten Plan + Few-Shot
│  (bestehend)  │
└──────┬───────┘
       │
       ▼
┌──────────────────┐
│  Code-Execution   │  (Deterministisch) — bestehend
│  + Geometry Check │  AST, build(), Volume, BBox
└──────┬─────────────┘
       │
       ▼
┌──────────────┐
│   Validator   │  (qwen3.5:9b) — bestehend, mit gezieltem Error-Feedback
│  (bestehend)  │
└──────┘
```

---

## 2. Neue Agents im Detail

### 2.1 Task-Classifier (9B)

**Zweck:** Kategorisiert die Aufgabe und steuert die gesamte nachfolgende Pipeline.

**Input:** Interpretierte Beschreibung vom Interpreter + ggf. aktueller Part-State (BBox, Features)

**Output (Pydantic-Schema):**
```python
class TaskClassification(BaseModel):
    task_type: Literal[
        "primitive_single",       # Einzelnes Grundobjekt (Box, Zylinder, etc.)
        "primitive_composite",    # Mehrere Grundobjekte kombiniert
        "feature_additive",       # Material hinzufügen (Extrusion, Boss, Rippe)
        "feature_subtractive",    # Material entfernen (Bohrung, Nut, Tasche)
        "feature_pattern",        # Muster (Array von Bohrungen, Pattern)
        "modification_transform", # Verschieben, Drehen, Skalieren
        "modification_fillet_chamfer",  # Kanten bearbeiten
        "complex_multi_step"      # Kombination mehrerer Typen
    ]
    difficulty: Literal["low", "medium", "high"]
    requires_current_geometry: bool  # Braucht der Planner BBox/Feature-Info?
    rag_categories: list[Literal[
        "primitives",
        "boolean_ops",
        "holes_single",
        "holes_multiple",
        "slots_grooves",
        "extrude_on_face",
        "fillets_chamfers",
        "patterns_arrays",
        "workplane_selection",
        "sketch_operations",
        "transforms",
        "assemblies"
    ]]
    planner_template: Literal[
        "template_simple",
        "template_boolean",
        "template_feature_add",
        "template_feature_subtract",
        "template_pattern",
        "template_modify",
        "template_complex"
    ]
    warnings: list[str]  # z.B. ["multi_hole_detected", "through_all_needed"]
```

**Prompt (~30 Zeilen):** Kurz, fokussiert, mit klaren Entscheidungsregeln.
Keine CadQuery-Details — nur Task-Verständnis.

---

### 2.2 Prompt-Assembler (Deterministisch)

**Zweck:** Baut den Planner-Prompt dynamisch zusammen. KEIN LLM.

**Logik:**
```python
def assemble_planner_prompt(
    classification: TaskClassification,
    interpreted_description: str,
    current_geometry: GeometryState | None,
    rag_store: RAGStore
) -> str:
    # 1. Basis-Template laden
    template = load_template(classification.planner_template)
    
    # 2. Relevante Regeln einfügen (NUR die für diesen Task-Typ)
    rules = load_rules(classification.task_type)
    
    # 3. RAG-Beispiele holen (max 2-3, nach Ähnlichkeit sortiert)
    examples = rag_store.get_top_k(
        categories=classification.rag_categories,
        query=interpreted_description,
        k=2
    )
    
    # 4. Warnungen als explizite Hinweise einfügen
    warning_rules = [WARNINGS_MAP[w] for w in classification.warnings]
    
    # 5. Geometry-Kontext (wenn nötig)
    geo_context = ""
    if classification.requires_current_geometry and current_geometry:
        geo_context = format_geometry_context(current_geometry)
    
    # 6. Zusammenbauen
    return template.format(
        description=interpreted_description,
        rules=rules,
        examples=examples,
        warnings=warning_rules,
        geometry=geo_context
    )
```

**Ergebnis:** Statt 150 Zeilen bekommt der Planner 40-70 Zeilen,
die ALLE relevant für genau diesen Task sind.

---

### 2.3 Plan-Validator (9B)

**Zweck:** Fängt Planner-Fehler ab BEVOR der teure 30B-Coder läuft.

**Prüft:**
- Sind alle Dimensionen explizit angegeben? (Keine impliziten Werte)
- Ist die Schnitttiefe bei subtraktiven Ops korrekt?
  - "Nut auf Oberfläche" → Tiefe < Teilhöhe
  - "Bohrung durch alles" → cutThruAll, nicht cutBlind
- Stimmen die Koordinatenreferenzen?
- Sind Boolesche Operationen in der richtigen Reihenfolge?
- Bei multi-hole: Sind Positionen als Liste definiert?

**Output:**
```python
class PlanValidation(BaseModel):
    is_valid: bool
    issues: list[PlanIssue]
    suggested_fixes: list[str]
    
class PlanIssue(BaseModel):
    severity: Literal["error", "warning"]
    step_index: int
    issue_type: str  # z.B. "missing_depth", "ambiguous_reference"
    description: str
```

---

## 3. Geometry-State-Tracking (Löst Center-Problem)

### Problem
Aktuell: Immer Center des ersten Teils als Referenz.
Das scheitert bei gestapelten/kombinierten Teilen.

### Lösung: GeometryState nach jedem Schritt aktualisieren

```python
class GeometryState(BaseModel):
    """Wird nach jedem erfolgreichen build() aktualisiert."""
    
    # Bounding Box
    bbox_min: tuple[float, float, float]
    bbox_max: tuple[float, float, float]
    bbox_center: tuple[float, float, float]
    
    # Dimensionen
    total_width: float   # X
    total_depth: float   # Y  
    total_height: float  # Z
    
    # Volumen
    volume: float
    
    # Verfügbare Flächen für Workplane-Selektion
    faces: list[FaceInfo]
    
    # Feature-History (was wurde schon gemacht)
    features: list[str]  # z.B. ["base_box_80x60x20", "hole_d10_center", "boss_30x30x15_top"]

class FaceInfo(BaseModel):
    face_id: str          # z.B. "top", "bottom", "front", ">Z", "<Y"
    normal: tuple[float, float, float]
    center: tuple[float, float, float]
    area: float
```

**Extraktion nach jedem build():**
```python
def extract_geometry_state(result) -> GeometryState:
    bb = result.val().BoundingBox()
    return GeometryState(
        bbox_min=(bb.xmin, bb.ymin, bb.zmin),
        bbox_max=(bb.xmax, bb.ymax, bb.zmax),
        bbox_center=(bb.center.x, bb.center.y, bb.center.z),
        total_width=bb.xmax - bb.xmin,
        total_depth=bb.ymax - bb.ymin,
        total_height=bb.zmax - bb.zmin,
        volume=result.val().Volume(),
        # ... faces extraction
    )
```

**Vorteil:** Der Planner weiß EXAKT wie das Teil gerade aussieht,
nicht nur wo der ursprüngliche Center war.

---

## 4. CadQuery-Funktionsabdeckung — Kategorisierte RAG-Struktur

Statt wenige große RAG-Dateien → viele kleine, kategoriespezifische.
Der Task-Classifier wählt nur die relevanten aus.

### 4.1 Grundkörper (primitives)
```
rag/primitives/
├── box.py              # Workplane("XY").box(L, W, H)
├── cylinder.py         # .cylinder(height, radius)
├── sphere.py           # .sphere(radius)
├── cone.py             # .cone(r_bottom, r_top, height) — ACHTUNG: CQ-Syntax!
├── wedge.py            # .wedge(dx, dy, dz, ...)
├── torus.py            # .torus(r_major, r_minor) — ACHTUNG: nicht .donut()!
└── polyhedron.py       # Freiform über Vertices
```

### 4.2 Sketch-Operationen (sketch_operations)
```
rag/sketch/
├── rect.py             # .rect(w, h)
├── circle.py           # .circle(r)
├── polygon.py          # .polygon(n_sides, diameter)  — ACHTUNG: Durchmesser, nicht Radius!
├── slot.py             # .slot2D(length, diameter)
├── spline.py           # .spline([points])
├── text.py             # .text("ABC", fontsize, distance)
├── offset.py           # .offset2D(distance)
└── combined_sketch.py  # Mehrere Sketches auf einer Workplane
```

### 4.3 Extrusion & Bodies (extrude_operations)
```
rag/extrude/
├── extrude_simple.py       # .extrude(height)
├── extrude_both.py         # .extrude(h, both=True)
├── extrude_taper.py        # .extrude(h, taper=angle)
├── extrude_on_face.py      # Workplane auf bestehender Fläche → extrude
├── revolve.py              # .revolve(angle, axis)
├── sweep.py                # .sweep(path)
├── loft.py                 # .loft([sections])
└── shell.py                # .shell(thickness)
```

### 4.4 Subtraktive Features (subtractive_features)
```
rag/subtractive/
├── hole_single.py          # .hole(diameter, depth=None)  — None = through all
├── hole_multiple.py        # .pushPoints([(x,y),...]).hole(d)
│                           # CRITICAL: pushPoints MUSS eine Liste von Tupeln sein
├── hole_countersink.py     # .cskHole(d, csk_d, csk_angle)
├── hole_counterbore.py     # .cboreHole(d, cb_d, cb_depth)
├── slot_groove.py          # .slot2D().cutBlind(depth)
│                           # WARNUNG: cutBlind(depth) — depth MUSS < Teilhöhe sein!
├── groove_surface.py       # Nut AUF Oberfläche (nicht durch Teil!)
│                           # Pattern: .workplane(offset=height-depth).rect().cutBlind(depth)
├── pocket.py               # .rect(w,h).cutBlind(depth)
├── cutThruAll.py           # .cutThruAll() — schneidet durch ALLES
│                           # WICHTIG: Nur verwenden wenn "durch alles/ganzes Teil" gewünscht
├── cut_at_angle.py         # Schnitt unter Winkel
└── boolean_cut.py          # result = part1.cut(part2)
```

### 4.5 Boolesche Operationen (boolean_ops)
```
rag/boolean/
├── union.py                # result = part1.union(part2)
├── cut.py                  # result = part1.cut(part2)
├── intersect.py            # result = part1.intersect(part2)
├── combine_then_cut.py     # WICHTIG: Erst union, DANN cutThruAll
│                           # Löst das "Bohrung nur durch erste Platte"-Problem
└── order_matters.py        # Beispiele wo Reihenfolge kritisch ist
```

### 4.6 Muster & Arrays (patterns_arrays)
```
rag/patterns/
├── linear_pattern.py       # Lineares Array von Features
├── polar_pattern.py        # .polarArray(radius, start, angle, count)
├── rect_pattern.py         # .rarray(xSpacing, ySpacing, xCount, yCount)
├── pushPoints_custom.py    # .pushPoints([(x1,y1), (x2,y2), ...])
│                           # Für beliebige Positionen
├── pattern_on_face.py      # Pattern auf nicht-XY-Fläche
└── mirror.py               # .mirror("XY") / .mirror("XZ")
```

### 4.7 Kanten-Features (fillets_chamfers)
```
rag/edges/
├── fillet_all.py           # .edges().fillet(radius)
├── fillet_selected.py      # .edges("|Z").fillet(r) — nur vertikale Kanten
│                           # Selektoren: |Z, |X, |Y, >Z, <Z, >X, <X, >Y, <Y
├── fillet_by_length.py     # .edges(selectors.LengthNthSelector(0)).fillet(r)
├── chamfer_all.py          # .edges().chamfer(distance)
├── chamfer_selected.py     # .edges("|Z").chamfer(d)
└── chamfer_asymmetric.py   # .edges().chamfer(d1, d2)
```

### 4.8 Workplane-Selektion (workplane_selection)
```
rag/workplanes/
├── standard_planes.py      # "XY", "XZ", "YZ", "front", "back", etc.
├── face_selection.py       # .faces(">Z").workplane()
│                           # ">Z" = höchste Z-Fläche (top)
│                           # "<Z" = niedrigste Z-Fläche (bottom)
├── offset_workplane.py     # .workplane(offset=10)
├── transformed_wp.py       # .transformed(offset=(x,y,z), rotate=(rx,ry,rz))
├── center_vs_origin.py     # .center(x,y) verschiebt WP-Zentrum
│                           # WICHTIG: center() ist relativ, nicht absolut!
└── nested_workplanes.py    # Workplane auf Workplane
```

### 4.9 Transformationen (transforms)
```
rag/transforms/
├── translate.py            # .translate((dx, dy, dz))
├── rotate.py               # .rotate((0,0,0), (0,0,1), angle)  — Achse + Winkel
├── scale.py                # Nur über CQ Assembly oder manuell
└── mirror_body.py          # .mirror("XY", basePointVector=(0,0,0))
```

---

## 5. Bekannte Fehler — Spezifische Fixes

### 5.1 Nut schneidet durch gesamtes Teil
**Ursache:** Planner gibt keine Tiefe an oder Coder nutzt cutThruAll statt cutBlind.

**Fix im Task-Classifier:**
```python
# Warnung triggern wenn "Nut" + "auf/entlang" erkannt wird
if "slot" in task_type or "groove" in task_type:
    if not "through" in description.lower():
        warnings.append("groove_surface_only")
```

**Fix im Planner-Template (template_feature_subtract):**
```
REGEL: Bei Nuten/Slots die NICHT "durch das gesamte Teil" gehen sollen:
- IMMER cutBlind(tiefe) verwenden, NIEMALS cutThruAll()
- Tiefe MUSS explizit angegeben werden
- Tiefe MUSS kleiner sein als die Dimension des Teils in Schnittrichtung
- Beispiel: Nut 5x5 auf Oberseite eines 20mm hohen Teils → cutBlind(5), NICHT cutThruAll
```

### 5.2 Bohrungen nur durch erste Platte bei gestapelten Teilen
**Ursache:** Teile werden nicht vorher vereinigt (union), oder cutBlind statt cutThruAll.

**Fix — Neue Regel für Planner:**
```
REGEL BEI "BOHRUNG DURCH GESAMTES TEIL":
1. ZUERST alle Körper mit .union() vereinigen
2. DANN Workplane auf der gewünschten Fläche erstellen
3. DANN .cutThruAll() verwenden (NICHT .hole(d, depth) mit fester Tiefe)

FALSCH:
  plate1 = Workplane("XY").box(100,100,10)
  plate2 = plate1.faces(">Z").workplane().box(50,50,15)
  result = plate2.faces(">Z").workplane().hole(10, 10)  # Nur durch plate2!

RICHTIG:
  plate1 = Workplane("XY").box(100,100,10)
  plate2 = plate1.faces(">Z").workplane().box(50,50,15)
  combined = plate1.union(plate2)  # ERST vereinigen!
  result = combined.faces(">Z").workplane().hole(10)  # None = through all
```

### 5.3 Mehrere Bohrungen gleichzeitig fehlerhaft
**Ursache:** pushPoints-Syntax falsch oder Positionen relativ statt absolut.

**Fix — Dedizierte RAG-Datei (holes_multiple.py):**
```python
# PATTERN: Mehrere Bohrungen auf einer Fläche
# IMMER pushPoints mit Liste von (x, y) Tupeln verwenden

import cadquery as cq

# Beispiel: 4 Bohrungen in den Ecken einer 100x80 Platte
# Bohrungen d=8mm, Abstand 10mm vom Rand
result = (
    cq.Workplane("XY")
    .box(100, 80, 20)
    .faces(">Z").workplane()
    .pushPoints([
        ( 40,  30),   # rechts-hinten  (100/2 - 10, 80/2 - 10)
        (-40,  30),   # links-hinten
        ( 40, -30),   # rechts-vorne
        (-40, -30),   # links-vorne
    ])
    .hole(8)          # diameter=8, depth=None → through all
)

# WICHTIG:
# - Koordinaten sind RELATIV zum Workplane-Center
# - Bei .box() ist der Center = Mittelpunkt des Rechtecks
# - pushPoints akzeptiert NUR eine Liste von Tupeln
# - NICHT: .pushPoints([(40, 30)]).hole(8).pushPoints([(-40, 30)]).hole(8)
#   SONDERN: Alle Punkte in EINER pushPoints-Liste!
```

---

## 6. RAG-Strategie — Weniger ist mehr

### Aktuelle Probleme
- Coder bekommt zu viele RAG-Beispiele → Aufmerksamkeit verwässert
- Planner bekommt zu wenige → macht Fehler bei Spezialfällen
- Kein System zur Auswahl der richtigen RAGs

### Neue Strategie

**Regel: Max 2-3 RAG-Chunks pro Agent pro Request**

```
Task-Classifier Output: rag_categories = ["holes_multiple", "boolean_ops"]
                                              │
                                              ▼
Prompt-Assembler wählt:
  Für Planner:  1x holes_multiple Regel-Snippet + 1x boolean Regel-Snippet
  Für Coder:    1x holes_multiple.py Beispiel + 1x combine_then_cut.py Beispiel
```

**RAG-Dateien aufteilen:**
```
rag/
├── rules/          # Kurze Regel-Snippets für den PLANNER (je 5-15 Zeilen)
│   ├── rules_holes.md
│   ├── rules_grooves.md
│   ├── rules_boolean_order.md
│   ├── rules_workplane.md
│   └── ...
│
├── examples/       # Code-Beispiele für den CODER (je 15-30 Zeilen)
│   ├── primitives/
│   ├── subtractive/
│   ├── boolean/
│   ├── patterns/
│   └── ...
│
└── few_shot/       # Erfolgreiche Runs aus JSONL (Input→Output Paare)
    ├── simple/
    ├── medium/
    └── complex/
```

---

## 7. Planner-Template-System

### Statt einem 150-Zeilen-Prompt → 7 fokussierte Templates

**template_simple.md** (~30 Zeilen)
- Für einzelne Grundkörper
- Minimale Regeln, klare Dimension-Anforderungen

**template_boolean.md** (~40 Zeilen)
- Für kombinierte Körper
- Regeln für union/cut Reihenfolge
- BBox-Tracking Pflicht

**template_feature_subtract.md** (~50 Zeilen)
- Für Bohrungen, Nuten, Taschen
- Explizite Tiefenregel (cutBlind vs cutThruAll)
- Workplane-Selektions-Regeln
- Warnung bei "durch alles" → erst union prüfen

**template_feature_add.md** (~40 Zeilen)
- Für Boss, Rippe, Extrusion auf Fläche
- Workplane-auf-Face-Regeln
- is_additive Flag

**template_pattern.md** (~45 Zeilen)
- Für Arrays, Muster, mehrere gleiche Features
- pushPoints-Regeln
- Koordinaten-System-Erklärung

**template_modify.md** (~35 Zeilen)
- Für Fillets, Chamfers, Transforms
- Kanten-Selektor-Referenz
- Reihenfolge-Regeln (Fillets NACH allen Features)

**template_complex.md** (~60 Zeilen)
- Für Multi-Step-Aufgaben
- Schrittweise Abarbeitung mit Zwischenvalidierung
- Geometry-State nach jedem Schritt

---

## 8. Implementierungs-Reihenfolge

### Phase 1: Quick Wins (1-2 Tage)
- [ ] RAG-Dateien aufteilen in categories-Struktur (rules/ + examples/)
- [ ] GeometryState-Extraktion nach jedem build() implementieren
- [ ] Bekannte Fehler-Fixes in dedizierte RAG-Rules extrahieren
- [ ] Planner-Prompt aufteilen in 7 Templates

### Phase 2: Task-Classifier (2-3 Tage)
- [ ] Pydantic-Schema für TaskClassification
- [ ] Task-Classifier Prompt schreiben + testen
- [ ] Prompt-Assembler (deterministisch) implementieren
- [ ] Integration in Pipeline (nach Interpreter, vor Planner)

### Phase 3: Plan-Validator (1-2 Tage)
- [ ] Pydantic-Schema für PlanValidation
- [ ] Plan-Validator Prompt + Regeln
- [ ] Retry-Loop: Plan-Validator → Planner (max 2x)

### Phase 4: Few-Shot-Retrieval (2-3 Tage)
- [ ] JSONL-Daten nach Erfolg/Misserfolg taggen
- [ ] Ähnlichkeitssuche implementieren (Embedding oder einfaches BM25)
- [ ] Dynamische Few-Shot-Auswahl für Coder integrieren

### Phase 5: Testing & Tuning (fortlaufend)
- [ ] Test-Suite mit 20-30 Standardaufgaben definieren
- [ ] Regressions-Tests (alte Fixes müssen weiterhin funktionieren!)
- [ ] Pro Template: 5 Tests (einfach bis schwer)
- [ ] Metriken: Erfolgsrate, Retry-Rate, Durchlaufzeit

---

## 9. Test-Suite Vorschlag

### Einfach (müssen 95%+ funktionieren)
1. Erstelle eine Box 80x60x20mm
2. Erstelle einen Zylinder d=40mm h=50mm
3. Erstelle eine Box mit einer Bohrung d=10mm in der Mitte
4. Erstelle eine Box mit Fase 2mm an allen Kanten
5. Erstelle eine Box mit Rundung r=3mm an allen Kanten

### Mittel (müssen 80%+ funktionieren)
6. Erstelle eine Box und extrudiere oben einen kleineren Zylinder
7. Erstelle eine Platte mit 4 Bohrungen in den Ecken
8. Erstelle eine Box mit einer Nut 5x5mm auf der Oberseite entlang Y
9. Erstelle eine L-förmige Platte aus zwei Boxen
10. Erstelle eine Platte mit Senkbohrung in der Mitte

### Schwer (müssen 60%+ funktionieren)
11. Erstelle zwei gestapelte Platten mit Bohrung durch beide
12. Erstelle eine Box mit Boss oben und Bohrung durch alles
13. Erstelle ein Teil mit 6 Bohrungen im Kreismuster
14. Erstelle eine Box mit Tasche 40x30x10 und 4 Bohrungen in der Tasche
15. Erstelle ein T-Profil durch Extrusion

---

## 10. Hardware-Optimierung (16GB VRAM / 64GB RAM)

### Modell-Zuweisung
| Agent           | Modell          | Läuft auf | ~Inferenzzeit |
|-----------------|-----------------|-----------|---------------|
| Interpreter     | qwen3.5:9b      | GPU       | 2-4s          |
| Task-Classifier | qwen3.5:9b      | GPU       | 1-3s          |
| Planner         | qwen3.5:27b     | GPU+RAM   | 8-15s         |
| Plan-Validator  | qwen3.5:9b      | GPU       | 2-4s          |
| Coder           | qwen3-coder:30b | GPU+RAM   | 15-30s        |
| Validator       | qwen3.5:9b      | GPU       | 2-4s          |

### Hinweis
Alle 9B-Agents nutzen dasselbe Modell — Ollama hält es im VRAM.
Kein Modell-Wechsel zwischen Interpreter → Task-Classifier → Plan-Validator → Validator.
Der Planner und Coder werden jeweils einzeln geladen wenn sie dran sind.

**Gesamte Pipeline-Zeit (geschätzt):** ~35-60 Sekunden pro Durchlauf
Davon ~10-15s für die 9B-Steps und ~25-45s für Planner+Coder.