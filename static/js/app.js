import { HologramUnit } from "./holograma_k.js";

// KELION AI - MAIN APPLICATION - Fixed by Antigravity

// Language Management
let currentLanguage = 'en';
const VOICE_PREFS = {
    'en': ['Microsoft David Desktop', 'Microsoft David', 'Google UK English Male', 'Daniel', 'Alex'],
    'ro': ['Microsoft Andrei', 'Andrei', 'Google română'],
    'de': ['Microsoft Stefan Desktop', 'Microsoft Stefan', 'Google Deutsch', 'Markus'],
    'fr': ['Microsoft Paul Desktop', 'Microsoft Paul', 'Thomas', 'Google français'],
    'es': ['Microsoft Pablo Desktop', 'Microsoft Pablo', 'Jorge', 'Diego', 'Google español'],
    'it': ['Microsoft Cosimo Desktop', 'Microsoft Cosimo', 'Luca', 'Google italiano'],
    'default': ['Microsoft David Desktop', 'Microsoft David', 'Daniel']
};

function getCurrentUserLanguage() {
    const user = (localStorage.getItem('k1_user') || '').toLowerCase();
    // Demo always defaults to English
    if (user === 'demo') return 'en';
    // Admin defaults to Romanian
    if (user === 'admin') {
        const adminLang = localStorage.getItem('k1_lang_admin');
        return adminLang || 'ro'; // Default Romanian for admin
    }
    // Subscribed users: get permanent language (persists after logout)
    const userId = localStorage.getItem('k1_user_id') || 'anon';
    return localStorage.getItem('k1_lang_' + userId) || 'en';
}

function setCurrentLanguage(code) {
    const user = (localStorage.getItem('k1_user') || '').toLowerCase();
    const langCode = (code || 'en').substring(0, 2).toLowerCase();
    currentLanguage = langCode;

    // Demo user: don't save language, always English
    if (user === 'demo') {
        currentLanguage = 'en';
        return;
    }

    // Admin user: save language preference
    if (user === 'admin') {
        localStorage.setItem('k1_lang_admin', langCode);
        console.log('🌍 Admin language set:', langCode);
        return;
    }

    // Subscribed users: save permanent language (persists after logout)
    const userId = localStorage.getItem('k1_user_id') || 'anon';
    localStorage.setItem('k1_lang_' + userId, langCode);
    console.log('🌍 Language set permanently:', langCode, 'for user:', userId);
}

// Reset demo language on logout
function resetDemoLanguage() {
    const user = (localStorage.getItem('k1_user') || '').toLowerCase();
    if (user === 'demo') {
        currentLanguage = 'en';
        // Update Contact button back to English
        const contactBtn = document.getElementById('k1ContactBtn');
        if (contactBtn) contactBtn.textContent = 'CONTACT';
    }
}

// Browser TTS
let speechSynthesis = window.speechSynthesis;

function speakWithBrowserTTS(text, onStart, onEnd) {
    if (!speechSynthesis) { if (onEnd) onEnd(); return; }
    speechSynthesis.cancel();
    const utt = new SpeechSynthesisUtterance(text);
    // Use saved voice settings or defaults
    utt.rate = window.k1VoiceSpeed || 0.95;
    utt.pitch = 1.0;
    utt.volume = window.k1VoiceVolume || 1.0;
    const voices = speechSynthesis.getVoices();
    const prefs = VOICE_PREFS[currentLanguage] || VOICE_PREFS['default'];
    let voice = null;
    for (const p of prefs) { voice = voices.find(v => v.name.includes(p)); if (voice) break; }
    if (!voice) voice = voices.find(v => v.lang.startsWith(currentLanguage)) || voices.find(v => v.lang.startsWith('en'));
    if (voice) utt.voice = voice;
    utt.onstart = () => { if (onStart) onStart(); };
    utt.onend = () => { if (onEnd) onEnd(); };
    utt.onerror = () => { if (onEnd) onEnd(); };
    speechSynthesis.speak(utt);
}

// DOM Helpers
const $ = (id) => document.getElementById(id);
const chatLog = $("chatLog");
const subtitleEl = $("k1Subtitle");
const chatInput = $("textInput");

// Audio element
let audioEl = $("tts");
if (!audioEl) { audioEl = document.createElement("audio"); audioEl.id = "tts"; audioEl.style.display = "none"; document.body.appendChild(audioEl); }

// User/Session IDs
const USER_ID = localStorage.getItem("k1_user_id") || (() => { const id = crypto.randomUUID(); localStorage.setItem("k1_user_id", id); return id; })();
const SESSION_ID = crypto.randomUUID();

// Status Bar
function initStatusBar() {
    const vEl = $("k1Version");
    const cEl = $("k1Clock");
    if (vEl) vEl.textContent = "v2.0.0 - Kelion AI";
    function tick() { const now = new Date(); if (cEl) cEl.textContent = String(now.getHours()).padStart(2, "0") + ":" + String(now.getMinutes()).padStart(2, "0"); }
    tick(); setInterval(tick, 30000);
}

