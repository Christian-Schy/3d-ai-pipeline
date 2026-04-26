# Feature Types Enum — Alle erkennbaren Feature-Typen
Tags: feature, typ, enum, katalog, klassifikation

## Feature-Katalog

### Grundkörper (root)
| Typ | Beschreibung |
|-----|-------------|
| `base_plate` | Rechteckige Platte/Block als Basis |
| `base_cylinder` | Zylindrische Basis (Nabe, Welle, Scheibe) |
| `base_sphere` | Kugelförmige Basis |

### Additive Features (union)
| Typ | Beschreibung |
|-----|-------------|
| `extrusion_rect` | Rechteckiger Aufsatz/Steg/Rippe |
| `extrusion_round` | Zylindrischer Boss/Nocke/Flansch |
| `extrusion_custom` | Freiform-Profil extrudiert |
| `step` | Stufe/Absatz (Box auf Face) |

### Subtraktive Features (cut)
| Typ | Beschreibung |
|-----|-------------|
| `hole_single` | Einzelne Bohrung (Durchgang oder Sackloch) |
| `hole_counterbore` | Stufenbohrung (zylindrische Senkung) |
| `hole_countersink` | Kegelsenkung |
| `pocket_rect` | Rechteckige Tasche/Vertiefung |
| `pocket_round` | Runde Tasche |
| `slot` | Nut/Langloch |
| `cutout` | Durchgangs-Ausschnitt (beliebige Form) |

### Muster (pattern)
| Typ | Beschreibung |
|-----|-------------|
| `hole_pattern_grid` | Lochraster (Reihen × Spalten) |
| `hole_pattern_circular` | Lochkreis/Bolt Circle |
| `pattern_linear` | Lineares Muster eines Features |
| `pattern_polar` | Polares Muster eines Features |
| `pattern_mirror` | Gespiegeltes Feature |

### Modifikationen (modify)
| Typ | Beschreibung |
|-----|-------------|
| `fillet` | Kantenverrundung |
| `chamfer` | Fase |
| `shell` | Aushöhlung |

### Komplex (advanced)
| Typ | Beschreibung |
|-----|-------------|
| `revolve` | Rotationskörper |
| `sweep` | Pfad-Extrusion |
| `loft` | Übergang zwischen Querschnitten |
| `thread` | Gewinde |
| `gear` | Zahnrad |

## Klassifikations-Regel
Wähle den SPEZIFISCHSTEN Typ. Beispiel:
- "Lochkreis" → `hole_pattern_circular` (nicht `hole_single`)
- "4 Löcher in den Ecken" → `hole_single` × 4 mit Positionen (kein Pattern)
- "Boss auf Platte" → `extrusion_round` (nicht `base_cylinder`)
