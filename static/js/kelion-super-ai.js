/**
 * KELION SUPER AI - Frontend Integration
 * ========================================
 * SDK JavaScript pentru comunicarea cu Super AI Backend.
 */

class KelionSuperAI {
    constructor(options = {}) {
        this.baseUrl = options.baseUrl || '/api/super';
        this.adminToken = options.adminToken || null;
        this.onStatusChange = options.onStatusChange || null;
        this.onMessage = options.onMessage || null;
        this.onError = options.onError || null;

        // Stare internă
        this.isGodMode = false;
        this.systemStatus = null;

        // Cache pentru voiceprint
        this._voiceprintVerified = false;
    }

    // ========================================================================
    // HELPERS
    // ========================================================================

    async _fetch(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const headers = {
            'Content-Type': 'application/json',
            ...(options.headers || {})
        };

        if (this.adminToken) {
            headers['X-Admin-Token'] = this.adminToken;
        }

        try {
            const response = await fetch(url, {
                ...options,
                headers
            });

            const data = await response.json();

            if (!response.ok) {
                if (response.status === 423) {
                    // System frozen
                    this._handleFrozen(data);
                }
                throw new Error(data.error || data.message || 'Request failed');
            }

            return data;
        } catch (error) {
            if (this.onError) {
                this.onError(error);
            }
            throw error;
        }
    }

    _handleFrozen(data) {
        if (this.onStatusChange) {
            this.onStatusChange({
                frozen: true,
                message: data.message
            });
        }
    }

    // ========================================================================
    // STATUS & SECURITY
    // ========================================================================

    /**
     * Obține starea completă a sistemului
     */
    async getStatus() {
        const status = await this._fetch('/status');
        this.systemStatus = status;

        if (this.onStatusChange) {
            this.onStatusChange(status);
        }

        return status;
    }

    /**
     * Pune sistemul în Freeze Total
     */
    async freeze(masterPassword) {
        return await this._fetch('/freeze', {
            method: 'POST',
            body: JSON.stringify({ password: masterPassword })
        });
    }

    /**
     * Reactivează sistemul din Freeze
     */
    async unfreeze(masterPassword) {
        const result = await this._fetch('/unfreeze', {
            method: 'POST',
            body: JSON.stringify({ password: masterPassword })
        });

        if (result.success) {
            await this.getStatus();
        }

        return result;
    }

    /**
     * Setează parola Master (ADMIN)
     */
    async setMasterPassword(password) {
        return await this._fetch('/admin/set-password', {
            method: 'POST',
            body: JSON.stringify({ password })
        });
    }

    // ========================================================================
    // CHAT (Core Intelligence)
    // ========================================================================

    /**
     * Trimite un mesaj către Kelion și primește răspuns
     */
    async chat(message, options = {}) {
        const includeContext = options.includeContext !== false;

        const result = await this._fetch('/chat', {
            method: 'POST',
            body: JSON.stringify({
                message,
                include_context: includeContext
            })
        });

        if (this.onMessage) {
            this.onMessage(result);
        }

        // Actualizează display-ul de credit
        if (result.usage) {
            this._updateCreditDisplay(result.usage.remaining_credit);
        }

        return result;
    }

    _updateCreditDisplay(remaining) {
        const creditEl = document.getElementById('kelion-credit');
        if (creditEl) {
            creditEl.textContent = `$${remaining.toFixed(2)}`;
            creditEl.classList.toggle('low', remaining < 0.50);
        }
    }

    // ========================================================================
    // MEMORY & KEYWORDS (Punct 27)
    // ========================================================================

    /**
     * Obține toate cuvintele cheie învățate
     */
    async getKeywords() {
        return await this._fetch('/memory/keywords');
    }

    /**
     * Adaugă un cuvânt cheie manual
     */
    async addKeyword(keyword, meaning) {
        return await this._fetch('/memory/keywords', {
            method: 'POST',
            body: JSON.stringify({ keyword, meaning })
        });
    }

