# tts_api.py
# Minimal TTS endpoint stub for Flask: /api/voice/tts
# Provider-agnostic.
# tts_provider(text: str, cinematic: bool) -> bytes  (audio bytes)

from __future__ import annotations
import base64
from flask import request, jsonify

def register_tts_api(app, tts_provider) -> None:
    @app.post("/api/voice/tts")
    def voice_tts():
        payload = request.get_json(force=True, silent=True) or {}
        text = (payload.get("text") or "").strip()
        cinematic = bool(payload.get("cinematic", True))
        if not text:
            return jsonify({"ok": False, "error": "missing_text"}), 400

        audio_bytes = tts_provider(text=text, cinematic=cinematic)
        b64 = base64.b64encode(audio_bytes).decode("ascii")
        return jsonify({"ok": True, "audio_b64": b64, "mime": "audio/mpeg"})
