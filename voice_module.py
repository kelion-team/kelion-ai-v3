"""
KELION SUPER AI - Voice Module
===============================
Punct 9: Voice Authority (Voce HD)
Punct 10: Voiceprint Unlock (Recunoaștere vocală)
Punct 11: Live Translator
"""

import os
import re
import json
import hashlib
import base64
import requests
from datetime import datetime, timezone
from typing import Optional, Dict, List

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")

# TTS Configuration
TTS_PROVIDER = os.getenv("TTS_PROVIDER", "openai")  # browser, openai, elevenlabs, deepgram
OPENAI_TTS_VOICE = os.getenv("OPENAI_TTS_VOICE", "onyx")  # Male voice
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "")
DEEPGRAM_VOICE = os.getenv("DEEPGRAM_VOICE", "aura-orion-en")  # MASCULINE voice (deep male)

# Voice storage
VOICEPRINT_FILE = os.path.join(os.path.dirname(__file__), "data", ".voiceprint_advanced")
AUDIO_CACHE_DIR = os.path.join(os.path.dirname(__file__), "static", "audio", "tts_cache")


class VoiceAuthority:
    """
    Sistemul vocal al lui Kelion.
    Gestionează TTS (Text-to-Speech) și vocea personalizată.
    """
    
    def __init__(self):
        self.current_voice = OPENAI_TTS_VOICE
        self.tts_provider = TTS_PROVIDER
        os.makedirs(AUDIO_CACHE_DIR, exist_ok=True)
    
    def _get_cache_key(self, text: str, voice: str) -> str:
        """Generează o cheie de cache pentru text+voice."""
        data = f"{text}:{voice}:{self.tts_provider}"
        return hashlib.md5(data.encode()).hexdigest()
    
    def _get_cached_audio(self, cache_key: str) -> Optional[str]:
        """Verifică dacă există audio în cache."""
        cache_path = os.path.join(AUDIO_CACHE_DIR, f"{cache_key}.mp3")
        if os.path.exists(cache_path):
            return f"/audio/tts_cache/{cache_key}.mp3"
        return None
    
    def synthesize(self, text: str, voice: Optional[str] = None) -> Dict:
        """
        Sintetizează text în audio.
        
        Args:
            text: Textul de sintetizat
            voice: Vocea de folosit (opțional)
        
        Returns:
            Dict cu audio_url sau instrucțiuni pentru browser TTS
        """
        voice = voice or self.current_voice
        
        # Verifică cache
        cache_key = self._get_cache_key(text, voice)
        cached = self._get_cached_audio(cache_key)
        if cached:
            return {"audio_url": cached, "cached": True}
        
        # Selectează provider
        if self.tts_provider == "browser":
            return self._browser_tts(text, voice)
        elif self.tts_provider == "openai":
            return self._openai_tts(text, voice, cache_key)
        elif self.tts_provider == "elevenlabs":
            return self._elevenlabs_tts(text, cache_key)
        elif self.tts_provider == "deepgram":
            return self._deepgram_tts(text, cache_key)
        
        # Default to Deepgram if configured, else browser
        if DEEPGRAM_API_KEY:
            return self._deepgram_tts(text, cache_key)
        return self._browser_tts(text, voice)
    
    def _browser_tts(self, text: str, voice: str) -> Dict:
        """Returnează instrucțiuni pentru Web Speech API (gratuit)."""
        lang = self.detect_language(text)
        browser_lang = "ro-RO" if lang == "ro" else "en-US"
        
        return {
            "use_browser_tts": True,
            "text": text,
            "voice_settings": {
                "lang": browser_lang,
                "rate": 1.0,
                "pitch": 0.9,
                "voice_name": voice  # Male voices preferred
            }
    
    def make_viseme_timeline(self, words: List[Dict]) -> List[Dict]:
        """Convertește timpii cuvintelor -> timeline de viseme (euristică)."""
        def viseme_for_word(w: str) -> str:
            w = (w or "").lower()
            if not w: return "REST"
            if w.startswith("th"): return "TH"
            if w.startswith(("ch", "sh", "j", "zh")): return "CH"
            if w.startswith(("f", "v")): return "FV"
            if w.startswith(("m", "b", "p")): return "MBP"
            if w.startswith(("k", "g", "q", "c")): return "KG"
            if w.startswith(("s", "z", "x")): return "S"
            if w.startswith("r"): return "R"
            if w.startswith("l"): return "L"
            if w.startswith("w"): return "WQ"
            m = re.search(r"[aeiouyăâîșț]+", w)
            if not m: return "REST"
            v = m.group(0)
            if v in ("oo", "u", "ou", "ow", "ua", "uo"): return "OO"
            if v in ("ee", "i", "ie", "ei", "y", "ea"): return "EE"
            return "AA"

        tl = []
        for it in words or []:
            try:
                t0 = float(it.get("start", 0.0))
                t1 = float(it.get("end", t0 + 0.12))
                word = it.get("word") or ""
                tl.append({"t0": t0, "t1": t1, "viseme": viseme_for_word(word)})
            except Exception:
                continue
        return tl

    def _get_lipsync_data(self, audio_bytes: bytes) -> Optional[Dict]:
        """Obține date de lipsync folosind Whisper (word-level timestamps)."""
        if not OPENAI_API_KEY:
            return None
        
        try:
            headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
            files = {"file": ("speech.mp3", audio_bytes)}
            data = {
                "model": "whisper-1",
                "response_format": "verbose_json",
                "timestamp_granularities[]": "word"
            }
            
            r = requests.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers=headers,
                files=files,
                data=data,
                timeout=60
            )
            r.raise_for_status()
            res = r.json()
            words = res.get("words", [])
            
            return {
                "words": words,
                "visemes": self.make_viseme_timeline(words)
            }
        except Exception:
            return None
        }
    
    def _openai_tts(self, text: str, voice: str, cache_key: str) -> Dict:
        """Sintetizează cu OpenAI TTS."""
        if not OPENAI_API_KEY:
            return self._browser_tts(text, voice)
        
        try:
            headers = {
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "tts-1-hd",
                "voice": voice,
                "input": text,
                "response_format": "mp3"
            }
            
            response = requests.post(
                "https://api.openai.com/v1/audio/speech",
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            
            # Salvează în cache
            cache_path = os.path.join(AUDIO_CACHE_DIR, f"{cache_key}.mp3")
            with open(cache_path, 'wb') as f:
                f.write(response.content)
            
            # Generare Lipsync (Opțional)
            lipsync = self._get_lipsync_data(response.content)
            
            return {
                "audio_url": f"/audio/tts_cache/{cache_key}.mp3",
                "lipsync": lipsync
            }
            
        except Exception as e:
            return {"error": str(e), "fallback": self._browser_tts(text, voice)}
    
    def _elevenlabs_tts(self, text: str, cache_key: str) -> Dict:
        """Sintetizează cu ElevenLabs (voce clonată)."""
        if not ELEVENLABS_API_KEY or not ELEVENLABS_VOICE_ID:
            return self._browser_tts(text, "default")
        
        try:
            headers = {
                "xi-api-key": ELEVENLABS_API_KEY,
                "Content-Type": "application/json"
            }
            
            payload = {
                "text": text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.8
                }
            }
            
            response = requests.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}",
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            
            # Salvează în cache
            cache_path = os.path.join(AUDIO_CACHE_DIR, f"{cache_key}.mp3")
            with open(cache_path, 'wb') as f:
                f.write(response.content)
            
            return {"audio_url": f"/audio/tts_cache/{cache_key}.mp3"}
            
        except Exception as e:
            return {"error": str(e), "fallback": self._browser_tts(text, "default")}
    
    def _deepgram_tts(self, text: str, cache_key: str) -> Dict:
        """Sintetizează cu Deepgram Aura TTS ($200 free credits!)."""
        if not DEEPGRAM_API_KEY:
            return self._browser_tts(text, "default")
        
        try:
            headers = {
                "Authorization": f"Token {DEEPGRAM_API_KEY}",
                "Content-Type": "application/json"
            }
            
            # Use configured voice model
            voice_model = DEEPGRAM_VOICE
            
            response = requests.post(
                f"https://api.deepgram.com/v1/speak?model={voice_model}",
                headers=headers,
                json={"text": text},
                timeout=30
            )
            response.raise_for_status()
            
            # Salvează în cache
            cache_path = os.path.join(AUDIO_CACHE_DIR, f"{cache_key}.mp3")
            with open(cache_path, 'wb') as f:
                f.write(response.content)
            
            # Track credit usage (caractere folosite)
            try:
                from voice_credits import get_credits_manager
                credits_manager = get_credits_manager()
                credits_manager.use_credits(len(text), f"TTS: {text[:50]}...")
            except ImportError:
                pass  # Voice credits module not available
            
            return {"audio_url": f"/audio/tts_cache/{cache_key}.mp3", "provider": "deepgram"}
            
        except Exception as e:
            return {"error": str(e), "fallback": self._browser_tts(text, "default")}