// Chat & Typewriter
let typewriterTimeout;
let isKSpeaking = false; // Turn-based: K is speaking
let messageQueue = []; // Queue messages if K is speaking

function append(role, text) {
    if (role === 'bot') window.lastBotText = text;
    const div = document.createElement("div"); div.className = "msg " + role; div.textContent = text;
    if (chatLog) { chatLog.appendChild(div); chatLog.scrollTop = chatLog.scrollHeight; }

    // Show in subtitle area for both user and K (but not system)
    if (role === 'user' || role === 'bot') {
        runTypewriter(text, 0, role);
    }

    // Save all messages
    saveMessage(role, text);
}

function saveMessage(role, text) {
    const messages = JSON.parse(localStorage.getItem('k1_messages_' + (localStorage.getItem('k1_user_id') || 'anon')) || '[]');
    messages.push({ role, text, timestamp: Date.now() });
    // Keep last 100 messages
    if (messages.length > 100) messages.shift();
    localStorage.setItem('k1_messages_' + (localStorage.getItem('k1_user_id') || 'anon'), JSON.stringify(messages));
}

function runTypewriter(text, duration, role = 'bot') {
    if (!subtitleEl) return;
    subtitleEl.innerHTML = ''; clearTimeout(typewriterTimeout);

    // Create prefix label
    const prefix = document.createElement("span");
    prefix.className = "k1-subtitle-prefix";
    prefix.textContent = role === 'bot' ? 'K: ' : 'You: ';
    prefix.style.color = role === 'bot' ? '#d4af37' : '#00f3ff';
    prefix.style.fontWeight = '700';
    subtitleEl.appendChild(prefix);

    // Create text span with proper color
    const span = document.createElement("span");
    span.className = "k1-subtitle-text" + (role === 'user' ? ' user-msg' : '');
    subtitleEl.appendChild(span);

    let charDelay = duration > 0 ? (duration * 1000) / text.length : 50;
    charDelay = Math.max(20, Math.min(charDelay, 150));
    let i = 0;
    function type() {
        if (i < text.length) {
            span.textContent += text.charAt(i++);
            typewriterTimeout = setTimeout(type, charDelay);
        } else {
            setTimeout(() => subtitleEl.classList.add("k1-slide-out"), 3000);
        }
    }
    subtitleEl.classList.remove("k1-slide-out");
    type();
}

// Hologram
let holo = null;
let holoInitialized = false;

function initHologram() {
    if (holoInitialized) return;
    const mount = $('hologramMount');
    if (!mount) { console.error('Hologram mount not found!'); return; }
    mount.style.opacity = '1'; mount.style.visibility = 'visible';
    mount.offsetHeight;
    console.log('Initializing hologram...');
    holo = new HologramUnit("hologramMount");
    holo.init();
    holo.attachAudioElement(audioEl);
    audioEl.addEventListener("play", () => holo.setState("speak"));
    audioEl.addEventListener("ended", () => { holo.resetMouth(); holo.setState("idle"); });
    setTimeout(() => { if (holo) holo.resize(); }, 100);
    setTimeout(() => { if (holo) holo.resize(); }, 500);
    holoInitialized = true;
    console.log('Hologram initialized!');
}

// Chat API
let recording = false;
let mediaRecorder = null;
let chunks = [];

async function sendText(text) {
    const t = (text || "").trim();
    if (!t) return;

    // Turn-based: wait if K is speaking
    if (isKSpeaking) {
        messageQueue.push(t);
        append("system", "(Please wait, K is responding...)");
        return;
    }

    append("user", t);
    if (chatInput) chatInput.value = "";
    if (holo) { holo.setListening(false); holo.setState("processing"); }

    try {
        const res = await fetch("/api/super/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-API-Token": sessionStorage.getItem("k1_api_token") || "" },
            body: JSON.stringify({ message: t, userId: USER_ID, sessionId: SESSION_ID })
        });
        const data = await res.json();
        if (!res.ok) { append("bot", data.error || "Request failed."); if (holo) holo.setState("idle"); return; }

        append("bot", data.text || "");

        // K starts speaking - block user input
        isKSpeaking = true;

        if (data.useBrowserTTS && data.text) {
            // Start typewriter synced with speech
            runTypewriter(data.text);
            speakWithBrowserTTS(data.text,
                () => { if (holo) holo.setState("speak"); },
                () => {
                    if (holo) { holo.resetMouth(); holo.setState("idle"); }
                    // K finished speaking - allow user
                    isKSpeaking = false;
                    processMessageQueue();
                }
            );
        } else if (data.audioUrl) {
            runTypewriter(data.text);
            audioEl.src = data.audioUrl;
            audioEl.onended = () => { isKSpeaking = false; processMessageQueue(); };
            audioEl.play().catch(() => { isKSpeaking = false; });
        } else {
            // No speech, just text
            runTypewriter(data.text);
            isKSpeaking = false;
        }
    } catch (e) {
        console.error("Chat error:", e);
        append("bot", "An error occurred.");
        if (holo) holo.setState("idle");
        isKSpeaking = false;
    }
}

