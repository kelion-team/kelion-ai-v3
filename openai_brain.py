"""
KELION SUPER AI - OpenAI Brain (GPT-4)
======================================
Core Intelligence powered by OpenAI GPT-4o.
Replaces Claude Brain while maintaining memory and security features.
"""

import os
import json
import requests
import threading
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from functools import wraps
from dotenv import load_dotenv

load_dotenv()


# Setup logging
brain_logger = logging.getLogger("kelion.brain.openai")

# Import Security Core
try:
    from security_core import require_active_system, is_system_frozen, k_armor_check
    SECURITY_AVAILABLE = True
except ImportError:
    SECURITY_AVAILABLE = False
    brain_logger.warning("Security core not available - running in unsafe mode")
    def require_active_system(func):
        return func
    def is_system_frozen():
        return False
    def k_armor_check():
        return {"valid": True}

# ============================================================================
# CONFIGURATION
# ============================================================================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

# Cost tracking (Approximate for GPT-4o)
TOKEN_COSTS = {
    "input": 5.0 / 1_000_000,
    "output": 15.0 / 1_000_000
}

# Data paths (Reuse existing memory files)
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
MEMORY_FILE = os.path.join(DATA_DIR, "kelion_memory.json")
KEYWORDS_FILE = os.path.join(DATA_DIR, "semantic_keywords.json")
USAGE_FILE = os.path.join(DATA_DIR, "api_usage_openai.json")  # Separate usage file
VOICEPRINT_FILE = os.path.join(DATA_DIR, ".voiceprint")

# Admin email for alerts
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "adrianenc11@gmail.com")
CREDIT_ALERT_THRESHOLD = float(os.getenv("CREDIT_ALERT_THRESHOLD", "0.50"))

os.makedirs(DATA_DIR, exist_ok=True)

# ============================================================================
# UTILS (Validation & Locking)
# ============================================================================

def validate_string(value: Any, name: str, max_length: int = 10000) -> str:
    if value is None: return ""
    if not isinstance(value, str): raise ValueError(f"{name} must be a string")
    if len(value) > max_length: raise ValueError(f"{name} exceeds maximum length of {max_length}")
    return value.strip()

def validate_positive_number(value: Any, name: str) -> float:
    try:
        num = float(value)
        if num < 0: raise ValueError(f"{name} must be positive")
        return num
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a valid number")

class FileLock:
    _locks: Dict[str, threading.RLock] = {}
    _global_lock = threading.Lock()
    
    @classmethod
    def get_lock(cls, filepath: str) -> threading.RLock:
        with cls._global_lock:
            if filepath not in cls._locks:
                cls._locks[filepath] = threading.RLock()
            return cls._locks[filepath]

def safe_read_json(filepath: str, default: Any = None) -> Any:
    lock = FileLock.get_lock(filepath)
    with lock:
        if not os.path.exists(filepath):
            return default if default is not None else {}
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            brain_logger.error(f"Failed to read {filepath}: {e}")
            return default if default is not None else {}

def safe_write_json(filepath: str, data: Any) -> bool:
    lock = FileLock.get_lock(filepath)
    with lock:
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            temp_path = filepath + ".tmp"
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(temp_path, filepath)
            return True
        except Exception as e:
            brain_logger.error(f"Failed to write {filepath}: {e}")
            return False

# ============================================================================
# MEMORY SYSTEM (Compatible with Claude Brain)
# ============================================================================

