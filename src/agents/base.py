"""
src/agents/base.py — Shared foundation for all pipeline agents.

Every agent (Planner, Coder, Validator, ...) inherits from BaseAgent.
Common logic lives here once — not repeated in every agent:
  - Ollama HTTP call
  - JSON-mode response parsing
  - Prompt loading from prompts/ directory
  - structlog setup
"""

import json
import socket
import urllib.request
import urllib.error
import structlog
from pathlib import Path
from src.config.loader import get_config

log = structlog.get_logger()

# Ollama runs locally on the default port
def _ollama_url() -> str:
    return get_config().ollama.base_url + "/api/chat"


# Prompt files live here — one .md file per agent
PROMPTS_DIR = Path("data/prompts/agents")


class BaseAgent:
    """Base class for all pipeline agents.

    Subclasses set:
      model    — which Ollama model to use (e.g. "qwen3:8b")
      name     — used for logging and prompt file lookup

    Subclasses implement:
      run(state) → dict  — reads from PipelineState, returns partial state update
    """

    model: str = "qwen3:8b"   # default; subclasses override
    name: str = "base"

    def __init__(self):
        self.log = structlog.get_logger().bind(agent=self.name)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def call(
        self,
        prompt: str,
        system: str = "",
        json_mode: bool = False,
    ) -> str:
        """Send a prompt to Ollama and return the raw response text.

        Args:
            prompt:    The user message.
            system:    Optional system prompt (sets agent persona + rules).
            json_mode: If True, Ollama is instructed to return valid JSON only.
                       Use this when you need structured output from the model.
                       No regex parsing needed — the model is forced into JSON.

        Returns:
            The model's response as a plain string.
            If json_mode=True this will be a valid JSON string.
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        think, temperature, num_ctx = get_config().get_agent_options(self.name)
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "think": think,
            "options": {
                "temperature": temperature,
                "num_ctx": num_ctx,
            },
        }

        # json_mode tells Ollama to constrain its output to valid JSON.
        # This is much more reliable than asking the model nicely in the prompt.
        if json_mode:
            payload["format"] = "json"

        self.log.info("agent_call_start", model=self.model,
                      prompt_chars=len(prompt), json_mode=json_mode)

        response_text = self._http_post(payload)

        # Store raw response for trace inspection (before JSON parsing etc.)
        self._last_raw_response: str = response_text

        self.log.info("agent_call_done", response_chars=len(response_text))
        return response_text

    @staticmethod
    def _extract_json(text: str) -> str:
        """Extract the first complete JSON object/array from text.

        Handles:
          - Clean JSON: '{"key": "value"}'
          - Markdown fences: '```json\\n{...}\\n```'
          - Freitext before JSON: 'Here is the result:\\n{...}'
          - Trailing text after JSON: '{...}\\nSome explanation'
        """
        clean = text.strip()

        # Step 1: Strip markdown code fences
        if clean.startswith("```"):
            lines = clean.split("\n")
            start_idx = 1  # skip ```json or ```
            end_idx = len(lines)
            for i in range(len(lines) - 1, 0, -1):
                if lines[i].strip().startswith("```"):
                    end_idx = i
                    break
            clean = "\n".join(lines[start_idx:end_idx]).strip()

        # Step 2: Find the first { or [ in the text (skip any preamble)
        json_start = -1
        for i, ch in enumerate(clean):
            if ch in "{[":
                json_start = i
                break

        if json_start < 0:
            return clean  # no JSON found — return as-is, let json.loads fail

        if json_start > 0:
            clean = clean[json_start:]

        # Step 3: Extract the first complete JSON object/array
        if clean and clean[0] in "{[":
            bracket = clean[0]
            close = "}" if bracket == "{" else "]"
            depth = 0
            in_string = False
            escape_next = False
            for i, ch in enumerate(clean):
                if escape_next:
                    escape_next = False
                    continue
                if ch == "\\":
                    escape_next = True
                    continue
                if ch == '"' and not escape_next:
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if ch == bracket:
                    depth += 1
                elif ch == close:
                    depth -= 1
                    if depth == 0:
                        return clean[:i + 1]

        return clean

    def call_json(self, prompt: str, system: str = "") -> dict:
        """Like call(), but parses the response as JSON and returns a dict.

        Use this whenever the agent needs to return structured data
        (e.g. Planner → Blueprint, Interpreter → is_complete signal).

        Raises ValueError if the response is not valid JSON.
        """
        raw = self.call(prompt, system=system, json_mode=True)
        clean = self._extract_json(raw)

        try:
            return json.loads(clean)
        except json.JSONDecodeError as e:
            self.log.warning("agent_json_parse_failed_retry",
                             error=str(e), raw_start=raw[:150])
            # One retry — LLMs sometimes produce truncated or malformed JSON
            # on first attempt but succeed on the second.
            try:
                raw2 = self.call(prompt, system=system, json_mode=True)
                clean2 = self._extract_json(raw2)
                return json.loads(clean2)
            except (json.JSONDecodeError, Exception) as e2:
                self.log.error("agent_json_parse_failed",
                               error=str(e), raw_response=raw[:300])
                raise ValueError(
                    f"{self.name}: Ollama returned invalid JSON (2 attempts).\n"
                    f"Error: {e}\n"
                    f"Response start: {raw[:300]}"
                ) from e

    def load_prompt(self, filename: str) -> str:
        """Load a prompt from the prompts/ directory.

        Args:
            filename: e.g. "coder.md" — relative to the prompts/ dir.

        Why prompts live in files and not in code:
            Git shows exactly what changed between prompt versions.
            config.yaml is for numbers — not for multi-line instructions.
        """
        path = PROMPTS_DIR / filename
        if not path.exists():
            self.log.warning("prompt_file_missing", path=str(path))
            return ""
        return path.read_text(encoding="utf-8")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _http_post(self, payload: dict) -> str:
        """Make the HTTP POST to Ollama and return the response content string.

        Uses urllib (stdlib) instead of requests to avoid adding a dependency.
        If Ollama is not running, this raises a clear ConnectionRefusedError.
        """
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            _ollama_url(),
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        max_retries = 3
        base_delay = 5  # seconds
        data = json.dumps(payload).encode("utf-8")  # keep for retry rebuilds

        for attempt in range(max_retries):
            try:
                with urllib.request.urlopen(req, timeout=get_config().ollama.timeout_seconds) as response:
                    raw = response.read().decode("utf-8")
                # Empty response = model aborted — treat as retriable
                if not raw.strip():
                    if attempt < max_retries - 1:
                        import time
                        delay = base_delay * (2 ** attempt)
                        structlog.get_logger().warning(
                            "ollama_retry",
                            attempt=attempt + 1,
                            max=max_retries,
                            delay_s=delay,
                            reason="EmptyResponse",
                        )
                        time.sleep(delay)
                        req = urllib.request.Request(
                            _ollama_url(),
                            data=data,
                            headers={"Content-Type": "application/json"},
                            method="POST",
                        )
                        continue
                    raise ValueError("Ollama returned empty response after retries.")
                break  # success — exit retry loop

            except ConnectionRefusedError as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    structlog.get_logger().warning(
                        "ollama_retry",
                        attempt=attempt + 1,
                        max=max_retries,
                        delay_s=delay,
                        reason="ConnectionRefused",
                    )
                    import time; time.sleep(delay)
                    continue
                raise ConnectionRefusedError(
                    f"Cannot reach Ollama at {_ollama_url()} after {max_retries} attempts. "
                    "Is 'ollama serve' running?"
                ) from e

            except (TimeoutError, socket.timeout) as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    structlog.get_logger().warning(
                        "ollama_retry",
                        attempt=attempt + 1,
                        max=max_retries,
                        delay_s=delay,
                        reason="Timeout",
                    )
                    import time; time.sleep(delay)
                    # Rebuild request — urlopen consumes it
                    req = urllib.request.Request(
                        _ollama_url(),
                        data=data,
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    continue
                raise TimeoutError(
                    f"Ollama did not respond after {max_retries} attempts. "
                    "Model may be overloaded."
                ) from e

            except urllib.error.URLError as e:
                # urllib wraps socket.timeout in URLError on some Python versions
                if isinstance(e.reason, (socket.timeout, TimeoutError)):
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        structlog.get_logger().warning(
                            "ollama_retry",
                            attempt=attempt + 1,
                            max=max_retries,
                            delay_s=delay,
                            reason="URLError_Timeout",
                        )
                        import time; time.sleep(delay)
                        req = urllib.request.Request(
                            _ollama_url(),
                            data=data,
                            headers={"Content-Type": "application/json"},
                            method="POST",
                        )
                        continue
                    raise TimeoutError(
                        f"Ollama did not respond after {max_retries} attempts. "
                        "Model may be overloaded."
                    ) from e
                if isinstance(e.reason, ConnectionRefusedError):
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        structlog.get_logger().warning(
                            "ollama_retry",
                            attempt=attempt + 1,
                            max=max_retries,
                            delay_s=delay,
                            reason="URLError_ConnectionRefused",
                        )
                        import time; time.sleep(delay)
                        continue
                    raise ConnectionRefusedError(
                        f"Cannot reach Ollama at {_ollama_url()} after {max_retries} attempts. "
                        "Is 'ollama serve' running?"
                    ) from e
                raise

            except urllib.error.HTTPError as e:
                if e.code == 404:
                    raise ValueError(
                        f"Model '{payload.get('model')}' not found in Ollama. "
                        f"Run 'ollama list' to see available models."
                    ) from e
                if e.code == 400 and "think" in payload:
                    # Model does not support the 'think' parameter — retry without it
                    structlog.get_logger().warning(
                        "ollama_think_not_supported",
                        model=payload.get("model"),
                        agent=self.name,
                    )
                    payload.pop("think")
                    data = json.dumps(payload).encode("utf-8")
                    req = urllib.request.Request(
                        _ollama_url(),
                        data=data,
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    continue
                raise

        # Ollama wraps the content in {"message": {"content": "..."}}
        data = json.loads(raw)
        return data["message"]["content"]
