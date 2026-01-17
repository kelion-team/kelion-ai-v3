// KELION Admin - Broadcast Messages System
// Send alerts to all users or specific users with read confirmation

window.AdminBroadcast = {
  // Store pending broadcasts
  pendingMessages: [],

  // Load broadcast panel
  async loadPanel() {
    const dashView = document.getElementById('k1DashView');
    if (!dashView) return;

    dashView.innerHTML = `
        <div class="k1-broadcast-panel">
          <div class="k1-admin-header">
            <h3>📢 BROADCAST MESSAGES</h3>
            <button class="k1-btn-refresh" onclick="AdminBroadcast.loadPanel()">⟳ Refresh</button>
          </div>
          
          <!-- Compose Section -->
          <div class="k1-broadcast-compose">
            <h4>✉️ New Broadcast</h4>
            <div class="k1-form-group">
              <label>Recipients:</label>
              <select id="broadcastTarget" class="k1-select" onchange="AdminBroadcast.toggleUserSelect()">
                <option value="all">📣 All Users</option>
                <option value="specific">👤 Specific User</option>
              </select>
              <input type="text" id="broadcastUserId" class="k1-input" placeholder="Enter User ID..." style="display:none;">
            </div>
            <div class="k1-form-group">
              <label>Priority:</label>
              <select id="broadcastPriority" class="k1-select">
                <option value="info">ℹ️ Info</option>
                <option value="warning">⚠️ Warning</option>
                <option value="urgent">🚨 Urgent</option>
              </select>
            </div>
            <div class="k1-form-group">
              <label>Message:</label>
              <textarea id="broadcastMessage" class="k1-textarea" rows="3" placeholder="Enter your message..."></textarea>
            </div>
            <div class="k1-form-actions">
              <button class="k1-btn-primary" onclick="AdminBroadcast.send()">📤 Send Broadcast</button>
            </div>
          </div>
          
          <!-- Active Broadcasts -->
          <div class="k1-broadcast-list">
            <h4>📋 Active Broadcasts (Pending Read)</h4>
            <div id="activeBroadcasts" class="k1-broadcasts-container">
              <div class="k1-loading"><span>Loading...</span></div>
            </div>
          </div>
          
          <!-- History -->
          <div class="k1-broadcast-history">
            <h4>📜 Broadcast History</h4>
            <div id="broadcastHistory" class="k1-history-container">
              <div class="k1-loading"><span>Loading...</span></div>
            </div>
          </div>
        </div>
        `;

    await this.loadBroadcasts();
  },

  toggleUserSelect() {
    const target = document.getElementById('broadcastTarget').value;
    const userInput = document.getElementById('broadcastUserId');
    userInput.style.display = target === 'specific' ? 'block' : 'none';
  },

  async send() {
    const target = document.getElementById('broadcastTarget').value;
    const userId = document.getElementById('broadcastUserId')?.value?.trim();
    const priority = document.getElementById('broadcastPriority').value;
    const message = document.getElementById('broadcastMessage').value.trim();

    if (!message) {
      alert('Please enter a message');
      return;
    }

    if (target === 'specific' && !userId) {
      alert('Please enter a User ID');
      return;
    }

    const adminToken = localStorage.getItem('k1_admin_token');
    if (!adminToken) {
      alert('Admin token required');
      return;
    }

    try {
      const res = await fetch('/api/admin/broadcast', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Admin-Token': adminToken
        },
        body: JSON.stringify({
          target: target,
          user_id: target === 'specific' ? userId : null,
          priority: priority,
          message: message
        })
      });

      const data = await res.json();
      if (data.success) {
        alert('✅ Broadcast sent successfully!');
        document.getElementById('broadcastMessage').value = '';
        this.loadBroadcasts();
      } else {
        alert('❌ Error: ' + (data.error || 'Unknown error'));
      }
    } catch (e) {
      alert('❌ Failed to send: ' + e.message);
    }
  },

  async loadBroadcasts() {
    const adminToken = localStorage.getItem('k1_admin_token');
    if (!adminToken) return;

    try {
      const res = await fetch('/api/admin/broadcasts', {
        headers: { 'X-Admin-Token': adminToken }
      });
      const data = await res.json();

      // Active (unread)
      const activeEl = document.getElementById('activeBroadcasts');
      const active = (data.broadcasts || []).filter(b => !b.read_at);

      if (active.length === 0) {
        activeEl.innerHTML = '<div class="k1-empty">No pending broadcasts</div>';
      } else {
        activeEl.innerHTML = active.map(b => `
                    <div class="k1-broadcast-item ${b.priority}">
                        <div class="k1-broadcast-header">
                            <span class="k1-broadcast-priority">${this.getPriorityIcon(b.priority)}</span>
                            <span class="k1-broadcast-target">${b.target === 'all' ? '📣 All Users' : '👤 ' + b.user_id}</span>
                            <span class="k1-broadcast-time">${this.formatTime(b.created_at)}</span>
                        </div>
                        <div class="k1-broadcast-message">${this.escapeHtml(b.message)}</div>
                        <div class="k1-broadcast-status">
                            <span class="k1-status-pending">⏳ Awaiting confirmation</span>
                            <button class="k1-btn-small" onclick="AdminBroadcast.delete('${b.id}')">🗑️ Delete</button>
                        </div>
                    </div>
                `).join('');
      }

      // History (read)
      const historyEl = document.getElementById('broadcastHistory');
      const history = (data.broadcasts || []).filter(b => b.read_at);

      if (history.length === 0) {
        historyEl.innerHTML = '<div class="k1-empty">No broadcast history</div>';
      } else {
        historyEl.innerHTML = history.slice(0, 20).map(b => `
                    <div class="k1-broadcast-item read">
                        <div class="k1-broadcast-header">
                            <span class="k1-broadcast-priority">${this.getPriorityIcon(b.priority)}</span>
                            <span class="k1-broadcast-target">${b.target === 'all' ? '📣 All' : '👤 ' + b.user_id}</span>
                            <span class="k1-broadcast-time">${this.formatTime(b.created_at)}</span>
                        </div>
                        <div class="k1-broadcast-message">${this.escapeHtml(b.message)}</div>
                        <div class="k1-broadcast-status">
                            <span class="k1-status-read">✅ Read: ${this.formatTime(b.read_at)}</span>
                        </div>
                    </div>
                `).join('');
      }
    } catch (e) {
      console.error('Failed to load broadcasts:', e);
    }
  },

  async delete(id) {
    if (!confirm('Delete this broadcast?')) return;

    const adminToken = localStorage.getItem('k1_admin_token');
    try {
      await fetch(`/api/admin/broadcast/${id}`, {
        method: 'DELETE',
        headers: { 'X-Admin-Token': adminToken }
      });
      this.loadBroadcasts();
    } catch (e) {
      alert('Failed to delete: ' + e.message);
    }
  },

  getPriorityIcon(priority) {
    const icons = { info: 'ℹ️', warning: '⚠️', urgent: '🚨' };
    return icons[priority] || 'ℹ️';
  },

  formatTime(ts) {
    if (!ts) return '--';
    const d = new Date(ts);
    return d.toLocaleString('ro-RO', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
  },

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
};