function processMessageQueue() {
    if (messageQueue.length > 0) {
        const nextMsg = messageQueue.shift();
        setTimeout(() => sendText(nextMsg), 500);
    }
}

async function startRecording() {
    if (recording) return;
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream); chunks = [];
        mediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data); };
        mediaRecorder.onstop = async () => {
            const blob = new Blob(chunks, { type: "audio/webm" });
            const formData = new FormData(); formData.append("audio", blob, "speech.webm");
            try {
                const res = await fetch("/api/stt", { method: "POST", body: formData });
                const data = await res.json();
                if (data.text) { if (data.language) setCurrentLanguage(data.language); sendText(data.text); }
            } catch (e) { append("bot", "Could not transcribe speech."); }
            stream.getTracks().forEach(t => t.stop());
        };
        mediaRecorder.start(); recording = true;
        const btn = $("btnMic"); if (btn) btn.classList.add("listening");
        if (holo) holo.setListening(true);
    } catch (e) { append("bot", "Microphone permission required."); }
}

function stopRecording() {
    if (!mediaRecorder || !recording) return;
    mediaRecorder.stop(); recording = false;
    const btn = $("btnMic"); if (btn) btn.classList.remove("listening");
}

// Login System
function isUserLoggedIn() { return sessionStorage.getItem('k1_authenticated') === 'true'; }

function showLoginPage() {
    const layer = $('k1LoginLayer');
    if (layer) layer.style.display = 'flex';
    initLoginHandlers();
}

function initLoginHandlers() {
    const step1Form = $('k1Step1Form');
    const step2Form = $('k1Step2Form');
    const registerForm = $('k1RegisterForm');
    const useDemoBtn = $('k1UseDemoBtn');
    const changeUserBtn = $('changeUserBtn');
    const backToStep1Btn = $('backToStep1');
    const togglePasswordBtn = $('togglePassword');

    const step1 = $('authStep1');
    const step2 = $('authStep2');
    const step3 = $('authStep3');

    let currentUsername = '';

    // Helper to switch steps
    function goToStep(stepNum) {
        [step1, step2, step3].forEach(s => s && s.classList.remove('active'));
        if (stepNum === 1 && step1) step1.classList.add('active');
        if (stepNum === 2 && step2) step2.classList.add('active');
        if (stepNum === 3 && step3) step3.classList.add('active');
        hideError();
    }

    // Step 1: Email/Username submission
    if (step1Form) {
        step1Form.onsubmit = async (e) => {
            e.preventDefault();
            const identifier = $('authIdentifier').value.trim();
            if (!identifier) return;
            currentUsername = identifier;

            // Check if user exists
            try {
                const res = await fetch('/api/check-user', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username: identifier })
                });
                const data = await res.json();

                if (data.exists) {
                    // Existing user - go to password step
                    $('displayUsername').textContent = identifier;
                    goToStep(2);
                    setTimeout(() => $('authPassword').focus(), 100);
                } else {
                    // New user - go to registration step
                    $('registerUsername').value = identifier;
                    goToStep(3);
                    setTimeout(() => $('registerEmail').focus(), 100);
                }
            } catch (e) {
                // Fallback: assume existing user
                $('displayUsername').textContent = identifier;
                goToStep(2);
            }
        };
    }

    // Step 2: Password submission (existing user)
    if (step2Form) {
        step2Form.onsubmit = async (e) => {
            e.preventDefault();
            const password = $('authPassword').value;
            if (!password) return;

            try {
                const res = await fetch('/api/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ userId: currentUsername, user: currentUsername, password })
                });
                const data = await res.json();

                if (res.ok || (currentUsername === 'demo' && password === 'demo')) {
                    sessionStorage.setItem('k1_authenticated', 'true');
                    sessionStorage.setItem('k1_api_token', data.token || 'temp');
                    localStorage.setItem('k1_user', currentUsername);
                    localStorage.setItem('k1_user_id', data.userId || currentUsername);
                    if (data.adminToken) localStorage.setItem('k1_admin_token', data.adminToken);
                    transitionToHologram();
                } else { showError(data.error || 'Invalid password'); }
            } catch (e) {
                if (currentUsername === 'demo' && password === 'demo') {
                    sessionStorage.setItem('k1_authenticated', 'true');
                    localStorage.setItem('k1_user', 'demo');
                    transitionToHologram();
                } else { showError('Connection error'); }
            }
        };
    }

    // Step 3: Registration
    if (registerForm) {
        registerForm.onsubmit = async (e) => {
            e.preventDefault();
            const username = $('registerUsername').value.trim() || currentUsername;
            const email = $('registerEmail').value.trim();
            const password = $('registerPassword').value;

            if (!password || password.length < 4) { showError('Password must be at least 4 characters'); return; }

            try {
                const res = await fetch('/api/register', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, password, email })
                });
                const data = await res.json();
                if (res.ok) {
                    sessionStorage.setItem('k1_authenticated', 'true');
                    localStorage.setItem('k1_user', username);
                    transitionToHologram();
                } else { showError(data.error || 'Registration failed'); }
            } catch (e) { showError('Connection error'); }
        };
    }

    // Demo button - quick access
    if (useDemoBtn) {
        useDemoBtn.onclick = () => {
            currentUsername = 'demo';
            sessionStorage.setItem('k1_authenticated', 'true');
            localStorage.setItem('k1_user', 'demo');
            transitionToHologram();
        };
    }

    // Change user button
    if (changeUserBtn) {
        changeUserBtn.onclick = () => {
            $('authPassword').value = '';
            goToStep(1);
            $('authIdentifier').focus();
        };
    }

    // Back button from registration
    if (backToStep1Btn) {
        backToStep1Btn.onclick = () => {
            goToStep(1);
            $('authIdentifier').focus();
        };
    }

    // Toggle password visibility
    if (togglePasswordBtn) {
        togglePasswordBtn.onclick = () => {
            const pwd = $('authPassword');
            if (pwd.type === 'password') {
                pwd.type = 'text';
                togglePasswordBtn.textContent = '🙈';
            } else {
                pwd.type = 'password';
                togglePasswordBtn.textContent = '👁';
            }
        };
    }

    // Create particles for login background
    createParticles($('loginParticles'));
}

