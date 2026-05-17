# Konventions-Bibliothek (ADR 0014 W2)

Geteilte Prompt-Fragmente. Jede Datei hier ist EIN Positionierungs-/
DIN-Konvention-Block, der wortgleich in mehrere Klassifizierer-Prompts
injiziert wird.

**Warum:** Vor W2 lebte z.B. die Ecken-Regel nur im `pocket_classifier`
und fehlte in `hole_/slot_/circular_classifier` — Konventions-
Fragmentierung (ADR 0014 §1). Eine Konvention zu aendern hiess, sie an
mehreren Stellen nachzuziehen, und genau das wurde vergessen.

**Jetzt:** Konvention aendern = eine Datei hier aendern. Sie propagiert
automatisch in jeden Prompt, der sie via `load_convention()` einbindet.

## Mechanik

`src/utils/prompt_loader.load_convention("<name>")` liest
`data/prompts/conventions/<name>.md` und gibt den Text zurueck. Die
`prompt_classifier_*.py`-Dateien setzen ihr `SYSTEM_PROMPT` aus einem
klassifizierer-spezifischen Kopf + diesen Fragmenten zusammen.

## Fragmente

| Datei | Inhalt | Eingebunden von |
|---|---|---|
| `seite.md` | Seiten-Vokabular + Face-Auswahl + PARENT-Erbung | alle |
| `punkt_positionierung.md` | abstand_*/versatz_* fuer punktfoermige Features | hole, grid, circular, linear |
| `flaeche_positionierung.md` | abstand_* vs kante_* (edge-to-center vs edge-to-edge) + buendig | pocket, slot |
| `ecken_regel.md` | Feature in Face-Ecke → zwei abstand_-Keys, Bewegungsrichtung-Mapping | pocket, hole, slot, grid, circular, linear |
| `rotation.md` | rotation_deg Vorzeichen (CCW positiv, CW negativ) | pocket, slot, grid, linear |
| `json_only.md` | Antwort-Format-Abschluss | alle |

Quelle der Konventionen: `docs/conventions/` (DIN-Dokumente).
