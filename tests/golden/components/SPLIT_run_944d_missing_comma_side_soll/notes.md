# SPLIT_run_944d — Splitter merged Aktionen wenn Komma vor "Seite + soll" fehlt

**Status heute (Pre-Fix):** ROT — Splitter produziert 7 Phrasen statt 9.
**Erwartet (Post-Fix):** GRUEN — 9 Phrasen.

## Real-Run-Bug-Befund (User, 2026-05-08)

User-Spec hatte zwei Stellen wo Komma zwischen Aktionen verschluckt wurde:

```
... 20mm tiefe links soll eine nut 10x10 ...
                  ^ kein Komma — splitter merged
... 20mm tiefe unten soll von der unteren ...
                  ^ kein Komma — splitter merged
```

Splitter-Code (`src/tools/aktions_splitter.py:133-136`) splittet aktuell
NUR an Kommas:
```python
def _comma_split(spec: str) -> List[str]:
    return [s.strip() for s in spec.split(",") if s.strip()]
```

Folgefehler stromabwaerts:
- Klassifizierer bekommt 7 Phrasen, kann zwei davon nicht klassifizieren
  (Phrase 2 = rechts-bohrung + links-nut → klassifiziert nur rechts-bohrung,
  links-nut verloren). Phrase 4 = oben-bohrung + unten-bohrung → faellt
  ganz raus.
- 3 von 9 Aktionen verschwinden komplett vor feature_definierer.

## Zwei moegliche Fix-Pfade

**Fix A (deterministisch, im Splitter):** Pre-Processor regext
`(\b(?:tiefe|breite|hoehe|durchmesser|radius)\b\s+)(\b(?:oben|unten|rechts|links|vorne|hinten)\b\s+soll)`
und insertiert Komma vor dem zweiten Match. Damit findet `_comma_split`
die Grenze.

**Fix B (LLM, im Punctuation-Agent):** Trainings-Cases mit genau diesem
Pattern; Punctuation-Agent muss das Komma einfuegen bevor Splitter laeuft.

Empfehlung (siehe Diskussion 2026-05-08): **beides**. Fix B ist die
saubere Wurzel-Behebung, Fix A ist der Sicherheits-Guertel falls
Punctuation patzt.

## Test-Workflow

1. Heute: `pytest tests/golden/components/ -k SPLIT_run_944d` → ROT
2. Splitter um Pre-Processor erweitern (Fix A) ODER Punctuation
   verbessern (Fix B + erweiterten Test mit punctuierter spec.txt)
3. `pytest tests/golden/components/` → GRUEN, alle anderen ebenfalls
4. Wenn ein anderer Run wieder dieses Pattern sieht: regression-frei.

## Erwartete 9 Phrasen

1. `oben soll von der hinteren kante entfernt um 20mm und von der rechten kante 10mm entfernt eine 20mm bohrung hin mit 10mm tiefe`
2. `rechts vom würfel soll eine nut entlang der y-achse mit 5x5 hin`
3. `rechts soll 10mm über der mitte eine 10mm bohrung hin mit 20mm tiefe`
4. `links soll eine nut 10x10 entlang der z-achse hin`
5. `vorne soll oben rechts jweils von den kanten 10mm entfernt eine 20mm bohrung mit 20mm tiefe hin`
6. `oben soll von der vorderen kante 20mm und von der linken 10mm entfernt eine 20mm bohrung hin mit 20mm tiefe`
7. `unten soll von der unteren kante 10mm entfernt und vond er rechten kante 20mm entfernt eine 10mm bohrung mit 10mm tiefe hin`
8. `unten soll entlang der y-achse eine 5x5 nut hin von der mitte 10mm nach rechts versetzt`
9. `unten soll eine nut entlang der x-ache hin`

Alle teil_id="wuerfel", phrase_idx 0-8, parent_phrase_idx None.

User-Tippfehler ("jweils", "vond er", "x-ache") bewusst aus Original
uebernommen — der Splitter darf nicht von Rechtschreibung abhaengen,
und der Test soll real-input-tolerant sein.