function hideError() { const el = $('k1LoginError'); if (el) el.style.display = 'none'; }

function showError(msg) { const el = $('k1LoginError'); if (el) { el.textContent = msg; el.style.display = 'block'; } }

function transitionToHologram() {
    const loginLayer = $('k1LoginLayer');
    const holoMount = $('hologramMount');
    const mainUI = $('k1MainUI');
    if (loginLayer) loginLayer.classList.add('exiting');
    setTimeout(() => initHologram(), 200);
    setTimeout(() => { if (holoMount) { holoMount.style.opacity = '1'; holoMount.classList.add('revealing'); } if (holo) holo.resize(); }, 400);
    setTimeout(() => { if (mainUI) { mainUI.style.opacity = '1'; mainUI.style.pointerEvents = 'auto'; mainUI.classList.add('revealing'); } }, 600);
    setTimeout(() => { if (loginLayer) loginLayer.style.display = 'none'; if (holo) holo.resize(); initMainApp(); }, 1200);
}

// Intro Page
let narratorActive = false;

function initIntroPage() {
    const introLayer = $('k1IntroLayer');
    const enterBtn = $('k1EnterBtn');

    // Hide the enter button - auto-init instead
    if (enterBtn) enterBtn.style.display = 'none';

    if (!introLayer) { if (isUserLoggedIn()) initHologramAndApp(); else showLanguageSelection(); return; }
    createParticles($('introParticles'));

    // Auto-transition after narration completes
    const autoTransition = () => {
        if (introLayer.classList.contains('exiting')) return;
        sessionStorage.clear();
        if (speechSynthesis) speechSynthesis.cancel();
        narratorActive = false;
        introLayer.classList.add('exiting');
        setTimeout(() => {
            introLayer.style.display = 'none';
            if (isUserLoggedIn()) initHologramAndApp();
            else showLanguageSelection();
        }, 1000);
    };

    // Play narration then auto-transition when finished
    setTimeout(() => {
        if (!narratorActive) {
            playIntroNarration(autoTransition);
        }
    }, 1000);

    // Allow skip with Space key
    document.addEventListener('keydown', (e) => { if (e.code === 'Space') { e.preventDefault(); autoTransition(); } }, { once: true });
}

// ======================================
// LANGUAGE SELECTION - PAGE 2
// Hologram interaction for language detection
// ======================================
let selectedLanguageCode = 'en';
let languageHolo = null;

function showLanguageSelection() {
    // PAGE 2 REMOVED - Go directly to login
    showLoginPage();
}

// Language detection patterns - common words/phrases by language
const LANG_PATTERNS = {
    'ro': { words: ['bună', 'salut', 'da', 'nu', 'ce', 'și', 'cum', 'eu', 'tu', 'sunt', 'ești', 'alo', 'hei', 'noroc', 'mulțumesc', 'te', 'îmi', 'mă', 'vă'], flag: '🇷🇴', name: 'Română', greeting: 'Bună! Bine ai venit!', contact: 'CONTACT' },
    'en': { words: ['hello', 'hi', 'hey', 'good', 'yes', 'no', 'what', 'how', 'the', 'is', 'are', 'am', 'thanks', 'thank', 'you', 'i', 'my', 'me'], flag: '🇬🇧', name: 'English', greeting: 'Hello! Welcome!', contact: 'CONTACT' },
    'de': { words: ['hallo', 'guten', 'tag', 'morgen', 'ja', 'nein', 'was', 'wie', 'ich', 'bin', 'du', 'bist', 'danke', 'bitte', 'und', 'ist'], flag: '🇩🇪', name: 'Deutsch', greeting: 'Hallo! Willkommen!', contact: 'KONTAKT' },
    'fr': { words: ['bonjour', 'salut', 'bonsoir', 'oui', 'non', 'quoi', 'comment', 'je', 'suis', 'tu', 'es', 'merci', 'et', 'le', 'la', 'les'], flag: '🇫🇷', name: 'Français', greeting: 'Bonjour! Bienvenue!', contact: 'CONTACT' },
    'es': { words: ['hola', 'buenos', 'buenas', 'sí', 'no', 'qué', 'cómo', 'yo', 'soy', 'tú', 'eres', 'gracias', 'y', 'el', 'la', 'los'], flag: '🇪🇸', name: 'Español', greeting: '¡Hola! ¡Bienvenido!', contact: 'CONTACTO' },
    'it': { words: ['ciao', 'buongiorno', 'buonasera', 'sì', 'no', 'cosa', 'come', 'io', 'sono', 'tu', 'sei', 'grazie', 'e', 'il', 'la', 'i'], flag: '🇮🇹', name: 'Italiano', greeting: 'Ciao! Benvenuto!', contact: 'CONTATTO' }
};

