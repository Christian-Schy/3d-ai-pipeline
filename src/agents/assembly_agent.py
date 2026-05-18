"""
src/agents/assembly_agent.py — Step 3 of the 3-Step Blueprint Chain.

Takes all individual part definitions and assembles them into a complete
semantic blueprint. Determines:
  - Which part is root (parent=null)?
  - How are parts connected (parent + position relationships)?
  - What is the build order?

Output is the semantic blueprint format consumed by blueprint_resolver
and everything downstream.
"""

import json
import structlog

from src.agents.base import BaseAgent
from src.config.loader import get_config
from src.utils.prompt_loader import load_prompt

log = structlog.get_logger()

_prompt = load_prompt("prompt_assembly.py")
SYSTEM_PROMPT = _prompt.SYSTEM_PROMPT
ASSEMBLY_PROMPT_TEMPLATE = _prompt.ASSEMBLY_PROMPT_TEMPLATE


class AssemblyAgent(BaseAgent):
    """Assembles part definitions into a complete semantic blueprint."""

    name = "assembly"
    dspy_demo_fields = {
        "input_fields": ["specification", "inventar", "teil_definitionen"],
        "output_field": "blueprint",
    }

    def __init__(self):
        cfg = get_config()
        self.model = cfg.models.assembly
        super().__init__()

    def assemble(self, inventar: dict, teil_definitionen: list[dict],
                 specification: str) -> dict:
        """Combine part definitions into a complete semantic blueprint.

        Args:
            inventar: The inventory from Step 1 (teil_count, teile, aktionen).
            teil_definitionen: List of part definitions from Step 2.
            specification: The original user spec for context.

        Returns:
            dict: Complete semantic blueprint (description, build_order, features).
        """
        # Format inventory summary
        inventar_lines = []
        for teil in inventar.get("teile", []):
            inventar_lines.append(
                f"- {teil['id']}: {teil.get('beschreibung', teil.get('type', 'box'))}"
            )
        inventar_summary = "\n".join(inventar_lines)

        # Format teil definitions
        teil_defs_text = json.dumps(teil_definitionen, indent=2, ensure_ascii=False)

        prompt = ASSEMBLY_PROMPT_TEMPLATE.format(
            specification=specification,
            teil_count=inventar.get("teil_count", len(teil_definitionen)),
            inventar_summary=inventar_summary,
            teil_definitionen=teil_defs_text,
        )

        result = self.call_json(prompt, system=SYSTEM_PROMPT)
        result = self._validate(result, inventar, teil_definitionen)
        return result

    def _validate(self, data: dict, inventar: dict,
                  teil_definitionen: list[dict]) -> dict:
        """Validate the assembled blueprint structure."""
        if "features" not in data or not isinstance(data.get("features"), dict):
            raise ValueError("Assembly: 'features' fehlt oder ist kein dict")

        if "build_order" not in data or not isinstance(data.get("build_order"), list):
            raise ValueError("Assembly: 'build_order' fehlt oder ist keine Liste")

        if "description" not in data:
            data["description"] = ""

        # Check: root feature exists (exactly one parent=null)
        roots = [
            fid for fid, feat in data["features"].items()
            if feat.get("parent") is None
        ]
        if len(roots) == 0:
            raise ValueError("Assembly: Kein Root-Feature (parent=null) gefunden")
        if len(roots) > 1:
            self.log.warning("assembly_multiple_roots", roots=roots)

        # Check: all build_order entries exist in features
        for fid in data["build_order"]:
            if fid not in data["features"]:
                self.log.warning("assembly_missing_feature",
                                 build_order_id=fid)

        # Check: all features appear in build_order
        for fid in data["features"]:
            if fid not in data["build_order"]:
                data["build_order"].append(fid)
                self.log.warning("assembly_added_to_build_order", fid=fid)

        # Check: parent references are valid
        for fid, feat in data["features"].items():
            parent = feat.get("parent")
            if parent and parent not in data["features"]:
                self.log.warning("assembly_invalid_parent",
                                 feature=fid, parent=parent)

        # Ensure parent comes before child in build_order
        data["build_order"] = self._sort_build_order(data)

        return data

    def _sort_build_order(self, data: dict) -> list[str]:
        """Topological sort: parents before children."""
        features = data["features"]
        order = []
        visited = set()

        def visit(fid: str):
            if fid in visited or fid not in features:
                return
            parent = features[fid].get("parent")
            if parent and parent not in visited:
                visit(parent)
            visited.add(fid)
            order.append(fid)

        # Start with root(s), then remaining
        for fid, feat in features.items():
            if feat.get("parent") is None:
                visit(fid)
        for fid in features:
            visit(fid)

        return order
