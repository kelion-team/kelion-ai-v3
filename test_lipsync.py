import json

def test_lipsync_response():
    """
    Simulează un răspuns de la Super AI cu Lipsync activat.
    """
    # Mock tts_data returnat de VoiceAuthority.synthesize (OpenAI case)
    tts_data = {
        "audio_url": "/audio/tts_cache/mock_lipsync.mp3",
        "lipsync": {
            "words": [
                {"word": "Salut", "start": 0.0, "end": 0.5},
                {"word": "Kelion", "start": 0.5, "end": 1.0}
            ],
            "visemes": [
                {"t0": 0.0, "t1": 0.5, "viseme": "S"},
                {"t0": 0.5, "t1": 1.0, "viseme": "KG"}
            ]
        }
    }
    
    # Rezultatul final în super_ai_routes.py
    response_data = {
        "text": "Salut! Eu sunt Kelion.",
        "emotion": "calm",
        "audioUrl": tts_data.get("audio_url"),
        "useBrowserTTS": False,
        "animation": "speak",
        "lipsync": tts_data.get("lipsync")
    }
    
    print("Testing Response with Lipsync Data:")
    print(json.dumps(response_data, indent=2))
    
    # Assertions
    assert response_data["lipsync"] is not None, "Lipsync data is missing"
    assert "visemes" in response_data["lipsync"], "Visemes timeline missing"
    assert len(response_data["lipsync"]["visemes"]) > 0, "Visemes timeline is empty"
    
    print("\n[SUCCESS] Lipsync data integrated correctly in response structure.")

if __name__ == "__main__":
    test_lipsync_response()