// User-side: Check and display broadcasts
window.UserBroadcast = {
  async check() {
    const userId = localStorage.getItem('k1_user_id');
    if (!userId) return;

    try {
      const res = await fetch(`/api/user/broadcasts?user_id=${encodeURIComponent(userId)}`);
      const data = await res.json();

      if (data.broadcasts && data.broadcasts.length > 0) {
        this.display(data.broadcasts[0]);
      }
    } catch (e) {
      console.error('Failed to check broadcasts:', e);
    }
  },

  display(broadcast) {
    // Create overlay
    const overlay = document.createElement('div');
    overlay.id = 'broadcastOverlay';
    overlay.className = 'k1-broadcast-overlay';
    overlay.innerHTML = `
            <div class="k1-broadcast-modal ${broadcast.priority}">
                <div class="k1-broadcast-modal-icon">${this.getPriorityIcon(broadcast.priority)}</div>
                <div class="k1-broadcast-modal-title">
                    ${broadcast.priority === 'urgent' ? '🚨 URGENT MESSAGE' :
        broadcast.priority === 'warning' ? '⚠️ IMPORTANT NOTICE' : 'ℹ️ MESSAGE'}
                </div>
                <div class="k1-broadcast-modal-body">${broadcast.message}</div>
                <button class="k1-broadcast-confirm" onclick="UserBroadcast.confirm('${broadcast.id}')">
                    ✓ I have read this message
                </button>
            </div>
        `;

    // Prevent interaction until confirmed
    overlay.style.cssText = `
            position: fixed; top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.85); z-index: 99999;
            display: flex; align-items: center; justify-content: center;
        `;

    document.body.appendChild(overlay);
  },

  async confirm(id) {
    const userId = localStorage.getItem('k1_user_id');
    try {
      await fetch('/api/user/broadcast/confirm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ broadcast_id: id, user_id: userId })
      });
    } catch (e) {
      console.error('Failed to confirm:', e);
    }

    // Remove overlay
    const overlay = document.getElementById('broadcastOverlay');
    if (overlay) overlay.remove();

    // Check for more broadcasts
    setTimeout(() => this.check(), 1000);
  },

  getPriorityIcon(priority) {
    const icons = { info: 'ℹ️', warning: '⚠️', urgent: '🚨' };
    return icons[priority] || 'ℹ️';
  }
};

// Auto-check broadcasts on page load for users
document.addEventListener('DOMContentLoaded', () => {
  setTimeout(() => UserBroadcast.check(), 2000);
});

// Make globally available
window.loadBroadcast = () => AdminBroadcast.loadPanel();
if (typeof window.app === 'undefined') window.app = {};
window.app.loadBroadcast = window.loadBroadcast;