function initLanguageInputHandlers() {
    const input = $('k1LangInput');
    const detectedEl = $('k1LangDetected');
    const flagEl = $('detectedFlag');
    const nameEl = $('detectedName');
    const responseEl = $('k1LangResponse');

    if (!input) return;

    // Detect language as user types
    input.oninput = () => {
        const text = input.value.toLowerCase().trim();
        if (text.length < 2) {
            if (detectedEl) detectedEl.style.opacity = '0';
            return;
        }

        // Detect language from text
        const detected = detectLanguageFromText(text);
        selectedLanguageCode = detected.code;
        setCurrentLanguage(detected.code);

        // Update UI
        if (flagEl) flagEl.textContent = detected.flag;
        if (nameEl) nameEl.textContent = detected.name;
        if (detectedEl) detectedEl.style.opacity = '1';

        // Update Contact button
        const contactBtn = $('k1ContactBtn');
        if (contactBtn) contactBtn.textContent = detected.contact;
    };

    // Enter to confirm
    input.onkeydown = (e) => {
        if (e.key === 'Enter' && input.value.trim()) {
            e.preventDefault();

            const detected = LANG_PATTERNS[selectedLanguageCode] || LANG_PATTERNS['en'];

            // Prepare confirmation message in detected language
            const confirmationMessages = {
                'ro': `Noua limbă este Română`,
                'en': `The new language is English`,
                'de': `Die neue Sprache ist Deutsch`,
                'fr': `La nouvelle langue est Français`,
                'es': `El nuevo idioma es Español`,
                'it': `La nuova lingua è Italiano`
            };
            const confirmMsg = confirmationMessages[selectedLanguageCode] || confirmationMessages['en'];

            // Show K's response in detected language
            if (responseEl) responseEl.textContent = confirmMsg;

            // SPEAK CONFIRMATION IN DETECTED LANGUAGE with native voice, then transition
            speakLanguageGreeting(confirmMsg, () => {
                setTimeout(() => transitionToLogin(), 1000);
            });
        }
    };
}

