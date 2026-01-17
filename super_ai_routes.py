"""
KELION SUPER AI - Complete API Routes v2.0 (HARDENED)
=======================================================
Toate endpoint-urile pentru funcționalitățile Super AI.
Securitate îmbunătățită conform auditului AI.
"""

from flask import Blueprint, jsonify, request
import os
import base64
import logging
import threading
import time
from functools import wraps
from collections import defaultdict

# Setup logging
api_logger = logging.getLogger("kelion.api")

# Import toate modulele
try:
    from security_core import (
        freeze_system, unfreeze_system, is_system_frozen,
        set_master_password, verify_master_password,
        register_authorized_host, k_armor_check, save_code_integrity,
        secure_compare  # Import secure comparison
    )
    from claude_brain import (
        call_claude, get_memory, get_usage_tracker,
        analyze_own_code, register_voiceprint, verify_voiceprint
    )
    from vision_module import (
        analyze_image, get_face_tracking, get_vision_observer
    )
    from voice_module import (
        synthesize_speech, verify_voice, translate_text,
        get_voice_authority, get_voiceprint_auth, get_translator
    )
    from extensions_module import (
        get_web_search, get_iot_controller, get_financial_guardian,
        get_offline_vault, get_legacy_mode
    )
    SUPER_AI_AVAILABLE = True
except ImportError as e:
    SUPER_AI_AVAILABLE = False
    api_logger.error(f"Super AI modules not available: {e}")

# Blueprint
super_ai_bp = Blueprint('super_ai', __name__, url_prefix='/api/super')


# ============================================================================
# MIDDLEWARE
# ============================================================================

@super_ai_bp.before_request
def check_system_status():
    """Verifică starea sistemului înainte de fiecare request."""
    if not SUPER_AI_AVAILABLE:
        return jsonify({"error": "Super AI modules not loaded"}), 500
    
    # Normalize path for comparison
    allowed_frozen = ['/api/super/unfreeze', '/api/super/status', '/api/super/health']
    normalized_path = request.path.rstrip('/')
    if normalized_path in allowed_frozen:
        return None
    
    if is_system_frozen():
        api_logger.warning(f"Request blocked - system frozen: {request.path}")
        return jsonify({
            "error": "SYSTEM_FROZEN",
            "message": "Kelion este în Repaus Total."
        }), 423


def require_admin():
    """
    Verifică token-ul admin folosind constant-time comparison.
    Previne timing attacks.
    """
    admin_token = request.headers.get("X-Admin-Token", "")
    expected_token = os.getenv("K1_ADMIN_TOKEN", "")
    
    if not expected_token:
        api_logger.error("K1_ADMIN_TOKEN not configured!")
        return False
    
    # Use secure constant-time comparison
    is_valid = secure_compare(admin_token, expected_token)
    
    if not is_valid:
        client_ip = request.remote_addr or "unknown"
        api_logger.warning(f"Invalid admin token from: {client_ip}")
    else:
        api_logger.info(f"Admin access granted: {request.path}")
    
    return is_valid


# ============================================================================
# RATE LIMITING
# ============================================================================

class APIRateLimiter:
    """Rate limiter simplu pentru API endpoints."""
    
    def __init__(self):
        self._requests = defaultdict(list)
        self._lock = threading.RLock()
        # Start cleanup thread
        t = threading.Thread(target=self._cleanup_loop, daemon=True)
        t.start()
    
    def is_allowed(self, identifier: str, max_requests: int = 60, window_seconds: int = 60) -> bool:
        """Verifică dacă request-ul este permis."""
        now = time.time()
        cutoff = now - window_seconds
        
        with self._lock:
            return self._check_and_add(identifier, now, cutoff, max_requests)
    
    def _check_and_add(self, identifier: str, now: float, cutoff: float, max_requests: int) -> bool:
        # Cleanup old requests for this specific user inline
        self._requests[identifier] = [ts for ts in self._requests[identifier] if ts > cutoff]
        
        if len(self._requests[identifier]) >= max_requests:
            return False
        
        self._requests[identifier].append(now)
        return True

    def _cleanup_loop(self):
        while True:
            time.sleep(300) # Cleanup every 5 minutes
            with self._lock:
                now = time.time()
                cutoff = now - 3600 # Clear anything older than 1 hour
                keys_to_del = []
                for k, v in self._requests.items():
                    # Keep recent
                    new_v = [ts for ts in v if ts > cutoff]
                    if not new_v:
                        keys_to_del.append(k)
                    else:
                        self._requests[k] = new_v
                for k in keys_to_del:
                    del self._requests[k]


