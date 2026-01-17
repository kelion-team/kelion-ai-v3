// KELION Admin Panel - Audit Log Viewer
// Loads and displays audit logs from /admin/audit

window.loadAdmin = async function () {
    const dashView = document.getElementById('k1DashView');
    if (!dashView) return;

    dashView.innerHTML = `
    <div class="k1-admin-panel">
      <div class="k1-admin-header">
        <h3>📊 SYSTEM AUDIT LOGS</h3>
        <div class="k1-admin-controls">
          <select id="auditLimit" class="k1-select">
            <option value="25">Last 25</option>
            <option value="50">Last 50</option>
            <option value="100" selected>Last 100</option>
            <option value="500">Last 500</option>
          </select>
          <button class="k1-btn-refresh" onclick="loadAdmin()">⟳ Refresh</button>
        </div>
      </div>
      <div id="auditContent" class="k1-audit-content">
        <div class="k1-loading">
          <div class="k1-spinner"></div>
          <span>Loading audit logs...</span>
        </div>
      </div>
    </div>
  `;

    const adminToken = localStorage.getItem('k1_admin_token') || prompt('Enter Admin Token:');
    if (!adminToken) {
        dashView.innerHTML = '<div class="k1-error">Admin token required</div>';
        return;
    }
    localStorage.setItem('k1_admin_token', adminToken);

    try {
        const limit = document.getElementById('auditLimit')?.value || 100;
        const res = await fetch(`/admin/audit?limit=${limit}`, {
            headers: { 'X-Admin-Token': adminToken }
        });

        if (!res.ok) {
            throw new Error(`Unauthorized (${res.status})`);
        }

        const data = await res.json();
        const content = document.getElementById('auditContent');

        if (!data.items || data.items.length === 0) {
            content.innerHTML = '<div class="k1-empty">No audit logs found</div>';
            return;
        }

        content.innerHTML = `
      <div class="k1-audit-table">
        <div class="k1-audit-header-row">
          <span class="k1-col-time">Timestamp</span>
          <span class="k1-col-action">Action</span>
          <span class="k1-col-user">User</span>
          <span class="k1-col-detail">Details</span>
        </div>
        ${data.items.map(item => `
          <div class="k1-audit-row">
            <span class="k1-col-time">${formatTime(item.ts)}</span>
            <span class="k1-col-action k1-action-${getActionType(item.action)}">${item.action}</span>
            <span class="k1-col-user">${item.user_id || 'system'}</span>
            <span class="k1-col-detail">${formatDetail(item.detail)}</span>
          </div>
        `).join('')}
      </div>
    `;
    } catch (e) {
        document.getElementById('auditContent').innerHTML = `
      <div class="k1-error">
        <p>Failed to load audit logs</p>
        <small>${e.message}</small>
        <button class="k1-btn-retry" onclick="localStorage.removeItem('k1_admin_token'); loadAdmin();">
          Retry with new token
        </button>
      </div>
    `;
    }
};

function formatTime(ts) {
    if (!ts) return '--';
    const d = new Date(ts);
    return d.toLocaleString('en-US', {
        month: 'short',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
}

function getActionType(action) {
    if (!action) return 'default';
    if (action.includes('error')) return 'error';
    if (action.includes('login') || action.includes('subscribe')) return 'success';
    if (action.includes('input') || action.includes('output')) return 'chat';
    return 'default';
}

function formatDetail(detail) {
    if (!detail) return '-';
    if (typeof detail === 'string') return detail.slice(0, 80);

    // Extract key info
    let parts = [];
    if (detail.text) parts.push(`"${detail.text.slice(0, 40)}..."`);
    if (detail.error) parts.push(`⚠️ ${detail.error.slice(0, 50)}`);
    if (detail.tier) parts.push(`Tier: ${detail.tier}`);
    if (detail.email) parts.push(`Email: ${detail.email}`);
    if (detail.rating) parts.push(`Rating: ${'⭐'.repeat(detail.rating)}`);

    return parts.length ? parts.join(' | ') : JSON.stringify(detail).slice(0, 60);
}

// Make globally available
if (typeof window.app === 'undefined') window.app = {};
window.app.loadAdmin = window.loadAdmin;
