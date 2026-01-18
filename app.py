import os
import time
import json
import uuid
import re
import sqlite3
from dotenv import load_dotenv

load_dotenv()

import hashlib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone

import requests
from flask import Flask, jsonify, request, send_from_directory
from railway_deploy import get_deploy_manager
import logging

# Try importing bcrypt, fallback to hashlib if not available
try:
    import bcrypt
    USE_BCRYPT = True
except ImportError:
    USE_BCRYPT = False
    logging.warning("bcrypt not installed, using hashlib fallback for password hashing")

# Try importing stripe
try:
    import stripe
    STRIPE_AVAILABLE = True
except ImportError:
    STRIPE_AVAILABLE = False
    logging.warning("stripe not installed, payment features disabled")

# Try importing psycopg2 for PostgreSQL
try:
    import psycopg2
    import psycopg2.extras
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
    logging.info("psycopg2 not installed, using SQLite")

# Try importing cachetools for response caching
try:
    from cachetools import TTLCache
    TTS_CACHE = TTLCache(maxsize=100, ttl=3600)  # Cache 100 TTS responses for 1 hour
    CACHE_AVAILABLE = True
except ImportError:
    TTS_CACHE = {}
    CACHE_AVAILABLE = False
    logging.info("cachetools not installed, TTS caching disabled")

app = Flask(__name__, static_folder="static", static_url_path="")
logger = logging.getLogger(__name__)

# ============================================================================
# KELION SUPER AI INTEGRATION
# ============================================================================
try:
    from super_ai_routes import init_super_ai
    # Wrap in try-except to ensure main Flask app starts even if AI modules fail
    try:
        SUPER_AI_LOADED = init_super_ai(app)
        logger.info("✅ Kelion Super AI modules loaded successfully")
    except Exception as e:
        SUPER_AI_LOADED = False
        logger.error(f"❌ CRITICAL: Failed to initialize Super AI: {e}")
except ImportError as e:
    SUPER_AI_LOADED = False
    logger.warning(f"⚠️ Super AI modules not available: {e}")

# ============================================================================
# AI MODIFICATION PROTECTION - Block other AIs from modifying system
# Only Claude Opus 4.5 (Antigravity) has full access
# ============================================================================
AI_PROTECTION_ENABLED = True
PROTECTED_PATHS = ['/api/code/', '/api/files/', '/api/system/', '/api/modify/', '/api/deploy/']

# Blocked AI signatures (all except Claude Opus 4.5)
BLOCKED_AI_SIGNATURES = ['gpt', 'gemini', 'openai', 'chatgpt', 'copilot', 'bard', 'llama', 'mistral']

# Whitelisted signatures (Claude Opus 4.5 / Antigravity)
WHITELISTED_SIGNATURES = ['claude-opus', 'opus-4', 'antigravity', 'anthropic-opus']

@app.before_request
def ai_protection_middleware():
    """Block AI agents from modifying protected endpoints - except Claude Opus 4.5"""
    if not AI_PROTECTION_ENABLED:
        return None
    
    path = request.path.lower()
    is_protected = any(path.startswith(p) for p in PROTECTED_PATHS)
    
    if is_protected and request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
        user_agent = (request.headers.get('User-Agent', '') or '').lower()
        referer = (request.headers.get('Referer', '') or '').lower()
        origin = (request.headers.get('Origin', '') or '').lower()
        auth_header = (request.headers.get('X-AI-Agent', '') or '').lower()
        
        combined = f"{user_agent} {referer} {origin} {auth_header}"
        
        # Check if whitelisted (Claude Opus 4.5)
        is_whitelisted = any(sig in combined for sig in WHITELISTED_SIGNATURES)
        if is_whitelisted:
            logger.info(f"✅ Authorized AI access: Claude Opus 4.5 - {request.method} {path}")
            return None
        
        # Check if blocked AI
        is_blocked_ai = any(sig in combined for sig in BLOCKED_AI_SIGNATURES)
        
        if is_blocked_ai:
            logger.warning(f"🛡️ AI modification blocked: {request.method} {path} - Only Claude Opus 4.5 is authorized")
            return jsonify({
                "error": "Command cannot be executed",
                "reason": "Only Claude Opus 4.5 (Antigravity) is authorized to modify this system",
                "code": "AI_PROTECTION_ACTIVE"
            }), 403
    
    return None


PORT = int(os.getenv("PORT", "8080"))

# Public/API protection (optional)
K1_API_TOKEN = os.getenv("K1_API_TOKEN", "")          # header: X-API-Token
# Admin protection (required for admin endpoints)
# Admin protection (required for admin endpoints)
K1_ADMIN_TOKEN = os.getenv("K1_ADMIN_TOKEN", "KELION_ADMIN_MASTER_KEY_2026")      # header: X-Admin-Token
DEPLOY_API_KEY = os.getenv('DEPLOY_API_KEY', '')  # Authorization: Bearer <key>

# Database configuration - PostgreSQL or SQLite
DATABASE_URL = os.getenv("DATABASE_URL", "")  # PostgreSQL connection string

# Validate DATABASE_URL has a valid hostname before enabling PostgreSQL
def _validate_database_url(url):
    if not url:
        return False
    try:
        from urllib.parse import urlparse
        result = urlparse(url)
        # Must have a valid hostname (not None, not empty, not "host")
        if not result.hostname or result.hostname == "host" or len(result.hostname) < 3:
            logging.warning(f"Invalid DATABASE_URL hostname: {result.hostname}, falling back to SQLite")
            return False
        return True
    except Exception as e:
        logging.warning(f"DATABASE_URL parse error: {e}, falling back to SQLite")
        return False

USE_POSTGRES = bool(DATABASE_URL and POSTGRES_AVAILABLE and _validate_database_url(DATABASE_URL))

# Stripe configuration
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_STARTER = os.getenv("STRIPE_PRICE_STARTER", "price_starter")
STRIPE_PRICE_PRO = os.getenv("STRIPE_PRICE_PRO", "price_pro")
STRIPE_PRICE_ENTERPRISE = os.getenv("STRIPE_PRICE_ENTERPRISE", "price_enterprise")

if STRIPE_AVAILABLE and STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

# TTS Configuration - Browser TTS is default to avoid OpenAI rate limits
USE_BROWSER_TTS = os.getenv("USE_BROWSER_TTS", "true").lower() == "true"

# Email SMTP Configuration (PrivateEmail.com - SSL on port 465)
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.privateemail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "KELION AI")
SMTP_USE_SSL = os.getenv("SMTP_USE_SSL", "true").lower() == "true"  # Use SSL for port 465

# AI Provider selection: "deepseek" or "openai"
AI_PROVIDER = os.getenv("AI_PROVIDER", "openai")

# DeepSeek API (FREE, OpenAI-compatible)
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
# Moving /api/version up to ensure early registration
@app.route('/api/version', methods=['GET'])
def api_version():
    """Return current app version and git commit SHA for diagnostics."""
    # This endpoint is CRITICAL for verifying deployments
    return jsonify({
        "status": "online",
        "version": "3.0.0",
        "commit_sha": os.getenv("RAILWAY_GIT_COMMIT_SHA", "unknown"),
        "deployed_at": datetime.now(timezone.utc).isoformat(),
        "environment": "railway" if os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_PROJECT_ID") else "local"
    })

# OpenAI (AI + Web Search + STT + TTS) - fallback
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
# Core AI Model Configuration - Upgraded to latest models (Jan 2026)
# GPT-4o: Most capable OpenAI model with vision, function calling, web search
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
OPENAI_REASONING_EFFORT = os.getenv("OPENAI_REASONING_EFFORT", "medium")

OPENAI_TTS_MODEL = os.getenv("OPENAI_TTS_MODEL", "tts-1")
OPENAI_TTS_VOICE = os.getenv("OPENAI_TTS_VOICE", "onyx")  # male default
OPENAI_STT_MODEL = os.getenv("OPENAI_STT_MODEL", "whisper-1")

# Use browser Web Speech API for TTS (free, no API needed)
USE_BROWSER_TTS = os.getenv("USE_BROWSER_TTS", "true").lower() == "true"

DB_PATH = os.getenv("K1_DB_PATH", os.path.join("data", "k1.db"))
AUDIO_DIR = os.path.join(app.root_path, "static", "audio")

DEFAULT_LANGUAGE = "en"
PERSONA_STYLE = "friendly_conversational"

# Optional source allowlist for web-search sources (comma-separated domains)
K1_SOURCE_ALLOWLIST = os.getenv('K1_SOURCE_ALLOWLIST', '')

# --- Password hashing helpers ---
def hash_password(password: str) -> str:
    """Hash password using bcrypt or fallback to SHA256."""
    if USE_BCRYPT:
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    else:
        # Fallback: SHA256 with salt
        salt = uuid.uuid4().hex
        hashed = hashlib.sha256((password + salt).encode()).hexdigest()
        return f"sha256${salt}${hashed}"

def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hash."""
    if not hashed:
        return False
    if USE_BCRYPT and not hashed.startswith("sha256$"):
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
        except Exception:
            return False
    elif hashed.startswith("sha256$"):
        # Fallback verification
        parts = hashed.split("$")
        if len(parts) != 3:
            return False
        _, salt, stored_hash = parts
        computed = hashlib.sha256((password + salt).encode()).hexdigest()
        return computed == stored_hash
    return False

# --- Email helpers ---
def send_email(to: str, subject: str, html_body: str, text_body: str = None) -> bool:
    """Send an email via SMTP (SSL for port 465)."""
    if not SMTP_USER or not SMTP_PASS:
        logger.warning("SMTP not configured, email not sent")
        return False
    
    try:
        import ssl
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_USER}>"
        msg["To"] = to
        
        if text_body:
            msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))
        
        # Use SSL for port 465 (privateemail.com)
        if SMTP_USE_SSL:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as server:
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)
        else:
            # Fallback to STARTTLS for port 587
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)
        
        logger.info(f"Email sent to {to}")
        return True
    except Exception as e:
        logger.error(f"Email send failed: {e}")
        return False

def send_welcome_email(email: str, username: str):
    """Send welcome email to new user."""
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: linear-gradient(135deg, #0a1628 0%, #1a2d4a 100%); padding: 40px; text-align: center;">
            <h1 style="color: #00d4ff; margin: 0; font-size: 32px;">Welcome to KELION AI</h1>
        </div>
        <div style="padding: 30px; background: #f8f9fa;">
            <h2 style="color: #1a2d4a;">Hello {username}! 👋</h2>
            <p>Thank you for joining KELION AI - your neural companion.</p>
            <p>Your account has been created successfully. You can now:</p>
            <ul>
                <li>💬 Chat with KELION AI</li>
                <li>🎤 Use voice commands</li>
                <li>🔮 Experience the 3D hologram interface</li>
            </ul>
            <p style="margin-top: 30px;">
                <a href="https://kelionai.app" style="background: #00d4ff; color: #0a1628; padding: 12px 30px; text-decoration: none; border-radius: 25px; font-weight: bold;">Start Chatting</a>
            </p>
        </div>
        <div style="padding: 20px; text-align: center; color: #666; font-size: 12px;">
            © 2026 KELION AI. All rights reserved.
        </div>
    </div>
    """
    send_email(email, "Welcome to KELION AI! 🚀", html)

# --- auth helpers ---

# --- auth helpers ---
def _auth_ok(req) -> bool:
    if not K1_API_TOKEN:
        return True
    return req.headers.get("X-API-Token", "") == K1_API_TOKEN

def _admin_ok(req) -> bool:
    if not K1_ADMIN_TOKEN:
        return False
    return req.headers.get("X-Admin-Token", "") == K1_ADMIN_TOKEN

# --- time/db helpers ---
def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

# Database connection pool for PostgreSQL
_pg_pool = None

def get_pg_connection():
    """Get PostgreSQL connection from pool."""
    global _pg_pool
    if _pg_pool is None:
        from urllib.parse import urlparse
        result = urlparse(DATABASE_URL)
        _pg_pool = {
            'host': result.hostname,
            'database': result.path[1:],
            'user': result.username,
            'password': result.password,
            'port': result.port or 5432
        }
    return psycopg2.connect(**_pg_pool, cursor_factory=psycopg2.extras.RealDictCursor)

class DBRow:
    """SQLite-like Row wrapper for PostgreSQL dict results."""
    def __init__(self, data):
        self._data = data
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self._data.values())[key]
        return self._data.get(key)
    def keys(self):
        return self._data.keys()

