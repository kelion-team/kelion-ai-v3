// KELION Messages Panel - Chat History Viewer
// Displays chat history and conversation analytics

window.loadMessages = async function () {
    const dashView = document.getElementById('k1DashView');
    if (!dashView) return;

    dashView.innerHTML = `
    <div class="k1-messages-panel">
      <div class="k1-admin-header">
        <h3>💬 CONVERSATION HISTORY</h3>
        <div class="k1-admin-controls">
          <input type="text" id="msgUserFilter" class="k1-input" placeholder="Filter by User ID...">
          <select id="msgLimit" class="k1-select">
            <option value="20">Last 20</option>
            <option value="50" selected>Last 50</option>
            <option value="100">Last 100</option>
          </select>
          <button class="k1-btn-refresh" onclick="loadMessages()">⟳ Refresh</button>
        </div>
      </div>
      <div id="messagesContent" class="k1-messages-content">
        <div class="k1-loading">
          <div class="k1-spinner"></div>
          <span>Loading conversations...</span>
        </div>
      </div>
    </div>
  `;

    const adminToken = localStorage.getItem('k1_admin_token');
    if (!adminToken) {
        const token = prompt('Enter Admin Token:');
        if (!token) {
            dashView.innerHTML = '<div class="k1-error">Admin token required</div>';
            return;
        }
        localStorage.setItem('k1_admin_token', token);
    }

    try {
        const userId = document.getElementById('msgUserFilter')?.value?.trim() || 'anon';
        const limit = document.getElementById('msgLimit')?.value || 50;

        const res = await fetch(`/admin/messages?user_id=${encodeURIComponent(userId)}&limit=${limit}`, {
            headers: { 'X-Admin-Token': localStorage.getItem('k1_admin_token') }
        });

        if (!res.ok) throw new Error(`Unauthorized (${res.status})`);

        const data = await res.json();
        const content = document.getElementById('messagesContent');

        if (!data.items || data.items.length === 0) {
            content.innerHTML = `
        <div class="k1-empty">
          <p>No messages found for user: <strong>${data.user_id}</strong></p>
          <small>Try a different user ID or check audit logs for active users</small>
        </div>
      `;
            return;
        }

        // Group by session
        const sessions = {};
        data.items.forEach(msg => {
            const sid = msg.session_id || 'unknown';
            if (!sessions[sid]) sessions[sid] = [];
            sessions[sid].push(msg);
        });

        content.innerHTML = `
      <div class="k1-conversation-info">
        <span>User: <strong>${data.user_id}</strong></span>
        <span>Sessions: <strong>${Object.keys(sessions).length}</strong></span>
        <span>Messages: <strong>${data.items.length}</strong></span>
      </div>
      
      <div class="k1-conversations-list">
        ${Object.entries(sessions).map(([sessionId, messages]) => `
          <div class="k1-conversation-block">
            <div class="k1-session-header">
              <span class="k1-session-id">📁 Session: ${sessionId.slice(0, 8)}...</span>
              <span class="k1-session-count">${messages.length} messages</span>
            </div>
            <div class="k1-messages-thread">
              ${messages.reverse().map(msg => `
                <div class="k1-thread-msg ${msg.role}">
                  <div class="k1-msg-avatar">${msg.role === 'user' ? '👤' : '🤖'}</div>
                  <div class="k1-msg-body">
                    <div class="k1-msg-text">${escapeHtml(msg.content || '')}</div>
                    <div class="k1-msg-meta">
                      <span>${formatMsgTime(msg.created_at)}</span>
                      ${msg.meta?.emotion ? `<span class="k1-emotion">${getEmotionIcon(msg.meta.emotion)} ${msg.meta.emotion}</span>` : ''}
                      ${msg.meta?.sources?.length ? `<span class="k1-sources-count">📚 ${msg.meta.sources.length} sources</span>` : ''}
                    </div>
                  </div>
                </div>
              `).join('')}
            </div>
          </div>
        `).join('')}
      </div>
    `;
    } catch (e) {
        document.getElementById('messagesContent').innerHTML = `
      <div class="k1-error">
        <p>Failed to load messages</p>
        <small>${e.message}</small>
        <button class="k1-btn-retry" onclick="localStorage.removeItem('k1_admin_token'); loadMessages();">
          Retry with new token
        </button>
      </div>
    `;
    }
};

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatMsgTime(ts) {
    if (!ts) return '--';
    const d = new Date(ts);
    return d.toLocaleString('en-US', {
        month: 'short',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function getEmotionIcon(emotion) {
    const icons = {
        'happy': '😊',
        'calm': '😌',
        'empathetic': '🤗',
        'curious': '🤔',
        'default': '🙂'
    };
    return icons[emotion] || icons.default;
}

// Bind filter input
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => {
        const filter = document.getElementById('msgUserFilter');
        if (filter) {
            filter.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') loadMessages();
            });
        }
    }, 1000);
});

// Make globally available
if (typeof window.app === 'undefined') window.app = {};
window.app.loadMessages = window.loadMessages;