function detectLanguageFromText(text) {
    const words = text.split(/\s+/).map(w => w.replace(/[.,!?'"]/g, '').toLowerCase());
    let bestMatch = { code: 'en', score: 0, flag: '🇬🇧', name: 'English', contact: 'CONTACT' };

    for (const [code, data] of Object.entries(LANG_PATTERNS)) {
        let score = 0;
        for (const word of words) {
            if (data.words.includes(word)) score += 2;
            for (const pattern of data.words) {
                if (word.length > 3 && word.includes(pattern)) score += 1;
            }
        }
        // Check for special characters
        if (code === 'ro' && /[ăîâșț]/i.test(text)) score += 3;
        if (code === 'de' && /[äöüß]/i.test(text)) score += 3;
        if (code === 'fr' && /[éèêëàâùûç]/i.test(text)) score += 3;
        if (code === 'es' && /[ñáéíóú¿¡]/i.test(text)) score += 3;

        if (score > bestMatch.score) {
            bestMatch = { code, score, flag: data.flag, name: data.name, contact: data.contact };
        }
    }

    return bestMatch;
}

function speakLanguageGreeting(text, onEnd) {
    if (!speechSynthesis) { if (onEnd) onEnd(); return; }
    speechSynthesis.cancel();

    const utt = new SpeechSynthesisUtterance(text);
    utt.rate = 0.9;
    utt.pitch = 1.0;
    utt.volume = 1.0;

    const voices = speechSynthesis.getVoices();
    const prefs = VOICE_PREFS[selectedLanguageCode] || VOICE_PREFS['default'];
    let voice = null;
    for (const p of prefs) { voice = voices.find(v => v.name.includes(p)); if (voice) break; }
    if (!voice) voice = voices.find(v => v.lang.startsWith(selectedLanguageCode)) || voices.find(v => v.lang.startsWith('en'));
    if (voice) utt.voice = voice;

    utt.onend = () => { if (onEnd) onEnd(); };
    utt.onerror = () => { if (onEnd) onEnd(); };

    speechSynthesis.speak(utt);
}

function transitionToLogin() {
    const langLayer = $('k1LanguageLayer');
    if (langLayer) {
        langLayer.classList.add('exiting');
        setTimeout(() => {
            langLayer.style.display = 'none';
            showLoginPage();
        }, 800);
    } else {
        showLoginPage();
    }
}

function playIntroNarration(onComplete) {
    if (narratorActive || !speechSynthesis) { if (onComplete) onComplete(); return; }
    narratorActive = true;
    const lines = document.querySelectorAll('.k1-story-line');
    if (!lines.length) { narratorActive = false; if (onComplete) onComplete(); return; }
    lines.forEach(l => { l.style.opacity = '0'; l.style.animation = 'none'; });
    const voices = speechSynthesis.getVoices();
    const voice = voices.find(v => v.name.includes('David') || v.name.includes('Daniel')) || voices[0];
    let idx = 0;
    const speakNext = () => {
        if (idx >= lines.length || !narratorActive) {
            narratorActive = false;
            // Narration finished - call callback
            if (onComplete) setTimeout(onComplete, 500);
            return;
        }
        const line = lines[idx]; line.style.opacity = '1'; line.style.transform = 'translateY(0)'; line.style.transition = 'all 0.6s ease';
        const utt = new SpeechSynthesisUtterance(line.textContent.trim());
        utt.rate = 0.85; utt.pitch = 0.9; utt.volume = 1; if (voice) utt.voice = voice;
        utt.onend = () => { idx++; setTimeout(speakNext, 300); };
        utt.onerror = () => { idx++; speakNext(); };
        speechSynthesis.speak(utt);
    };
    if (voices.length === 0) { speechSynthesis.onvoiceschanged = () => { speechSynthesis.onvoiceschanged = null; speakNext(); }; } else { speakNext(); }
}

function createParticles(container) {
    if (!container) return;
    for (let i = 0; i < 25; i++) {
        const p = document.createElement('div'); p.className = 'k1-particle';
        p.style.left = Math.random() * 100 + '%';
        p.style.animationDelay = Math.random() * 8 + 's';
        p.style.animationDuration = (6 + Math.random() * 6) + 's';
        const size = 2 + Math.random() * 4; p.style.width = p.style.height = size + 'px';
        p.style.background = 'hsla(' + (180 + Math.random() * 60) + ', 100%, 70%, 0.7)';
        container.appendChild(p);
    }
}

function initHologramAndApp() {
    const holoMount = $('hologramMount');
    const mainUI = $('k1MainUI');
    initHologram();
    if (holoMount) { holoMount.style.opacity = '1'; holoMount.classList.add('revealing'); }
    if (mainUI) { mainUI.style.opacity = '1'; mainUI.style.pointerEvents = 'auto'; mainUI.classList.add('revealing'); }
    setTimeout(() => { if (holo) holo.resize(); initMainApp(); }, 500);
}

// Main App
function initMainApp() {
    initStatusBar();
    currentLanguage = getCurrentUserLanguage();
    const sendBtn = $("btnSend");
    const micBtn = $("btnMic");
    const textInput = $("textInput");
    const contactBtn = $("k1ContactBtn");
    const authBtn = $("k1AuthBtn");
    const dash = $("k1Dashboard");
    const closeDash = $("k1CloseDash");

    if (sendBtn) sendBtn.onclick = () => sendText(textInput ? textInput.value : "");
    if (textInput) {
        textInput.onkeydown = (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendText(textInput.value); } };
        textInput.onfocus = () => { if (holo) holo.setListening(true); };
    }
    if (micBtn) micBtn.onclick = () => { if (!recording) startRecording(); else stopRecording(); };
    if (contactBtn) contactBtn.onclick = () => { window.location.href = "mailto:contact@kelionai.app?subject=KELION%20AI%20Inquiry"; };
    if (closeDash) closeDash.onclick = () => { dash.style.display = 'none'; };

    if (authBtn) {
        const isAuth = sessionStorage.getItem('k1_authenticated') === 'true';
        const username = localStorage.getItem('k1_user') || '';
        if (isAuth) {
            authBtn.textContent = 'LOGOUT';
            authBtn.onclick = () => {
                const isDemo = (localStorage.getItem('k1_user') || '').toLowerCase() === 'demo';
                append('bot', 'Session ended. Goodbye!');
                speakWithBrowserTTS('Goodbye!', null, () => {
                    sessionStorage.clear();
                    localStorage.removeItem('k1_admin_token');
                    // Reset to English on demo logout
                    if (isDemo) currentLanguage = 'en';
                    location.reload();
                });
            };
            if (username.toLowerCase() === 'admin' && !$('k1MenuBtn')) {
                const menuBtn = document.createElement('button'); menuBtn.id = 'k1MenuBtn'; menuBtn.className = 'k1-menu-btn'; menuBtn.textContent = 'ADMIN'; menuBtn.style.marginRight = '8px';
                menuBtn.onclick = () => { if (dash) dash.style.display = 'flex'; };
                authBtn.parentNode.insertBefore(menuBtn, authBtn);
            }
        } else { authBtn.textContent = 'LOGIN'; authBtn.onclick = () => location.reload(); }
    }

    setTimeout(() => {
        const user = localStorage.getItem('k1_user') || 'user';
        const msg = user === 'demo' || user === 'user' ? "Hello! I am K, your neural assistant. How can I help you?" : "Welcome back, " + user + "! I am K. How can I assist you today?";
        append("bot", msg);
        speakWithBrowserTTS(msg, () => { if (holo) holo.setState("speak"); }, () => { if (holo) { holo.resetMouth(); holo.setState("idle"); } });
    }, 800);

    // Initialize Settings Modal
    initSettingsModal();
}

// ======================================
// SETTINGS MODAL - Language & Voice Settings
// ======================================
const LANGUAGE_NAMES = {
    'ro': 'Română', 'en': 'English', 'de': 'Deutsch', 'fr': 'Français',
    'es': 'Español', 'it': 'Italiano', 'pt': 'Português',
    'ru': 'Русский', 'zh': '中文', 'ja': '日本語'
};

function initSettingsModal() {
    const settingsBtn = $('k1SettingsBtn');
    const settingsModal = $('k1SettingsModal');
    const closeSettings = $('k1CloseSettings');
    const saveSettings = $('k1SaveSettings');
    const languageGrid = $('languageGrid');
    const currentLangDisplay = $('currentLangDisplay');
    const volumeSlider = $('voiceVolume');
    const speedSlider = $('voiceSpeed');
    const volumeValue = $('volumeValue');
    const speedValue = $('speedValue');

    if (!settingsBtn || !settingsModal) return;

    // Load saved settings
    const savedVolume = localStorage.getItem('k1_voice_volume') || 100;
    const savedSpeed = localStorage.getItem('k1_voice_speed') || 95;
    if (volumeSlider) volumeSlider.value = savedVolume;
    if (speedSlider) speedSlider.value = savedSpeed;
    if (volumeValue) volumeValue.textContent = savedVolume + '%';
    if (speedValue) speedValue.textContent = (savedSpeed / 100).toFixed(2) + 'x';

    // Update current language display
    const updateLangDisplay = () => {
        const lang = getCurrentUserLanguage();
        if (currentLangDisplay) currentLangDisplay.textContent = LANGUAGE_NAMES[lang] || 'English';
        // Highlight active language button
        if (languageGrid) {
            languageGrid.querySelectorAll('.k1-lang-btn').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.lang === lang);
            });
        }
    };
    updateLangDisplay();

    // Open modal
    settingsBtn.onclick = () => {
        settingsModal.style.display = 'flex';
        updateLangDisplay();
    };

    // Close modal
    if (closeSettings) closeSettings.onclick = () => { settingsModal.style.display = 'none'; };
    settingsModal.onclick = (e) => { if (e.target === settingsModal) settingsModal.style.display = 'none'; };

    // Language buttons
    if (languageGrid) {
        languageGrid.querySelectorAll('.k1-lang-btn').forEach(btn => {
            btn.onclick = () => {
                const lang = btn.dataset.lang;
                setCurrentLanguage(lang);
                updateLangDisplay();

                // Speak confirmation in new language
                const confirmMsgs = {
                    'ro': 'Limba a fost schimbată în Română',
                    'en': 'Language changed to English',
                    'de': 'Sprache auf Deutsch geändert',
                    'fr': 'Langue changée en Français',
                    'es': 'Idioma cambiado a Español',
                    'it': 'Lingua cambiata in Italiano',
                    'pt': 'Idioma alterado para Português',
                    'ru': 'Язык изменён на Русский',
                    'zh': '语言已更改为中文',
                    'ja': '言語が日本語に変更されました'
                };
                speakWithBrowserTTS(confirmMsgs[lang] || 'Language changed');
            };
        });
    }

    // Volume slider
    if (volumeSlider) {
        volumeSlider.oninput = () => {
            const val = volumeSlider.value;
            if (volumeValue) volumeValue.textContent = val + '%';
        };
    }

    // Speed slider
    if (speedSlider) {
        speedSlider.oninput = () => {
            const val = speedSlider.value;
            if (speedValue) speedValue.textContent = (val / 100).toFixed(2) + 'x';
        };
    }

    // Save settings
    if (saveSettings) {
        saveSettings.onclick = () => {
            localStorage.setItem('k1_voice_volume', volumeSlider ? volumeSlider.value : 100);
            localStorage.setItem('k1_voice_speed', speedSlider ? speedSlider.value : 95);
            settingsModal.style.display = 'none';

            // Apply voice settings globally
            window.k1VoiceVolume = (volumeSlider ? volumeSlider.value : 100) / 100;
            window.k1VoiceSpeed = (speedSlider ? speedSlider.value : 95) / 100;

            speakWithBrowserTTS('Setările au fost salvate! / Settings saved!');
        };
    }
}

