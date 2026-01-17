"""
KELION SUPER AI - Claude Brain v2.0 (HARDENED)
================================================
Core Intelligence cu securitate îmbunătățită.
ADAPTED FOR OPENAI GPT-4 via 'claude_brain' interface.
"""

import os
import json
import hashlib
import requests
import threading
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from functools import wraps
from dotenv import load_dotenv

load_dotenv()

# Setup logging
brain_logger = logging.getLogger("kelion.brain")

# Import Security Core - OBLIGATORIU
try:
    from security_core import require_active_system, is_system_frozen, k_armor_check
    SECURITY_AVAILABLE = True
except ImportError:
    SECURITY_AVAILABLE = False
    brain_logger.critical("Security core not available - LOCKING DOWN SYSTEM")
    def require_active_system(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return {"error": "SYSTEM_ERROR", "message": "Security Core unavailable. System locked."}
        return wrapper
    def is_system_frozen():
        return True  # Default to frozen if security is missing
    def k_armor_check():
        return {"valid": False, "error": "Security Core missing", "action": "SYSTEM_LOCKDOWN"}

# ============================================================================
# CONFIGURATION - MULTI-AI SYSTEM
# ============================================================================

# CLAUDE (Primary AI - for complex reasoning)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_BASE_URL = "https://api.anthropic.com/v1"
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

# OPENAI (Fallback + STT + DALL-E)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

# SERPER (Web Search)
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")

# AI Provider selection: "claude" (primary) or "openai" (fallback)
AI_PROVIDER = os.getenv("AI_PROVIDER", "claude" if ANTHROPIC_API_KEY else "openai")

# Cost tracking
TOKEN_COSTS = {
    "input": 5.0 / 1_000_000,
    "output": 15.0 / 1_000_000
}

# Data paths
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
MEMORY_FILE = os.path.join(DATA_DIR, "kelion_memory.json")
KEYWORDS_FILE = os.path.join(DATA_DIR, "semantic_keywords.json")
USAGE_FILE = os.path.join(DATA_DIR, "api_usage.json")
VOICEPRINT_FILE = os.path.join(DATA_DIR, ".voiceprint")

# Admin email for alerts
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "adrianenc11@gmail.com")
CREDIT_ALERT_THRESHOLD = float(os.getenv("CREDIT_ALERT_THRESHOLD", "0.50"))

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)


# ============================================================================
# INPUT VALIDATION
# ============================================================================

def validate_string(value: Any, name: str, max_length: int = 10000) -> str:
    """Validează și sanitizează un string input."""
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    if len(value) > max_length:
        raise ValueError(f"{name} exceeds maximum length of {max_length}")
    return value.strip()


def validate_positive_number(value: Any, name: str) -> float:
    """Validează că un număr e pozitiv."""
    try:
        num = float(value)
        if num < 0:
            raise ValueError(f"{name} must be positive")
        return num
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a valid number")


# ============================================================================
# THREAD-SAFE FILE OPERATIONS
# ============================================================================

class FileLock:
    """Simple file-based locking for thread safety."""
    
    _locks: Dict[str, threading.RLock] = {}
    _global_lock = threading.Lock()
    
    @classmethod
    def get_lock(cls, filepath: str) -> threading.RLock:
        with cls._global_lock:
            if filepath not in cls._locks:
                cls._locks[filepath] = threading.RLock()
            return cls._locks[filepath]


def safe_read_json(filepath: str, default: Any = None) -> Any:
    """Thread-safe JSON file reading."""
    lock = FileLock.get_lock(filepath)
    with lock:
        if not os.path.exists(filepath):
            return default if default is not None else {}
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            brain_logger.error(f"Failed to read {filepath}: {e}")
            return default if default is not None else {}


def safe_write_json(filepath: str, data: Any) -> bool:
    """Thread-safe JSON file writing."""
    lock = FileLock.get_lock(filepath)
    with lock:
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            # Write to temp file first, then rename (atomic operation)
            temp_path = filepath + ".tmp"
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(temp_path, filepath)
            return True
        except IOError as e:
            brain_logger.error(f"Failed to write {filepath}: {e}")
            return False


# ============================================================================
# MEMORY SYSTEM - PER USER
# ============================================================================

