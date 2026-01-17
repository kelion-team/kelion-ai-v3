import { HologramUnit } from "./holograma_k.js";

// KELION AI - MAIN APPLICATION - Fixed by Antigravity

// Language Management
let currentLanguage = 'en';

const femaleVoices = [
    'ioana', 'microsoft ioana', 'google română', 'română', 'florina',
    'samantha', 'victoria', 'zira', 'hazel', 'karen', 'veena', 'tessa', 'susan', 'catherine', 'moira',
    'anna', 'petra', 'hedda', 'katja',
    'amélie', 'amelie', 'virginie', 'audrey',
    'monica', 'paulina', 'sabina', 'helena',
    'alice', 'elsa', 'federica',
    'luciana', 'joana', 'raquel',
    'milena', 'irina', 'ekaterina',
    'ting-ting', 'lili', 'kyoko', 'ayumi', 'huihui', 'yuna', 'xiaoxiao',
    'female', 'woman', 'girl', 'femeie'
];

const VOICE_PREFS = {
    // MALE ONLY - No female voices
    'en': ['Microsoft David Desktop', 'Microsoft David', 'Google UK English Male', 'Daniel', 'Alex', 'Fred'],
    'ro': ['Microsoft Andrei', 'Andrei'],  // NO Ioana
    'de': ['Microsoft Stefan Desktop', 'Microsoft Stefan', 'Markus'],  // NO Anna
    'fr': ['Microsoft Paul Desktop', 'Microsoft Paul', 'Thomas'],  // NO Amélie
    'es': ['Microsoft Pablo Desktop', 'Microsoft Pablo', 'Jorge', 'Diego'],  // NO Monica
    'it': ['Microsoft Cosimo Desktop', 'Microsoft Cosimo', 'Luca'],  // NO Alice
    'pt': ['Microsoft Daniel', 'Cristiano'],  // NO Luciana/Joana
    'ru': ['Microsoft Pavel Desktop', 'Microsoft Pavel', 'Yuri'],  // NO Milena
    'zh': ['Kangkang', 'Sinji'],  // NO Huihui/Ting-Ting
    'ja': ['Otoya', 'Hattori'],  // NO Ayumi/Kyoko
    'default': ['Microsoft David Desktop', 'Microsoft David', 'Daniel', 'Fred']
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
}

// Live Users Counter
function updateLiveUsersCount() {
    fetch('/api/live-users')
        .then(res => res.json())
        .then(data => {
            const el = document.getElementById('liveUsersCount');
            if (el && data.count !== undefined) {
                el.textContent = data.count;
            }
        })
        .catch(() => {});
}
setInterval(updateLiveUsersCount, 10000);
setTimeout(updateLiveUsersCount, 1000);