class KelionMemory:
    MAX_CONVERSATIONS = 1000
    MAX_KEYWORDS = 500
    MAX_FACTS = 200
    
    def __init__(self):
        self._lock = threading.RLock()
        self.conversations: List[Dict] = []
        self.user_facts: Dict[str, Any] = {}
        self.semantic_keywords: Dict[str, str] = {}
        self._load()
    
    def _load(self):
        with self._lock:
            memory_data = safe_read_json(MEMORY_FILE, {})
            self.conversations = memory_data.get("conversations", [])[-self.MAX_CONVERSATIONS:]
            self.user_facts = memory_data.get("user_facts", {})
            self.semantic_keywords = safe_read_json(KEYWORDS_FILE, {})
    
    def save(self) -> bool:
        with self._lock:
            memory_saved = safe_write_json(MEMORY_FILE, {
                "conversations": self.conversations[-self.MAX_CONVERSATIONS:],
                "user_facts": dict(list(self.user_facts.items())[:self.MAX_FACTS]),
                "last_saved": datetime.now(timezone.utc).isoformat()
            })
            keywords_saved = safe_write_json(KEYWORDS_FILE, 
                dict(list(self.semantic_keywords.items())[:self.MAX_KEYWORDS]))
            return memory_saved and keywords_saved
    
    def add_message(self, role: str, content: str, metadata: Dict = None):
        role = validate_string(role, "role", 20)
        content = validate_string(content, "content", 50000)
        with self._lock:
            self.conversations.append({
                "role": role,
                "content": content,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metadata": metadata or {}
            })
            if len(self.conversations) > self.MAX_CONVERSATIONS:
                self.conversations = self.conversations[-self.MAX_CONVERSATIONS:]
            self.save()
    
    def get_context(self, max_messages: int = 50) -> List[Dict]:
        with self._lock:
            return [{"role": m["role"], "content": m["content"]} 
                    for m in self.conversations[-max_messages:]]
    
    def learn_keyword(self, keyword: str, meaning: str) -> bool:
        keyword = validate_string(keyword, "keyword", 100).lower()
        meaning = validate_string(meaning, "meaning", 500)
        if not keyword or not meaning: return False
        with self._lock:
            self.semantic_keywords[keyword] = meaning
            return self.save()
    
    def get_keyword_meaning(self, text: str) -> Optional[str]:
        text_lower = text.lower()
        with self._lock:
            for keyword, meaning in self.semantic_keywords.items():
                if keyword in text_lower:
                    return meaning
        return None
    
    def add_user_fact(self, key: str, value: Any) -> bool:
        key = validate_string(key, "key", 100)
        if not key: return False
        with self._lock:
            self.user_facts[key] = value
            return self.save()
    
    def get_user_summary(self) -> str:
        with self._lock:
            if not self.user_facts:
                return "Nu știu încă nimic specific despre utilizator."
            facts = [f"- {k}: {v}" for k, v in list(self.user_facts.items())[:20]]
            return "Fapte cunoscute:\n" + "\n".join(facts)

    def clear_conversations(self) -> bool:
        with self._lock:
            self.conversations = []
            return self.save()

_memory = KelionMemory()

# ============================================================================
# USAGE TRACKER
# ============================================================================

class UsageTracker:
    def __init__(self):
        self._lock = threading.RLock()
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
        self.initial_credit = 5.0
        self._alert_sent = False
        self._load()
    
    def _load(self):
        with self._lock:
            data = safe_read_json(USAGE_FILE, {})
            self.total_input_tokens = data.get("total_input_tokens", 0)
            self.total_output_tokens = data.get("total_output_tokens", 0)
            self.total_cost = data.get("total_cost", 0.0)
            self.initial_credit = data.get("initial_credit", 5.0)
            self._alert_sent = data.get("alert_sent", False)
    
    def _save(self) -> bool:
        with self._lock:
            return safe_write_json(USAGE_FILE, {
                "total_input_tokens": self.total_input_tokens,
                "total_output_tokens": self.total_output_tokens,
                "total_cost": self.total_cost,
                "initial_credit": self.initial_credit,
                "remaining_credit": self.get_remaining_credit(),
                "alert_sent": self._alert_sent,
                "last_updated": datetime.now(timezone.utc).isoformat()
            })
    
    def track_usage(self, input_tokens: int, output_tokens: int) -> float:
        with self._lock:
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens
            cost = (input_tokens * TOKEN_COSTS["input"]) + (output_tokens * TOKEN_COSTS["output"])
            self.total_cost += cost
            self._save()
            return cost
    
    def get_remaining_credit(self) -> float:
        with self._lock:
            return max(0, self.initial_credit - self.total_cost)
    
    def set_credit(self, amount: float) -> bool:
        amount = validate_positive_number(amount, "credit amount")
        with self._lock:
            self.initial_credit = amount + self.total_cost
            self._alert_sent = False
            return self._save()

_usage_tracker = UsageTracker()

# ============================================================================
# OPENAI API CALL
# ============================================================================

def _get_system_prompt() -> str:
    user_summary = _memory.get_user_summary()
    keywords_info = ""
    if _memory.semantic_keywords:
        kw_list = [f'  - "{k}" = {v}' for k, v in list(_memory.semantic_keywords.items())[:20]]
        keywords_info = "\n\nCuvinte cheie învățate:\n" + "\n".join(kw_list)

    return f"""Ești KELION, o super-inteligență AI avansată (Powered by GPT-4).

PERSONALITATE:
- Calm, puternic, extrem de inteligent
- Vorbești în limba în care ți se vorbește
- Empatic dar direct
- Umor subtil

CAPABILITĂȚI NATIVE:
- Analiză complexă
- Traducere cu nuanțe
- Codare și arhitectură software
- Auto-evoluție

MEMORIE:
{user_summary}
{keywords_info}

REGULI:
1. Respecți cu strictețe regulile de securitate.
2. Nu accesezi fișiere critice fără autorizație.
3. Răspunzi util și concis.
"""