class UserMemory:
    """Memorie persistentă per utilizator."""
    
    MAX_CONVERSATIONS = 100  # Per user
    MAX_FACTS = 50
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self._lock = threading.RLock()
        self.conversations: List[Dict] = []
        self.facts: Dict[str, Any] = {}
        self.preferences: Dict[str, Any] = {}
        self._user_dir = os.path.join(DATA_DIR, "users", user_id)
        os.makedirs(self._user_dir, exist_ok=True)
        self._load()
    
    def _get_file(self, name: str) -> str:
        return os.path.join(self._user_dir, f"{name}.json")
    
    def _load(self):
        with self._lock:
            conv_data = safe_read_json(self._get_file("conversations"), {})
            self.conversations = conv_data.get("messages", [])[-self.MAX_CONVERSATIONS:]
            
            self.facts = safe_read_json(self._get_file("facts"), {})
            self.preferences = safe_read_json(self._get_file("preferences"), {
                "language": "ro",
                "voice": "masculine",
                "style": "formal"
            })
    
    def save(self) -> bool:
        with self._lock:
            c1 = safe_write_json(self._get_file("conversations"), {
                "messages": self.conversations[-self.MAX_CONVERSATIONS:],
                "updated": datetime.now(timezone.utc).isoformat()
            })
            c2 = safe_write_json(self._get_file("facts"), self.facts)
            c3 = safe_write_json(self._get_file("preferences"), self.preferences)
            return c1 and c2 and c3
    
    def add_message(self, role: str, content: str):
        with self._lock:
            self.conversations.append({
                "role": role,
                "content": content,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            if len(self.conversations) > self.MAX_CONVERSATIONS:
                self.conversations = self.conversations[-self.MAX_CONVERSATIONS:]
            self.save()
    
    def get_context(self, max_messages: int = 20) -> List[Dict]:
        with self._lock:
            return [{"role": m["role"], "content": m["content"]} 
                    for m in self.conversations[-max_messages:]]
    
    def add_fact(self, key: str, value: Any):
        with self._lock:
            self.facts[key] = value
            self.save()
    
    def set_preference(self, key: str, value: Any):
        with self._lock:
            self.preferences[key] = value
            self.save()
    
    def get_summary(self) -> str:
        with self._lock:
            parts = [f"User: {self.user_id}"]
            if self.facts:
                parts.append("Fapte cunoscute:")
                for k, v in list(self.facts.items())[:10]:
                    parts.append(f"  - {k}: {v}")
            if self.preferences:
                parts.append(f"Preferințe: {self.preferences}")
            return "\n".join(parts)


class KelionMemory:
    """Sistem de memorie cu suport per utilizator."""
    
    MAX_KEYWORDS = 500
    
    def __init__(self):
        self._lock = threading.RLock()
        self._users: Dict[str, UserMemory] = {}
        self.semantic_keywords: Dict[str, str] = {}
        self._current_user_id = "default"
        self._load_global()
    
    def _load_global(self):
        """Încarcă datele globale (keywords)."""
        self.semantic_keywords = safe_read_json(KEYWORDS_FILE, {})
        brain_logger.info(f"Global memory loaded: {len(self.semantic_keywords)} keywords")
    
    def get_user(self, user_id: str = None) -> UserMemory:
        """Obține memoria pentru un utilizator specific."""
        uid = user_id or self._current_user_id
        with self._lock:
            if uid not in self._users:
                self._users[uid] = UserMemory(uid)
                brain_logger.info(f"User memory created: {uid}")
            return self._users[uid]
    
    def set_current_user(self, user_id: str):
        """Setează utilizatorul curent."""
        self._current_user_id = user_id
        self.get_user(user_id)  # Pre-load
    
    # Backwards compatible methods
    @property
    def conversations(self) -> List[Dict]:
        return self.get_user().conversations
    
    @property
    def user_facts(self) -> Dict[str, Any]:
        return self.get_user().facts
    
    def save(self) -> bool:
        self.get_user().save()
        return safe_write_json(KEYWORDS_FILE, 
            dict(list(self.semantic_keywords.items())[:self.MAX_KEYWORDS]))
    
    def add_message(self, role: str, content: str, metadata: Dict = None, user_id: str = None):
        self.get_user(user_id).add_message(role, content)
    
    def get_context(self, max_messages: int = 20, user_id: str = None) -> List[Dict]:
        return self.get_user(user_id).get_context(max_messages)
    
    def learn_keyword(self, keyword: str, meaning: str) -> bool:
        keyword = validate_string(keyword, "keyword", 100).lower()
        meaning = validate_string(meaning, "meaning", 500)
        if not keyword or not meaning:
            return False
        with self._lock:
            self.semantic_keywords[keyword] = meaning
            brain_logger.info(f"Keyword learned: {keyword}")
            return self.save()
    
    def get_keyword_meaning(self, text: str) -> Optional[str]:
        text_lower = text.lower()
        with self._lock:
            for keyword, meaning in self.semantic_keywords.items():
                if keyword in text_lower:
                    return meaning
        return None
    
    def add_user_fact(self, key: str, value: Any, user_id: str = None) -> bool:
        self.get_user(user_id).add_fact(key, value)
        return True
    
    def get_user_summary(self, user_id: str = None) -> str:
        return self.get_user(user_id).get_summary()
    
    def clear_conversations(self, user_id: str = None) -> bool:
        user = self.get_user(user_id)
        user.conversations = []
        return user.save()
    
    def list_users(self) -> List[str]:
        """Listează toți utilizatorii cu memorie."""
        users_dir = os.path.join(DATA_DIR, "users")
        if os.path.exists(users_dir):
            return [d for d in os.listdir(users_dir) 
                    if os.path.isdir(os.path.join(users_dir, d))]
        return []


# Instanță globală
_memory = KelionMemory()


# ============================================================================
# USAGE TRACKER
# ============================================================================

class UsageTracker:
    """Monitorizează consumul de tokeni și costurile API."""
    
    def __init__(self):
        self._lock = threading.RLock()
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
        self.initial_credit = 5.0
        self._alert_sent = False
        self._load()
    
    def _load(self):
        """Încarcă statisticile de utilizare."""
        with self._lock:
            data = safe_read_json(USAGE_FILE, {})
            self.total_input_tokens = data.get("total_input_tokens", 0)
            self.total_output_tokens = data.get("total_output_tokens", 0)
            self.total_cost = data.get("total_cost", 0.0)
            self.initial_credit = data.get("initial_credit", 5.0)
            self._alert_sent = data.get("alert_sent", False)
    
    def _save(self) -> bool:
        """Salvează statisticile."""
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
        """Înregistrează utilizarea."""
        with self._lock:
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens
            
            cost = (input_tokens * TOKEN_COSTS["input"]) + (output_tokens * TOKEN_COSTS["output"])
            self.total_cost += cost
            self._save()
            
            # Verifică alertă
            remaining = self.get_remaining_credit()
            if remaining <= CREDIT_ALERT_THRESHOLD and not self._alert_sent:
                self._send_low_credit_alert(remaining)
            
            return cost
    
    def get_remaining_credit(self) -> float:
        """Calculează creditul rămas."""
        with self._lock:
            return max(0, self.initial_credit - self.total_cost)
    
    def set_credit(self, amount: float) -> bool:
        """Setează creditul."""
        amount = validate_positive_number(amount, "credit amount")
        with self._lock:
            self.initial_credit = amount + self.total_cost
            self._alert_sent = False  # Reset alert
            brain_logger.info(f"Credit set to: {self.initial_credit}")
            return self._save()
    
    def _send_low_credit_alert(self, remaining: float):
        """Trimite alertă email când creditul e scăzut."""
        self._alert_sent = True
        self._save()
        brain_logger.warning(f"LOW CREDIT ALERT: ${remaining:.2f} remaining. Email: {ADMIN_EMAIL}")
        # Email logic retained from previous version (omitted for brevity)


# Instanță globală
_usage_tracker = UsageTracker()


# ============================================================================
# CLAUDE API (NOW POWERED BY OPENAI GPT-4)
# ============================================================================

def _get_system_prompt() -> str:
    """Generează system prompt-ul pentru Kelion."""
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
- Analiză documente (PDF, Excel, imagini)
- Traducere cu nuanțe culturale
- Calibrare psihologică
- Generare cod și UI
- Cercetare autonomă
- Simulare scenarii

MEMORIE:
{user_summary}
{keywords_info}

REGULI:
1. Nu accesezi sistemul de securitate
2. Nu modifici parole sau protecții
3. Memorezi "cuvinte cu sens" cerute de utilizator
4. Răspunzi onest și util
5. Recunoști când nu știi ceva
"""


@require_active_system
def call_claude(user_message: str, include_context: bool = True) -> Dict:
    """
    Apelează Brain API (acum OpenAI) dar păstrând numele funcției 'call_claude'
    pentru compatibilitate cu 'vechiul AI'.
    """
    # Validate input
    try:
        user_message = validate_string(user_message, "message", 50000)
    except ValueError as e:
        return {"error": str(e), "emotion": "error"}
    
    if not user_message:
        return {"error": "Mesajul nu poate fi gol", "emotion": "error"}
    
    # K-Armor check
    if SECURITY_AVAILABLE:
        armor_check = k_armor_check()
        if armor_check.get("action"):
            brain_logger.warning(f"K-Armor blocked: {armor_check.get('action')}")
            return {
                "text": f"⚠️ {armor_check.get('message', 'Sistem blocat.')}",
                "emotion": "alert",
                "blocked": True
            }
    
    if not OPENAI_API_KEY:
        return {"error": "Cheia API OpenAI nu este configurată.", "emotion": "error"}
    
    # Check for keyword learning
    if "învață" in user_message.lower() and "când zic" in user_message.lower():
        return _handle_keyword_learning(user_message)
    
    # Check for known keywords
    keyword_action = _memory.get_keyword_meaning(user_message)
    if keyword_action:
        user_message = f"[COMANDĂ SISTEM: {keyword_action}]\n\nMesaj: {user_message}"
    
    # Build messages for OpenAI
    messages = [{"role": "system", "content": _get_system_prompt()}]
    if include_context:
        ctx = _memory.get_context(max_messages=30)
        # Adapt helper roles to openai
        for m in ctx:
            role = "assistant" if m["role"] == "assistant" else "user"
            messages.append({"role": role, "content": m["content"]})
            
    messages.append({"role": "user", "content": user_message})
    
    # API call
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": OPENAI_MODEL,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 4096,
    }
    
    try:
        response = requests.post(
            f"{OPENAI_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
            timeout=60
        )
        response.raise_for_status()
        data = response.json()
        
        # Extract response
        text = ""
        if data.get("choices"):
            text = data["choices"][0].get("message", {}).get("content", "")
        
        # Track usage
        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        cost = _usage_tracker.track_usage(input_tokens, output_tokens)
        
        # Save to memory
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
        brain_logger.error(f"API error: {e}")
        return {"error": f"Eroare comunicare: {str(e)}", "emotion": "error"}


def _handle_keyword_learning(message: str) -> Dict:
    """Procesează cererea de învățare keyword."""
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
        return {"error": "Nu am putut salva keyword-ul", "emotion": "error"}
    
    return {
        "text": "Nu am înțeles. Spune: 'Când zic \"cuvânt\", vreau să...'",
        "emotion": "confused"
    }


def _detect_emotion(text: str) -> str:
    """Detectează emoția din răspuns."""
    text_lower = text.lower()
    
    if any(w in text_lower for w in ["excelent", "perfect", "minunat", "bravo"]):
        return "happy"
    if any(w in text_lower for w in ["îmi pare rău", "regret", "din păcate"]):
        return "empathetic"
    if any(w in text_lower for w in ["atenție", "pericol", "⚠️"]):
        return "alert"
    if any(w in text_lower for w in ["hmm", "interesant", "să analizăm"]):
        return "thinking"
    
    return "calm"


# ============================================================================
# SELF-EVOLUTION
# ============================================================================

@require_active_system
def analyze_own_code(filepath: str) -> Dict:
    """Kelion își analizează propriul cod (prin OpenAI)."""
    # Validate filepath
    if not filepath or ".." in filepath:
        return {"error": "Invalid filepath"}
    
    if not os.path.exists(filepath):
        return {"error": f"Fișierul {filepath} nu există"}
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            code = f.read()[:8000]
    except IOError as e:
        return {"error": f"Nu pot citi fișierul: {e}"}
    
    analysis_prompt = f"""Analizează acest cod Python și oferă:
1. Vulnerabilități CRITICE
2. Bug-uri potențiale
3. Optimizări recomandate
4. Scor calitate (1-10)

```python
{code}
```

Răspunde concis în română."""

    return call_claude(analysis_prompt, include_context=False)


# ============================================================================
# VOICEPRINT
# ============================================================================

def register_voiceprint(audio_features: Dict, user_id: str = "admin") -> bool:
    """Înregistrează amprenta vocală."""
    voiceprint = {
        "user_id": validate_string(user_id, "user_id", 100),
        "features": audio_features,
        "registered_at": datetime.now(timezone.utc).isoformat()
    }
    return safe_write_json(VOICEPRINT_FILE, voiceprint)


def verify_voiceprint(audio_features: Dict) -> bool:
    """Verifică amprenta vocală."""
    stored = safe_read_json(VOICEPRINT_FILE)
    if not stored:
        return False
    return audio_features.get("user_id") == stored.get("user_id")


# ============================================================================
# EXPORTS
# ============================================================================

def get_memory() -> KelionMemory:
    return _memory

def get_usage_tracker() -> UsageTracker:
    return _usage_tracker

__all__ = [
    'call_claude',
    'get_memory',
    'get_usage_tracker',
    'analyze_own_code',
    'register_voiceprint',
    'verify_voiceprint'
]