_rate_limiter = APIRateLimiter()


def rate_limit(max_requests: int = 30, window_seconds: int = 60):
    """Decorator pentru rate limiting pe endpoint."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            identifier = request.remote_addr or "unknown"
            
            if not _rate_limiter.is_allowed(identifier, max_requests, window_seconds):
                api_logger.warning(f"Rate limited: {identifier} on {request.path}")
                return jsonify({
                    "error": "RATE_LIMITED",
                    "message": "Prea multe cereri. Așteaptă câteva secunde."
                }), 429
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


# ============================================================================
# HEALTH & STATUS
# ============================================================================

@super_ai_bp.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "system": "Kelion Super AI (Secure)"}) # Sanitized output



@super_ai_bp.route('/status', methods=['GET'])
def get_status():
    if not require_admin():
         return jsonify({"error": "Acces interzis"}), 403
    armor = k_armor_check()
    usage = get_usage_tracker()
    memory = get_memory()
    
    return jsonify({
        "frozen": is_system_frozen(),
        "host_authorized": armor.get("host_authorized", True),
        "code_integrity": armor.get("code_integrity", {}).get("valid", True),
        "credit": {
            "remaining": usage.get_remaining_credit(),
            "total_spent": usage.total_cost
        },
        "memory": {
            "conversations": len(memory.conversations),
            "keywords": len(memory.semantic_keywords),
            "user_facts": len(memory.user_facts)
        },
        "modules": {
            "vision": True,
            "voice": True,
            "extensions": True
        }
    })


# ============================================================================
# SECURITY (Kill Switch & K-Armor)
# ============================================================================

@super_ai_bp.route('/freeze', methods=['POST'])
@rate_limit(max_requests=5, window_seconds=60)
def freeze():
    data = request.get_json() or {}
    password = data.get("password", "")
    if not password:
        return jsonify({"error": "Parola Master este obligatorie"}), 400
    result = freeze_system(password)
    return jsonify(result), 200 if result.get("success") else 401


@super_ai_bp.route('/unfreeze', methods=['POST'])
@rate_limit(max_requests=5, window_seconds=60)
def unfreeze():
    data = request.get_json() or {}
    password = data.get("password", "")
    if not password:
        return jsonify({"error": "Parola Master este obligatorie"}), 400
    result = unfreeze_system(password)
    return jsonify(result), 200 if result.get("success") else 401


@super_ai_bp.route('/admin/set-password', methods=['POST'])
@rate_limit(max_requests=3, window_seconds=300)
def admin_set_password():
    if not require_admin():
        return jsonify({"error": "Acces interzis"}), 403
    data = request.get_json() or {}
    new_password = data.get("password", "")
    if not new_password or len(new_password) < 8:
        return jsonify({"error": "Parola trebuie să aibă minim 8 caractere"}), 400
    set_master_password(new_password)
    return jsonify({"success": True, "message": "Parola Master actualizată"})


@super_ai_bp.route('/admin/register-host', methods=['POST'])
def admin_register_host():
    if not require_admin():
        return jsonify({"error": "Acces interzis"}), 403
    result = register_authorized_host()
    return jsonify(result)


@super_ai_bp.route('/admin/save-integrity', methods=['POST'])
def admin_save_integrity():
    if not require_admin():
        return jsonify({"error": "Acces interzis"}), 403
    hashes = save_code_integrity()
    return jsonify({"success": True, "hashes": hashes})


# ============================================================================
# CHAT (Core Intelligence)
# ============================================================================

@super_ai_bp.route('/chat', methods=['POST'])
@rate_limit(max_requests=20, window_seconds=60)
def chat():
    data = request.get_json() or {}
    message = data.get("message", "").strip()
    include_context = data.get("include_context", True)
    
    if not message:
        return jsonify({"error": "Mesajul este obligatoriu"}), 400
    
    result = call_claude(message, include_context=include_context)
    
    if result.get("blocked"):
        return jsonify(result), 403
    
    return jsonify(result)


# ============================================================================
# MEMORY & KEYWORDS
# ============================================================================

@super_ai_bp.route('/memory/keywords', methods=['GET'])
def get_keywords():
    if not require_admin():
        return jsonify({"error": "Acces interzis"}), 403
    memory = get_memory()
    return jsonify({
        "keywords": memory.semantic_keywords,
        "count": len(memory.semantic_keywords)
    })


@super_ai_bp.route('/memory/keywords', methods=['POST'])
def add_keyword():
    if not require_admin():
        return jsonify({"error": "Acces interzis"}), 403
    data = request.get_json() or {}
    keyword = data.get("keyword", "").strip()
    meaning = data.get("meaning", "").strip()
    if not keyword or not meaning:
        return jsonify({"error": "keyword și meaning sunt obligatorii"}), 400
    memory = get_memory()
    memory.learn_keyword(keyword, meaning)
    return jsonify({"success": True, "message": f"Cuvânt cheie '{keyword}' salvat"})


@super_ai_bp.route('/memory/facts', methods=['GET'])
def get_facts():
    if not require_admin():
        return jsonify({"error": "Acces interzis"}), 403
    memory = get_memory()
    return jsonify({"facts": memory.user_facts})


@super_ai_bp.route('/memory/facts', methods=['POST'])
def add_fact():
    if not require_admin():
        return jsonify({"error": "Acces interzis"}), 403
    data = request.get_json() or {}
    key = data.get("key", "").strip()
    value = data.get("value")
    if not key:
        return jsonify({"error": "key este obligatoriu"}), 400
    memory = get_memory()
    memory.add_user_fact(key, value)
    return jsonify({"success": True})


@super_ai_bp.route('/memory/clear', methods=['POST'])
def clear_memory():
    if not require_admin():
        return jsonify({"error": "Acces interzis"}), 403
    memory = get_memory()
    memory.conversations = []
    memory.save()
    return jsonify({"success": True, "message": "Memoria conversațiilor a fost ștearsă"})


# ============================================================================
# USAGE & COST
# ============================================================================

@super_ai_bp.route('/usage', methods=['GET'])
def get_usage():
    if not require_admin():
        return jsonify({"error": "Acces interzis"}), 403
    tracker = get_usage_tracker()
    return jsonify({
        "total_input_tokens": tracker.total_input_tokens,
        "total_output_tokens": tracker.total_output_tokens,
        "total_cost": round(tracker.total_cost, 4),
        "remaining_credit": round(tracker.get_remaining_credit(), 4),
        "initial_credit": tracker.initial_credit
    })


@super_ai_bp.route('/usage/set-credit', methods=['POST'])
def set_credit():
    if not require_admin():
        return jsonify({"error": "Acces interzis"}), 403
    data = request.get_json() or {}
    amount = data.get("amount", 0)
    if amount <= 0:
        return jsonify({"error": "Suma trebuie să fie pozitivă"}), 400
    tracker = get_usage_tracker()
    tracker.set_credit(amount)
    return jsonify({"success": True, "new_credit": tracker.get_remaining_credit()})


# ============================================================================
# VISION
# ============================================================================

@super_ai_bp.route('/vision/analyze', methods=['POST'])
def vision_analyze():
    """Analizează o imagine cu Claude Vision."""
    data = request.get_json() or {}
    image_base64 = data.get("image", "")
    context = data.get("context", "")
    
    if not image_base64:
        return jsonify({"error": "Imaginea este obligatorie (base64)"}), 400
    
    # Elimină prefixul data:image/... dacă există
    if "base64," in image_base64:
        image_base64 = image_base64.split("base64,")[1]
    
    result = analyze_image(image_base64, context)
    return jsonify(result)


@super_ai_bp.route('/vision/face-tracking', methods=['GET'])
def vision_face_tracking():
    """Obține datele pentru face tracking."""
    return jsonify(get_face_tracking())


@super_ai_bp.route('/vision/observations', methods=['GET'])
def vision_observations():
    """Obține ultimele observații vizuale."""
    if not require_admin():
        return jsonify({"error": "Acces interzis"}), 403
    count = request.args.get("count", 5, type=int)
    observer = get_vision_observer()
    return jsonify({
        "observations": observer.get_recent_observations(count),
        "user_state": observer.get_user_state_summary()
    })


# ============================================================================
# VOICE
# ============================================================================

@super_ai_bp.route('/voice/synthesize', methods=['POST'])
def voice_synthesize():
    """Sintetizează text în audio."""
    data = request.get_json() or {}
    text = data.get("text", "").strip()
    voice = data.get("voice")
    
    if not text:
        return jsonify({"error": "Textul este obligatoriu"}), 400
    
    result = synthesize_speech(text, voice)
    return jsonify(result)


@super_ai_bp.route('/voice/translate', methods=['POST'])
def voice_translate():
    """Traduce text cu nuanțe culturale."""
    data = request.get_json() or {}
    text = data.get("text", "").strip()
    source = data.get("source", "auto")
    target = data.get("target", "en")
    
    if not text:
        return jsonify({"error": "Textul este obligatoriu"}), 400
    
    result = translate_text(text, target)
    return jsonify(result)


@super_ai_bp.route('/voiceprint/register', methods=['POST'])
def register_voice():
    if not require_admin():
        return jsonify({"error": "Acces interzis"}), 403
    data = request.get_json() or {}
    features = data.get("features", {})
    user_id = data.get("user_id", "admin")
    if not features:
        return jsonify({"error": "Audio features obligatorii"}), 400
    auth = get_voiceprint_auth()
    result = auth.register(features, user_id)
    return jsonify(result)


@super_ai_bp.route('/voiceprint/verify', methods=['POST'])
def verify_voiceprint_route():
    data = request.get_json() or {}
    features = data.get("features", {})
    if not features:
        return jsonify({"error": "Audio features obligatorii"}), 400
    result = verify_voice(features)
    return jsonify(result)


# ============================================================================
# WEB SEARCH
# ============================================================================

@super_ai_bp.route('/search', methods=['POST'])
def web_search():
    """Caută pe web."""
    data = request.get_json() or {}
    query = data.get("query", "").strip()
    num_results = data.get("num_results", 5)
    
    if not query:
        return jsonify({"error": "Query este obligatoriu"}), 400
    
    search_engine = get_web_search()
    result = search_engine.search(query, num_results)
    return jsonify(result)


@super_ai_bp.route('/search/news', methods=['GET'])
def web_news():
    """Obține știri."""
    topic = request.args.get("topic", "technology")
    search_engine = get_web_search()
    return jsonify(search_engine.get_news(topic))


@super_ai_bp.route('/search/weather', methods=['GET'])
def web_weather():
    """Obține vremea."""
    location = request.args.get("location", "Bucharest")
    search_engine = get_web_search()
    return jsonify(search_engine.get_weather(location))


# ============================================================================
# IoT CONTROL
# ============================================================================

@super_ai_bp.route('/iot/devices', methods=['GET'])
def iot_list_devices():
    """Listează dispozitivele IoT."""
    if not require_admin():
        return jsonify({"error": "Acces interzis"}), 403
    controller = get_iot_controller()
    return jsonify(controller.list_devices())


@super_ai_bp.route('/iot/control', methods=['POST'])
def iot_control():
    """Controlează un dispozitiv."""
    data = request.get_json() or {}
    device_id = data.get("device_id", "")
    action = data.get("action", "")
    params = data.get("params", {})
    
    if not require_admin():
        return jsonify({"error": "Acces interzis"}), 403
    
    if not device_id or not action:
        return jsonify({"error": "device_id și action sunt obligatorii"}), 400
    
    controller = get_iot_controller()
    result = controller.control_device(device_id, action, params)
    return jsonify(result)


@super_ai_bp.route('/iot/scenes', methods=['POST'])
def iot_create_scene():
    """Creează o scenă."""
    data = request.get_json() or {}
    name = data.get("name", "")
    devices_states = data.get("devices", [])
    
    if not require_admin():
        return jsonify({"error": "Acces interzis"}), 403
    
    if not name:
        return jsonify({"error": "Numele scenei este obligatoriu"}), 400
    
    controller = get_iot_controller()
    result = controller.create_scene(name, devices_states)
    return jsonify(result)


@super_ai_bp.route('/iot/scenes/<name>/activate', methods=['POST'])
def iot_activate_scene(name):
    """Activează o scenă."""
    if not require_admin():
        return jsonify({"error": "Acces interzis"}), 403
    controller = get_iot_controller()
    result = controller.activate_scene(name)
    return jsonify(result)


# ============================================================================
# FINANCIAL GUARDIAN
# ============================================================================

@super_ai_bp.route('/finance/crypto/<symbol>', methods=['GET'])
def finance_crypto_price(symbol):
    """Obține prețul unei criptomonede."""
    if not require_admin():
        return jsonify({"error": "Acces interzis"}), 403
    guardian = get_financial_guardian()
    return jsonify(guardian.get_crypto_price(symbol))


@super_ai_bp.route('/finance/portfolio', methods=['GET'])
def finance_portfolio():
    """Obține valoarea portofoliului."""
    if not require_admin():
        return jsonify({"error": "Acces interzis"}), 403
    guardian = get_financial_guardian()
    return jsonify(guardian.get_portfolio_value())


@super_ai_bp.route('/finance/portfolio', methods=['POST'])
def finance_add_holding():
    """Adaugă un activ în portofoliu."""
    data = request.get_json() or {}
    symbol = data.get("symbol", "")
    amount = data.get("amount", 0)
    buy_price = data.get("buy_price", 0)
    
    if not require_admin():
        return jsonify({"error": "Acces interzis"}), 403
    
    if not symbol or amount <= 0:
        return jsonify({"error": "symbol și amount sunt obligatorii"}), 400
    
    guardian = get_financial_guardian()
    result = guardian.add_holding(symbol, amount, buy_price)
    return jsonify(result)


@super_ai_bp.route('/finance/alerts', methods=['POST'])
def finance_set_alert():
    """Setează o alertă de preț."""
    data = request.get_json() or {}
    symbol = data.get("symbol", "")
    target_price = data.get("target_price", 0)
    direction = data.get("direction", "above")
    
    if not require_admin():
        return jsonify({"error": "Acces interzis"}), 403
    
    if not symbol or target_price <= 0:
        return jsonify({"error": "symbol și target_price sunt obligatorii"}), 400
    
    guardian = get_financial_guardian()
    result = guardian.set_price_alert(symbol, target_price, direction)
    return jsonify(result)


@super_ai_bp.route('/finance/alerts/check', methods=['GET'])
def finance_check_alerts():
    """Verifică alertele."""
    if not require_admin():
        return jsonify({"error": "Acces interzis"}), 403
    guardian = get_financial_guardian()
    triggered = guardian.check_alerts()
    return jsonify({"triggered": triggered})


# ============================================================================
# OFFLINE VAULT
# ============================================================================

@super_ai_bp.route('/vault/search', methods=['GET'])
def vault_search():
    """Caută în vault."""
    query = request.args.get("q", "")
    if not require_admin():
        return jsonify({"error": "Acces interzis"}), 403
    if not query:
        return jsonify({"error": "Query obligatoriu"}), 400
    vault = get_offline_vault()
    results = vault.search(query)
    return jsonify({"results": results})


@super_ai_bp.route('/vault/survival', methods=['GET'])
def vault_survival():
    """Obține cunoștințe de supraviețuire."""
    vault = get_offline_vault()
    return jsonify(vault.get_survival_basics())


@super_ai_bp.route('/vault/add', methods=['POST'])
def vault_add():
    """Adaugă cunoștințe în vault."""
    if not require_admin():
        return jsonify({"error": "Acces interzis"}), 403
    data = request.get_json() or {}
    topic = data.get("topic", "")
    content = data.get("content", "")
    if not topic or not content:
        return jsonify({"error": "topic și content sunt obligatorii"}), 400
    vault = get_offline_vault()
    result = vault.add_knowledge(topic, content)
    return jsonify(result)


# ============================================================================
# LEGACY MODE (Digital Twin)
# ============================================================================

@super_ai_bp.route('/legacy/profile', methods=['GET'])
def legacy_profile():
    """Obține profilul digital twin."""
    if not require_admin():
        return jsonify({"error": "Acces interzis"}), 403
    legacy = get_legacy_mode()
    return jsonify({
        "profile": legacy.profile,
        "memories_count": len(legacy.memories),
        "style_learned": bool(legacy.style_patterns)
    })


@super_ai_bp.route('/legacy/profile', methods=['POST'])
def legacy_update_profile():
    """Actualizează profilul."""
    data = request.get_json() or {}
    key = data.get("key", "")
    value = data.get("value")
    if not require_admin():
        return jsonify({"error": "Acces interzis"}), 403
    
    if not key:
        return jsonify({"error": "key este obligatoriu"}), 400
    legacy = get_legacy_mode()
    result = legacy.update_profile(key, value)
    return jsonify(result)


@super_ai_bp.route('/legacy/memory', methods=['POST'])
def legacy_add_memory():
    """Adaugă o amintire."""
    data = request.get_json() or {}
    memory = data.get("memory", "")
    importance = data.get("importance", 5)
    if not require_admin():
        return jsonify({"error": "Acces interzis"}), 403
        
    if not memory:
        return jsonify({"error": "memory este obligatoriu"}), 400
    legacy = get_legacy_mode()
    result = legacy.add_memory(memory, importance)
    return jsonify(result)


@super_ai_bp.route('/legacy/learn-style', methods=['POST'])
def legacy_learn_style():
    """Învață stilul de scriere."""
    data = request.get_json() or {}
    samples = data.get("samples", [])
    if not require_admin():
        return jsonify({"error": "Acces interzis"}), 403
    
    if not samples:
        return jsonify({"error": "samples este obligatoriu (list de texte)"}), 400
    legacy = get_legacy_mode()
    result = legacy.learn_style(samples)
    return jsonify(result)


@super_ai_bp.route('/legacy/speak', methods=['POST'])
def legacy_speak():
    """Generează un răspuns ca digital twin."""
    data = request.get_json() or {}
    prompt = data.get("prompt", "")
    if not require_admin():
        return jsonify({"error": "Acces interzis"}), 403
        
    if not prompt:
        return jsonify({"error": "prompt este obligatoriu"}), 400
    legacy = get_legacy_mode()
    result = legacy.generate_response_as_twin(prompt)
    return jsonify(result)


# ============================================================================
# SELF-EVOLUTION
# ============================================================================


@super_ai_bp.route('/analyze-code', methods=['POST'])
def analyze_code():
    if not require_admin():
        return jsonify({"error": "Acces interzis"}), 403
    data = request.get_json() or {}
    filepath = data.get("file", "app.py")
    allowed_files = ["app.py", "claude_brain.py", "security_core.py", 
                     "super_ai_routes.py", "vision_module.py", "voice_module.py",
                     "extensions_module.py"]
    if filepath not in allowed_files:
        return jsonify({"error": "Fișier nepermis pentru analiză"}), 400
    base_dir = os.path.dirname(__file__)
    full_path = os.path.join(base_dir, filepath)
    result = analyze_own_code(full_path)
    return jsonify(result)



@super_ai_bp.route('/admin/write-file', methods=['POST'])
def write_file_node():
    """
    PERMITE AI-ULUI SĂ SALVEZE FIȘIERE PE DISC.
    Critic pentru auto-evoluție și modificări persistente.
    """
    if not require_admin():
        return jsonify({"error": "Acces interzis - Necesită Admin Token"}), 403
        
    data = request.get_json() or {}
    filename = data.get("filename", "")
    content = data.get("content", "")
    
    if not filename or content is None:
        return jsonify({"error": "Filename și content sunt obligatorii"}), 400
        
    # Security check: Prevent directory traversal outside allowed project
    if ".." in filename or filename.startswith("/") or "\\" in filename:
         return jsonify({"error": "Invalid filename security check"}), 400

    try:
        base_dir = os.path.dirname(__file__)
        full_path = os.path.join(base_dir, filename)
        
        # Create backup logic here if needed, but for now just write
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
            
        api_logger.warning(f"FILE MODIFIED BY AI/ADMIN: {filename}")
        return jsonify({
            "success": True, 
            "message": f"Fișierul {filename} a fost salvat cu succes.",
            "size": len(content)
        })
    except Exception as e:
        api_logger.error(f"Write error: {e}")
        return jsonify({"error": str(e)}), 500


@super_ai_bp.route('/admin/download-archive', methods=['GET'])
def download_active_archive():
    """
    Permite descărcarea proactivă a ultimei arhive create de sistem.
    """
    if not require_admin():
        return jsonify({"error": "Acces interzis"}), 403

    try:
        base_dir = os.path.dirname(__file__)
        # Găsește cel mai recent fișier ZIP care începe cu KELION_PROJECT_FULL
        files = [f for f in os.listdir(base_dir) if f.startswith("KELION_PROJECT_FULL") and f.endswith(".zip")]
        if not files:
             return jsonify({"error": "Nu există nicio arhivă disponibilă."}), 404
             
        # Sortează după timp (cel mai recent ultimul)
        latest_file = max(files, key=lambda f: os.path.getmtime(os.path.join(base_dir, f)))
        full_path = os.path.join(base_dir, latest_file)
        
        from flask import send_file
        return send_file(full_path, as_attachment=True, download_name=latest_file)

    except Exception as e:
        api_logger.error(f"Download error: {e}")
        return jsonify({"error": str(e)}), 500




# ============================================================================
# FULL STACK AUDIT
# ============================================================================

@super_ai_bp.route('/audit/full', methods=['POST'])
def full_audit():
    """Rulează audit complet pe tot codul."""
    if not require_admin():
        return jsonify({"error": "Acces interzis"}), 403
    
    files_to_audit = [
        "app.py", "claude_brain.py", "security_core.py",
        "vision_module.py", "voice_module.py", "extensions_module.py"
    ]
    
    results = {}
    for filepath in files_to_audit:
        base_dir = os.path.dirname(__file__)
        full_path = os.path.join(base_dir, filepath)
        if os.path.exists(full_path):
            audit_result = analyze_own_code(full_path)
            results[filepath] = audit_result
    
    return jsonify({
        "audit_complete": True,
        "files_audited": len(results),
        "results": results
    })


# ============================================================================
# AUTO-PILOT: SELF-MONITORING & AUTO-HEALING
# ============================================================================

class AutoPilot:
    """
    Sistemul de auto-management al lui Kelion.
    Monitorizează sănătatea, detectează probleme și le rezolvă automat.
    """
    
    def __init__(self):
        self._running = False
        self._thread = None
        self._issues = []
        self._fixes_applied = []
        self._last_check = 0
        self._check_interval = 60  # Check every 60 seconds
    
    def start(self):
        """Pornește monitorizarea automată."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        api_logger.info("🤖 AUTO-PILOT started")
    
    def stop(self):
        """Oprește monitorizarea."""
        self._running = False
        api_logger.info("🤖 AUTO-PILOT stopped")
    
    def _monitor_loop(self):
        """Loop principal de monitorizare."""
        while self._running:
            try:
                self._run_health_check()
            except Exception as e:
                api_logger.error(f"AUTO-PILOT error: {e}")
            time.sleep(self._check_interval)
    
    def _run_health_check(self):
        """Rulează verificarea de sănătate și repară problemele."""
        self._last_check = time.time()
        self._issues = []
        
        # 1. Check Credit Level
        try:
            tracker = get_usage_tracker()
            credit = tracker.get_remaining_credit()
            if credit < 0.10:
                self._issues.append({
                    "type": "LOW_CREDIT",
                    "severity": "critical",
                    "message": f"Credit foarte scăzut: ${credit:.2f}",
                    "auto_fix": False
                })
            elif credit < 0.50:
                self._issues.append({
                    "type": "LOW_CREDIT_WARNING",
                    "severity": "warning",
                    "message": f"Credit scăzut: ${credit:.2f}",
                    "auto_fix": False
                })
        except Exception as e:
            api_logger.error(f"Credit check failed: {e}")
        
        # 2. Check Memory Size
        try:
            memory = get_memory()
            conv_count = len(memory.conversations)
            if conv_count > 900:  # Near MAX_CONVERSATIONS
                self._issues.append({
                    "type": "MEMORY_FULL",
                    "severity": "warning", 
                    "message": f"Memoria aproape plină: {conv_count}/1000",
                    "auto_fix": True
                })
                # Auto-fix: trim old conversations
                memory.conversations = memory.conversations[-800:]
                memory.save()
                self._fixes_applied.append({
                    "type": "MEMORY_TRIMMED",
                    "time": time.time(),
                    "detail": "Reduced conversations from 900+ to 800"
                })
        except Exception as e:
            api_logger.error(f"Memory check failed: {e}")
        
        # 3. Check Code Integrity
        try:
            armor = k_armor_check()
            if armor.get("code_integrity", {}).get("modified"):
                self._issues.append({
                    "type": "CODE_MODIFIED",
                    "severity": "alert",
                    "message": "Fișiere modificate neautorizat",
                    "auto_fix": False,
                    "files": armor.get("code_integrity", {}).get("modified_files", [])
                })
        except Exception as e:
            pass  # K-Armor might not be configured
        
        # 4. Check System Frozen
        try:
            if is_system_frozen():
                self._issues.append({
                    "type": "SYSTEM_FROZEN",
                    "severity": "info",
                    "message": "Sistemul este în Freeze Total",
                    "auto_fix": False
                })
        except:
            pass
        
        # Log issues
        if self._issues:
            api_logger.warning(f"AUTO-PILOT detected {len(self._issues)} issues")
    
    def get_status(self):
        """Returnează starea AUTO-PILOT."""
        return {
            "running": self._running,
            "last_check": self._last_check,
            "issues": self._issues,
            "fixes_applied": self._fixes_applied[-10:],  # Last 10 fixes
            "check_interval": self._check_interval
        }
    
    def diagnose(self):
        """Rulează diagnosticare completă și returnează raport."""
        self._run_health_check()
        
        # Additional deep diagnostics
        diagnostics = {
            "timestamp": time.time(),
            "issues_found": len(self._issues),
            "issues": self._issues,
            "fixes_applied_total": len(self._fixes_applied),
            "system_status": "HEALTHY" if not self._issues else "NEEDS_ATTENTION"
        }
        
        # Count by severity
        severity_count = {"critical": 0, "warning": 0, "info": 0, "alert": 0}
        for issue in self._issues:
            severity_count[issue.get("severity", "info")] += 1
        diagnostics["by_severity"] = severity_count
        
        # Overall health score (0-100)
        score = 100
        score -= severity_count["critical"] * 30
        score -= severity_count["alert"] * 20
        score -= severity_count["warning"] * 10
        score -= severity_count["info"] * 2
        diagnostics["health_score"] = max(0, score)
        
        return diagnostics