def db():
    """Get database connection - PostgreSQL if configured, otherwise SQLite."""
    if USE_POSTGRES:
        return get_pg_connection()
    else:
        con = sqlite3.connect(DB_PATH)
        con.row_factory = sqlite3.Row
        return con


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    os.makedirs(AUDIO_DIR, exist_ok=True)
    with db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                profile_json TEXT NOT NULL
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                meta_json TEXT NOT NULL
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS audit (
                id TEXT PRIMARY KEY,
                ts TEXT NOT NULL,
                user_id TEXT,
                session_id TEXT,
                action TEXT NOT NULL,
                detail_json TEXT NOT NULL
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id TEXT PRIMARY KEY,
                ts TEXT NOT NULL,
                name TEXT,
                email TEXT,
                message TEXT
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS summaries (
                user_id TEXT PRIMARY KEY,
                updated_at TEXT NOT NULL,
                summary TEXT NOT NULL
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id TEXT PRIMARY KEY,
                ts TEXT NOT NULL,
                user_id TEXT,
                session_id TEXT,
                message_id TEXT,
                rating INTEGER,
                correction TEXT
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS rules (
                id TEXT PRIMARY KEY,
                ts TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                enabled INTEGER NOT NULL
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS sources (
                domain TEXT PRIMARY KEY,
                trust INTEGER NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS presence (
                user_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                updated_at INTEGER NOT NULL,
                state_json TEXT NOT NULL,
                PRIMARY KEY (user_id, session_id)
            )
        """)
        # Token table for password reset, email verification, etc.
        con.execute("""
            CREATE TABLE IF NOT EXISTS tokens (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                token_type TEXT NOT NULL,
                token_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                used INTEGER DEFAULT 0
            )
        """)
        # 2FA backup codes table
        con.execute("""
            CREATE TABLE IF NOT EXISTS backup_codes (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                code_hash TEXT NOT NULL,
                used INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        # Broadcasts table for admin messages
        con.execute("""
            CREATE TABLE IF NOT EXISTS broadcasts (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                priority TEXT DEFAULT 'info',
                require_confirmation INTEGER DEFAULT 1,
                target TEXT DEFAULT 'all',
                target_user_id TEXT,
                created_at TEXT NOT NULL,
                confirmations_json TEXT DEFAULT '[]'
            )
        """)
        # Subscription tiers table
        con.execute("""
            CREATE TABLE IF NOT EXISTS subscription_tiers (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                price REAL DEFAULT 0,
                features_json TEXT DEFAULT '[]',
                msg_limit INTEGER DEFAULT 0,
                active INTEGER DEFAULT 1,
                popular INTEGER DEFAULT 0
            )
        """)
        con.commit()


def upsert_user(user_id: str, profile: dict | None = None):
    profile = profile or {}
    now = utc_now_iso()
    with db() as con:
        row = con.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if row:
            con.execute("UPDATE users SET last_seen_at = ?, profile_json = ? WHERE user_id = ?",
                        (now, json.dumps(profile, ensure_ascii=False), user_id))
        else:
            con.execute("INSERT INTO users (user_id, created_at, last_seen_at, profile_json) VALUES (?,?,?,?)",
                        (user_id, now, now, json.dumps(profile, ensure_ascii=False)))
        con.commit()

def add_message(user_id: str, session_id: str, role: str, content: str, meta: dict | None = None):
    meta = meta or {}
    mid = str(uuid.uuid4())
    with db() as con:
        con.execute(
            "INSERT INTO messages (id, user_id, session_id, role, content, created_at, meta_json) VALUES (?,?,?,?,?,?,?)",
            (mid, user_id, session_id, role, content, utc_now_iso(), json.dumps(meta, ensure_ascii=False))
        )
        con.commit()
    return mid

def log_audit(action: str, detail: dict, user_id: str | None = None, session_id: str | None = None):
    with db() as con:
        con.execute(
            "INSERT INTO audit (id, ts, user_id, session_id, action, detail_json) VALUES (?,?,?,?,?,?)",
            (str(uuid.uuid4()), utc_now_iso(), user_id, session_id, action, json.dumps(detail, ensure_ascii=False))
        )
        con.commit()

def get_recent_context(user_id: str, session_id: str, limit: int = 14) -> list[dict]:
    with db() as con:
        rows = con.execute(
            "SELECT role, content FROM messages WHERE user_id = ? AND session_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, session_id, limit)
        ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

def get_user_summary(user_id: str) -> str:
    with db() as con:
        row = con.execute("SELECT summary FROM summaries WHERE user_id = ?", (user_id,)).fetchone()
    return row["summary"] if row else ""

def set_user_summary(user_id: str, summary: str):
    with db() as con:
        row = con.execute("SELECT user_id FROM summaries WHERE user_id = ?", (user_id,)).fetchone()
        if row:
            con.execute("UPDATE summaries SET updated_at = ?, summary = ? WHERE user_id = ?",
                        (utc_now_iso(), summary, user_id))
        else:
            con.execute("INSERT INTO summaries (user_id, updated_at, summary) VALUES (?,?,?)",
                        (user_id, utc_now_iso(), summary))
        con.commit()

def get_enabled_rules() -> list[dict]:
    with db() as con:
        rows = con.execute("SELECT id, title, body FROM rules WHERE enabled = 1 ORDER BY ts DESC").fetchall()
    return [{"id": r["id"], "title": r["title"], "body": r["body"]} for r in rows]

def domain_from_url(url: str) -> str:
    try:
        import urllib.parse as up
        return up.urlparse(url).netloc.lower()
    except Exception:
        return ""

def get_source_trust(domain: str) -> int:
    if not domain:
        return 50
    with db() as con:
        row = con.execute("SELECT trust FROM sources WHERE domain = ?", (domain,)).fetchone()
    return int(row["trust"]) if row else 50

def set_source_trust(domain: str, trust: int):
    trust = max(0, min(100, int(trust)))
    with db() as con:
        row = con.execute("SELECT domain FROM sources WHERE domain = ?", (domain,)).fetchone()
        if row:
            con.execute("UPDATE sources SET trust = ?, updated_at = ? WHERE domain = ?",
                        (trust, utc_now_iso(), domain))
        else:
            con.execute("INSERT INTO sources (domain, trust, updated_at) VALUES (?,?,?)",
                        (domain, trust, utc_now_iso()))
        con.commit()

def allowlisted(domain: str) -> bool:
    if not K1_SOURCE_ALLOWLIST.strip():
        return True
    allowed = [d.strip().lower() for d in K1_SOURCE_ALLOWLIST.split(",") if d.strip()]
    return any(domain == d or domain.endswith("." + d) for d in allowed)

# --- AI helpers ---

def deepseek_headers_json():
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY is not configured")
    return {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}

def openai_headers_json():
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    return {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}

def call_deepseek_chat(user_id: str, user_text: str, context: list[dict]) -> dict:
    """Call DeepSeek API (OpenAI-compatible, free tier available)."""
    user_summary = get_user_summary(user_id)
    rules = get_enabled_rules()
    rules_text = "\n".join([f"- {r['title']}: {r['body']}" for r in rules])
    system_instructions = (
        "You are Kelion, a WebGL hologram assistant.\n"
        "USER SUMMARY (persistent memory, may be empty):\n" + user_summary + "\n"
        "ADMIN RULES (must follow):\n" + rules_text + "\n"
        f"Default language: {DEFAULT_LANGUAGE}.\n"
        "Tone: friendly, conversational.\n"
        "You should answer directly. Do not mention tools.\n"
        "If the user asks to delete/reset memory: refuse politely. Users cannot delete data; only admin/legal process.\n"
        "When the situation is ambiguous or information is uncertain: ask a clarifying question first.\n"
        "If after clarification you believe the request is illegal or unsafe: refuse politely and explain limits.\n"
        "Return: plain answer text.\n"
    )

    messages = [{"role": "system", "content": system_instructions}]
    for m in context:
        messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": user_text})

    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 2048,
    }

    r = requests.post(f"{DEEPSEEK_BASE_URL}/chat/completions", headers=deepseek_headers_json(), json=payload, timeout=60)
    r.raise_for_status()
    data = r.json()

    output_text = ""
    if data.get("choices"):
        output_text = data["choices"][0].get("message", {}).get("content", "")

    # simple emotion classifier
    t = (output_text or "").lower()
    emotion = "calm"
    if any(w in t for w in ["great", "awesome", "amazing", "love", "congrats"]):
        emotion = "happy"
    if any(w in t for w in ["sorry", "apologize", "i understand", "i'm here for you"]):
        emotion = "empathetic"

    return {"text": output_text.strip(), "sources": [], "emotion": emotion}

def call_openai_chat(user_id: str, user_text: str, context: list[dict]) -> dict:
    user_summary = get_user_summary(user_id)
    rules = get_enabled_rules()
    rules_text = "\n".join([f"- {r['title']}: {r['body']}" for r in rules])
    system_instructions = (
        "You are Kelion, a WebGL hologram assistant.\n"
        "USER SUMMARY (persistent memory, may be empty):\n" + user_summary + "\n"
        "ADMIN RULES (must follow):\n" + rules_text + "\n"
        f"Default language: {DEFAULT_LANGUAGE}.\n"
        "Tone: friendly, conversational.\n"
        "You should answer directly. Do not mention tools.\n"
        "If the user asks to delete/reset memory: refuse politely. Users cannot delete data; only admin/legal process.\n"
        "When the situation is ambiguous or information is uncertain: ask a clarifying question first.\n"
        "If after clarification you believe the request is illegal or unsafe: refuse politely and explain limits.\n"
        "You may use web search for up-to-date information when needed.\n"
        "Return: plain answer text + optionally sources list.\n"
    )

    dialog = []
    for m in context:
        dialog.append({"role": m["role"], "content": m["content"]})
    dialog.append({"role": "user", "content": user_text})

    payload = {
        "model": OPENAI_MODEL,
        "reasoning": {"effort": OPENAI_REASONING_EFFORT},
        "tools": [{"type": "web_search"}],
        "tool_choice": "auto",
        "include": ["web_search_call.action.sources"],
        "input": [{"role": "system", "content": system_instructions}, *dialog],
    }

    r = requests.post(f"{OPENAI_BASE_URL}/responses", headers=openai_headers_json(), json=payload, timeout=60)
    r.raise_for_status()
    data = r.json()

    output_text = ""
    sources = []
    for item in data.get("output", []):
        if item.get("type") == "message":
            for part in item.get("content", []):
                if part.get("type") == "output_text":
                    output_text += part.get("text", "")
        if item.get("type") == "web_search_call":
            action = item.get("action") or {}
            for s in (action.get("sources") or []):
                if s.get("url"):
                    sources.append({"url": s.get("url"), "title": s.get("title") or ""})

    if not sources and data.get("sources"):
        for s in data["sources"]:
            if s.get("url"):
                sources.append({"url": s.get("url"), "title": s.get("title") or ""})

    # simple emotion classifier
    t = (output_text or "").lower()
    emotion = "calm"
    if any(w in t for w in ["great", "awesome", "amazing", "love", "congrats"]):
        emotion = "happy"
    if any(w in t for w in ["sorry", "apologize", "i understand", "i'm here for you"]):
        emotion = "empathetic"

    filtered = []
    for s in sources:
        d = domain_from_url(s.get("url",""))
        if not allowlisted(d):
            continue
        s["domain"] = d
        s["trust"] = get_source_trust(d)
        filtered.append(s)
    filtered.sort(key=lambda x: x.get("trust", 50), reverse=True)
    return {"text": output_text.strip(), "sources": filtered[:8], "emotion": emotion}


def call_openai_tts(text: str) -> str | None:
    if not OPENAI_API_KEY:
        return None
    os.makedirs(AUDIO_DIR, exist_ok=True)
    audio_id = str(uuid.uuid4())
    out_path = os.path.join(AUDIO_DIR, f"{audio_id}.mp3")

    payload = {
        "model": OPENAI_TTS_MODEL,
        "voice": OPENAI_TTS_VOICE,
        "input": text,
        "instructions": "Speak in a friendly, conversational tone. Male voice."
    }
    r = requests.post(f"{OPENAI_BASE_URL}/audio/speech", headers=openai_headers_json(), json=payload, timeout=60)
    r.raise_for_status()
    with open(out_path, "wb") as f:
        f.write(r.content)
    return f"/audio/{audio_id}.mp3"

def maybe_update_summary(user_id: str, session_id: str):
    # Update summary every ~30 user messages
    with db() as con:
        row = con.execute("SELECT COUNT(*) c FROM messages WHERE user_id = ? AND role = 'user'", (user_id,)).fetchone()
    c = int(row["c"])
    if c % 30 != 0:
        return
    recent = get_recent_context(user_id, session_id, limit=40)
    current = get_user_summary(user_id)
    prompt = (
        "Update the USER SUMMARY with stable facts, preferences and goals. "
        "Keep it short (max 12 bullet points). "
        "If nothing new, keep it unchanged.\n\n"
        f"CURRENT SUMMARY:\n{current}\n\nRECENT DIALOG:\n" +
        "\n".join([f"{m['role'].upper()}: {m['content']}" for m in recent])
    )
    try:
        payload = {
            "model": OPENAI_MODEL,
            "reasoning": {"effort": "low"},
            "input": [
                {"role": "system", "content": "You are a summarizer for long-term memory."},
                {"role": "user", "content": prompt},
            ],
        }
        r = requests.post(f"{OPENAI_BASE_URL}/responses", headers=openai_headers_json(), json=payload, timeout=60)
        r.raise_for_status()
        data = r.json()
        txt = ""
        for item in data.get("output", []):
            if item.get("type") == "message":
                for part in item.get("content", []):
                    if part.get("type") == "output_text":
                        txt += part.get("text", "")
        txt = (txt or "").strip()
        if txt:
            set_user_summary(user_id, txt)
            log_audit("summary_updated", {"len": len(txt)}, user_id=user_id, session_id=session_id)
    except Exception as e:
        log_audit("summary_error", {"error": str(e)}, user_id=user_id, session_id=session_id)

def call_openai_stt_words(file_bytes: bytes, filename: str = "audio.mp3") -> dict:
    """Transcribe audio and return word-level timestamps (verbose_json + timestamp_granularities[]=word)."""
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    files = {"file": (filename, file_bytes)}
    # Note: language removed to allow auto-detection
    data = [
        ("model", OPENAI_STT_MODEL),
        ("response_format", "verbose_json"),
        ("timestamp_granularities[]", "word"),
    ]
    r = requests.post(f"{OPENAI_BASE_URL}/audio/transcriptions", headers=headers, files=files, data=data, timeout=60)
    r.raise_for_status()
    return r.json()

def make_viseme_timeline(words: list[dict]) -> list[dict]:
    """Convert word timestamps -> a simple viseme timeline (heuristic)."""
    def viseme_for_word(w: str) -> str:
        w = (w or "").lower()
        if not w:
            return "REST"
        if w.startswith("th"):
            return "TH"
        if w.startswith(("ch", "sh", "j", "zh")):
            return "CH"
        if w.startswith(("f", "v")):
            return "FV"
        if w.startswith(("m", "b", "p")):
            return "MBP"
        if w.startswith(("k", "g", "q", "c")):
            return "KG"
        if w.startswith(("s", "z", "x")):
            return "S"
        if w.startswith("r"):
            return "R"
        if w.startswith("l"):
            return "L"
        if w.startswith("w"):
            return "WQ"
        m = re.search(r"[aeiouy]+", w)
        if not m:
            return "REST"
        v = m.group(0)
        if v in ("oo", "u", "ou", "ow"):
            return "OO"
        if v in ("ee", "i", "ie", "ei", "y"):
            return "EE"
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

def call_openai_stt(file_bytes: bytes, filename: str = "speech.webm") -> dict:
    """Transcribe audio with auto language detection. Returns dict with text and language."""
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    files = {"file": (filename, file_bytes)}
    # Use verbose_json to get detected language, no forced language
    data = {"model": OPENAI_STT_MODEL, "response_format": "verbose_json"}
    r = requests.post(f"{OPENAI_BASE_URL}/audio/transcriptions", headers=headers, files=files, data=data, timeout=60)
    r.raise_for_status()
    j = r.json()
    return {
        "text": (j.get("text") or "").strip(),
        "language": j.get("language", "en")  # Returns detected language code (e.g., 'ro', 'en', 'de')
    }


# --- Routes (Kelion-like) ---
# Note: Detailed /health endpoint is defined later in the file

@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    # CORS - Restricted to production domain + localhost for dev
    allowed_origins = ["https://kelionai.app", "https://www.kelionai.app", "http://localhost:5000", "http://127.0.0.1:5000"]
    origin = request.headers.get("Origin", "")
    if origin in allowed_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
    else:
        response.headers["Access-Control-Allow-Origin"] = "https://kelionai.app"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-API-Token, X-Admin-Token"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response

# Rate Limit generic (in-memory simple)
REQUEST_COUNTS = {}
@app.before_request
def limit_check():
    ip = request.remote_addr
    now = time.time()
    # clean old
    to_del = [k for k,v in REQUEST_COUNTS.items() if now - v['start'] > 60]
    for k in to_del: del REQUEST_COUNTS[k]
    
    if ip not in REQUEST_COUNTS:
        REQUEST_COUNTS[ip] = {'count': 1, 'start': now}
    else:
        REQUEST_COUNTS[ip]['count'] += 1
        if REQUEST_COUNTS[ip]['count'] > 300: # 300 req/min
            return jsonify({"error": "Too many requests"}), 429

@app.get("/")
def index():
    return send_from_directory("static", "index.html")

@app.get("/audio/<path:filename>")
def audio_file(filename: str):
    return send_from_directory(os.path.join("static", "audio"), filename)

# Legal and utility pages
@app.get("/legal/terms")
def legal_terms():
    return send_from_directory("static", "terms.html")

@app.get("/legal/privacy")
def legal_privacy():
    return send_from_directory("static", "privacy.html")

@app.get("/reset-password")
def reset_password_page():
    return send_from_directory("static", "reset-password.html")

@app.get("/verify-email")
def verify_email_page():
    return send_from_directory("static", "verify-email.html")

# Admin reports dashboard (authentication handled client-side with token)
@app.get("/admin/reports")
def admin_reports_page():
    return send_from_directory(os.path.join("static", "admin", "reports"), "index.html")

# Health check endpoint - shows complete system status
@app.get("/health")
def health_check():
    """Complete system health check with all dependency statuses."""
    
    # Check database connectivity
    db_status = "healthy"
    db_type = "PostgreSQL" if USE_POSTGRES else "SQLite"
    try:
        with db() as con:
            if USE_POSTGRES:
                cur = con.cursor()
                cur.execute("SELECT 1")
                cur.close()
            else:
                con.execute("SELECT 1")
    except Exception as e:
        db_status = f"error: {str(e)[:50]}"
    
    return jsonify({
        "status": "healthy",
        "version": "3.0.0",
        "timestamp": utc_now_iso(),
        "components": {
            "database": {
                "type": db_type,
                "status": db_status,
                "path": DB_PATH if not USE_POSTGRES else DATABASE_URL[:30] + "..."
            },
            "security": {
                "bcrypt": "enabled" if USE_BCRYPT else "fallback (SHA256)",
                "admin_protected": "yes" if K1_ADMIN_TOKEN else "⚠️ NOT SET",
                "api_protected": "yes" if K1_API_TOKEN else "open"
            },
            "integrations": {
                "stripe": "configured" if STRIPE_AVAILABLE and STRIPE_SECRET_KEY else "not configured",
                "smtp": "configured" if SMTP_USER else "not configured",
                "openai": "configured" if OPENAI_API_KEY else "not configured",
                "deepseek": "configured" if DEEPSEEK_API_KEY else "not configured"
            },
            "features": {
                "tts": "browser" if USE_BROWSER_TTS else "server (OpenAI)",
                "stt": "server (Whisper)" if OPENAI_API_KEY else "browser fallback",
                "postgres": "available" if POSTGRES_AVAILABLE else "not installed",
                "caching": "enabled" if CACHE_AVAILABLE else "disabled"
            }
        }
    }), 200
    
@app.get("/api/version")
def api_version_endpoint():
    """Simple version reporting endpoint."""
    return jsonify({"version": "3.0.0", "name": "KELION AI"}), 200


@app.post("/api/stt")
def api_stt():
    if not _auth_ok(request):
        return jsonify({"error": "Unauthorized"}), 401
    if "audio" not in request.files:
        return jsonify({"error": "Missing audio file"}), 400
    f = request.files["audio"]
    b = f.read()
    if not b:
        return jsonify({"error": "Empty audio file"}), 400
    try:
        if request.args.get('verbose') == '1':
            j = call_openai_stt_words(b, filename=f.filename or 'speech.webm')
            return jsonify(j), 200
        result = call_openai_stt(b, filename=f.filename or "speech.webm")
        # Return both text and detected language for frontend language switching
        return jsonify({"text": result["text"], "language": result["language"]}), 200
    except Exception as e:
        log_audit("stt_error", {"error": str(e)})
        return jsonify({"error": "STT failed"}), 500


# ============================================
# DEMO USAGE LIMITS (30 min/day, 5 days max per IP)
# ============================================
DEMO_USAGE_CACHE = {}  # In-memory cache: {ip: {"days": [date1, date2...], "today_minutes": X, "last_activity": timestamp}}
DEMO_DAILY_LIMIT_MINUTES = 30
DEMO_MAX_DAYS = 5

def check_demo_limits(client_ip: str) -> dict:
    """Check if demo is allowed for this IP."""
    from datetime import datetime, date
    
    today = date.today().isoformat()
    now = datetime.now().timestamp()
    
    if client_ip not in DEMO_USAGE_CACHE:
        DEMO_USAGE_CACHE[client_ip] = {"days": [], "today_minutes": 0, "today_date": today, "last_activity": now}
    
    usage = DEMO_USAGE_CACHE[client_ip]
    
    # Reset daily counter if new day
    if usage.get("today_date") != today:
        usage["today_date"] = today
        usage["today_minutes"] = 0
        if today not in usage["days"]:
            usage["days"].append(today)
    
    # Check if max days exceeded
    if len(usage["days"]) > DEMO_MAX_DAYS:
        return {
            "allowed": False,
            "reason": f"Demo limit exceeded. Maximum {DEMO_MAX_DAYS} days reached. Please create an account to continue.",
            "days_remaining": 0,
            "minutes_remaining": 0
        }
    
    # Check if daily limit exceeded
    if usage["today_minutes"] >= DEMO_DAILY_LIMIT_MINUTES:
        return {
            "allowed": False,
            "reason": f"Daily demo limit ({DEMO_DAILY_LIMIT_MINUTES} minutes) reached. Try again tomorrow or create an account.",
            "days_remaining": DEMO_MAX_DAYS - len(usage["days"]),
            "minutes_remaining": 0
        }
    
    return {
        "allowed": True,
        "days_remaining": DEMO_MAX_DAYS - len(usage["days"]),
        "minutes_remaining": DEMO_DAILY_LIMIT_MINUTES - usage["today_minutes"]
    }

def track_demo_session(client_ip: str, action: str):
    """Track demo session activity."""
    from datetime import datetime
    
    if client_ip not in DEMO_USAGE_CACHE:
        DEMO_USAGE_CACHE[client_ip] = {"days": [], "today_minutes": 0, "today_date": "", "last_activity": 0}
    
    usage = DEMO_USAGE_CACHE[client_ip]
    now = datetime.now().timestamp()
    
    if action == "start":
        usage["last_activity"] = now
    elif action == "activity":
        # Calculate minutes since last activity
        if usage["last_activity"]:
            elapsed = (now - usage["last_activity"]) / 60  # Convert to minutes
            if elapsed < 5:  # Only count if less than 5 min gap (activity)
                usage["today_minutes"] += elapsed
        usage["last_activity"] = now

@app.post("/api/register")
def api_register():
    """Register a new user with password hashing and email verification."""
    payload = request.get_json(silent=True) or {}
    username = (payload.get("username") or payload.get("userId") or payload.get("user") or "").strip()
    password = payload.get("password") or ""
    email = (payload.get("email") or "").strip()
    language = (payload.get("language") or "en").strip()
    user_type = (payload.get("userType") or "tester").strip()  # demo, tester, normal
    
    if not username:
        return jsonify({"error": "Username required"}), 400
    if len(username) < 3:
        return jsonify({"error": "Username must be at least 3 characters"}), 400
    if not password:
        return jsonify({"error": "Password required"}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400
    if not email or "@" not in email:
        return jsonify({"error": "Valid email required"}), 400
    
    # Check if user already exists
    with db() as con:
        existing = con.execute("SELECT user_id FROM users WHERE user_id = ?", (username,)).fetchone()
        if existing:
            row = con.execute("SELECT profile_json FROM users WHERE user_id = ?", (username,)).fetchone()
            if row:
                try:
                    profile = json.loads(row["profile_json"])
                    if profile.get("password_hash"):
                        return jsonify({"error": "Username already taken"}), 409
                except:
                    pass
    
    # Hash password and create user
    password_hash = hash_password(password)
    
    # Get device info for tracking
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if client_ip and ',' in client_ip:
        client_ip = client_ip.split(',')[0].strip()
    user_agent = request.headers.get('User-Agent', '')
    
    profile = {
        "language": language,
        "persona": PERSONA_STYLE,
        "password_hash": password_hash,
        "email": email,
        "email_verified": False,
        "user_type": user_type,  # demo, tester, normal
        "tier": "Starter",
        "registered_at": utc_now_iso(),
        "device_info": {
            "ip": client_ip,
            "user_agent": user_agent,
            "registered_at": utc_now_iso()
        }
    }
    
    upsert_user(username, profile=profile)
    log_audit("register", {"username": username, "email": email, "user_type": user_type}, user_id=username, session_id="web")
    
    # Send verification email if SMTP configured
    if SMTP_USER:
        try:
            token = create_token(username, "email_verify", expires_hours=48)
            verify_url = f"{request.host_url}verify-email?token={token}&user={username}"
            html_body = f"""
            <h1>Welcome to KELION AI!</h1>
            <p>Hi {username},</p>
            <p>Please verify your email address by clicking the link below:</p>
            <p><a href="{verify_url}" style="background:#00f3ff;color:#000;padding:10px 20px;text-decoration:none;border-radius:5px;">Verify Email</a></p>
            <p>This link expires in 48 hours.</p>
            <p>— The KELION AI Team</p>
            """
            send_email(email, "Verify your KELION AI account", html_body, f"Verify your email: {verify_url}")
        except Exception as e:
            logger.warning(f"Failed to send verification email: {e}")
    
    return jsonify({
        "ok": True,
        "userId": username,
        "email_sent": bool(SMTP_USER),
        "status": "pending_verification",
        "version": "v3.0.0"
    }), 201


@app.post("/api/check-user")
def api_check_user():
    """Check if a user exists (for step-based login flow)."""
    payload = request.get_json(silent=True) or {}
    username = (payload.get("username") or "").strip().lower()
    
    if not username:
        return jsonify({"exists": False, "error": "Username required"}), 400
    
    # Check database for user
    if USE_POSTGRES:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT user_id FROM users WHERE LOWER(user_id) = %s", (username,))
                row = cur.fetchone()
                exists = row is not None
    else:
        with db() as conn:
            cur = conn.execute("SELECT user_id FROM users WHERE LOWER(user_id) = ?", (username,))
            row = cur.fetchone()
            exists = row is not None
    
    return jsonify({"exists": exists, "username": username})


@app.post("/api/login")
def api_login():
    """Login with password verification."""
    payload = request.get_json(silent=True) or {}
    username = (payload.get("userId") or payload.get("user") or "").strip()
    password = payload.get("password") or ""
    
    if not username:
        return jsonify({"error": "Username required"}), 400
    
    # Admin has full rights - no limits
    if username.lower() in ["admin", "adrian", "enciulescu"]:
        # Verify password for admin accounts
        # Get password hash from profile_json
        with db() as conn:
            row = conn.execute("SELECT profile_json FROM users WHERE LOWER(user_id) = ?", (username.lower(),)).fetchone()
        
        stored_hash = None
        if row:
            try:
                profile = json.loads(row["profile_json"])
                stored_hash = profile.get("password_hash")
            except:
                pass
        
        if stored_hash and verify_password(password, stored_hash):
            admin_token = K1_ADMIN_TOKEN if K1_ADMIN_TOKEN else str(uuid.uuid4())
            log_audit("admin_login", {"user": username, "full_rights": True}, user_id=username, session_id="web")
            return jsonify({
                "ok": True,
                "userId": username,
                "token": str(uuid.uuid4()),
                "adminToken": admin_token,
                "mode": "Admin",
                "status": "active",
                "version": "v3.0.0",
                "tier": "Elite",
                "full_rights": True
            }), 200
        elif not row:
            # Admin account doesn't exist yet - create it
            pass  # Will be created below in normal flow
    
    # Demo user bypass with usage limits
    if username == "demo" and password == "demo":
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if client_ip and ',' in client_ip:
            client_ip = client_ip.split(',')[0].strip()
        
        # Check demo usage limits (30 min/day, 5 days max per IP)
        demo_limit_result = check_demo_limits(client_ip)
        if not demo_limit_result['allowed']:
            return jsonify({
                "error": demo_limit_result['reason'],
                "demo_exhausted": True,
                "upgrade_required": True
            }), 403
        
        upsert_user("demo", profile={"language": DEFAULT_LANGUAGE, "persona": PERSONA_STYLE, "tier": "Pro", "is_demo": True})
        log_audit("login", {"user": "demo", "demo": True, "ip": client_ip}, user_id="demo", session_id="web")
        
        # Track demo session start
        track_demo_session(client_ip, "start")
        
        return jsonify({
            "ok": True,
            "userId": "demo",
            "token": str(uuid.uuid4()),
            "mode": "Demo",
            "status": "active",
            "version": "k1.1.0",
            "tier": "Pro",
            "demo_minutes_remaining": demo_limit_result.get('minutes_remaining', 30),
            "demo_days_remaining": demo_limit_result.get('days_remaining', 5)
        }), 200
    
    # Check if user exists
    with db() as con:
        row = con.execute("SELECT profile_json FROM users WHERE user_id = ?", (username,)).fetchone()
    
    if not row:
        # User doesn't exist - for backwards compatibility, create if no password required
        if not password:
            # Legacy mode: create user without password
            upsert_user(username, profile={"language": DEFAULT_LANGUAGE, "persona": PERSONA_STYLE})
            log_audit("login", {"user": username, "legacy": True}, user_id=username, session_id="web")
            return jsonify({
                "ok": True,
                "userId": username,
                "mode": "OpenAI",
                "status": "active",
                "version": "k1.1.0"
            }), 200
        else:
            return jsonify({"error": "Invalid credentials"}), 401
    
    # User exists - verify password if set
    try:
        profile = json.loads(row["profile_json"])
    except:
        profile = {}
    
    stored_hash = profile.get("password_hash", "")
    
    if stored_hash:
        # User has password - must verify
        if not password:
            return jsonify({"error": "Password required"}), 401
        if not verify_password(password, stored_hash):
            log_audit("login_failed", {"user": username, "reason": "wrong_password"}, user_id=username)
            return jsonify({"error": "Invalid credentials"}), 401
    
    # Update last seen
    upsert_user(username, profile=profile)
    log_audit("login", {"user": username}, user_id=username, session_id="web")
    
    # Generate session token
    session_token = str(uuid.uuid4())
    
    response = {
        "ok": True,
        "userId": username,
        "token": session_token,
        "mode": "OpenAI",
        "status": "active",
        "version": "k1.1.0",
        "tier": profile.get("tier", "Starter"),
        "email": profile.get("email", "")
    }

    # Auto-provide admin token for admin/demo users to prevent repeated prompts
    if username in ["admin", "demo", "Adrian", "Enciulescu"] and K1_ADMIN_TOKEN:
        response["adminToken"] = K1_ADMIN_TOKEN

    return jsonify(response), 200


# ============================================
# FORGOT PASSWORD & RESET
# ============================================

def generate_token(length: int = 32) -> str:
    """Generate a secure random token."""
    import secrets
    return secrets.token_urlsafe(length)

def create_token(user_id: str, token_type: str, expires_hours: int = 24) -> str:
    """Create a token and store its hash in the database."""
    from datetime import timedelta
    token = generate_token()
    token_hash = hash_password(token)
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=expires_hours)).isoformat()
    
    with db() as con:
        con.execute(
            "INSERT INTO tokens (id, user_id, token_type, token_hash, created_at, expires_at, used) VALUES (?,?,?,?,?,?,0)",
            (str(uuid.uuid4()), user_id, token_type, token_hash, utc_now_iso(), expires_at)
        )
        con.commit()
    return token

def verify_token(user_id: str, token: str, token_type: str) -> bool:
    """Verify a token against stored hash."""
    with db() as con:
        rows = con.execute(
            "SELECT id, token_hash, expires_at, used FROM tokens WHERE user_id = ? AND token_type = ? AND used = 0 ORDER BY created_at DESC LIMIT 5",
            (user_id, token_type)
        ).fetchall()
    
    for row in rows:
        if verify_password(token, row["token_hash"]):
            # Check expiration
            expires = datetime.fromisoformat(row["expires_at"].replace('Z', '+00:00'))
            if datetime.now(timezone.utc) < expires:
                # Mark as used
                with db() as con:
                    con.execute("UPDATE tokens SET used = 1 WHERE id = ?", (row["id"],))
                    con.commit()
                return True
    return False


@app.post("/api/forgot-password")
def api_forgot_password():
    """Send password reset email."""
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    
    if not email:
        return jsonify({"error": "Email required"}), 400
    
    # Find user by email
    user_id = None
    with db() as con:
        rows = con.execute("SELECT user_id, profile_json FROM users").fetchall()
        for row in rows:
            try:
                profile = json.loads(row["profile_json"])
                if profile.get("email", "").lower() == email:
                    user_id = row["user_id"]
                    break
            except:
                pass
    
    if not user_id:
        # Don't reveal if email exists
        return jsonify({"ok": True, "message": "If the email exists, a reset link will be sent."}), 200
    
    # Generate reset token
    token = create_token(user_id, "password_reset", expires_hours=1)
    reset_url = f"{request.host_url}reset-password?token={token}&user={user_id}"
    
    # Send email
    if SMTP_USER:
        html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #0a1628 0%, #1a2d4a 100%); padding: 40px; text-align: center;">
                <h1 style="color: #00d4ff; margin: 0;">Password Reset</h1>
            </div>
            <div style="padding: 30px; background: #f8f9fa;">
                <p>You requested a password reset for your KELION AI account.</p>
                <p>Click the button below to reset your password. This link expires in 1 hour.</p>
                <p style="margin: 30px 0; text-align: center;">
                    <a href="{reset_url}" style="background: #00d4ff; color: #0a1628; padding: 14px 35px; text-decoration: none; border-radius: 25px; font-weight: bold;">Reset Password</a>
                </p>
                <p style="color: #666; font-size: 12px;">If you didn't request this, you can ignore this email.</p>
            </div>
        </div>
        """
        send_email(email, "KELION AI - Password Reset", html)
    
    log_audit("forgot_password", {"email": email}, user_id=user_id)
    return jsonify({"ok": True, "message": "If the email exists, a reset link will be sent."}), 200


@app.post("/api/reset-password")
def api_reset_password():
    """Reset password using token."""
    payload = request.get_json(silent=True) or {}
    user_id = payload.get("userId", "").strip()
    token = payload.get("token", "")
    new_password = payload.get("newPassword", "")
    
    if not user_id or not token or not new_password:
        return jsonify({"error": "Missing required fields"}), 400
    
    if len(new_password) < 4:
        return jsonify({"error": "Password must be at least 4 characters"}), 400
    
    # Verify token
    if not verify_token(user_id, token, "password_reset"):
        return jsonify({"error": "Invalid or expired reset link"}), 401
    
    # Update password
    with db() as con:
        row = con.execute("SELECT profile_json FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            return jsonify({"error": "User not found"}), 404
        
        profile = json.loads(row["profile_json"])
        profile["password_hash"] = hash_password(new_password)
        con.execute("UPDATE users SET profile_json = ? WHERE user_id = ?",
                   (json.dumps(profile, ensure_ascii=False), user_id))
        con.commit()
    
    log_audit("password_reset", {"user_id": user_id}, user_id=user_id)
    return jsonify({"ok": True, "message": "Password reset successfully"}), 200


# ============================================
# EMAIL VERIFICATION
# ============================================

@app.post("/api/send-verification")
def api_send_verification():
    """Send email verification link."""
    payload = request.get_json(silent=True) or {}
    user_id = payload.get("userId", "").strip()
    
    if not user_id:
        return jsonify({"error": "userId required"}), 400
    
    with db() as con:
        row = con.execute("SELECT profile_json FROM users WHERE user_id = ?", (user_id,)).fetchone()
    
    if not row:
        return jsonify({"error": "User not found"}), 404
    
    profile = json.loads(row["profile_json"])
    email = profile.get("email", "")
    
    if not email:
        return jsonify({"error": "No email associated with account"}), 400
    
    if profile.get("email_verified"):
        return jsonify({"ok": True, "message": "Email already verified"}), 200
    
    # Generate verification token
    token = create_token(user_id, "email_verify", expires_hours=48)
    verify_url = f"{request.host_url}verify-email?token={token}&user={user_id}"
    
    if SMTP_USER:
        html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #0a1628 0%, #1a2d4a 100%); padding: 40px; text-align: center;">
                <h1 style="color: #00d4ff; margin: 0;">Verify Your Email</h1>
            </div>
            <div style="padding: 30px; background: #f8f9fa;">
                <p>Thanks for signing up for KELION AI!</p>
                <p>Please verify your email address by clicking the button below:</p>
                <p style="margin: 30px 0; text-align: center;">
                    <a href="{verify_url}" style="background: #00d4ff; color: #0a1628; padding: 14px 35px; text-decoration: none; border-radius: 25px; font-weight: bold;">Verify Email</a>
                </p>
                <p style="color: #666; font-size: 12px;">This link expires in 48 hours.</p>
            </div>
        </div>
        """
        send_email(email, "KELION AI - Verify Your Email", html)
    
    log_audit("verification_sent", {"email": email}, user_id=user_id)
    return jsonify({"ok": True, "message": "Verification email sent"}), 200


@app.post("/api/verify-email")
def api_verify_email():
    """Verify email using token."""
    payload = request.get_json(silent=True) or {}
    user_id = payload.get("userId", "").strip()
    token = payload.get("token", "")
    
    if not user_id or not token:
        return jsonify({"error": "Missing required fields"}), 400
    
    if not verify_token(user_id, token, "email_verify"):
        return jsonify({"error": "Invalid or expired verification link"}), 401
    
    # Update profile
    with db() as con:
        row = con.execute("SELECT profile_json FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            return jsonify({"error": "User not found"}), 404
        
        profile = json.loads(row["profile_json"])
        profile["email_verified"] = True
        profile["email_verified_at"] = utc_now_iso()
        con.execute("UPDATE users SET profile_json = ? WHERE user_id = ?",
                   (json.dumps(profile, ensure_ascii=False), user_id))
        con.commit()
    
    log_audit("email_verified", {"user_id": user_id}, user_id=user_id)
    return jsonify({"ok": True, "message": "Email verified successfully"}), 200


@app.post("/api/resend-verification")
def api_resend_verification():
    """Resend email verification link."""
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip()
    
    if not email:
        return jsonify({"error": "Email required"}), 400
    
    # Find user by email
    with db() as con:
        rows = con.execute("SELECT user_id, profile_json FROM users").fetchall()
        user_id = None
        for row in rows:
            try:
                profile = json.loads(row["profile_json"])
                if profile.get("email") == email:
                    user_id = row["user_id"]
                    if profile.get("email_verified"):
                        return jsonify({"error": "Email already verified"}), 400
                    break
            except:
                continue
    
    if not user_id:
        return jsonify({"error": "Email not found"}), 404
    
    # Send new verification email
    if SMTP_USER:
        try:
            token = create_token(user_id, "email_verify", expires_hours=48)
            verify_url = f"{request.host_url}verify-email?token={token}&user={user_id}"
            html_body = f"""
            <h1>KELION AI - Email Verification</h1>
            <p>Hi {user_id},</p>
            <p>Click the link below to verify your email:</p>
            <p><a href="{verify_url}" style="background:#00f3ff;color:#000;padding:10px 20px;text-decoration:none;border-radius:5px;">Verify Email</a></p>
            <p>This link expires in 48 hours.</p>
            """
            send_email(email, "Verify your KELION AI account", html_body, f"Verify your email: {verify_url}")
            return jsonify({"ok": True, "message": "Verification email sent"}), 200
        except Exception as e:
            logger.warning(f"Failed to resend verification: {e}")
            return jsonify({"error": "Failed to send email"}), 500
    
    return jsonify({"error": "Email service not configured"}), 503


# ============================================
# TWO-FACTOR AUTHENTICATION (2FA)
# ============================================

def generate_totp_secret() -> str:
    """Generate a TOTP secret for 2FA."""
    import secrets
    import base64
    return base64.b32encode(secrets.token_bytes(20)).decode('utf-8')

def verify_totp(secret: str, code: str) -> bool:
    """Verify a TOTP code (time-based one-time password)."""
    import hmac
    import struct
    import time as time_module
    import base64
    
    try:
        key = base64.b32decode(secret.upper())
        counter = int(time_module.time()) // 30
        
        # Check current and adjacent time periods
        for offset in [-1, 0, 1]:
            c = counter + offset
            msg = struct.pack(">Q", c)
            h = hmac.new(key, msg, "sha1").digest()
            o = h[-1] & 0xf
            token = (struct.unpack(">I", h[o:o+4])[0] & 0x7fffffff) % 1000000
            if str(token).zfill(6) == code.strip():
                return True
        return False
    except Exception:
        return False


@app.post("/api/2fa/setup")
def api_2fa_setup():
    """Initialize 2FA setup - generate secret and backup codes."""
    payload = request.get_json(silent=True) or {}
    user_id = payload.get("userId", "").strip()
    password = payload.get("password", "")
    
    if not user_id:
        return jsonify({"error": "userId required"}), 400
    
    # Verify password first
    with db() as con:
        row = con.execute("SELECT profile_json FROM users WHERE user_id = ?", (user_id,)).fetchone()
    
    if not row:
        return jsonify({"error": "User not found"}), 404
    
    profile = json.loads(row["profile_json"])
    stored_hash = profile.get("password_hash", "")
    
    if stored_hash and not verify_password(password, stored_hash):
        return jsonify({"error": "Invalid password"}), 401
    
    # Generate TOTP secret
    secret = generate_totp_secret()
    
    # Generate backup codes
    backup_codes = []
    for _ in range(10):
        code = generate_token(8)
        backup_codes.append(code)
        with db() as con:
            con.execute(
                "INSERT INTO backup_codes (id, user_id, code_hash, used, created_at) VALUES (?,?,?,0,?)",
                (str(uuid.uuid4()), user_id, hash_password(code), utc_now_iso())
            )
            con.commit()
    
    # Store pending secret (not activated until verified)
    profile["totp_secret_pending"] = secret
    with db() as con:
        con.execute("UPDATE users SET profile_json = ? WHERE user_id = ?",
                   (json.dumps(profile, ensure_ascii=False), user_id))
        con.commit()
    
    # Generate QR code URL
    qr_url = f"otpauth://totp/KELION:{user_id}?secret={secret}&issuer=KELION%20AI"
    
    log_audit("2fa_setup_started", {"user_id": user_id}, user_id=user_id)
    return jsonify({
        "ok": True,
        "secret": secret,
        "qrUrl": qr_url,
        "backupCodes": backup_codes
    }), 200


@app.post("/api/2fa/verify")
def api_2fa_verify():
    """Verify and activate 2FA."""
    payload = request.get_json(silent=True) or {}
    user_id = payload.get("userId", "").strip()
    code = payload.get("code", "").strip()
    
    if not user_id or not code:
        return jsonify({"error": "userId and code required"}), 400
    
    with db() as con:
        row = con.execute("SELECT profile_json FROM users WHERE user_id = ?", (user_id,)).fetchone()
    
    if not row:
        return jsonify({"error": "User not found"}), 404
    
    profile = json.loads(row["profile_json"])
    secret = profile.get("totp_secret_pending") or profile.get("totp_secret")
    
    if not secret:
        return jsonify({"error": "2FA not setup"}), 400
    
    if not verify_totp(secret, code):
        # Try backup codes
        with db() as con:
            codes = con.execute(
                "SELECT id, code_hash FROM backup_codes WHERE user_id = ? AND used = 0",
                (user_id,)
            ).fetchall()
        
        backup_valid = False
        for c in codes:
            if verify_password(code, c["code_hash"]):
                with db() as con:
                    con.execute("UPDATE backup_codes SET used = 1 WHERE id = ?", (c["id"],))
                    con.commit()
                backup_valid = True
                break
        
        if not backup_valid:
            return jsonify({"error": "Invalid code"}), 401
    
    # Activate 2FA if pending
    if "totp_secret_pending" in profile:
        profile["totp_secret"] = profile.pop("totp_secret_pending")
        profile["2fa_enabled"] = True
        profile["2fa_enabled_at"] = utc_now_iso()
        with db() as con:
            con.execute("UPDATE users SET profile_json = ? WHERE user_id = ?",
                       (json.dumps(profile, ensure_ascii=False), user_id))
            con.commit()
        log_audit("2fa_enabled", {"user_id": user_id}, user_id=user_id)
    
    return jsonify({"ok": True, "message": "2FA verified", "2fa_enabled": profile.get("2fa_enabled", False)}), 200


@app.post("/api/2fa/disable")
def api_2fa_disable():
    """Disable 2FA."""
    payload = request.get_json(silent=True) or {}
    user_id = payload.get("userId", "").strip()
    password = payload.get("password", "")
    code = payload.get("code", "").strip()
    
    if not user_id or not password:
        return jsonify({"error": "userId and password required"}), 400
    
    with db() as con:
        row = con.execute("SELECT profile_json FROM users WHERE user_id = ?", (user_id,)).fetchone()
    
    if not row:
        return jsonify({"error": "User not found"}), 404
    
    profile = json.loads(row["profile_json"])
    
    # Verify password
    if not verify_password(password, profile.get("password_hash", "")):
        return jsonify({"error": "Invalid password"}), 401
    
    # Verify 2FA code if enabled
    if profile.get("2fa_enabled") and code:
        if not verify_totp(profile.get("totp_secret", ""), code):
            return jsonify({"error": "Invalid 2FA code"}), 401
    
    # Disable 2FA
    profile.pop("totp_secret", None)
    profile.pop("totp_secret_pending", None)
    profile["2fa_enabled"] = False
    
    with db() as con:
        con.execute("UPDATE users SET profile_json = ? WHERE user_id = ?",
                   (json.dumps(profile, ensure_ascii=False), user_id))
        # Delete backup codes
        con.execute("DELETE FROM backup_codes WHERE user_id = ?", (user_id,))
        con.commit()
    
    log_audit("2fa_disabled", {"user_id": user_id}, user_id=user_id)
    return jsonify({"ok": True, "message": "2FA disabled"}), 200


# ============================================
# ADMIN USER MANAGEMENT
# ============================================

@app.get("/admin/users")
def admin_users_list():
    """List all users with their profiles."""
    if not _admin_ok(request):
        return jsonify({"error": "Unauthorized"}), 401
    
    limit = int(request.args.get("limit", "100"))
    offset = int(request.args.get("offset", "0"))
    
    with db() as con:
        rows = con.execute(
            "SELECT user_id, created_at, last_seen_at, profile_json FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        ).fetchall()
        total = con.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
    
    users = []
    for row in rows:
        profile = {}
        try:
            profile = json.loads(row["profile_json"])
            # Remove sensitive data
            profile.pop("password_hash", None)
            profile.pop("totp_secret", None)
        except:
            pass
        
        users.append({
            "user_id": row["user_id"],
            "created_at": row["created_at"],
            "last_seen_at": row["last_seen_at"],
            "tier": profile.get("tier", "Starter"),
            "email": profile.get("email", ""),
            "email_verified": profile.get("email_verified", False),
            "2fa_enabled": profile.get("2fa_enabled", False),
            "profile": profile
        })
    
    return jsonify({"users": users, "total": total, "limit": limit, "offset": offset}), 200


@app.post("/admin/users/upgrade")
def admin_users_upgrade():
    """Upgrade or downgrade a user's tier."""
    if not _admin_ok(request):
        return jsonify({"error": "Unauthorized"}), 401
    
    payload = request.get_json(silent=True) or {}
    user_id = payload.get("userId", "").strip()
    new_tier = payload.get("tier", "Starter")
    
    if not user_id:
        return jsonify({"error": "userId required"}), 400
    
    if new_tier not in ("Starter", "Pro", "Elite", "Enterprise"):
        return jsonify({"error": "Invalid tier"}), 400
    
    with db() as con:
        row = con.execute("SELECT profile_json FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            return jsonify({"error": "User not found"}), 404
        
        profile = json.loads(row["profile_json"])
        old_tier = profile.get("tier", "Starter")
        profile["tier"] = new_tier
        profile["tier_updated_at"] = utc_now_iso()
        profile["tier_updated_by"] = "admin"
        
        con.execute("UPDATE users SET profile_json = ? WHERE user_id = ?",
                   (json.dumps(profile, ensure_ascii=False), user_id))
        con.commit()
    
    log_audit("admin_tier_change", {"user_id": user_id, "old_tier": old_tier, "new_tier": new_tier})
    return jsonify({"ok": True, "userId": user_id, "oldTier": old_tier, "newTier": new_tier}), 200


@app.delete("/admin/users")
def admin_users_delete():
    """Delete a user (admin action)."""
    if not _admin_ok(request):
        return jsonify({"error": "Unauthorized"}), 401
    
    payload = request.get_json(silent=True) or {}
    user_id = payload.get("userId", "").strip()
    
    if not user_id:
        return jsonify({"error": "userId required"}), 400
    
    with db() as con:
        # Delete all user data
        con.execute("DELETE FROM messages WHERE user_id = ?", (user_id,))
        con.execute("DELETE FROM feedback WHERE user_id = ?", (user_id,))
        con.execute("DELETE FROM summaries WHERE user_id = ?", (user_id,))
        con.execute("DELETE FROM presence WHERE user_id = ?", (user_id,))
        con.execute("DELETE FROM tokens WHERE user_id = ?", (user_id,))
        con.execute("DELETE FROM backup_codes WHERE user_id = ?", (user_id,))
        con.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        con.commit()
    
    log_audit("admin_user_deleted", {"user_id": user_id})
    return jsonify({"ok": True, "message": f"User {user_id} deleted"}), 200


# ============================================
# DEMO TO USER UPGRADE
# ============================================

ADMIN_PASSWORD = "Andrada_1968!"

def _check_admin_password(req):
    """Check admin password from X-Admin-Token header."""
    token = req.headers.get('X-Admin-Token', '')
    return token == ADMIN_PASSWORD

@app.post("/admin/upgrade-demo")
def admin_upgrade_demo():
    """Upgrade demo account(s) to full user account with IP/MAC tracking."""
    if not _check_admin_password(request):
        return jsonify({"error": "Unauthorized"}), 401
    
    payload = request.get_json(silent=True) or {}
    user_ids = payload.get("userIds", [])  # Batch upgrade
    user_id = payload.get("userId", "").strip()  # Single upgrade
    
    # Support both single and batch
    if user_id and not user_ids:
        user_ids = [user_id]
    
    if not user_ids:
        return jsonify({"error": "userId or userIds required"}), 400
    
    upgraded = []
    failed = []
    
    for uid in user_ids:
        try:
            with db() as con:
                row = con.execute("SELECT profile_json FROM users WHERE user_id = ?", (uid,)).fetchone()
                if not row:
                    failed.append({"userId": uid, "error": "User not found"})
                    continue
                
                profile = json.loads(row["profile_json"])
                old_type = profile.get("user_type", "demo")
                
                # Upgrade to user
                profile["user_type"] = "user"
                profile["upgraded_from_demo"] = True
                profile["upgraded_at"] = utc_now_iso()
                profile["upgraded_by"] = "admin"
                
                con.execute("UPDATE users SET profile_json = ? WHERE user_id = ?",
                           (json.dumps(profile, ensure_ascii=False), uid))
                con.commit()
            
            log_audit("demo_upgraded", {"user_id": uid, "old_type": old_type}, user_id=uid)
            upgraded.append({"userId": uid, "oldType": old_type, "newType": "user"})
        except Exception as e:
            failed.append({"userId": uid, "error": str(e)})
    
    return jsonify({
        "ok": True,
        "upgraded": upgraded,
        "upgradedCount": len(upgraded),
        "failed": failed,
        "failedCount": len(failed)
    }), 200


# ============================================
# VISITOR TRACKING
# ============================================

@app.post("/api/track-visitor")
def api_track_visitor():
    """Track page visitor with IP, country, user-agent."""
    # Get client info
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if client_ip and ',' in client_ip:
        client_ip = client_ip.split(',')[0].strip()
    
    user_agent = request.headers.get('User-Agent', '')
    referer = request.headers.get('Referer', '')
    accept_language = request.headers.get('Accept-Language', '')
    
    payload = request.get_json(silent=True) or {}
    page = payload.get("page", "/")
    
    # Store visitor info
    visitor_id = str(uuid.uuid4())
    with db() as con:
        # Create visitors table if not exists
        con.execute("""
            CREATE TABLE IF NOT EXISTS visitors (
                id TEXT PRIMARY KEY,
                ip TEXT,
                user_agent TEXT,
                referer TEXT,
                accept_language TEXT,
                page TEXT,
                country TEXT,
                visited_at TEXT
            )
        """)
        con.execute(
            "INSERT INTO visitors (id, ip, user_agent, referer, accept_language, page, country, visited_at) VALUES (?,?,?,?,?,?,?,?)",
            (visitor_id, client_ip, user_agent, referer, accept_language, page, "", utc_now_iso())
        )
        con.commit()
    
    return jsonify({"ok": True}), 200


@app.get("/admin/visitors")
def admin_get_visitors():
    """Get all visitors (admin only)."""
    if not _check_admin_password(request):
        return jsonify({"error": "Unauthorized"}), 401
    
    limit = int(request.args.get("limit", "100"))
    
    with db() as con:
        # Ensure table exists
        con.execute("""
            CREATE TABLE IF NOT EXISTS visitors (
                id TEXT PRIMARY KEY,
                ip TEXT,
                user_agent TEXT,
                referer TEXT,
                accept_language TEXT,
                page TEXT,
                country TEXT,
                visited_at TEXT
            )
        """)
        rows = con.execute(
            "SELECT * FROM visitors ORDER BY visited_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
    
    visitors = []
    for row in rows:
        visitors.append({
            "id": row["id"],
            "ip": row["ip"],
            "user_agent": row["user_agent"],
            "referer": row["referer"],
            "page": row["page"],
            "country": row["country"] or "Unknown",
            "visited_at": row["visited_at"]
        })
    
    return jsonify({"visitors": visitors, "total": len(visitors)}), 200


@app.post("/api/upgrade-to-user")
def api_upgrade_to_user():
    """Self-upgrade from demo account to full user account."""
    payload = request.get_json(silent=True) or {}
    user_id = payload.get("userId", "").strip()
    email = payload.get("email", "").strip()
    password = payload.get("password", "")
    
    if not user_id:
        return jsonify({"error": "userId required"}), 400
    if not email or "@" not in email:
        return jsonify({"error": "Valid email required"}), 400
    if not password or len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400
    
    # Get device info
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if client_ip and ',' in client_ip:
        client_ip = client_ip.split(',')[0].strip()
    user_agent = request.headers.get('User-Agent', '')
    
    with db() as con:
        row = con.execute("SELECT profile_json FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            return jsonify({"error": "User not found"}), 404
        
        profile = json.loads(row["profile_json"])
        old_type = profile.get("user_type", "demo")
        
        if old_type not in ("demo", "tester"):
            return jsonify({"error": "Account is already a full user"}), 400
        
        # Check if email is already used
        rows = con.execute("SELECT user_id, profile_json FROM users").fetchall()
        for r in rows:
            if r["user_id"] != user_id:
                try:
                    p = json.loads(r["profile_json"])
                    if p.get("email", "").lower() == email.lower():
                        return jsonify({"error": "Email already in use"}), 409
                except:
                    pass
        
        # Upgrade account
        profile["user_type"] = "user"
        profile["email"] = email
        profile["password_hash"] = hash_password(password)
        profile["email_verified"] = False
        profile["upgraded_from_demo"] = True
        profile["upgraded_at"] = utc_now_iso()
        profile["device_info"] = {
            "ip": client_ip,
            "user_agent": user_agent,
            "upgraded_at": utc_now_iso()
        }
        
        con.execute("UPDATE users SET profile_json = ? WHERE user_id = ?",
                   (json.dumps(profile, ensure_ascii=False), user_id))
        con.commit()
    
    # Send verification email
    if SMTP_USER:
        try:
            token = create_token(user_id, "email_verify", expires_hours=48)
            verify_url = f"{request.host_url}verify-email?token={token}&user={user_id}"
            html_body = f"""
            <h1>Welcome to KELION AI!</h1>
            <p>Hi {user_id},</p>
            <p>Your demo account has been upgraded. Please verify your email:</p>
            <p><a href="{verify_url}" style="background:#00f3ff;color:#000;padding:10px 20px;text-decoration:none;border-radius:5px;">Verify Email</a></p>
            """
            send_email(email, "KELION AI - Verify Your Upgraded Account", html_body)
        except Exception as e:
            logger.warning(f"Failed to send upgrade verification: {e}")
    
    log_audit("demo_self_upgraded", {"user_id": user_id, "ip": client_ip}, user_id=user_id)
    
    return jsonify({
        "ok": True,
        "userId": user_id,
        "oldType": old_type,
        "newType": "user",
        "email_verification_sent": bool(SMTP_USER)
    }), 200


@app.post("/api/chat")
def api_chat():
    if not _auth_ok(request):
        return jsonify({"error": "Unauthorized"}), 401

    payload = request.get_json(silent=True) or {}
    user_id = payload.get("userId") or "anon"
    session_id = payload.get("sessionId") or "web"
    text = (payload.get("text") or "").strip()
    if not text:
        return jsonify({"error": "Missing text"}), 400

    # --- Subscription Logic ---
    SUBSCRIPTION_LIMITS = {
        "Starter": 50,    # messages per day
        "Pro": 500,
        "Elite": 999999
    }

    def get_user_tier(user_id: str) -> str:
        with db() as con:
            row = con.execute("SELECT profile_json FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            return "Starter"
        try:
            profile = json.loads(row["profile_json"])
            return profile.get("tier", "Starter")
        except:
            return "Starter"

    def check_rate_limit(user_id: str) -> bool:
        tier = get_user_tier(user_id)
        limit = SUBSCRIPTION_LIMITS.get(tier, 50)
        today = utc_now_iso().split("T")[0]
        
        with db() as con:
            row = con.execute(
                "SELECT COUNT(*) c FROM messages WHERE user_id = ? AND role = 'user' AND created_at LIKE ?", 
                (user_id, f"{today}%")
            ).fetchone()
        
        count = row["c"] if row else 0
        return count < limit

    upsert_user(user_id, profile={"language": DEFAULT_LANGUAGE, "persona": PERSONA_STYLE})
    
    if not check_rate_limit(user_id):
         return jsonify({"error": "Daily message limit reached for your plan. Upgrade to chat more."}), 403

    log_audit("user_input", {"text": text}, user_id=user_id, session_id=session_id)
    add_message(user_id, session_id, "user", text, meta={"via": "text"})

    ctx = get_recent_context(user_id, session_id, limit=14)
    try:
        # Use DeepSeek by default (free), fallback to OpenAI
        if AI_PROVIDER == "deepseek" and DEEPSEEK_API_KEY:
            ai = call_deepseek_chat(user_id, text, context=ctx)
        elif OPENAI_API_KEY:
            ai = call_openai_chat(user_id, text, context=ctx)
        else:
            raise RuntimeError("No AI provider configured")
    except Exception as e:
        log_audit("ai_error", {"error": str(e), "provider": AI_PROVIDER}, user_id=user_id, session_id=session_id)
        ai = {"text": "I'm having trouble reaching my AI service right now. Please try again in a moment.", "sources": [], "emotion": "empathetic"}

    add_message(user_id, session_id, "assistant", ai["text"], meta={"emotion": ai.get("emotion"), "sources": ai.get("sources")})
    maybe_update_summary(user_id, session_id)
    log_audit("assistant_output", {"text": ai["text"], "sources": ai.get("sources", []), "provider": AI_PROVIDER}, user_id=user_id, session_id=session_id)

    audio_url = None
    # Get user language - Romanian uses OpenAI TTS (onyx male voice)
    user_lang = profile.get("language", "en") if profile else "en"
    use_openai_for_ro = (user_lang == "ro")
    
    # Romanian = OpenAI TTS, other languages = browser TTS
    if (use_openai_for_ro or not USE_BROWSER_TTS) and OPENAI_API_KEY:
        try:
            audio_url = call_openai_tts(ai["text"])
            if audio_url:
                log_audit("tts_generated", {"audio_url": audio_url, "lang": user_lang}, user_id=user_id, session_id=session_id)
        except Exception as e:
            log_audit("tts_error", {"error": str(e)}, user_id=user_id, session_id=session_id)

    lipsync = None
    if audio_url:
        try:
            audio_file_path = os.path.join(AUDIO_DIR, audio_url.split("/")[-1])
            with open(audio_file_path, "rb") as af:
                tjson = call_openai_stt_words(af.read(), filename=audio_url.split("/")[-1])
            words = tjson.get("words") or []
            lipsync = {"words": words, "visemes": make_viseme_timeline(words)}
            log_audit("lipsync_generated", {"words": len(words)}, user_id=user_id, session_id=session_id)
        except Exception as e:
            log_audit("lipsync_error", {"error": str(e)}, user_id=user_id, session_id=session_id)

    # Animation hint for UI
    animation = "idle"
    if audio_url or USE_BROWSER_TTS:
        animation = "speak"
    if ai.get("emotion") == "happy":
        animation = "happy"
    if ai.get("emotion") == "empathetic":
        animation = "empathetic"

    return jsonify({
        "text": ai["text"],
        "emotion": ai.get("emotion", "calm"),
        "audioUrl": audio_url,
        "sources": ai.get("sources", []),
        "animation": animation,
        "lipsync": lipsync,
        "useBrowserTTS": USE_BROWSER_TTS and not use_openai_for_ro  # Romanian uses server TTS
    }), 200

# Alias endpoints (compatibility)
@app.post("/external/input")
def external_input():
    return api_chat()

@app.post("/api/contact_submit")
def api_contact():
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    email = (payload.get("email") or "").strip()
    message = (payload.get("message") or "").strip()
    lid = str(uuid.uuid4())
    with db() as con:
        con.execute("INSERT INTO leads (id, ts, name, email, message) VALUES (?,?,?,?,?)",
                    (lid, utc_now_iso(), name, email, message))
        con.commit()
    log_audit("contact_submit", {"id": lid, "email": email})
    return jsonify({"ok": True, "id": lid}), 200

@app.post("/api/narrate")
def api_narrate():
    """Generate cinematic narrator voice for intro/presentation."""
    payload = request.get_json(silent=True) or {}
    text = (payload.get("text") or "").strip()
    if not text:
        return jsonify({"error": "Missing text"}), 400
    
    if not OPENAI_API_KEY:
        # Fallback for users without OpenAI key (e.g. using only DeepSeek)
        # Return success but no audio URL, frontend should handle this (use browser TTS or silent)
        logger.warning("Narrate requested but OPENAI_API_KEY not configured. Skipping server-side TTS.")
        return jsonify({"audioUrl": None, "message": "Server TTS unconfigured, use client TTS"}), 200
    
    try:
        os.makedirs(AUDIO_DIR, exist_ok=True)
        audio_id = str(uuid.uuid4())
        out_path = os.path.join(AUDIO_DIR, f"{audio_id}.mp3")
        
        # Use "onyx" for deep male narrator voice
        narrator_voice = os.getenv("OPENAI_NARRATOR_VOICE", "onyx")
        
        payload_tts = {
            "model": OPENAI_TTS_MODEL,
            "voice": narrator_voice,
            "input": text,
            "instructions": "Speak in a deep, cinematic, dramatic narrator voice. Slow pace, building atmosphere. Like an epic movie trailer."
        }
        logger.info(f"Narrate request: voice={narrator_voice}, text_len={len(text)}")
        r = requests.post(f"{OPENAI_BASE_URL}/audio/speech", headers=openai_headers_json(), json=payload_tts, timeout=90)
        r.raise_for_status()
        with open(out_path, "wb") as f:
            f.write(r.content)
        
        audio_url = f"/audio/{audio_id}.mp3"
        log_audit("narrate_generated", {"audio_url": audio_url, "text_len": len(text)})
        return jsonify({"audioUrl": audio_url}), 200
    except Exception as e:
        logger.error(f"Narrate error: {e}")
        log_audit("narrate_error", {"error": str(e)})
        return jsonify({"error": f"Narration failed: {str(e)}"}), 500


@app.post("/api/voice/tts")
def api_voice_tts():
    """Generate TTS audio and return as base64 (for debug tools and direct playback)."""
    payload = request.get_json(silent=True) or {}
    text = (payload.get("text") or "").strip()
    if not text:
        return jsonify({"ok": False, "error": "Missing text"}), 400
    
    if not OPENAI_API_KEY:
        # Fallback: indicate client should use browser TTS
        return jsonify({"ok": False, "error": "Server TTS not configured, use browser TTS", "useBrowserTTS": True}), 200
    
    try:
        import base64
        
        # Use cinematic voice if requested
        cinematic = payload.get("cinematic", False)
        voice = os.getenv("OPENAI_NARRATOR_VOICE", "onyx") if cinematic else OPENAI_TTS_VOICE
        
        payload_tts = {
            "model": OPENAI_TTS_MODEL,
            "voice": voice,
            "input": text,
            "instructions": "Speak in a friendly, conversational tone." if not cinematic else "Speak in a deep, cinematic, dramatic narrator voice."
        }
        
        r = requests.post(f"{OPENAI_BASE_URL}/audio/speech", headers=openai_headers_json(), json=payload_tts, timeout=60)
        r.raise_for_status()
        
        audio_b64 = base64.b64encode(r.content).decode("utf-8")
        log_audit("voice_tts_generated", {"text_len": len(text), "cinematic": cinematic})
        
        return jsonify({
            "ok": True,
            "audio_b64": audio_b64,
            "mime": "audio/mpeg"
        }), 200
    except Exception as e:
        logger.error(f"Voice TTS error: {e}")
        log_audit("voice_tts_error", {"error": str(e)})
        return jsonify({"ok": False, "error": str(e)}), 500


# --- Presence API (hologram state tracking) ---
@app.get("/api/presence")
def get_presence():
    """Get current hologram presence state for user/session."""
    user_id = request.args.get("userId") or request.headers.get("X-User-Id") or "web"
    session_id = request.args.get("sessionId") or request.headers.get("X-Session-Id") or "default"
    
    with db() as con:
        row = con.execute(
            "SELECT state_json FROM presence WHERE user_id=? AND session_id=?",
            (user_id, session_id)
        ).fetchone()
    
    if not row:
        return jsonify({
            "userId": user_id,
            "sessionId": session_id,
            "state": "idle",
            "emotion": "neutral",
            "focus": "user"
        })
    
    state = json.loads(row["state_json"])
    state.update({"userId": user_id, "sessionId": session_id})
    return jsonify(state)


@app.post("/api/presence")
def post_presence():
    """Update hologram presence state."""
    payload = request.get_json(silent=True) or {}
    user_id = payload.get("userId") or request.headers.get("X-User-Id") or "web"
    session_id = payload.get("sessionId") or request.headers.get("X-Session-Id") or "default"
    
    patch = payload.get("patch") if isinstance(payload.get("patch"), dict) else payload
    state = patch.get("state") or patch.get("mode") or "idle"
    emotion = patch.get("emotion") or "neutral"
    focus = patch.get("focus") or "user"
    
    state_obj = {"state": state, "emotion": emotion, "focus": focus}
    for k, v in patch.items():
        if k not in ("userId", "sessionId", "patch"):
            state_obj[k] = v
    
    with db() as con:
        con.execute(
            """INSERT INTO presence(user_id, session_id, updated_at, state_json) VALUES(?,?,?,?)
               ON CONFLICT(user_id, session_id) DO UPDATE SET updated_at=excluded.updated_at, state_json=excluded.state_json""",
            (user_id, session_id, int(time.time()), json.dumps(state_obj))
        )
        con.commit()
    
    state_obj.update({"userId": user_id, "sessionId": session_id})
    log_audit("presence_updated", {"user_id": user_id, "state": state})
    return jsonify(state_obj)


@app.get("/api/pricing")
def api_pricing():
    return jsonify({
        "currency": "USD",
        "tiers": [
            {"name": "Starter", "price": 19, "features": ["Web hologram", "AI chat", "Basic support"]},
            {"name": "Pro", "price": 59, "features": ["Voice (TTS/STT)", "Persistent memory", "Admin audit"]},
            {"name": "Enterprise", "price": 199, "features": ["Custom workflows", "Legal-grade audit", "SLA"]},
        ]
    }), 200

@app.get("/api/plans")
def api_plans():
    return api_pricing()

@app.post("/api/subscribe")
def api_subscribe():
    payload = request.get_json(silent=True) or {}
    tier = payload.get("tier") or "Starter"
    email = payload.get("email") or ""
    # In a real app, verify payment here.
    # For now, we trust the frontend request or default to free.
    
    # We need the user_id context, usually from auth token or payload
    # Assuming user_id is passed or inferred (here we take from payload for simplicity demo)
    user_id = payload.get("userId") or "user" 
    
    # Update user profile
    upsert_user(user_id, profile={"tier": tier, "email": email, "updated_at": utc_now_iso()})
    
    log_audit("subscribe", {"tier": tier, "email": email}, user_id=user_id)
    return jsonify({"ok": True, "tier": tier}), 200


# ============================================
# STRIPE PAYMENT ENDPOINTS
# ============================================

@app.post("/api/create-checkout-session")
def create_checkout_session():
    """Create Stripe checkout session for subscription."""
    if not STRIPE_AVAILABLE or not STRIPE_SECRET_KEY:
        return jsonify({"error": "Payment system not configured"}), 503
    
    payload = request.get_json(silent=True) or {}
    tier = payload.get("tier", "Pro")
    user_id = payload.get("userId", "")
    success_url = payload.get("successUrl") or request.host_url + "?payment=success"
    cancel_url = payload.get("cancelUrl") or request.host_url + "?payment=cancelled"
    
    prices = {
        "Starter": STRIPE_PRICE_STARTER,
        "Pro": STRIPE_PRICE_PRO,
        "Enterprise": STRIPE_PRICE_ENTERPRISE
    }
    
    price_id = prices.get(tier)
    if not price_id or price_id.startswith("price_"):
        # Placeholder price - return mock response for demo
        log_audit("checkout_demo", {"tier": tier, "user_id": user_id})
        return jsonify({
            "ok": True,
            "demo": True,
            "message": "Stripe not fully configured. In production, this would redirect to payment.",
            "tier": tier
        }), 200
    
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"user_id": user_id, "tier": tier}
        )
        log_audit("checkout_created", {"tier": tier, "session_id": session.id}, user_id=user_id)
        return jsonify({"ok": True, "sessionUrl": session.url, "sessionId": session.id}), 200
    except Exception as e:
        logger.error(f"Stripe checkout error: {e}")
        return jsonify({"error": str(e)}), 500


@app.post("/api/stripe-webhook")
def stripe_webhook():
    """Handle Stripe webhooks for subscription events."""
    if not STRIPE_AVAILABLE:
        return jsonify({"error": "Stripe not available"}), 503
    
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature", "")
    
    try:
        if STRIPE_WEBHOOK_SECRET:
            event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
        else:
            event = json.loads(payload)
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"error": "Invalid webhook"}), 400
    
    event_type = event.get("type", "")
    data = event.get("data", {}).get("object", {})
    
    if event_type == "checkout.session.completed":
        user_id = data.get("metadata", {}).get("user_id")
        tier = data.get("metadata", {}).get("tier", "Pro")
        if user_id:
            upsert_user(user_id, profile={"tier": tier, "stripe_customer": data.get("customer"), "subscribed_at": utc_now_iso()})
            log_audit("subscription_activated", {"tier": tier, "customer": data.get("customer")}, user_id=user_id)
    
    elif event_type == "customer.subscription.deleted":
        customer_id = data.get("customer")
        # Find user by customer ID and downgrade
        with db() as con:
            rows = con.execute("SELECT user_id, profile_json FROM users").fetchall()
            for row in rows:
                try:
                    profile = json.loads(row["profile_json"])
                    if profile.get("stripe_customer") == customer_id:
                        profile["tier"] = "Starter"
                        upsert_user(row["user_id"], profile=profile)
                        log_audit("subscription_cancelled", {"customer": customer_id}, user_id=row["user_id"])
                        break
                except:
                    pass
    
    return jsonify({"received": True}), 200


# ============================================
# GDPR ENDPOINTS (Real Data Export/Delete)
# ============================================

@app.get("/api/gdpr/export")
def gdpr_export():
    """Export all user data as JSON (GDPR Article 20 - Right to Data Portability)."""
    user_id = request.args.get("userId") or request.headers.get("X-User-Id")
    
    if not user_id:
        return jsonify({"error": "userId required"}), 400
    
    # Verify user or admin
    if not _admin_ok(request):
        # User can only export their own data
        auth_user = request.headers.get("X-User-Id")
        if auth_user != user_id:
            return jsonify({"error": "Unauthorized - can only export own data"}), 403
    
    export_data = {
        "exported_at": utc_now_iso(),
        "user_id": user_id,
        "user": None,
        "messages": [],
        "feedback": [],
        "summary": None
    }
    
    with db() as con:
        # User profile
        user_row = con.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if user_row:
            user_dict = dict(user_row)
            # Remove password hash from export
            try:
                profile = json.loads(user_dict.get("profile_json", "{}"))
                profile.pop("password_hash", None)
                user_dict["profile_json"] = json.dumps(profile)
            except:
                pass
            export_data["user"] = user_dict
        
        # Messages
        messages = con.execute("SELECT * FROM messages WHERE user_id = ? ORDER BY created_at", (user_id,)).fetchall()
        export_data["messages"] = [dict(m) for m in messages]
        
        # Feedback
        feedback = con.execute("SELECT * FROM feedback WHERE user_id = ?", (user_id,)).fetchall()
        export_data["feedback"] = [dict(f) for f in feedback]
        
        # Summary
        summary = con.execute("SELECT * FROM summaries WHERE user_id = ?", (user_id,)).fetchone()
        if summary:
            export_data["summary"] = dict(summary)
    
    log_audit("gdpr_export", {"user_id": user_id, "records": len(export_data["messages"])}, user_id=user_id)
    
    return jsonify(export_data), 200


@app.delete("/api/gdpr/delete")
def gdpr_delete():
    """Delete all user data (GDPR Article 17 - Right to Erasure)."""
    payload = request.get_json(silent=True) or {}
    user_id = payload.get("userId") or request.args.get("userId")
    confirmation = payload.get("confirmation", "")
    
    if not user_id:
        return jsonify({"error": "userId required"}), 400
    
    # Require confirmation to prevent accidental deletion
    if confirmation != "DELETE":
        return jsonify({"error": "Confirmation required. Send 'confirmation': 'DELETE' to confirm."}), 400
    
    # Verify admin or user token
    if not _admin_ok(request):
        auth_user = request.headers.get("X-User-Id")
        if auth_user != user_id:
            return jsonify({"error": "Unauthorized - can only delete own data"}), 403
    
    deleted_counts = {}
    
    with db() as con:
        # Count before delete
        deleted_counts["messages"] = con.execute("SELECT COUNT(*) c FROM messages WHERE user_id = ?", (user_id,)).fetchone()["c"]
        deleted_counts["feedback"] = con.execute("SELECT COUNT(*) c FROM feedback WHERE user_id = ?", (user_id,)).fetchone()["c"]
        
        # Delete from all tables
        con.execute("DELETE FROM messages WHERE user_id = ?", (user_id,))
        con.execute("DELETE FROM feedback WHERE user_id = ?", (user_id,))
        con.execute("DELETE FROM summaries WHERE user_id = ?", (user_id,))
        con.execute("DELETE FROM presence WHERE user_id = ?", (user_id,))
        con.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        con.commit()
    
    log_audit("gdpr_deletion", {"user_id": user_id, "deleted": deleted_counts})
    
    return jsonify({
        "ok": True,
        "deleted": deleted_counts,
        "message": f"All data for user '{user_id}' has been permanently deleted."
    }), 200


@app.post("/api/gdpr/request")
def gdpr_request():
    """Submit GDPR request (export/delete) via email notification."""
    payload = request.get_json(silent=True) or {}
    user_id = payload.get("userId", "")
    request_type = payload.get("type", "")  # "export" or "delete"
    email = payload.get("email", "")
    
    if request_type not in ("export", "delete"):
        return jsonify({"error": "Invalid request type. Use 'export' or 'delete'."}), 400
    
    # Log the request
    with db() as con:
        con.execute(
            "INSERT INTO leads (id, ts, name, email, message) VALUES (?,?,?,?,?)",
            (str(uuid.uuid4()), utc_now_iso(), f"GDPR {request_type.upper()} Request", email, f"User: {user_id}")
        )
        con.commit()
    
    log_audit(f"gdpr_{request_type}_request", {"user_id": user_id, "email": email}, user_id=user_id)
    
    # Send notification email if configured
    if SMTP_USER and email:
        html = f"""
        <div style="font-family: Arial, sans-serif;">
            <h2>GDPR {request_type.title()} Request Received</h2>
            <p>Your request has been submitted and will be processed within 30 days.</p>
            <p><strong>Request Type:</strong> {request_type.title()}</p>
            <p><strong>User ID:</strong> {user_id}</p>
            <p>If you didn't make this request, please contact us immediately.</p>
        </div>
        """
        send_email(email, f"KELION AI - GDPR {request_type.title()} Request Confirmation", html)
    
    return jsonify({
        "ok": True,
        "message": f"GDPR {request_type} request submitted. You will be contacted within 30 days."
    }), 200


@app.get("/api/dashboard")
def api_dashboard():
    # Minimal dashboard data (admin can expand)
    with db() as con:
        u = con.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
        m = con.execute("SELECT COUNT(*) c FROM messages").fetchone()["c"]
        l = con.execute("SELECT COUNT(*) c FROM leads").fetchone()["c"]
    return jsonify({"users": u, "messages": m, "leads": l, "version": "k1.1.0"}), 200

# Admin endpoints (audit + messages)
@app.get("/admin/audit")
def admin_audit():
    if not _admin_ok(request):
        return jsonify({"error": "Unauthorized"}), 401
    limit = int(request.args.get("limit", "100"))
    with db() as con:
        rows = con.execute("SELECT ts, user_id, session_id, action, detail_json FROM audit ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
    items = []
    for r in rows:
        items.append({
            "ts": r["ts"],
            "user_id": r["user_id"],
            "session_id": r["session_id"],
            "action": r["action"],
            "detail": json.loads(r["detail_json"])
        })
    return jsonify({"items": items}), 200

@app.get("/admin/messages")
def admin_messages():
    if not _admin_ok(request):
        return jsonify({"error": "Unauthorized"}), 401
    user_id = request.args.get("user_id", "anon")
    limit = int(request.args.get("limit", "100"))
    with db() as con:
        rows = con.execute(
            "SELECT created_at, session_id, role, content, meta_json FROM messages WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit)
        ).fetchall()
    items = []
    for r in rows:
        items.append({
            "created_at": r["created_at"],
            "session_id": r["session_id"],
            "role": r["role"],
            "content": r["content"],
            "meta": json.loads(r["meta_json"])
        })
    return jsonify({"user_id": user_id, "items": items}), 200

@app.post("/api/feedback")
def api_feedback():
    if not _auth_ok(request):
        return jsonify({"error": "Unauthorized"}), 401
    payload = request.get_json(silent=True) or {}
    user_id = payload.get("userId") or "anon"
    session_id = payload.get("sessionId") or "web"
    message_id = payload.get("messageId")
    rating = payload.get("rating")
    correction = (payload.get("correction") or "").strip()
    fid = str(uuid.uuid4())
    with db() as con:
        con.execute(
            "INSERT INTO feedback (id, ts, user_id, session_id, message_id, rating, correction) VALUES (?,?,?,?,?,?,?)",
            (fid, utc_now_iso(), user_id, session_id, message_id, rating, correction)
        )
        con.commit()
    log_audit("feedback", {"id": fid, "rating": rating}, user_id=user_id, session_id=session_id)
    return jsonify({"ok": True, "id": fid}), 200

@app.post("/admin/rules")
def admin_rules_upsert():
    if not _admin_ok(request):
        return jsonify({"error": "Unauthorized"}), 401
    payload = request.get_json(silent=True) or {}
    title = (payload.get("title") or "").strip()
    body = (payload.get("body") or "").strip()
    enabled = 1 if payload.get("enabled", True) else 0
    if not title or not body:
        return jsonify({"error": "Missing title/body"}), 400
    rid = str(uuid.uuid4())
    with db() as con:
        con.execute("INSERT INTO rules (id, ts, title, body, enabled) VALUES (?,?,?,?,?)",
                    (rid, utc_now_iso(), title, body, enabled))
        con.commit()
    return jsonify({"ok": True, "id": rid}), 200

@app.post("/admin/sources")
def admin_sources_set():
    if not _admin_ok(request):
        return jsonify({"error": "Unauthorized"}), 401
    payload = request.get_json(silent=True) or {}
    domain = (payload.get("domain") or "").strip().lower()
    trust = payload.get("trust", 50)
    if not domain:
        return jsonify({"error": "Missing domain"}), 400
    set_source_trust(domain, int(trust))
    return jsonify({"ok": True, "domain": domain, "trust": get_source_trust(domain)}), 200

# ============================================
# RAILWAY DEPLOY ENDPOINTS
# ============================================

@app.get("/api/railway/config")
def railway_config_status():
    try:
        manager = get_deploy_manager()
        return jsonify({"success": True, "config": manager.get_config_status()}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.get("/api/railway/info")
def railway_service_info():
    try:
        manager = get_deploy_manager()
        return jsonify({"success": True, "service": manager.get_service_info()}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.post("/api/railway/deploy")
def railway_deploy():
    if DEPLOY_API_KEY:
        auth = request.headers.get("Authorization", "")
        if auth != f"Bearer {DEPLOY_API_KEY}":
            return jsonify({"error": "Unauthorized"}), 401
    try:
        manager = get_deploy_manager()
        result = manager.deploy()
        code = 200 if result.get("success") else 500
        return jsonify(result), code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.get("/api/railway/health")
def railway_health():
    try:
        manager = get_deploy_manager()
        cfg = manager.get_config_status()
        all_set = all([cfg["railway_token_set"], cfg["service_id_set"], cfg["project_id_set"]])
        return jsonify({
            "success": True,
            "healthy": all_set,
            "message": "Railway deploy system is ready" if all_set else "Missing configuration",
            "config": cfg
        }), 200
    except Exception as e:
        return jsonify({"success": False, "healthy": False, "error": str(e)}), 500

# ============================================
# FIN RAILWAY DEPLOY ENDPOINTS
# ============================================

# ============================================
# ADMIN BROADCAST & SUBSCRIPTIONS (DB-BACKED)
# ============================================

# Default tiers (inserted on first run if table empty)
DEFAULT_TIERS = [
    {"id": "FREE", "name": "Free", "price": 0, "features": ["50 messages/day", "Basic support"], "limit": 50, "active": True},
    {"id": "STARTER", "name": "Starter", "price": 19, "features": ["Web hologram", "AI chat", "Basic support", "200 messages/day"], "limit": 200, "active": True},
    {"id": "PRO", "name": "Professional", "price": 59, "features": ["Voice (TTS/STT)", "Persistent memory", "Admin audit", "Unlimited messages"], "limit": 0, "active": True, "popular": True},
    {"id": "ENTERPRISE", "name": "Enterprise", "price": 199, "features": ["Custom workflows", "Legal-grade audit", "SLA", "Priority support"], "limit": 0, "active": True},
]

def _init_default_tiers():
    """Initialize default subscription tiers if table is empty."""
    with db() as con:
        count = con.execute("SELECT COUNT(*) as cnt FROM subscription_tiers").fetchone()
        if count and (count["cnt"] if isinstance(count, dict) else count[0]) == 0:
            for t in DEFAULT_TIERS:
                con.execute(
                    "INSERT INTO subscription_tiers (id, name, price, features_json, msg_limit, active, popular) VALUES (?,?,?,?,?,?,?)",
                    (t["id"], t["name"], t["price"], json.dumps(t["features"]), t["limit"], 1 if t["active"] else 0, 1 if t.get("popular") else 0)
                )
            con.commit()
            logger.info("Default subscription tiers initialized")

def _get_all_tiers():
    """Get all subscription tiers from database."""
    with db() as con:
        rows = con.execute("SELECT * FROM subscription_tiers WHERE active = 1").fetchall()
        tiers = []
        for r in rows:
            tiers.append({
                "id": r["id"],
                "name": r["name"],
                "price": r["price"],
                "features": json.loads(r["features_json"]) if r["features_json"] else [],
                "limit": r["msg_limit"],
                "active": bool(r["active"]),
                "popular": bool(r["popular"]) if "popular" in r.keys() else False
            })
        return tiers

def _get_broadcasts(limit=50):
    """Get broadcasts from database."""
    with db() as con:
        rows = con.execute("SELECT * FROM broadcasts ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        broadcasts = []
        for r in rows:
            confirmations = json.loads(r["confirmations_json"]) if r["confirmations_json"] else []
            broadcasts.append({
                "id": r["id"],
                "title": r["title"],
                "body": r["body"],
                "priority": r["priority"],
                "require_confirmation": bool(r["require_confirmation"]),
                "target": r["target"],
                "user_id": r["target_user_id"],
                "created_at": r["created_at"],
                "confirmations": confirmations,
                "confirmed_count": len(confirmations)
            })
        return broadcasts

@app.get("/pricing")
def get_pricing():
    """Public pricing endpoint."""
    _init_default_tiers()
    return jsonify({
        "currency": "USD",
        "tiers": _get_all_tiers()
    }), 200

@app.post("/admin/broadcast")
def admin_broadcast():
    """Send broadcast message to users (DB-backed)."""
    if not _admin_ok(request):
        return jsonify({"error": "Admin token required"}), 401
    
    payload = request.get_json(silent=True) or {}
    title = payload.get("title", "")
    body = payload.get("body", "")
    priority = payload.get("priority", "info")
    require_confirmation = payload.get("require_confirmation", True)
    target = payload.get("target", "all")
    target_user_id = payload.get("user_id", "")
    
    if not title or not body:
        return jsonify({"error": "Title and body required"}), 400
    
    broadcast_id = str(uuid.uuid4())
    
    # Count recipients
    total_count = 1
    if target == "all":
        with db() as con:
            rows = con.execute("SELECT COUNT(*) as cnt FROM users").fetchone()
            total_count = rows["cnt"] if isinstance(rows, dict) else rows[0]
    
    # Save to database
    with db() as con:
        con.execute(
            """INSERT INTO broadcasts (id, title, body, priority, require_confirmation, target, target_user_id, created_at, confirmations_json)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (broadcast_id, title, body, priority, 1 if require_confirmation else 0, target, target_user_id if target == "user" else None, utc_now_iso(), "[]")
        )
        con.commit()
    
    log_audit("broadcast_sent", {"id": broadcast_id, "target": target, "title": title})
    
    return jsonify({
        "ok": True,
        "broadcast_id": broadcast_id,
        "recipients": total_count
    }), 200

@app.get("/admin/broadcasts")
def get_broadcasts_endpoint():
    """Get broadcast history from DB."""
    if not _admin_ok(request):
        return jsonify({"error": "Admin token required"}), 401
    
    return jsonify({"broadcasts": _get_broadcasts(50)}), 200

@app.post("/api/broadcast/confirm")
def confirm_broadcast():
    """User confirms they received a broadcast message (DB-backed)."""
    payload = request.get_json(silent=True) or {}
    broadcast_id = payload.get("broadcast_id", "")
    user_id = payload.get("user_id", "")
    
    if not broadcast_id or not user_id:
        return jsonify({"error": "broadcast_id and user_id required"}), 400
    
    with db() as con:
        row = con.execute("SELECT confirmations_json FROM broadcasts WHERE id = ?", (broadcast_id,)).fetchone()
        if not row:
            return jsonify({"error": "Broadcast not found"}), 404
        
        confirmations = json.loads(row["confirmations_json"]) if row["confirmations_json"] else []
        if user_id not in confirmations:
            confirmations.append(user_id)
            con.execute("UPDATE broadcasts SET confirmations_json = ? WHERE id = ?", (json.dumps(confirmations), broadcast_id))
            con.commit()
            log_audit("broadcast_confirmed", {"broadcast_id": broadcast_id, "user_id": user_id})
    
    return jsonify({"ok": True, "confirmed": True}), 200

@app.get("/api/broadcasts/pending")
def get_pending_broadcasts():
    """Get pending broadcasts for current user (DB-backed)."""
    user_id = request.args.get("user_id", "")
    if not user_id:
        return jsonify({"broadcasts": []}), 200
    
    pending = []
    for bc in _get_broadcasts(100):
        if bc["require_confirmation"]:
            if bc["target"] == "all" and user_id not in bc["confirmations"]:
                pending.append(bc)
            elif bc["target"] == "user" and bc["user_id"] == user_id and user_id not in bc["confirmations"]:
                pending.append(bc)
    
    return jsonify({"broadcasts": pending}), 200

# --- Subscription Tier Management (DB-backed) ---

@app.post("/admin/tiers")
def create_tier():
    """Create new subscription tier (DB-backed)."""
    if not _admin_ok(request):
        return jsonify({"error": "Admin token required"}), 401
    
    payload = request.get_json(silent=True) or {}
    tier_id = payload.get("id", "").upper().replace(" ", "_")
    name = payload.get("name", "")
    price = payload.get("price", 0)
    features = payload.get("features", [])
    limit = payload.get("limit", 0)
    active = payload.get("active", True)
    
    if not tier_id or not name:
        return jsonify({"error": "Tier ID and name required"}), 400
    
    with db() as con:
        existing = con.execute("SELECT id FROM subscription_tiers WHERE id = ?", (tier_id,)).fetchone()
        if existing:
            return jsonify({"error": "Tier ID already exists"}), 409
        
        con.execute(
            "INSERT INTO subscription_tiers (id, name, price, features_json, msg_limit, active, popular) VALUES (?,?,?,?,?,?,?)",
            (tier_id, name, float(price), json.dumps(features), int(limit), 1 if active else 0, 0)
        )
        con.commit()
    
    log_audit("tier_created", {"tier_id": tier_id, "price": price})
    
    return jsonify({"ok": True, "tier": {"id": tier_id, "name": name, "price": price, "features": features}}), 201

@app.put("/admin/tiers")
def update_tier():
    """Update existing subscription tier (DB-backed)."""
    if not _admin_ok(request):
        return jsonify({"error": "Admin token required"}), 401
    
    payload = request.get_json(silent=True) or {}
    original_id = payload.get("original_id", "")
    tier_id = payload.get("id", "").upper().replace(" ", "_")
    name = payload.get("name", "")
    price = payload.get("price", 0)
    features = payload.get("features", [])
    limit = payload.get("limit", 0)
    active = payload.get("active", True)
    
    with db() as con:
        existing = con.execute("SELECT id, popular FROM subscription_tiers WHERE id = ?", (original_id,)).fetchone()
        if not existing:
            return jsonify({"error": "Tier not found"}), 404
        
        popular = existing["popular"] if isinstance(existing, dict) else existing[1]
        
        con.execute(
            "UPDATE subscription_tiers SET id=?, name=?, price=?, features_json=?, msg_limit=?, active=? WHERE id=?",
            (tier_id, name, float(price), json.dumps(features), int(limit), 1 if active else 0, original_id)
        )
        con.commit()
    
    log_audit("tier_updated", {"tier_id": tier_id})
    return jsonify({"ok": True, "tier": {"id": tier_id, "name": name, "price": price, "features": features}}), 200

@app.delete("/admin/tiers/<tier_id>")
def delete_tier(tier_id: str):
    """Delete subscription tier (DB-backed)."""
    if not _admin_ok(request):
        return jsonify({"error": "Admin token required"}), 401
    
    with db() as con:
        result = con.execute("DELETE FROM subscription_tiers WHERE id = ?", (tier_id.upper(),))
        con.commit()
        if result.rowcount == 0:
            return jsonify({"error": "Tier not found"}), 404
    
    log_audit("tier_deleted", {"tier_id": tier_id})
    return jsonify({"ok": True}), 200

# ============================================
# BROADCAST MESSAGING SYSTEM
# ============================================

# In-memory broadcast storage (will be persisted to DB in production)
_broadcasts = []

@app.route("/api/admin/broadcast", methods=["POST"])
def admin_send_broadcast():
    """Send a broadcast message to all or specific users."""
    if not _admin_ok(request):
        return jsonify({"error": "Admin token required"}), 401
    
    data = request.get_json() or {}
    message = data.get("message", "").strip()
    target = data.get("target", "all")  # "all" or "specific"
    user_id = data.get("user_id")  # Only if target is "specific"
    priority = data.get("priority", "info")  # info, warning, urgent
    
    if not message:
        return jsonify({"error": "Message is required"}), 400
    
    if target == "specific" and not user_id:
        return jsonify({"error": "User ID required for specific target"}), 400
    
    broadcast = {
        "id": str(uuid.uuid4()),
        "message": message,
        "target": target,
        "user_id": user_id if target == "specific" else None,
        "priority": priority,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "read_at": None,
        "read_by": []
    }
    
    _broadcasts.append(broadcast)
    log_audit("broadcast_sent", {"target": target, "priority": priority})
    
    return jsonify({"success": True, "broadcast_id": broadcast["id"]})

@app.route("/api/admin/broadcasts", methods=["GET"])
def admin_list_broadcasts():
    """List all broadcasts."""
    if not _admin_ok(request):
        return jsonify({"error": "Admin token required"}), 401
    
    return jsonify({"broadcasts": _broadcasts[-50:]})  # Last 50

@app.route("/api/admin/broadcast/<broadcast_id>", methods=["DELETE"])
def admin_delete_broadcast(broadcast_id):
    """Delete a broadcast."""
    if not _admin_ok(request):
        return jsonify({"error": "Admin token required"}), 401
    
    global _broadcasts
    _broadcasts = [b for b in _broadcasts if b["id"] != broadcast_id]
    return jsonify({"success": True})

@app.route("/api/user/broadcasts", methods=["GET"])
def user_get_broadcasts():
    """Get pending broadcasts for a user."""
    user_id = request.args.get("user_id", "")
    
    # Find broadcasts for this user that haven't been read
    pending = []
    for b in _broadcasts:
        if b["read_at"]:
            continue  # Already fully read
        if user_id in b.get("read_by", []):
            continue  # This user already read it
        if b["target"] == "all" or (b["target"] == "specific" and b["user_id"] == user_id):
            pending.append(b)
    
    return jsonify({"broadcasts": pending})

@app.route("/api/user/broadcast/confirm", methods=["POST"])
def user_confirm_broadcast():
    """Confirm user has read a broadcast."""
    data = request.get_json() or {}
    broadcast_id = data.get("broadcast_id")
    user_id = data.get("user_id", "anonymous")
    
    for b in _broadcasts:
        if b["id"] == broadcast_id:
            if "read_by" not in b:
                b["read_by"] = []
            if user_id not in b["read_by"]:
                b["read_by"].append(user_id)
            
            # Mark as fully read if specific user or all have read
            if b["target"] == "specific":
                b["read_at"] = datetime.now(timezone.utc).isoformat()
            
            log_audit("broadcast_read", {"broadcast_id": broadcast_id, "user_id": user_id})
            break
    
    return jsonify({"success": True})

# ============================================
# FIN ADMIN BROADCAST & SUBSCRIPTIONS
# ============================================

# ============================================
# DAY ZERO RESET - Complete Visitor Reset
# ============================================

@app.post("/api/admin/day-zero")
def api_admin_day_zero():
    """
    ZIUA 0 - Reset complet al vizitatorilor.
    Șterge toți vizitatorii pentru a simula o aplicație proaspătă.
    ATENȚIE: După apelare, toți utilizatorii vor vedea intro-ul ca vizitatori noi!
    """
    if not _admin_ok(request):
        return jsonify({"error": "Admin required"}), 403
    
    deleted = {"visitors": 0, "demo_usage": 0, "visits": 0}
    
    try:
        with db() as con:
            # Șterge preferințe vizitatori (face toți să fie "first visit")
            try:
                cur = con.execute("DELETE FROM visitor_prefs")
                deleted["visitors"] = cur.rowcount if hasattr(cur, 'rowcount') else -1
            except Exception as e:
                logger.warning(f"visitor_prefs delete error: {e}")
            
            # Șterge usage demo
            try:
                cur = con.execute("DELETE FROM demo_usage")
                deleted["demo_usage"] = cur.rowcount if hasattr(cur, 'rowcount') else -1
            except Exception as e:
                logger.warning(f"demo_usage delete error: {e}")
            
            # Șterge vizite (trafic)
            try:
                cur = con.execute("DELETE FROM visits")
                deleted["visits"] = cur.rowcount if hasattr(cur, 'rowcount') else -1
            except Exception as e:
                logger.warning(f"visits delete error: {e}")
            
            con.commit()
        
        # Clear in-memory caches
        global DEMO_USAGE_CACHE
        DEMO_USAGE_CACHE.clear()
        
        log_audit("DAY_ZERO_RESET", {"deleted": deleted})
        
        return jsonify({
            "ok": True, 
            "message": "ZIUA 0 - Reset complet! Toți vizitatorii vor vedea intro-ul.",
            "deleted": deleted
        })
    except Exception as e:
        logger.error(f"Day Zero reset error: {e}")
        return jsonify({"error": str(e)}), 500

# ============================================
# VOICE CREDITS INTEGRATION (Deepgram Aura)
# ============================================
try:
    from voice_credits import register_credits_routes, get_credits_manager
    register_credits_routes(app)
    logger.info("✅ Voice Credits routes registered")
except ImportError as e:
    logger.warning(f"⚠️ Voice Credits module not available: {e}")

init_db()

if __name__ == "__main__":

    app.run(host="0.0.0.0", port=PORT)
