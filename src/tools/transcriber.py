"""Speech-to-text transcription using faster-whisper (runs locally, no API key)."""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


class Transcriber:
    """Lazy-loading wrapper around faster-whisper WhisperModel."""

    def __init__(self, model_size: str = "base", device: str = "auto", compute_type: str = "auto"):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model = None

    # ------------------------------------------------------------------
    def preload(self) -> None:
        """Load the Whisper model in the background (called at startup)."""
        try:
            self._load_model()
        except Exception as e:
            logger.warning("Whisper preload failed (will retry on first use): %s", e)

    def _load_model(self):
        if self._model is not None:
            return self._model
        from faster_whisper import WhisperModel

        device = self.device
        compute_type = self.compute_type

        # Auto-detect: use GPU if available, else CPU
        if device == "auto":
            try:
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                device = "cpu"

        if compute_type == "auto":
            compute_type = "float16" if device == "cuda" else "int8"

        logger.info("Loading Whisper model '%s' on %s (%s)…", self.model_size, device, compute_type)
        self._model = WhisperModel(self.model_size, device=device, compute_type=compute_type)
        logger.info("Whisper model ready.")
        return self._model

    # ------------------------------------------------------------------
    def transcribe(self, audio_path: str, language: str | None = None) -> str:
        """Transcribe an audio file and return the text.

        Args:
            audio_path: Path to audio file (wav, mp3, m4a, …).
            language:   BCP-47 language code or None for auto-detect.

        Returns:
            Transcribed text, or empty string on failure.
        """
        if not audio_path or not os.path.exists(audio_path):
            logger.warning("Transcriber: file not found: %s", audio_path)
            return ""

        try:
            model = self._load_model()
            segments, _ = model.transcribe(
                audio_path,
                language=language,
                beam_size=5,
                vad_filter=True,  # skip silence
            )
            text = " ".join(seg.text.strip() for seg in segments).strip()
            logger.info("Transcription: %r", text[:120])
            return text
        except Exception as e:
            logger.error("Transcription failed: %s", e)
            return ""
