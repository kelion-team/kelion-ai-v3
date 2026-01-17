// KELION Users Panel - User Management
// Displays user statistics and management options

window.loadUsers = async function () {
  const dashView = document.getElementById('k1DashView');
  if (!dashView) return;

  dashView.innerHTML = `
    <div class="k1-users-panel">
      <div class="k1-admin-header">
        <h3>👥 USER MANAGEMENT</h3>
        <button class="k1-btn-refresh" onclick="loadUsers()">⟳ Refresh</button>
      </div>
      <div id="usersContent" class="k1-users-content">
        <div class="k1-loading">
          <div class="k1-spinner"></div>
          <span>Loading user data...</span>
        </div>
      </div>
    </div>
  `;

  try {
    // Get dashboard stats
    const dashRes = await fetch('/api/dashboard');
    const dashData = await dashRes.json();

    // Get admin token
    const adminToken = localStorage.getItem('k1_admin_token');

    // Try to get full user list if admin
    let usersList = [];
    let showAdminTools = false;

    if (adminToken) {
      try {
        const usersRes = await fetch('/admin/users?limit=50', {
          headers: { 'X-Admin-Token': adminToken }
        });
        if (usersRes.ok) {
          const usersData = await usersRes.json();
          usersList = usersData.users || [];
          showAdminTools = true;
        }
      } catch (e) {
        console.log('Admin users fetch failed:', e);
      }
    }

    const content = document.getElementById('usersContent');

    content.innerHTML = `
      <div class="k1-stats-grid">
        <div class="k1-stat-card">
          <div class="k1-stat-icon">👤</div>
          <div class="k1-stat-value">${dashData.users || 0}</div>
          <div class="k1-stat-label">Total Users</div>
        </div>
        <div class="k1-stat-card">
          <div class="k1-stat-icon">💬</div>
          <div class="k1-stat-value">${dashData.messages || 0}</div>
          <div class="k1-stat-label">Total Messages</div>
        </div>
        <div class="k1-stat-card">
          <div class="k1-stat-icon">📧</div>
          <div class="k1-stat-value">${dashData.leads || 0}</div>
          <div class="k1-stat-label">Leads</div>
        </div>
        <div class="k1-stat-card">
          <div class="k1-stat-icon">🔧</div>
          <div class="k1-stat-value">${dashData.version || 'k1.0.0'}</div>
          <div class="k1-stat-label">Version</div>
        </div>
      </div>
      
      ${showAdminTools ? `
      <div class="k1-users-section">
        <h4>📋 All Users (${usersList.length})</h4>
        <div class="k1-users-table-container">
          <table class="k1-users-table">
            <thead>
              <tr>
                <th>User ID</th>
                <th>Email</th>
                <th>Tier</th>
                <th>Verified</th>
                <th>2FA</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              ${usersList.map(u => `
                <tr>
                  <td><strong>${u.user_id}</strong></td>
                  <td>${u.email || '-'}</td>
                  <td>
                    <select class="k1-tier-select" data-userid="${u.user_id}" onchange="changeTier('${u.user_id}', this.value)">
                      <option value="Starter" ${u.tier === 'Starter' ? 'selected' : ''}>Starter</option>
                      <option value="Pro" ${u.tier === 'Pro' ? 'selected' : ''}>Pro</option>
                      <option value="Elite" ${u.tier === 'Elite' ? 'selected' : ''}>Elite</option>
                      <option value="Enterprise" ${u.tier === 'Enterprise' ? 'selected' : ''}>Enterprise</option>
                    </select>
                  </td>
                  <td>${u.email_verified ? '✅' : '❌'}</td>
                  <td>${u['2fa_enabled'] ? '🔐' : '-'}</td>
                  <td>${new Date(u.created_at).toLocaleDateString()}</td>
                  <td>
                    <button class="k1-btn-small" onclick="viewUserMessages('${u.user_id}')">💬</button>
                    <button class="k1-btn-small k1-btn-danger" onclick="deleteUser('${u.user_id}')">🗑️</button>
                  </td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>
      ` : ''}
      
      <div class="k1-users-section">
        <h4>📊 User Lookup</h4>
        <div class="k1-user-search">
          <input type="text" id="userIdInput" class="k1-input" placeholder="Enter User ID...">
          <button class="k1-btn-primary" onclick="lookupUser()">Search</button>
        </div>
        <div id="userLookupResult"></div>
      </div>

      <div class="k1-users-section">
        <h4>📋 Subscription Tiers</h4>
        <div class="k1-tiers-grid">
          <div class="k1-tier-card k1-tier-starter">
            <div class="k1-tier-name">STARTER</div>
            <div class="k1-tier-price">$19/mo</div>
            <ul>
              <li>50 messages/day</li>
              <li>Web hologram</li>
              <li>AI chat</li>
              <li>Basic support</li>
            </ul>
          </div>
          <div class="k1-tier-card k1-tier-pro">
            <div class="k1-tier-name">PRO</div>
            <div class="k1-tier-price">$59/mo</div>
            <ul>
              <li>500 messages/day</li>
              <li>Voice (TTS/STT)</li>
              <li>Persistent memory</li>
              <li>Admin audit</li>
            </ul>
          </div>
          <div class="k1-tier-card k1-tier-enterprise">
            <div class="k1-tier-name">ENTERPRISE</div>
            <div class="k1-tier-price">$199/mo</div>
            <ul>
              <li>Unlimited messages</li>
              <li>Custom workflows</li>
              <li>Legal-grade audit</li>
              <li>SLA guarantee</li>
            </ul>
          </div>
        </div>
      </div>
    `;

    // Add table styles dynamically
    if (!document.getElementById('usersTableStyles')) {
      const style = document.createElement('style');
      style.id = 'usersTableStyles';
      style.textContent = `
        .k1-users-table-container {
          overflow-x: auto;
          margin-top: 15px;
          border-radius: 10px;
          border: 1px solid rgba(0, 243, 255, 0.2);
        }
        .k1-users-table {
          width: 100%;
          border-collapse: collapse;
          font-size: 13px;
        }
        .k1-users-table th, .k1-users-table td {
          padding: 12px 10px;
          text-align: left;
          border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        .k1-users-table th {
          background: rgba(0, 243, 255, 0.1);
          color: #00f3ff;
          font-weight: 600;
          text-transform: uppercase;
          font-size: 11px;
          letter-spacing: 1px;
        }
        .k1-users-table tr:hover {
          background: rgba(0, 243, 255, 0.05);
        }
        .k1-tier-select {
          background: rgba(0, 0, 0, 0.3);
          border: 1px solid rgba(0, 243, 255, 0.3);
          color: #fff;
          padding: 5px 8px;
          border-radius: 5px;
          cursor: pointer;
        }
        .k1-btn-small {
          padding: 5px 10px;
          background: rgba(0, 243, 255, 0.1);
          border: 1px solid rgba(0, 243, 255, 0.3);
          color: #00f3ff;
          border-radius: 5px;
          cursor: pointer;
          margin-right: 5px;
        }
        .k1-btn-small:hover {
          background: rgba(0, 243, 255, 0.2);
        }
        .k1-btn-danger {
          border-color: rgba(255, 77, 109, 0.5);
          color: #ff4d6d;
        }
        .k1-btn-danger:hover {
          background: rgba(255, 77, 109, 0.2);
        }
      `;
      document.head.appendChild(style);
    }
  } catch (e) {
    document.getElementById('usersContent').innerHTML = `
      <div class="k1-error">
        <p>Failed to load user data</p>
        <small>${e.message}</small>
      </div>
    `;
  }
};

window.changeTier = async function (userId, newTier) {
  const adminToken = localStorage.getItem('k1_admin_token');
  if (!adminToken) {
    alert('Admin token required');
    return;
  }

  try {
    const res = await fetch('/admin/users/upgrade', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Admin-Token': adminToken
      },
      body: JSON.stringify({ userId, tier: newTier })
    });

    const data = await res.json();
    if (res.ok && data.ok) {
      alert(`✅ User ${userId} upgraded to ${newTier}`);
    } else {
      alert(`❌ Error: ${data.error || 'Failed to upgrade'}`);
    }
  } catch (e) {
    alert(`❌ Error: ${e.message}`);
  }
};

window.deleteUser = async function (userId) {
  const adminToken = localStorage.getItem('k1_admin_token');
  if (!adminToken) {
    alert('Admin token required');
    return;
  }

  if (!confirm(`⚠️ Are you sure you want to delete user "${userId}"?\n\nThis will permanently delete all their data!`)) {
    return;
  }

  if (!confirm('This action cannot be undone. Confirm deletion?')) {
    return;
  }

  try {
    const res = await fetch('/admin/users', {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
        'X-Admin-Token': adminToken
      },
      body: JSON.stringify({ userId })
    });

    const data = await res.json();
    if (res.ok && data.ok) {
      alert(`✅ User ${userId} deleted successfully`);
      loadUsers(); // Refresh the list
    } else {
      alert(`❌ Error: ${data.error || 'Failed to delete'}`);
    }
  } catch (e) {
    alert(`❌ Error: ${e.message}`);
  }
};

window.viewUserMessages = function (userId) {
  document.getElementById('userIdInput').value = userId;
  lookupUser();
};

window.lookupUser = async function () {
  const userId = document.getElementById('userIdInput')?.value?.trim();
  const resultDiv = document.getElementById('userLookupResult');

  if (!userId || !resultDiv) return;

  const adminToken = localStorage.getItem('k1_admin_token');
  if (!adminToken) {
    resultDiv.innerHTML = '<div class="k1-error">Admin token required. Go to Admin panel first.</div>';
    return;
  }

  resultDiv.innerHTML = '<div class="k1-loading"><div class="k1-spinner"></div></div>';

  try {
    const res = await fetch(`/admin/messages?user_id=${encodeURIComponent(userId)}&limit=20`, {
      headers: { 'X-Admin-Token': adminToken }
    });

    if (!res.ok) throw new Error('Unauthorized');

    const data = await res.json();

    if (!data.items || data.items.length === 0) {
      resultDiv.innerHTML = '<div class="k1-empty">No messages found for this user</div>';
      return;
    }

    resultDiv.innerHTML = `
      <div class="k1-user-messages">
        <h5>Recent Messages for ${userId}</h5>
        ${data.items.slice(0, 10).map(m => `
          <div class="k1-message-preview ${m.role}">
            <span class="k1-msg-role">${m.role === 'user' ? '👤' : '🤖'}</span>
            <span class="k1-msg-content">${m.content?.slice(0, 100) || '-'}${m.content?.length > 100 ? '...' : ''}</span>
            <span class="k1-msg-time">${new Date(m.created_at).toLocaleTimeString()}</span>
          </div>
        `).join('')}
      </div>
    `;
  } catch (e) {
    resultDiv.innerHTML = `<div class="k1-error">Error: ${e.message}</div>`;
  }
};

// Make globally available
if (typeof window.app === 'undefined') window.app = {};
window.app.loadUsers = window.loadUsers;