# Global AUTO-PILOT instance
_auto_pilot = AutoPilot()


@super_ai_bp.route('/autopilot/status', methods=['GET'])
def autopilot_status():
    """Obține starea AUTO-PILOT."""
    return jsonify(_auto_pilot.get_status())


@super_ai_bp.route('/autopilot/diagnose', methods=['POST'])
def autopilot_diagnose():
    """Rulează diagnosticare completă."""
    return jsonify(_auto_pilot.diagnose())


@super_ai_bp.route('/autopilot/start', methods=['POST'])
def autopilot_start():
    """Pornește AUTO-PILOT."""
    if not require_admin():
        return jsonify({"error": "Acces interzis"}), 403
    _auto_pilot.start()
    return jsonify({"success": True, "message": "AUTO-PILOT started"})


@super_ai_bp.route('/autopilot/stop', methods=['POST'])
def autopilot_stop():
    """Oprește AUTO-PILOT."""
    if not require_admin():
        return jsonify({"error": "Acces interzis"}), 403
    _auto_pilot.stop()
    return jsonify({"success": True, "message": "AUTO-PILOT stopped"})


# ============================================================================
# INIT
# ============================================================================

def init_super_ai(app):
    """Inițializează Super AI și înregistrează blueprint-ul."""
    app.register_blueprint(super_ai_bp)
    
    # Start AUTO-PILOT automatically
    _auto_pilot.start()
    
    print("✅ Kelion Super AI Complete Routes loaded")
    print(f"   📍 Endpoints: /api/super/*")
    print(f"   🧠 Modules: Security, Brain, Vision, Voice, Extensions")
    print(f"   🤖 AUTO-PILOT: Active")
    return True