class VoiceprintAuth:
    """
    Sistemul de autentificare prin amprentă vocală.
    Punct 10: Voiceprint Unlock
    """
    
    def __init__(self):
        self.registered_voiceprint: Optional[Dict] = None
        self._load_voiceprint()
    
    def _load_voiceprint(self):
        """Încarcă amprenta vocală înregistrată."""
        if os.path.exists(VOICEPRINT_FILE):
            try:
                with open(VOICEPRINT_FILE, 'r') as f:
                    self.registered_voiceprint = json.load(f)
            except:
                pass
    
    def register(self, audio_features: Dict, user_id: str = "admin") -> Dict:
        """
        Înregistrează amprenta vocală.
        
        Args:
            audio_features: Caracteristici extrase din voce (MFCC, pitch, etc.)
            user_id: ID-ul utilizatorului
        """
        voiceprint = {
            "user_id": user_id,
            "features": audio_features,
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "feature_hash": hashlib.sha256(json.dumps(audio_features, sort_keys=True).encode()).hexdigest()
        }
        
        os.makedirs(os.path.dirname(VOICEPRINT_FILE), exist_ok=True)
        with open(VOICEPRINT_FILE, 'w') as f:
            json.dump(voiceprint, f)
        
        self.registered_voiceprint = voiceprint
        
        return {
            "success": True,
            "message": "Amprentă vocală înregistrată cu succes",
            "user_id": user_id
        }
    
    def verify(self, audio_features: Dict) -> Dict:
        """
        Verifică dacă vocea corespunde cu amprenta înregistrată.
        
        Returns:
            Dict cu verified (bool), confidence (float), auto_login (bool)
        """
        if not self.registered_voiceprint:
            return {
                "verified": False,
                "error": "Nu există amprentă vocală înregistrată",
                "auto_login": False
            }
        
        # Calculează similaritatea
        # În producție, aici s-ar folosi un model ML real pentru comparație
        stored_features = self.registered_voiceprint.get("features", {})
        
        confidence = self._calculate_similarity(stored_features, audio_features)
        verified = confidence > 0.85  # Threshold 85%
        
        return {
            "verified": verified,
            "confidence": confidence,
            "auto_login": verified,
            "god_mode": verified,  # Activează toate funcțiile dacă vocea e verificată
            "user_id": self.registered_voiceprint.get("user_id") if verified else None
        }
    
    def _calculate_similarity(self, stored: Dict, incoming: Dict) -> float:
        """
        Calculează similaritatea între două seturi de features vocale.
        Implementare simplificată - în producție se folosește ML.
        """
        if not stored or not incoming:
            return 0.0
        
        # Dacă avem același user_id, considerăm match (pentru demo)
        if stored.get("user_id") == incoming.get("user_id"):
            return 0.95
        
        # Calculează overlap de features
        common_keys = set(stored.keys()) & set(incoming.keys())
        if not common_keys:
            return 0.0
        
        matches = 0
        for key in common_keys:
            if stored[key] == incoming[key]:
                matches += 1
        
        return matches / len(common_keys) if common_keys else 0.0


