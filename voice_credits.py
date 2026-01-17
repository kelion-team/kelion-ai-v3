"""
KELION AI - Voice Credits Manager
=================================
Tracks voice usage, alerts when low, provides purchase links.
Supports: Deepgram, ElevenLabs
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger("kelion.voice_credits")

# Configuration
DATA_DIR = Path(__file__).parent / "data"
CREDITS_FILE = DATA_DIR / "voice_credits.json"
ALERT_THRESHOLD = 500  # Alert when 500 characters remaining

# Ensure data directory exists
DATA_DIR.mkdir(exist_ok=True)

# Provider URLs
PROVIDER_URLS = {
    "deepgram": {
        "signup": "https://console.deepgram.com/signup",
        "billing": "https://console.deepgram.com/billing",
        "pricing": "https://deepgram.com/pricing",
        "free_credits": 200.00  # $200 free on signup
    },
    "elevenlabs": {
        "signup": "https://elevenlabs.io/sign-up",
        "billing": "https://elevenlabs.io/subscription",
        "pricing": "https://elevenlabs.io/pricing",
        "free_credits": 10000  # 10,000 characters free
    }
}


class VoiceCreditsManager:
    """Manages voice credits and usage tracking."""
    
    def __init__(self, provider: str = "deepgram"):
        self.provider = provider.lower()
        self.data = self._load()
    
    def _load(self) -> Dict[str, Any]:
        """Load credits data from file."""
        if CREDITS_FILE.exists():
            try:
                with open(CREDITS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        
        # Default data structure
        return {
            "provider": self.provider,
            "total_credits": 0,
            "used_credits": 0,
            "alert_threshold": ALERT_THRESHOLD,
            "alert_sent": False,
            "last_alert": None,
            "usage_history": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
    
    def _save(self) -> bool:
        """Save credits data to file."""
        try:
            self.data["updated_at"] = datetime.now(timezone.utc).isoformat()
            with open(CREDITS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            return True
        except IOError as e:
            logger.error(f"Failed to save credits: {e}")
            return False
    
    def set_credits(self, amount: int) -> Dict[str, Any]:
        """Set total available credits."""
        self.data["total_credits"] = amount
        self.data["alert_sent"] = False
        self._save()
        return self.get_status()
    
    def add_credits(self, amount: int) -> Dict[str, Any]:
        """Add credits to the account."""
        self.data["total_credits"] += amount
        self.data["alert_sent"] = False
        self._save()
        logger.info(f"Added {amount} credits. New total: {self.data['total_credits']}")
        return self.get_status()
    
    def use_credits(self, amount: int, description: str = "") -> Dict[str, Any]:
        """Use credits and check if alert needed."""
        self.data["used_credits"] += amount
        
        # Add to history
        self.data["usage_history"].append({
            "amount": amount,
            "description": description,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        # Keep only last 100 entries
        self.data["usage_history"] = self.data["usage_history"][-100:]
        
        remaining = self.get_remaining()
        
        # Check if alert needed
        alert_triggered = False
        if remaining <= self.data["alert_threshold"] and not self.data["alert_sent"]:
            self.data["alert_sent"] = True
            self.data["last_alert"] = datetime.now(timezone.utc).isoformat()
            alert_triggered = True
            logger.warning(f"LOW CREDITS ALERT: {remaining} characters remaining!")
        
        self._save()
        
        return {
            "success": True,
            "used": amount,
            "remaining": remaining,
            "alert_triggered": alert_triggered,
            "alert_message": f"⚠️ ATENȚIE: Mai ai doar {remaining} caractere! Achiziționează mai multe." if alert_triggered else None,
            "purchase_url": PROVIDER_URLS.get(self.provider, {}).get("billing")
        }
    
    def get_remaining(self) -> int:
        """Get remaining credits."""
        return max(0, self.data["total_credits"] - self.data["used_credits"])
    
    def get_status(self) -> Dict[str, Any]:
        """Get full status of credits."""
        remaining = self.get_remaining()
        provider_info = PROVIDER_URLS.get(self.provider, {})
        
        return {
            "provider": self.provider,
            "total_credits": self.data["total_credits"],
            "used_credits": self.data["used_credits"],
            "remaining_credits": remaining,
            "alert_threshold": self.data["alert_threshold"],
            "is_low": remaining <= self.data["alert_threshold"],
            "is_empty": remaining <= 0,
            "percentage_used": round((self.data["used_credits"] / max(1, self.data["total_credits"])) * 100, 2),
            "purchase_url": provider_info.get("billing"),
            "pricing_url": provider_info.get("pricing"),
            "signup_url": provider_info.get("signup"),
            "last_updated": self.data["updated_at"]
        }
    
    def set_alert_threshold(self, threshold: int) -> Dict[str, Any]:
        """Set the alert threshold."""
        self.data["alert_threshold"] = threshold
        self.data["alert_sent"] = False
        self._save()
        return self.get_status()
    
    def reset_usage(self) -> Dict[str, Any]:
        """Reset usage counter (for new billing period)."""
        self.data["used_credits"] = 0
        self.data["alert_sent"] = False
        self.data["usage_history"] = []
        self._save()
        return self.get_status()
    
    def get_usage_history(self, limit: int = 50) -> list:
        """Get recent usage history."""
        return self.data["usage_history"][-limit:]


# Global instance
_credits_manager: Optional[VoiceCreditsManager] = None


def get_credits_manager(provider: str = "deepgram") -> VoiceCreditsManager:
    """Get or create the credits manager instance."""
    global _credits_manager
    if _credits_manager is None:
        _credits_manager = VoiceCreditsManager(provider)
    return _credits_manager


# Flask routes for Admin Panel
def register_credits_routes(app):
    """Register Flask routes for credits management."""
    from flask import jsonify, request
    
    @app.route('/api/voice/credits/status', methods=['GET'])
    def voice_credits_status():
        """Get current credits status."""
        manager = get_credits_manager()
        return jsonify(manager.get_status())
    
    @app.route('/api/voice/credits/add', methods=['POST'])
    def voice_credits_add():
        """Add credits (admin only)."""
        data = request.get_json() or {}
        amount = data.get('amount', 0)
        
        if not isinstance(amount, int) or amount <= 0:
            return jsonify({"error": "Invalid amount"}), 400
        
        manager = get_credits_manager()
        return jsonify(manager.add_credits(amount))
    
    @app.route('/api/voice/credits/set', methods=['POST'])
    def voice_credits_set():
        """Set total credits (admin only)."""
        data = request.get_json() or {}
        amount = data.get('amount', 0)
        
        if not isinstance(amount, int) or amount < 0:
            return jsonify({"error": "Invalid amount"}), 400
        
        manager = get_credits_manager()
        return jsonify(manager.set_credits(amount))
    
    @app.route('/api/voice/credits/threshold', methods=['POST'])
    def voice_credits_threshold():
        """Set alert threshold (admin only)."""
        data = request.get_json() or {}
        threshold = data.get('threshold', ALERT_THRESHOLD)
        
        if not isinstance(threshold, int) or threshold < 0:
            return jsonify({"error": "Invalid threshold"}), 400
        
        manager = get_credits_manager()
        return jsonify(manager.set_alert_threshold(threshold))
    
    @app.route('/api/voice/credits/history', methods=['GET'])
    def voice_credits_history():
        """Get usage history."""
        manager = get_credits_manager()
        limit = request.args.get('limit', 50, type=int)
        return jsonify(manager.get_usage_history(limit))
    
    @app.route('/api/voice/credits/purchase-urls', methods=['GET'])
    def voice_purchase_urls():
        """Get purchase URLs for all providers."""
        return jsonify(PROVIDER_URLS)
    
    logger.info("Voice credits routes registered")