    /**
     * Obține faptele cunoscute despre utilizator
     */
    async getFacts() {
        return await this._fetch('/memory/facts');
    }

    // ========================================================================
    // USAGE & COST
    // ========================================================================

    /**
     * Obține statisticile de utilizare
     */
    async getUsage() {
        return await this._fetch('/usage');
    }

    /**
     * Setează creditul disponibil (ADMIN)
     */
    async setCredit(amount) {
        return await this._fetch('/usage/set-credit', {
            method: 'POST',
            body: JSON.stringify({ amount })
        });
    }

    // ========================================================================
    // VOICEPRINT (Punct 10)
    // ========================================================================

    /**
     * Verifică amprenta vocală pentru auto-login
     * @param {Float32Array} audioFeatures - Features extrase din audio
     */
    async verifyVoiceprint(audioFeatures) {
        const result = await this._fetch('/voiceprint/verify', {
            method: 'POST',
            body: JSON.stringify({ features: audioFeatures })
        });

        if (result.verified) {
            this._voiceprintVerified = true;
            this.isGodMode = result.god_mode;

            // Trigger auto-login
            if (this.onStatusChange) {
                this.onStatusChange({
                    voiceVerified: true,
                    godMode: true
                });
            }
        }

        return result;
    }

    /**
     * Înregistrează amprenta vocală (ADMIN)
     */
    async registerVoiceprint(audioFeatures) {
        return await this._fetch('/voiceprint/register', {
            method: 'POST',
            body: JSON.stringify({ features: audioFeatures })
        });
    }

    // ========================================================================
    // SELF-EVOLUTION (Punct 2)
    // ========================================================================

    /**
     * Solicită analiza codului propriu (ADMIN)
     */
    async analyzeCode(filename = 'app.py') {
        return await this._fetch('/analyze-code', {
            method: 'POST',
            body: JSON.stringify({ file: filename })
        });
    }
}

// ============================================================================
// VOICE RECOGNITION HELPER
// ============================================================================

class VoiceRecognition {
    constructor(kelionAI) {
        this.kelion = kelionAI;
        this.recognition = null;
        this.isListening = false;

        this._initRecognition();
    }

    _initRecognition() {
        if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
            console.warn('Speech Recognition not supported');
            return;
        }

        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        this.recognition = new SpeechRecognition();
        this.recognition.continuous = false;
        this.recognition.interimResults = false;
        this.recognition.lang = 'en-US';

        this.recognition.onresult = async (event) => {
            const transcript = event.results[0][0].transcript;
            console.log('Voice input:', transcript);

            // Trimite către Kelion
            await this.kelion.chat(transcript);
        };

        this.recognition.onerror = (event) => {
            console.error('Speech recognition error:', event.error);
            this.isListening = false;
        };

        this.recognition.onend = () => {
            this.isListening = false;
        };
    }

    start() {
        if (!this.recognition) return;
        this.recognition.start();
        this.isListening = true;
    }

    stop() {
        if (!this.recognition) return;
        this.recognition.stop();
        this.isListening = false;
    }

    toggle() {
        if (this.isListening) {
            this.stop();
        } else {
            this.start();
        }
        return this.isListening;
    }
}

// ============================================================================
// GLOBAL EXPORTS
// ============================================================================

window.KelionSuperAI = KelionSuperAI;
window.VoiceRecognition = VoiceRecognition;

// Auto-init dacă există element #kelion-chat
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('kelion-chat') || document.getElementById('kelion-container')) {
        window.kelion = new KelionSuperAI({
            onStatusChange: (status) => {
                console.log('Kelion status:', status);
            },
            onMessage: (msg) => {
                console.log('Kelion response:', msg);
            },
            onError: (err) => {
                console.error('Kelion error:', err);
            }
        });

        window.kelionVoice = new VoiceRecognition(window.kelion);

        console.log('✅ Kelion Super AI SDK initialized');
    }
});
