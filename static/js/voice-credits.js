/**
 * KELION AI - Voice Credits Admin Panel
 * =====================================
 * Manages voice credits display, alerts, and purchase links.
 */

// Voice Credits Manager
window.VoiceCredits = {
    status: null,
    alertShown: false,

    // Initialize
    async init() {
        await this.refresh();
        // Check status every 30 seconds
        setInterval(() => this.refresh(), 30000);
    },

    // Refresh status from server
    async refresh() {
        try {
            const response = await fetch('/api/voice/credits/status');
            if (response.ok) {
                this.status = await response.json();
                this.updateUI();
                this.checkAlert();
            }
        } catch (error) {
            console.error('Failed to fetch voice credits:', error);
        }
    },

    // Update UI elements
    updateUI() {
        const container = document.getElementById('voiceCreditsPanel');
        if (!container || !this.status) return;

        const { remaining_credits, total_credits, percentage_used, is_low, is_empty, provider } = this.status;

        // Determine status color
        let statusColor = '#00ff88'; // Green
        let statusText = 'OK';
        if (is_empty) {
            statusColor = '#ff4444';
            statusText = 'EMPTY';
        } else if (is_low) {
            statusColor = '#ffaa00';
            statusText = 'LOW';
        }

        container.innerHTML = `
            <div class="k1-voice-credits">
                <div class="k1-vc-header">
                    <span class="k1-vc-icon">🔊</span>
                    <span class="k1-vc-title">Voice Credits</span>
                    <span class="k1-vc-provider">${provider.toUpperCase()}</span>
                </div>
                
                <div class="k1-vc-meter">
                    <div class="k1-vc-bar" style="width: ${100 - percentage_used}%; background: ${statusColor}"></div>
                </div>
                
                <div class="k1-vc-stats">
                    <div class="k1-vc-remaining">
                        <span class="k1-vc-number" style="color: ${statusColor}">${remaining_credits.toLocaleString()}</span>
                        <span class="k1-vc-label">caractere rămase</span>
                    </div>
                    <div class="k1-vc-status">
                        <span class="k1-vc-badge" style="background: ${statusColor}">${statusText}</span>
                    </div>
                </div>
                
                <div class="k1-vc-actions">
                    <button onclick="VoiceCredits.showAddCredits()" class="k1-btn-secondary">
                        ➕ Adaugă
                    </button>
                    <button onclick="VoiceCredits.openPurchase()" class="k1-btn-primary">
                        💳 Cumpără
                    </button>
                </div>
                
                ${is_low ? `
                <div class="k1-vc-alert">
                    ⚠️ Credite insuficiente! <a href="${this.status.purchase_url}" target="_blank">Achiziționează acum</a>
                </div>
                ` : ''}
            </div>
        `;
    },

    // Check if alert needed
    checkAlert() {
        if (this.status && this.status.is_low && !this.alertShown) {
            this.alertShown = true;
            this.showNotification(
                `⚠️ Mai ai doar ${this.status.remaining_credits} caractere voice! Achiziționează mai multe pentru a continua.`,
                'warning'
            );
        }
    },

    // Show notification
    showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `k1-notification k1-notification-${type}`;
        notification.innerHTML = `
            <div class="k1-notif-content">
                <span class="k1-notif-message">${message}</span>
                <button onclick="this.parentElement.parentElement.remove()" class="k1-notif-close">✕</button>
            </div>
            <div class="k1-notif-actions">
                <button onclick="VoiceCredits.openPurchase(); this.parentElement.parentElement.remove();" class="k1-btn-primary">
                    Cumpără Acum
                </button>
            </div>
        `;

        document.body.appendChild(notification);

        // Auto-remove after 30 seconds
        setTimeout(() => notification.remove(), 30000);
    },

    // Open purchase page
    openPurchase() {
        if (this.status && this.status.purchase_url) {
            window.open(this.status.purchase_url, '_blank');
        } else {
            // Default to Deepgram
            window.open('https://console.deepgram.com/billing', '_blank');
        }
    },

    // Show add credits dialog
    showAddCredits() {
        const amount = prompt('Câte caractere vrei să adaugi? (după achiziție)', '100000');
        if (amount && !isNaN(parseInt(amount))) {
            this.addCredits(parseInt(amount));
        }
    },

    // Add credits via API
    async addCredits(amount) {
        try {
            const response = await fetch('/api/voice/credits/add', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ amount })
            });

            if (response.ok) {
                this.alertShown = false;
                await this.refresh();
                this.showNotification(`✅ ${amount.toLocaleString()} caractere adăugate!`, 'success');
            } else {
                throw new Error('Failed to add credits');
            }
        } catch (error) {
            this.showNotification('❌ Eroare la adăugarea creditelor', 'error');
        }
    },

    // Set credits (for initial setup)
    async setCredits(amount) {
        try {
            const response = await fetch('/api/voice/credits/set', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ amount })
            });

            if (response.ok) {
                this.alertShown = false;
                await this.refresh();
            }
        } catch (error) {
            console.error('Failed to set credits:', error);
        }
    },

    // Get compact status for header display
    async getCompactStatus() {
        if (!this.status) await this.refresh();
        if (!this.status) return null;

        return {
            remaining: this.status.remaining_credits,
            isLow: this.status.is_low,
            isEmpty: this.status.is_empty
        };
    }
};

