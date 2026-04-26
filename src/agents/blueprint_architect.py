"""
src/agents/blueprint_architect.py — Single-shot Blueprint generation from spec.

Replaces the former 5-agent "Häppchen" chain:
  Feature Tagger → Feature Assigner → Feature Position Assigner
  → Part Position Assigner → Blueprint Assembler

One strong model (qwen3.5:35b) now does the complete job in a single call:
  spec + RAG context → complete Feature Tree Blueprint (JSON)

Supports three modes:
  - fresh:  New spec → new blueprint
  - modify: Existing blueprint + change description → updated blueprint
  - fix:    Existing blueprint + validation errors → corrected blueprint
"""

import json
import structlog
from pydantic import ValidationError

from src.agents.base import BaseAgent
from src.config.loader import get_config
from src.graph.feature_tree import FeatureTree
from src.rag.blueprint_rag import BlueprintRAG
from src.utils.prompt_loader import load_prompt

log = structlog.get_logger()

# Load prompt templates
_prompt = load_prompt("prompt_blueprint_architect.py")
SYSTEM_PROMPT = _prompt.SYSTEM_PROMPT
FRESH_PROMPT_TEMPLATE = _prompt.FRESH_PROMPT_TEMPLATE
MODIFY_PROMPT_TEMPLATE = _prompt.MODIFY_PROMPT_TEMPLATE
FIX_PROMPT_TEMPLATE = _prompt.FIX_PROMPT_TEMPLATE