class LiveTranslator:
    """
    Sistemul de traducere live.
    Punct 11: Live Translator cu nuanțe culturale.
    """
    
    SUPPORTED_LANGUAGES = {
        "ro": "Română",
        "en": "English",
        "de": "Deutsch",
        "fr": "Français",
        "es": "Español",
        "it": "Italiano",
        "ja": "日本語",
        "zh": "中文",
        "ko": "한국어",
        "ru": "Русский"
    }
    
    def __init__(self):
        self.source_lang = "ro"
        self.target_lang = "en"
    
    def translate(self, text: str, source: str = "auto", target: str = "en") -> Dict:
        """
        Traduce text folosind Claude pentru nuanțe culturale.
        
        Args:
            text: Textul de tradus
            source: Limba sursă (sau "auto" pentru detectare)
            target: Limba țintă
        """
        if not ANTHROPIC_API_KEY:
            return {"error": "API key not configured"}
        
        headers = {
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        
        prompt = f"""Traduce următorul text în {self.SUPPORTED_LANGUAGES.get(target, target)}.

IMPORTANT:
- Păstrează nuanțele culturale și emoționale
- Adaptează expresiile idiomatice la cultura țintă
- Menține tonul original (formal/informal)
- Dacă există umor sau sarcasm, adaptează-l cultural

Text de tradus:
"{text}"

Răspunde DOAR cu traducerea, fără explicații."""

        payload = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}]
        }
        
        try:
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            translated = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    translated += block.get("text", "")
            
            return {
                "original": text,
                "translated": translated.strip(),
                "source_lang": source,
                "target_lang": target
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def detect_language(self, text: str) -> str:
        """Detectează limba textului."""
        # Implementare simplificată
        romanian_chars = set("ăâîșț")
        if any(c in text.lower() for c in romanian_chars):
            return "ro"
        
        # Default la engleză
        return "en"


# Instanțe globale
_voice_authority = VoiceAuthority()
_voiceprint_auth = VoiceprintAuth()
_live_translator = LiveTranslator()


def get_voice_authority() -> VoiceAuthority:
    return _voice_authority

def get_voiceprint_auth() -> VoiceprintAuth:
    return _voiceprint_auth

def get_translator() -> LiveTranslator:
    return _live_translator

def synthesize_speech(text: str, voice: str = None) -> Dict:
    return _voice_authority.synthesize(text, voice)

def verify_voice(audio_features: Dict) -> Dict:
    return _voiceprint_auth.verify(audio_features)

def translate_text(text: str, target: str = "en") -> Dict:
    return _live_translator.translate(text, target=target)


__all__ = [
    'VoiceAuthority',
    'VoiceprintAuth', 
    'LiveTranslator',
    'get_voice_authority',
    'get_voiceprint_auth',
    'get_translator',
    'synthesize_speech',
    'verify_voice',
    'translate_text'
]