// Apply saved voice settings to TTS
window.k1VoiceVolume = (localStorage.getItem('k1_voice_volume') || 100) / 100;
window.k1VoiceSpeed = (localStorage.getItem('k1_voice_speed') || 95) / 100;

// Bootstrap - FORCE LOGOUT on app start to always show intro/login
document.addEventListener("DOMContentLoaded", () => {
    // FORȚEAZĂ DELOGARE la fiecare pornire a aplicației
    localStorage.removeItem('k1_user');
    localStorage.removeItem('k1_is_admin');
    localStorage.removeItem('k1_admin_token');
    sessionStorage.clear();

    // Invalidează sesiunea pe server (async, nu așteptăm)
    fetch('/api/logout', { method: 'POST', credentials: 'include' }).catch(() => { });
    console.log('🔒 Session cleared on startup - user must re-login');

    document.body.style.overflow = 'hidden';
    initIntroPage();
});

// ======================================
// AUTOSAVE SYSTEM - Saves state every 30 seconds
// ======================================
let autosaveInterval = null;

function initAutosave() {
    if (autosaveInterval) return;
    autosaveInterval = setInterval(() => {
        const state = {
            timestamp: new Date().toISOString(),
            user: localStorage.getItem('k1_user'),
            userId: localStorage.getItem('k1_user_id'),
            language: currentLanguage,
            authenticated: sessionStorage.getItem('k1_authenticated') === 'true'
        };
        localStorage.setItem('k1_autosave', JSON.stringify(state));
        console.log('✅ Autosave completed:', state.timestamp);
    }, 30000); // Every 30 seconds
}

