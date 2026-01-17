// KELION Admin - Traffic Analytics Module
// Shows user traffic statistics and analytics

window.loadTraffic = async function () {
    const dashView = document.getElementById('k1DashView');
    if (!dashView) return;

    dashView.innerHTML = `
    <div class="k1-admin-panel">
      <div class="k1-admin-header">
        <h3>📈 TRAFFIC ANALYTICS</h3>
        <button class="k1-btn-refresh" onclick="loadTraffic()">⟳ Refresh</button>
      </div>
      <div id="trafficContent" class="k1-traffic-content">
        <div class="k1-loading">
          <div class="k1-spinner"></div>
          <span>Loading analytics...</span>
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
        // Fetch user stats
        const usersRes = await fetch('/admin/users', {
            headers: { 'X-Admin-Token': adminToken }
        });

        const auditRes = await fetch('/admin/audit?limit=500', {
            headers: { 'X-Admin-Token': adminToken }
        });

        if (!usersRes.ok) throw new Error('Failed to load users');

        const usersData = await usersRes.json();
        const auditData = auditRes.ok ? await auditRes.json() : { items: [] };

        const users = usersData.users || [];
        const audits = auditData.items || [];

        // Calculate stats
        const totalUsers = users.length;
        const today = new Date().toISOString().split('T')[0];
        const activeToday = audits.filter(a => a.ts && a.ts.startsWith(today)).length;
        const logins = audits.filter(a => a.action && a.action.includes('login')).length;
        const messages = audits.filter(a => a.action && (a.action.includes('input') || a.action.includes('output'))).length;

        // Calculate users by day (last 7 days)
        const last7Days = [];
        for (let i = 6; i >= 0; i--) {
            const d = new Date();
            d.setDate(d.getDate() - i);
            const dateStr = d.toISOString().split('T')[0];
            const dayName = d.toLocaleDateString('en-US', { weekday: 'short' });
            const count = audits.filter(a => a.ts && a.ts.startsWith(dateStr)).length;
            last7Days.push({ day: dayName, count });
        }

        const maxCount = Math.max(...last7Days.map(d => d.count), 1);

        document.getElementById('trafficContent').innerHTML = `
        <div class="k1-stats-grid">
          <div class="k1-stat-card">
            <div class="k1-stat-value">${totalUsers}</div>
            <div class="k1-stat-label">Total Users</div>
          </div>
          <div class="k1-stat-card">
            <div class="k1-stat-value">${activeToday}</div>
            <div class="k1-stat-label">Events Today</div>
          </div>
          <div class="k1-stat-card">
            <div class="k1-stat-value">${logins}</div>
            <div class="k1-stat-label">Total Logins</div>
          </div>
          <div class="k1-stat-card">
            <div class="k1-stat-value">${messages}</div>
            <div class="k1-stat-label">Messages</div>
          </div>
        </div>
        
        <div class="k1-chart-section">
          <h4>Activity (Last 7 Days)</h4>
          <div class="k1-bar-chart">
            ${last7Days.map(d => `
              <div class="k1-bar-item">
                <div class="k1-bar" style="height: ${(d.count / maxCount) * 100}%">
                  <span class="k1-bar-value">${d.count}</span>
                </div>
                <div class="k1-bar-label">${d.day}</div>
              </div>
            `).join('')}
          </div>
        </div>
        
        <div class="k1-users-list">
          <h4>Recent Users</h4>
          <table class="k1-table">
            <thead>
              <tr>
                <th>User</th>
                <th>Last Seen</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              ${users.slice(0, 15).map(u => `
                <tr>
                  <td>${u.user_id || 'unknown'}</td>
                  <td>${formatTimeAgo(u.last_seen_at)}</td>
                  <td><span class="k1-status-badge ${isRecent(u.last_seen_at) ? 'active' : 'inactive'}">
                    ${isRecent(u.last_seen_at) ? 'Active' : 'Inactive'}
                  </span></td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      `;
    } catch (e) {
        document.getElementById('trafficContent').innerHTML = `
      <div class="k1-error">
        <p>Failed to load traffic data</p>
        <small>${e.message}</small>
      </div>
    `;
    }
};

function formatTimeAgo(ts) {
    if (!ts) return 'Never';
    const d = new Date(ts);
    const now = new Date();
    const diffMs = now - d;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return d.toLocaleDateString();
}

function isRecent(ts) {
    if (!ts) return false;
    const d = new Date(ts);
    const now = new Date();
    return (now - d) < 24 * 60 * 60 * 1000; // 24 hours
}

// Make globally available
if (typeof window.app === 'undefined') window.app = {};
window.app.loadTraffic = window.loadTraffic;
