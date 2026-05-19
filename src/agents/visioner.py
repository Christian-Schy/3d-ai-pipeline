"""
src/agents/visioner.py — Analyses an image/sketch and produces a text specification.

The Visioner runs BEFORE the Interpreter. It extracts:
  - Overall shape and dimensions (if visible/measurable)
  - Visible features: holes, chamfers, fillets, ribs, threads
  - Material hints (if obvious)
  - Anything unclear → marked as UNKNOWN for Interpreter to ask about

Output is a partial specification string, e.g.:
  "Rectangular plate, roughly 80x40mm. Central through-hole visible,
   diameter UNKNOWN. Four corner holes visible, diameter UNKNOWN.
   Thickness UNKNOWN."

The Interpreter then receives this as a pre-filled starting point and
only asks clarifying questions for the UNKNOWN fields.

Model: qwen3-vl:30b — vision-capable, runs locally via Ollama.
"""

import base64
import json
from pathlib import Path

import structlog

from src.agents.base import BaseAgent
from src.config.loader import get_config
from src.graph.state import PipelineState
from src.utils.prompt_loader import load_prompt

log = structlog.get_logger()

_prompt = load_prompt("prompt_visioner.py")
VISIONER_SYSTEM_PROMPT = _prompt.SYSTEM_PROMPT


class VisionerAgent(BaseAgent):
    """Analyses an image and returns a partial text specification.

    Called by visioner_node before the Interpreter.
    The partial spec is stored in state['specification'] as a starting point.
    """

    model = get_config().models.visioner  # set from config.yaml
    name = "visioner"

    def run(self, state: PipelineState) -> dict:
        image_path = state.get("image_path", "")
        text_hint = state.get("description", "").strip()

        if not image_path:
            log.warning("visioner_no_image")
            return {"specification": ""}

        # Load and encode image
        try:
            image_b64, media_type = self._encode_image(image_path)
        except (FileNotFoundError, ValueError) as e:
            log.error("visioner_image_load_failed", error=str(e))
            return {"specification": ""}

        # Build prompt — optional text hint from user
        if text_hint:
            user_text = (
                f"Analyse this image of a 3D part.\n"
                f"The user also described it as: '{text_hint}'\n"
                f"Use both the image and the description to write the specification."
            )
        else:
            user_text = "Analyse this image of a 3D part and write a specification."

        log.info("visioner_start",
                 image_path=image_path,
                 has_text_hint=bool(text_hint))

        spec = self._call_vision(user_text, image_b64, media_type)

        log.info("visioner_done", spec_len=len(spec), spec_preview=spec[:80])
        return {"specification": spec}

    def _encode_image(self, image_path: str) -> tuple[str, str]:
        """Read image file and return (base64_string, media_type)."""
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        suffix = path.suffix.lower()
        media_type_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
            ".gif": "image/gif",
        }
        media_type = media_type_map.get(suffix)
        if not media_type:
            raise ValueError(f"Unsupported image format: {suffix}")

        data = path.read_bytes()
        return base64.b64encode(data).decode("utf-8"), media_type

    def _call_vision(self, text: str, image_b64: str, media_type: str) -> str:
        """Call Ollama with image + text using the multimodal message format.

        Ollama's vision API expects images as base64 in the 'images' field
        of the message, alongside the text content.
        """
        import urllib.error
        import urllib.request

        cfg = get_config()
        url = cfg.ollama.base_url + "/api/chat"

        payload = {
            "model": self.model,
            "stream": False,
            "messages": [
                {
                    "role": "system",
                    "content": VISIONER_SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": text,
                    "images": [image_b64],  # Ollama vision: base64 images list
                }
            ],
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        log.info("visioner_api_call",
                 model=self.model,
                 image_bytes=len(image_b64))

        try:
            with urllib.request.urlopen(
                req, timeout=cfg.ollama.timeout_seconds
            ) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            log.error("visioner_http_error", code=e.code, reason=str(e))
            return ""
        except TimeoutError:
            log.error("visioner_timeout")
            return ""

        try:
            parsed = json.loads(raw)
            return parsed["message"]["content"].strip()
        except (json.JSONDecodeError, KeyError) as e:
            log.error("visioner_parse_error", error=str(e))
            return ""