// Start autosave when app loads
setTimeout(initAutosave, 5000);

// Reset on forced exit (X button, etc.) - restart from intro
window.addEventListener('beforeunload', () => {
    // Clear session to force restart from intro
    sessionStorage.removeItem('k1_authenticated');
    sessionStorage.removeItem('k1_api_token');
    localStorage.removeItem('k1_admin_token');

    // If demo user, reset language to English
    const user = (localStorage.getItem('k1_user') || '').toLowerCase();
    if (user === 'demo') {
        // Demo user language is never saved, so nothing to remove
    }
    // User languages are preserved in localStorage permanently
});

// Global app functions - merge with existing window.app (set by admin.js, messages.js, etc.)
// Use existing functions if available, otherwise fallback to console.log
const existingApp = window.app || {};
window.app = {
    loadAdmin: existingApp.loadAdmin || window.loadAdmin || (() => console.log('Loading Audit...')),
    loadUsers: existingApp.loadUsers || window.loadUsers || (() => console.log('Loading Users...')),
    loadTraffic: existingApp.loadTraffic || window.loadTraffic || (() => console.log('Loading Traffic...')),
    loadBroadcast: existingApp.loadBroadcast || window.loadBroadcast || (() => console.log('Loading Broadcast...')),
    loadMessages: existingApp.loadMessages || window.loadMessages || (() => console.log('Loading Messages...')),
    loadSubscriptions: existingApp.loadSubscriptions || window.loadSubscriptions || (() => console.log('Loading Subscriptions...')),
    loadGDPR: existingApp.loadGDPR || window.loadGDPR || (() => console.log('Loading GDPR...')),
    loadSuperAI: existingApp.loadSuperAI || window.loadSuperAI || ((feature) => console.log('Loading Super AI:', feature)),
    loadVoiceCredits: existingApp.loadVoiceCredits || window.loadVoiceCredits || (() => console.log('Loading Voice Credits...')),

    // DAY ZERO RESET - Admin function to reset all visitor data
    dayZero: async () => {
        if (!confirm('⚠️ ATENȚIE: Această acțiune va șterge TOȚI vizitatorii!\n\nToți utilizatorii vor vedea intro-ul ca vizitatori noi.\n\nEști sigur că vrei să continui?')) {
            return;
        }

        const adminToken = localStorage.getItem('k1_admin_token');
        if (!adminToken) {
            alert('❌ Admin token required!');
            return;
        }

        try {
            const res = await fetch('/api/admin/day-zero', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Admin-Token': adminToken
                }
            });

            const data = await res.json();

            if (res.ok && data.ok) {
                alert(`✅ ZIUA 0 - Reset complet!\n\nȘterse:\n- Vizitatori: ${data.deleted?.visitors || 0}\n- Demo usage: ${data.deleted?.demo_usage || 0}\n- Vizite: ${data.deleted?.visits || 0}\n\nToți utilizatorii vor vedea intro-ul.`);

                // Clear local session data too
                localStorage.removeItem('k1_user');
                localStorage.removeItem('k1_is_admin');
                sessionStorage.clear();

                // Reload to show intro
                location.reload();
            } else {
                alert(`❌ Eroare: ${data.error || 'Unknown error'}`);
            }
        } catch (e) {
            console.error('Day Zero error:', e);
            alert('❌ Eroare de conexiune. Verifică consola.');
        }
    }
};
