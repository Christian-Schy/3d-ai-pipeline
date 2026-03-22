"""
src/agents/code_fixer.py — Phase 2 specialist: analyzes repeated code failures.

The CodeFixer is called when the Coder has failed 2+ times.
At that point, the error is probably not a simple typo — there's a
pattern to the failure that needs diagnosis.

What CodeFixer does:
  - Reads all previous error messages and failed code attempts
  - Identifies the root cause (wrong API usage, wrong geometry approach, etc.)
  - Writes a concrete fix_plan string
  - Coder reads fix_plan on its next attempt as additional guidance

Why not just give Coder more attempts?
  After 2 failures with the same approach, more attempts of the same thing
  won't help. CodeFixer forces a step back: diagnose first, then fix.

Model: qwen3:8b — diagnosis doesn't need the big model, Coder does the heavy lifting.
"""

import json
import structlog
from src.agents.base import BaseAgent
from src.graph.state import PipelineState
from src.utils.prompt_loader import load_prompt

log = structlog.get_logger()

_prompt = load_prompt("prompt_code_fixer.py")
SYSTEM_PROMPT = _prompt.SYSTEM_PROMPT


class CodeFixerAgent(BaseAgent):
    """Diagnoses repeated code failures and produces a fix plan for the Coder.

    Called by code_fixer_node in Phase 2 of the error loop.
    Returns {"fix_plan": str} — written to state, read by coder_node.
    """

    name = "code_fixer"

    @property
    def model(self) -> str:
        from src.config.loader import get_config
        return get_config().models.code_fixer

    def diagnose(self, state: PipelineState) -> dict:
        """Analyze the failure pattern and return a fix plan.

        Returns: {"fix_plan": "..."}
        """
        error = state.get("execution_error") or state.get("validation_error", "")
        code = state.get("code", "")
        blueprint = state.get("blueprint", {})
        attempts = state.get("attempts", 0)

        self.log.info("code_fixer_start", attempts=attempts, error=error[:80])

        prompt = (
            f"## Failed after {attempts} attempts\n\n"
            f"## Blueprint\n```json\n{json.dumps(blueprint, indent=2)}\n```\n\n"
            f"## Last code that failed\n```python\n{code[:2000]}\n```\n\n"
            f"## Error message\n{error}\n\n"
            "Diagnose the root cause and write a fix plan."
        )

        # Fast-path: known error patterns don't need LLM diagnosis
        fast_fix = self._fast_fix(error, code)
        if fast_fix:
            self.log.info("code_fixer_fast_fix", pattern=fast_fix[:60])
            return {"fix_plan": fast_fix}

        try:
            raw = self.call(prompt, system=SYSTEM_PROMPT)
        except (ConnectionRefusedError, ValueError) as e:
            self.log.warning("code_fixer_fallback", error=str(e))
            return {"fix_plan": "Could not reach LLM. Try reducing complexity or check the error message manually."}

        # Parse plain-text format: ROOT_CAUSE: ... / FIX_PLAN: ...
        root_cause, fix_plan = "", ""
        for line in raw.splitlines():
            if line.startswith("ROOT_CAUSE:"):
                root_cause = line[len("ROOT_CAUSE:"):].strip()
            elif line.startswith("FIX_PLAN:"):
                fix_plan = line[len("FIX_PLAN:"):].strip()
            elif fix_plan:
                fix_plan += "\n" + line  # continuation lines

        if not fix_plan:
            fix_plan = raw.strip()  # fallback: use whole response

        self.log.info("code_fixer_done",
                      root_cause=root_cause[:80],
                      fix_plan_len=len(fix_plan))

        combined = f"Root cause: {root_cause}\n\nFix plan:\n{fix_plan}" if root_cause else fix_plan
        return {"fix_plan": combined}

    @staticmethod
    def _fast_fix(error: str, code: str) -> str:
        """Return an instant fix plan for known error patterns — no LLM needed."""
        if "fillet" in error.lower() and "fillet" in code:
            return (
                "Root cause: fillet() fails after hole() — CadQuery cannot fillet "
                "edges adjacent to through-holes with this selector.\n\n"
                "Fix plan:\n"
                "1. Remove ALL .fillet() calls from the code completely.\n"
                "2. Do NOT replace fillet with chamfer — omit edge treatment entirely.\n"
                "3. Keep the rest of the code unchanged."
            )

        if "NearestToPointSelector" in error and "NameError" in error:
            return (
                "Root cause: NearestToPointSelector ist nicht importiert.\n\n"
                "Fix plan:\n"
                "1. Stelle sicher, dass ganz oben im Code steht: "
                "from cadquery.selectors import NearestToPointSelector\n"
                "2. Nichts anderes am Code ändern."
            )

        if "Workplane.__init__() got an unexpected keyword argument" in error:
            return (
                "Root cause: cq.Workplane() bekommt ungültige kwargs (z.B. centerOption).\n\n"
                "Fix plan:\n"
                "1. cq.Workplane() akzeptiert NUR einen Ebenen-String, z.B. cq.Workplane('XY')\n"
                "2. centerOption gehört zu .workplane() bei Face-Selektion, NICHT zu cq.Workplane()\n"
                "3. FALSCH: cq.Workplane('XY', centerOption='CenterOfBoundBox')\n"
                "4. RICHTIG: body.faces('>Z').workplane(centerOption='CenterOfBoundBox')\n"
                "5. Restlichen Code unverändert lassen."
            )

        if "got an unexpected keyword argument" in error and any(
            k in error for k in ("slot2D", "rect", "circle", "polygon", "ellipse")
        ):
            return (
                "Root cause: CadQuery 2D-Primitiv mit ungültigem Keyword-Argument aufgerufen.\n\n"
                "Fix plan:\n"
                "1. slot2D(length, diameter) — NUR Positionsargumente! KEIN centered, KEIN width, KEIN height!\n"
                "2. rect(xLen, yLen) — NUR Positionsargumente! KEIN length, KEIN width als Kwarg!\n"
                "3. circle(radius) — NUR Positionsargument! KEIN diameter, KEIN r als Kwarg!\n"
                "4. Alle erfundenen Keyword-Arguments entfernen — NUR die dokumentierten Positionsargumente verwenden.\n"
                "5. Restlicher Code unverändert lassen."
            )

        if "'tuple' object has no attribute" in error and "cylinder" in code.lower():
            return (
                "Root cause: Zylinder-Stapelung über neues cq.Workplane() + union() "
                "statt face-basiertem .circle().extrude().\n\n"
                "Fix plan:\n"
                "1. NIEMALS eine neue cq.Workplane()-Instanz für gestapelte Zylinder erstellen\n"
                "2. RICHTIG für jeden add_*() Zylinder auf vorherigem Zylinder:\n"
                "   return (body.faces('>Z')\n"
                "           .workplane(centerOption='CenterOfBoundBox')\n"
                "           .circle(RADIUS)\n"
                "           .extrude(HEIGHT))\n"
                "3. Nach Union-Operationen: NearestToPointSelector statt '>Z' verwenden\n"
                "4. Alle add_*() Funktionen nach diesem Schema umschreiben."
            )

        if "not watertight" in error.lower() or "watertight" in error.lower():
            # Non-manifold mesh — CadQuery/OCCT tessellation problem.
            # Strategy depends on what code approach was used.
            return (
                "Root cause: CadQuery/OCCT erzeugt non-manifold Tessellation bei "
                "Boolean-Operationen (besonders bei flush-edge Kontakt).\n\n"
                "Fix plan — 3 SCHRITTE:\n"
                "1. .clean() nach JEDER .union() und .cut() Operation hinzufügen\n"
                "2. Bei Aufsätzen die bündig an einer Kante sitzen:\n"
                "   Vermeide exakte Kantenkontakt-Geometrie — verwende 0.01mm Inset:\n"
                "   STATT: .translate((20, 0, BASE_Z))  # exakt bündig\n"
                "   BESSER: .translate((19.99, 0, BASE_Z))  # minimaler Inset\n"
                "3. Export mit engerer Toleranz am Ende:\n"
                "   cq.exporters.export(result, OUTPUT_PATH, tolerance=0.001)\n\n"
                "WICHTIG: Ändere NUR diese 3 Dinge. Keine strukturelle Umschreibung nötig."
            )

        # --- Hole pattern anti-patterns ---
        # Manual pushPoints loop instead of rArray for grid patterns
        if ("Null TopoDS_Shape" in error or "No pending wires" in error) and (
            "pushPoints" in code or "push_points" in code
        ):
            return (
                "Root cause: Manueller pushPoints-Loop statt .rArray() für Lochraster.\n"
                "pushPoints erzeugt Punkte, keine Solids — body.cut(wp) schlägt fehl.\n\n"
                "Fix plan:\n"
                "1. LÖSCHE den gesamten manuellen Loop (for i in range... pushPoints...)\n"
                "2. Ersetze durch die korrekte CadQuery-Methode .rArray():\n"
                "   result = (body.faces('>Z')\n"
                "             .workplane(centerOption='CenterOfBoundBox')\n"
                "             .center(OFFSET_X, OFFSET_Y)\n"
                "             .rArray(X_SPACING, Y_SPACING, X_COUNT, Y_COUNT)\n"
                "             .hole(DIAMETER))       # ohne depth = Durchgangsbohrung\n"
                "             .hole(DIAMETER, DEPTH)  # mit depth = Sackloch\n"
                "3. rArray zentriert das Raster automatisch — KEIN manuelles ±spacing/2 nötig\n"
                "4. KEIN .cut() nötig — .hole() schneidet direkt\n"
                "5. Ergebnis direkt zurückgeben: return result.clean()"
            )

        # Discarded return values (immutable CadQuery API)
        if "Null TopoDS_Shape" in error and ".cut(" in code:
            return (
                "Root cause: CadQuery-Methoden geben ein NEUES Objekt zurück.\n"
                "Ergebnis von .hole()/.extrude()/.cut() wurde nicht zugewiesen.\n\n"
                "Fix plan:\n"
                "1. CadQuery ist immutable — jede Operation gibt ein neues Objekt zurück\n"
                "2. FALSCH: wp.hole(10)  ← Ergebnis geht verloren!\n"
                "3. RICHTIG: result = wp.hole(10)  ← Ergebnis speichern!\n"
                "4. Am besten: Methoden-Chain verwenden:\n"
                "   return (body.faces('>Z')\n"
                "           .workplane(centerOption='CenterOfBoundBox')\n"
                "           .hole(DIAMETER, DEPTH)\n"
                "           .clean())\n"
                "5. Prüfe JEDE Zeile: wird das Ergebnis zugewiesen oder geht es verloren?"
            )

        return ""