class BlueprintArchitect(BaseAgent):
    """Generates a complete Feature Tree Blueprint from a natural-language spec.

    Uses RAG to inject relevant examples (offset formulas, patterns, face rules)
    into the prompt, then calls qwen3.5:35b with json_mode=True.
    """

    name = "blueprint_architect"

    def __init__(self):
        cfg = get_config()
        self.model = cfg.models.blueprint_architect
        super().__init__()
        self.rag = BlueprintRAG()
        self.rag.build()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self, specification: str) -> dict:
        """Generate a fresh blueprint from a specification.

        Args:
            specification: Natural-language part description (German).

        Returns:
            dict with keys: blueprint (FeatureTree dict), raw_response, rag_chunks_used
        """
        # RAG: find relevant knowledge chunks for this spec
        rag_context = self._get_rag_context(specification)

        prompt = FRESH_PROMPT_TEMPLATE.format(
            rag_context=rag_context,
            specification=specification,
        )

        raw_json = self.call_json(prompt, system=SYSTEM_PROMPT)
        blueprint = self._validate_and_fix(raw_json, specification, rag_context)

        return {
            "blueprint": blueprint,
            "raw_response": raw_json,
            "rag_chunks_used": self.rag.last_chunks_used,
        }

    def modify(self, specification: str, change_description: str,
               previous_blueprint: dict) -> dict:
        """Modify an existing blueprint based on a change description.

        Args:
            specification:      Original spec text.
            change_description: What to change (e.g. "Bohrung größer machen").
            previous_blueprint: The current blueprint dict.

        Returns:
            dict with keys: blueprint, raw_response, rag_chunks_used
        """
        rag_context = self._get_rag_context(
            f"{specification} {change_description}"
        )

        prompt = MODIFY_PROMPT_TEMPLATE.format(
            rag_context=rag_context,
            specification=specification,
            change_description=change_description,
            previous_blueprint=json.dumps(previous_blueprint, indent=2, ensure_ascii=False),
        )

        raw_json = self.call_json(prompt, system=SYSTEM_PROMPT)
        blueprint = self._validate_and_fix(raw_json, specification, rag_context)

        return {
            "blueprint": blueprint,
            "raw_response": raw_json,
            "rag_chunks_used": self.rag.last_chunks_used,
        }

    def fix(self, specification: str, previous_blueprint: dict,
            validation_errors: str) -> dict:
        """Fix a blueprint that failed validation.

        Args:
            specification:     Original spec text.
            previous_blueprint: The broken blueprint dict.
            validation_errors:  String describing what's wrong.

        Returns:
            dict with keys: blueprint, raw_response, rag_chunks_used
        """
        rag_context = self._get_rag_context(
            f"{specification} {validation_errors}"
        )

        prompt = FIX_PROMPT_TEMPLATE.format(
            rag_context=rag_context,
            specification=specification,
            previous_blueprint=json.dumps(previous_blueprint, indent=2, ensure_ascii=False),
            validation_errors=validation_errors,
        )

        raw_json = self.call_json(prompt, system=SYSTEM_PROMPT)
        blueprint = self._validate_and_fix(raw_json, specification, rag_context)

        return {
            "blueprint": blueprint,
            "raw_response": raw_json,
            "rag_chunks_used": self.rag.last_chunks_used,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_rag_context(self, query_text: str) -> str:
        """Query RAG and format results as context block for the prompt."""
        chunks = self.rag.query(query_text)
        if not chunks:
            return ""

        parts = ["## Relevante Referenzen\n"]
        for i, chunk in enumerate(chunks):
            parts.append(f"### Referenz {i + 1} ({chunk['source']}):")
            parts.append(chunk["text"])
            parts.append("")

        return "\n".join(parts)

    def _validate_and_fix(self, raw_json: dict, specification: str,
                          rag_context: str) -> dict:
        """Validate the LLM output against FeatureTree schema.

        If validation fails, attempts one self-correction round.
        Returns the validated blueprint dict.
        Raises ValueError if both attempts fail.
        """
        # First attempt: validate directly
        errors = self._validate_blueprint(raw_json)
        if not errors:
            return raw_json

        self.log.warning("blueprint_validation_failed",
                         errors=errors, attempt=1)

        # Self-correction: ask the model to fix its own output
        fix_prompt = FIX_PROMPT_TEMPLATE.format(
            rag_context=rag_context,
            specification=specification,
            previous_blueprint=json.dumps(raw_json, indent=2, ensure_ascii=False),
            validation_errors="\n".join(errors),
        )

        fixed_json = self.call_json(fix_prompt, system=SYSTEM_PROMPT)
        errors2 = self._validate_blueprint(fixed_json)
        if not errors2:
            self.log.info("blueprint_self_corrected")
            return fixed_json

        # Both attempts failed — return the better one with a warning
        self.log.error("blueprint_validation_failed_twice",
                       errors_attempt1=errors, errors_attempt2=errors2)

        # Return whichever has fewer errors
        if len(errors2) < len(errors):
            return fixed_json
        return raw_json

    def _validate_blueprint(self, data: dict) -> list[str]:
        """Check a blueprint dict against FeatureTree schema and logic rules.

        Returns list of error strings. Empty list = valid.
        """
        errors = []

        # 1. Pydantic schema validation
        try:
            tree = FeatureTree.from_dict(data)
        except (ValidationError, Exception) as e:
            errors.append(f"Schema-Fehler: {e}")
            return errors  # Can't check further without valid tree

        # 2. build_order references must exist in features
        for fid in tree.build_order:
            if fid not in tree.features:
                errors.append(
                    f"build_order enthält '{fid}', aber features hat keinen Eintrag dafür"
                )

        # 3. All features must appear in build_order
        for fid in tree.features:
            if fid not in tree.build_order:
                errors.append(
                    f"Feature '{fid}' existiert in features, fehlt aber in build_order"
                )

        # 4. Parent must appear before child in build_order
        for fid, feature in tree.features.items():
            if feature.parent and feature.parent in tree.features:
                if fid in tree.build_order and feature.parent in tree.build_order:
                    child_idx = tree.build_order.index(fid)
                    parent_idx = tree.build_order.index(feature.parent)
                    if parent_idx >= child_idx:
                        errors.append(
                            f"Parent '{feature.parent}' muss vor Child '{fid}' in build_order stehen"
                        )

        # 5. Parent references must exist
        for fid, feature in tree.features.items():
            if feature.parent and feature.parent not in tree.features:
                errors.append(
                    f"Feature '{fid}' referenziert Parent '{feature.parent}', der nicht existiert"
                )

        # 6. Root feature must have parent=null
        root_count = sum(1 for f in tree.features.values() if f.parent is None)
        if root_count == 0:
            errors.append("Kein Root-Feature (parent=null) gefunden")
        elif root_count > 1:
            errors.append(
                f"Mehrere Root-Features gefunden ({root_count}). Nur eines erlaubt."
            )

        # 7. Child features must have placement
        for fid, feature in tree.features.items():
            if feature.parent and not feature.placement:
                errors.append(
                    f"Feature '{fid}' hat Parent aber kein placement"
                )

        return errors
