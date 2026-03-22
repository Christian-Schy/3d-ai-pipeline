# CLAUDE.md — Prompt-Arbeitsbereich

## Beim Bearbeiten von Prompts

### Kontextqualität prüfen (nicht Token-Kosten!)
Die Modelle haben große Kontextfenster (128-250k), aber die Qualität
der Antwort sinkt bei zu langem Input. Es geht nicht um Kosten sondern
um die Aufmerksamkeitsspanne des Modells:

- **9b:** Max ~13 Regeln. Darüber ignoriert das Modell Regeln oder halluziniert.
- **35b:** Deutlich mehr Kapazität (~20-25 Regeln), kann Chain-of-Thought.
- **30b Coder:** Code-spezialisiert, braucht gute Beispiele, verträgt längere Kontexte.

### Prompt-Änderungs-Workflow
1. Öffne den Prompt
2. Identifiziere: Welcher LLM-Output ist falsch?
3. Formuliere eine Regel die das verhindert
4. Prüfe Kollision mit bestehenden Regeln
5. Füge die Regel an der richtigen Stelle ein (Priorität!)
6. Zähle Regelanzahl (9b ≤ 13, 35b ≤ 25)
7. Teste mit echtem Pipeline-Run (nicht nur Unit Test)

### Regeln für 9b-Modell-Prompts
- Max 13 Regeln (hart getestet — darüber wird ignoriert)
- Jede Regel max 1-2 Sätze
- Nummerierte Listen, keine Prosa
- Enum-Werte explizit auflisten
- JSON-Schema im Prompt für Output-Format
- 1 konkretes Beispiel (Input → Output)
- NIEMALS "denke nach" oder "überlege" — direkte Anweisungen

### Regeln für 35b-Prompts (Interpreter, Planner)
- Bis ~25 Regeln möglich
- Chain-of-Thought: "Denke Schritt für Schritt" funktioniert hier
- 2-3 Beispiele (positiv + negativ)
- Komplexere Reasoning-Aufgaben OK
- Output-Schema trotzdem strikt vorgeben
- Notes/Freitext-Felder im Output auf Länge begrenzen