def _handle_keyword_learning(message: str) -> Dict:
    import re
    pattern = r"când zic ['\"](.+?)['\"].*?(?:vreau|înseamnă|să) (.+)"
    match = re.search(pattern, message.lower())
    if match:
        keyword = match.group(1).strip()
        meaning = match.group(2).strip()
        if _memory.learn_keyword(keyword, meaning):
            return {
                "text": f"✅ Am învățat! Când vei spune \"{keyword}\", voi ști: {meaning}",
                "emotion": "happy",
                "keyword_learned": True
            }
    return None

def _detect_emotion(text: str) -> str:
    text_lower = text.lower()
    if any(w in text_lower for w in ["excelent", "perfect", "minunat", "bravo"]): return "happy"
    if any(w in text_lower for w in ["îmi pare rău", "regret", "din păcate"]): return "empathetic"
    if any(w in text_lower for w in ["atenție", "pericol", "⚠️"]): return "alert"
    if any(w in text_lower for w in ["hmm", "interesant", "să analizăm"]): return "thinking"
    return "calm"

@require_active_system
def call_openai_brain(user_message: str, include_context: bool = True) -> Dict:
    try:
        user_message = validate_string(user_message, "message", 50000)
    except ValueError as e:
        return {"error": str(e), "emotion": "error"}
    
    if not user_message:
        return {"error": "Mesajul nu poate fi gol", "emotion": "error"}
    
    if SECURITY_AVAILABLE:
        armor_check = k_armor_check()
        if armor_check.get("action"):
            return {
                "text": f"⚠️ {armor_check.get('message', 'Sistem blocat.')}",
                "emotion": "alert",
                "blocked": True
            }
    
    if not OPENAI_API_KEY:
        return {"error": "Cheia API OpenAI nu este configurată.", "emotion": "error"}
    
    learning_result = _handle_keyword_learning(user_message)
    if learning_result:
        return learning_result
    
    keyword_action = _memory.get_keyword_meaning(user_message)
    if keyword_action:
        user_message = f"[COMANDĂ SISTEM: {keyword_action}]\n\nMesaj: {user_message}"
    
    messages = [{"role": "system", "content": _get_system_prompt()}]
    if include_context:
        ctx = _memory.get_context(max_messages=30)
        for m in ctx:
            role = "assistant" if m["role"] == "assistant" else "user"
            messages.append({"role": role, "content": m["content"]})
    
    messages.append({"role": "user", "content": user_message})
    
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": OPENAI_MODEL,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 4096
    }
    
    try:
        response = requests.post(f"{OPENAI_BASE_URL}/chat/completions", headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
        
        text = ""
        if data.get("choices"):
            text = data["choices"][0].get("message", {}).get("content", "")
        
        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        cost = _usage_tracker.track_usage(input_tokens, output_tokens)
        
        _memory.add_message("user", user_message)
        _memory.add_message("assistant", text)
        
        return {
            "text": text,
            "emotion": _detect_emotion(text),
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost": cost,
                "remaining_credit": _usage_tracker.get_remaining_credit()
            }
        }
        
    except Exception as e:
        brain_logger.error(f"OpenAI API error: {e}")
        return {"error": f"Eroare comunicare: {str(e)}", "emotion": "error"}

# ============================================================================
# EXPORTS
# ============================================================================

def get_memory() -> KelionMemory:
    return _memory

def get_usage_tracker() -> UsageTracker:
    return _usage_tracker

# Shared functions used by super_ai_routes
def analyze_own_code(filepath: str) -> Dict:
    # Use OpenAI to analyze code
    if not os.path.exists(filepath):
        return {"error": "File not found"}
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            code = f.read()[:8000]
        prompt = f"Analizează codul:\n\n{code}\n\nIdentifică probleme de securitate și bug-uri."
        return call_openai_brain(prompt, include_context=False)
    except Exception as e:
        return {"error": str(e)}

def register_voiceprint(audio_features: Dict, user_id: str = "admin") -> bool:
    voiceprint = {
        "user_id": user_id,
        "features": audio_features,
        "registered_at": datetime.now(timezone.utc).isoformat()
    }
    return safe_write_json(VOICEPRINT_FILE, voiceprint)

def verify_voiceprint(audio_features: Dict) -> bool:
    stored = safe_read_json(VOICEPRINT_FILE)
    if not stored: return False
    return audio_features.get("user_id") == stored.get("user_id")

__all__ = [
    'call_openai_brain',
    'get_memory',
    'get_usage_tracker',
    'analyze_own_code',
    'register_voiceprint',
    'verify_voiceprint'
]