// Load Voice Credits in Admin Panel
window.loadVoiceCredits = async function () {
    const container = document.getElementById('k1DashView');
    if (!container) return;

    container.innerHTML = `
        <div class="k1-admin-section">
            <div class="k1-admin-header">
                <h2>🔊 Voice Credits Management</h2>
                <p>Gestionează creditele pentru sinteza vocală</p>
            </div>
            
            <div id="voiceCreditsPanel" class="k1-credits-panel">
                <div class="k1-loading">Se încarcă...</div>
            </div>
            
            <div class="k1-admin-section">
                <h3>📊 Istoric Utilizare</h3>
                <div id="voiceCreditsHistory" class="k1-history-panel">
                    <div class="k1-loading">Se încarcă...</div>
                </div>
            </div>
            
            <div class="k1-admin-section">
                <h3>⚙️ Setări</h3>
                <div class="k1-settings-form">
                    <div class="k1-form-group">
                        <label>Prag alertă (caractere)</label>
                        <input type="number" id="alertThreshold" value="500" min="0">
                        <button onclick="VoiceCredits.setThreshold()" class="k1-btn-secondary">Salvează</button>
                    </div>
                </div>
            </div>
            
            <div class="k1-admin-section">
                <h3>🔗 Link-uri Utile</h3>
                <div class="k1-links-grid">
                    <a href="https://console.deepgram.com/signup" target="_blank" class="k1-link-card">
                        <span class="k1-link-icon">📝</span>
                        <span class="k1-link-text">Deepgram Signup</span>
                        <span class="k1-link-badge">$200 FREE</span>
                    </a>
                    <a href="https://console.deepgram.com/billing" target="_blank" class="k1-link-card">
                        <span class="k1-link-icon">💳</span>
                        <span class="k1-link-text">Deepgram Billing</span>
                    </a>
                    <a href="https://elevenlabs.io/sign-up" target="_blank" class="k1-link-card">
                        <span class="k1-link-icon">🎙️</span>
                        <span class="k1-link-text">ElevenLabs Signup</span>
                        <span class="k1-link-badge">FREE TIER</span>
                    </a>
                    <a href="https://elevenlabs.io/subscription" target="_blank" class="k1-link-card">
                        <span class="k1-link-icon">💳</span>
                        <span class="k1-link-text">ElevenLabs Billing</span>
                    </a>
                </div>
            </div>
        </div>
    `;

    // Initialize voice credits panel
    await VoiceCredits.init();
    await loadVoiceCreditsHistory();
};

// Load usage history
async function loadVoiceCreditsHistory() {
    const container = document.getElementById('voiceCreditsHistory');
    if (!container) return;

    try {
        const response = await fetch('/api/voice/credits/history?limit=20');
        if (!response.ok) throw new Error('Failed to load history');

        const history = await response.json();

        if (history.length === 0) {
            container.innerHTML = '<p class="k1-empty">Nu există istoric de utilizare</p>';
            return;
        }

        container.innerHTML = `
            <table class="k1-table">
                <thead>
                    <tr>
                        <th>Data</th>
                        <th>Caractere</th>
                        <th>Descriere</th>
                    </tr>
                </thead>
                <tbody>
                    ${history.reverse().map(item => `
                        <tr>
                            <td>${new Date(item.timestamp).toLocaleString('ro-RO')}</td>
                            <td>${item.amount.toLocaleString()}</td>
                            <td>${item.description || '-'}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } catch (error) {
        container.innerHTML = '<p class="k1-error">Eroare la încărcarea istoricului</p>';
    }
}

// Set threshold
VoiceCredits.setThreshold = async function () {
    const input = document.getElementById('alertThreshold');
    const threshold = parseInt(input.value);

    if (isNaN(threshold) || threshold < 0) {
        alert('Valoare invalidă');
        return;
    }

    try {
        const response = await fetch('/api/voice/credits/threshold', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ threshold })
        });

        if (response.ok) {
            VoiceCredits.showNotification(`✅ Prag alertă setat la ${threshold} caractere`, 'success');
        }
    } catch (error) {
        VoiceCredits.showNotification('❌ Eroare la salvare', 'error');
    }
};

// Add to window.app
if (typeof window.app === 'undefined') window.app = {};
window.app.loadVoiceCredits = window.loadVoiceCredits;

console.log('Voice Credits Admin loaded');
