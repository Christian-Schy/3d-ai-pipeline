import re

import structlog

log = structlog.get_logger()


class CodeExtractor:
    """Extracts Python code from a raw LLM response.
    
    The model usually wraps code in ```python ... ```.
    If it forgets the wrapper, we fall back to using the raw text.
    """

    def extract(self, text: str) -> str:
        """Extract code from the response and return it as a plain string."""

        match = re.search(r"```python\s*(.*?)```", text, re.DOTALL)

        if match:
            code = match.group(1).strip()
            code = self._sanitize(code)
            log.info("code_extracted", method="markdown_block", lines=code.count("\n") + 1)
            return code

        # Fallback: model returned code without markdown wrapper
        log.warning("code_extracted", method="fallback_raw_text")
        return self._sanitize(text.strip())

    # ------------------------------------------------------------------

    _BANNED_IMPORTS = re.compile(
        r"^\s*import\s+cadquery|^\s*from\s+cadquery|^\s*OUTPUT_PATH\s*=",
        re.MULTILINE,
    )

    def _sanitize(self, code: str) -> str:
        """Remove lines that must never appear in sandbox code."""
        lines = code.splitlines()
        clean = [line for line in lines if not self._BANNED_IMPORTS.match(line)]
        if len(clean) < len(lines):
            removed = len(lines) - len(clean)
            log.warning("code_sanitized", removed_lines=removed)
        return "\n".join(clean)
