"""
tests/agents/test_visioner.py — Tests für VisionerAgent.

Kein Ollama, kein echtes Bild nötig — HTTP-Call und Bildladung werden gemockt.
"""

import base64
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestVisionerImageEncoding:
    """_encode_image: Datei laden und korrekt als Base64 kodieren."""

    def get_agent(self):
        from src.agents.visioner import VisionerAgent
        return VisionerAgent()

    def test_png_encoded_correctly(self, tmp_path):
        img = tmp_path / "test.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n")  # PNG magic bytes
        agent = self.get_agent()
        b64, media_type = agent._encode_image(str(img))
        assert media_type == "image/png"
        assert base64.b64decode(b64) == b"\x89PNG\r\n\x1a\n"

    def test_jpeg_media_type(self, tmp_path):
        img = tmp_path / "photo.jpg"
        img.write_bytes(b"\xff\xd8\xff")  # JPEG magic bytes
        agent = self.get_agent()
        _, media_type = agent._encode_image(str(img))
        assert media_type == "image/jpeg"

    def test_missing_file_raises(self, tmp_path):
        agent = self.get_agent()
        with pytest.raises(FileNotFoundError):
            agent._encode_image(str(tmp_path / "nonexistent.png"))

    def test_unsupported_format_raises(self, tmp_path):
        img = tmp_path / "model.stl"
        img.write_bytes(b"solid test")
        agent = self.get_agent()
        with pytest.raises(ValueError, match="Unsupported"):
            agent._encode_image(str(img))


class TestVisionerRun:
    """run(): State-Handling und Fehlerbehandlung."""

    def get_agent(self):
        from src.agents.visioner import VisionerAgent
        return VisionerAgent()

    def test_no_image_returns_empty_spec(self):
        agent = self.get_agent()
        result = agent.run({"image_path": "", "description": "a cube"})
        assert result["specification"] == ""

    def test_image_path_missing_returns_empty(self):
        agent = self.get_agent()
        result = agent.run({"description": "something"})
        assert result["specification"] == ""

    def test_successful_vision_call(self, tmp_path):
        img = tmp_path / "part.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n")
        agent = self.get_agent()

        with patch.object(agent, "_call_vision",
                          return_value="Rectangular plate, 80x40mm. Central hole UNKNOWN."):
            result = agent.run({
                "image_path": str(img),
                "description": "",
            })

        assert "Rectangular plate" in result["specification"]

    def test_text_hint_passed_to_vision(self, tmp_path):
        img = tmp_path / "part.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n")
        agent = self.get_agent()

        captured = {}
        def fake_call_vision(text, b64, media_type):
            captured["text"] = text
            return "some spec"

        with patch.object(agent, "_call_vision", side_effect=fake_call_vision):
            agent.run({
                "image_path": str(img),
                "description": "bracket for shelf",
            })

        assert "bracket for shelf" in captured["text"]

    def test_failed_image_load_returns_empty(self):
        agent = self.get_agent()
        result = agent.run({
            "image_path": "/nonexistent/path/image.png",
            "description": "",
        })
        assert result["specification"] == ""


class TestVisionerApiCall:
    """_call_vision: Ollama API wird korrekt aufgerufen."""

    def get_agent(self):
        from src.agents.visioner import VisionerAgent
        return VisionerAgent()

    def test_images_field_in_payload(self):
        """Ollama Vision API erwartet 'images' als Liste im Message-Objekt."""
        agent = self.get_agent()
        captured = {}

        import json
        import urllib.request

        def fake_urlopen(req, timeout=None):
            captured["payload"] = json.loads(req.data.decode())
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_resp.read.return_value = json.dumps({
                "message": {"content": "Rectangular part"}
            }).encode()
            return mock_resp

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = agent._call_vision("analyse this", "abc123", "image/png")

        user_msg = captured["payload"]["messages"][-1]
        assert "images" in user_msg
        assert user_msg["images"] == ["abc123"]
        assert result == "Rectangular part"

    def test_http_error_returns_empty(self):
        import urllib.error
        agent = self.get_agent()

        with patch("urllib.request.urlopen",
                   side_effect=urllib.error.HTTPError(None, 404, "Not Found", {}, None)):
            result = agent._call_vision("test", "b64data", "image/png")

        assert result == ""
