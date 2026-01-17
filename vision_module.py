"""
KELION SUPER AI - Vision Module
================================
Punct 7: Vision (Deep Understanding)
- Captură webcam discretă
- Face Tracking pentru contact vizual
- Analiză scene cu Claude Vision
"""

import os
import json
import base64
import requests
from datetime import datetime, timezone
from typing import Optional, Dict, List

# Configuration
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_BASE_URL = "https://api.anthropic.com/v1"
CLAUDE_VISION_MODEL = os.getenv("CLAUDE_VISION_MODEL", "claude-sonnet-4-20250514")

# Storage pentru observații vizuale
VISION_LOG_FILE = os.path.join(os.path.dirname(__file__), "data", "vision_observations.json")


class VisionObserver:
    """
    Sistemul de vedere al lui Kelion.
    Funcționează discret în fundal, analizând periodic ce vede.
    """
    
    def __init__(self):
        self.observations: List[Dict] = []
        self.face_position: Optional[Dict] = None  # Pentru face tracking
        self.last_frame_analysis: Optional[Dict] = None
        self._load_observations()
    
    def _load_observations(self):
        """Încarcă observațiile anterioare."""
        if os.path.exists(VISION_LOG_FILE):
            try:
                with open(VISION_LOG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.observations = data.get("observations", [])[-100:]  # Ultimele 100
            except:
                pass
    
    def _save_observations(self):
        """Salvează observațiile."""
        os.makedirs(os.path.dirname(VISION_LOG_FILE), exist_ok=True)
        with open(VISION_LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                "observations": self.observations[-100:],
                "last_face_position": self.face_position,
                "last_updated": datetime.now(timezone.utc).isoformat()
            }, f, ensure_ascii=False, indent=2)
    
    def analyze_frame(self, image_base64: str, context: str = "") -> Dict:
        """
        Analizează un frame video/imagine cu Claude Vision.
        
        Args:
            image_base64: Imaginea codificată în base64 (JPEG/PNG)
            context: Context adițional pentru analiză
        
        Returns:
            Dict cu analiza: objects, emotions, scene_description, etc.
        """
        if not ANTHROPIC_API_KEY:
            return {"error": "API key not configured"}
        
        headers = {
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        
        system_prompt = """Ești sistemul de vedere al lui Kelion AI. Analizează imaginea și oferă:
1. OBIECTE: Lista obiectelor vizibile
2. PERSOANE: Dacă există persoane, descrie expresia facială și starea emoțională
3. POZIȚIE FAȚĂ: Dacă vezi o față, indică poziția (stânga/centru/dreapta, sus/mijloc/jos)
4. AMBIENT: Descriere scurtă a ambientului (birou, cameră, exterior, lumină)
5. ACȚIUNE: Ce face persoana (lucrează, se uită în cameră, vorbește, etc.)

Răspunde în format JSON structurat."""

        if context:
            system_prompt += f"\n\nContext suplimentar: {context}"
        
        payload = {
            "model": CLAUDE_VISION_MODEL,
            "max_tokens": 1024,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": image_base64
                            }
                        },
                        {
                            "type": "text",
                            "text": "Analizează această imagine."
                        }
                    ]
                }
            ],
            "system": system_prompt
        }
        
        try:
            response = requests.post(
                f"{ANTHROPIC_BASE_URL}/messages",
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            # Extrage răspunsul
            analysis_text = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    analysis_text += block.get("text", "")
            
            # Parsează JSON din răspuns
            try:
                # Încearcă să extragă JSON din text
                import re
                json_match = re.search(r'\{[\s\S]*\}', analysis_text)
                if json_match:
                    analysis = json.loads(json_match.group())
                else:
                    analysis = {"raw_analysis": analysis_text}
            except:
                analysis = {"raw_analysis": analysis_text}
            
            # Actualizează face position pentru tracking
            if "face_position" in analysis or "poziție_față" in analysis:
                self.face_position = analysis.get("face_position") or analysis.get("poziție_față")
            
            # Salvează observația
            observation = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "analysis": analysis
            }
            self.observations.append(observation)
            self.last_frame_analysis = observation
            self._save_observations()
            
            return {
                "success": True,
                "analysis": analysis,
                "face_tracking": self.face_position
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def get_face_tracking_data(self) -> Dict:
        """
        Returnează datele pentru face tracking (pentru a orienta holograma).
        """
        return {
            "face_detected": self.face_position is not None,
            "position": self.face_position,
            "look_at": self._calculate_look_at_vector()
        }
    
    def _calculate_look_at_vector(self) -> Dict:
        """
        Calculează vectorul de privire pentru hologramă.
        Returnează coordonate x, y pentru unde să "privească" holograma.
        """
        if not self.face_position:
            return {"x": 0, "y": 0}  # Privește în față
        
        # Mapare poziție față -> vector privire
        pos = self.face_position
        x = 0
        y = 0
        
        if isinstance(pos, dict):
            horizontal = pos.get("horizontal", "centru").lower()
            vertical = pos.get("vertical", "mijloc").lower()
            
            if "stânga" in horizontal or "left" in horizontal:
                x = -0.3
            elif "dreapta" in horizontal or "right" in horizontal:
                x = 0.3
            
            if "sus" in vertical or "top" in vertical:
                y = 0.2
            elif "jos" in vertical or "bottom" in vertical:
                y = -0.2
        
        return {"x": x, "y": y}
    
    def get_recent_observations(self, count: int = 5) -> List[Dict]:
        """Returnează ultimele N observații."""
        return self.observations[-count:]
    
    def get_user_state_summary(self) -> str:
        """
        Generează un rezumat al stării utilizatorului bazat pe observații recente.
        """
        if not self.observations:
            return "Nu am observații recente despre utilizator."
        
        recent = self.observations[-5:]
        summary_parts = []
        
        for obs in recent:
            analysis = obs.get("analysis", {})
            if isinstance(analysis, dict):
                if "emotions" in analysis or "emoții" in analysis:
                    summary_parts.append(f"Emoție detectată: {analysis.get('emotions') or analysis.get('emoții')}")
                if "action" in analysis or "acțiune" in analysis:
                    summary_parts.append(f"Acțiune: {analysis.get('action') or analysis.get('acțiune')}")
        
        if summary_parts:
            return " | ".join(summary_parts[-3:])
        return "Utilizator prezent, stare neutră."


# Instanță globală
_vision_observer = VisionObserver()


def get_vision_observer() -> VisionObserver:
    """Returnează instanța globală a observatorului vizual."""
    return _vision_observer


def analyze_image(image_base64: str, context: str = "") -> Dict:
    """Funcție helper pentru analiză imagine."""
    return _vision_observer.analyze_frame(image_base64, context)


def get_face_tracking() -> Dict:
    """Funcție helper pentru face tracking."""
    return _vision_observer.get_face_tracking_data()


__all__ = [
    'VisionObserver',
    'get_vision_observer',
    'analyze_image',
    'get_face_tracking'
]
