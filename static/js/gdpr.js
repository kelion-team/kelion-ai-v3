// KELION GDPR/Privacy Panel
// Data privacy options and compliance information

window.loadGDPR = async function () {
  const dashView = document.getElementById('k1DashView');
  if (!dashView) return;

  const userId = localStorage.getItem('k1_user_id') || 'Unknown';

  dashView.innerHTML = `
    <div class="k1-gdpr-panel">
      <div class="k1-admin-header">
        <h3>🔒 PRIVACY & DATA OPTIONS</h3>
      </div>
      
      <div class="k1-gdpr-content">
        <div class="k1-privacy-section">
          <h4>📋 Your Data</h4>
          <div class="k1-data-info">
            <div class="k1-info-row">
              <span class="k1-info-label">Your User ID:</span>
              <span class="k1-info-value">${userId}</span>
            </div>
            <div class="k1-info-row">
              <span class="k1-info-label">Session ID:</span>
              <span class="k1-info-value">${localStorage.getItem('k1_session_id') || 'None'}</span>
            </div>
            <div class="k1-info-row">
              <span class="k1-info-label">Data Stored:</span>
              <span class="k1-info-value">Conversations, preferences, session logs</span>
            </div>
          </div>
        </div>

        <div class="k1-privacy-section">
          <h4>📜 Data Collection Notice</h4>
          <div class="k1-notice-box">
            <p><strong>What we collect:</strong></p>
            <ul>
              <li>💬 Chat messages and responses</li>
              <li>🔊 Voice recordings (for STT, not stored permanently)</li>
              <li>📊 Usage analytics and session data</li>
              <li>⚙️ Preferences and settings</li>
            </ul>
            <p><strong>Why we collect it:</strong></p>
            <ul>
              <li>To provide personalized AI responses</li>
              <li>To maintain conversation context</li>
              <li>To improve our services</li>
              <li>For audit and compliance purposes</li>
            </ul>
          </div>
        </div>

        <div class="k1-privacy-section">
          <h4>🛡️ Your Rights (GDPR)</h4>
          <div class="k1-rights-grid">
            <div class="k1-right-card">
              <div class="k1-right-icon">📥</div>
              <div class="k1-right-title">Data Export</div>
              <div class="k1-right-desc">Request a copy of all data associated with your account</div>
              <button class="k1-btn-outline" onclick="requestDataExport()">Request Export</button>
            </div>
            <div class="k1-right-card">
              <div class="k1-right-icon">🗑️</div>
              <div class="k1-right-title">Data Deletion</div>
              <div class="k1-right-desc">Request permanent deletion of your data</div>
              <button class="k1-btn-danger" onclick="requestDataDeletion()">Request Deletion</button>
            </div>
            <div class="k1-right-card">
              <div class="k1-right-icon">✏️</div>
              <div class="k1-right-title">Data Rectification</div>
              <div class="k1-right-desc">Correct inaccurate personal data</div>
              <button class="k1-btn-outline" onclick="requestRectification()">Contact Support</button>
            </div>
            <div class="k1-right-card">
              <div class="k1-right-icon">⏸️</div>
              <div class="k1-right-title">Processing Restriction</div>
              <div class="k1-right-desc">Limit how we use your data</div>
              <button class="k1-btn-outline" onclick="requestRestriction()">Request Restriction</button>
            </div>
          </div>
        </div>

        <div class="k1-privacy-section">
          <h4>🔗 Legal Documents</h4>
          <div class="k1-legal-links">
            <a href="#" class="k1-legal-link" onclick="showPolicy('privacy')">
              <span>📄</span> Privacy Policy
            </a>
            <a href="#" class="k1-legal-link" onclick="showPolicy('terms')">
              <span>📄</span> Terms of Service
            </a>
            <a href="#" class="k1-legal-link" onclick="showPolicy('cookies')">
              <span>🍪</span> Cookie Policy
            </a>
            <a href="#" class="k1-legal-link" onclick="showPolicy('dpa')">
              <span>🤝</span> Data Processing Agreement
            </a>
          </div>
        </div>

        <div class="k1-privacy-section k1-contact-dpo">
          <h4>📞 Contact Data Protection Officer</h4>
          <p>For any privacy-related inquiries:</p>
          <a href="mailto:privacy@kelionai.app" class="k1-btn-primary">
            ✉️ privacy@kelionai.app
          </a>
        </div>
      </div>
    </div>
  `;
};

window.requestDataExport = async function () {
  const userId = localStorage.getItem('k1_user_id');
  const confirmed = confirm(
    `Request data export for User ID: ${userId}?\n\n` +
    `We will prepare a complete export of all your data.`
  );

  if (confirmed) {
    try {
      // Try direct export first
      const res = await fetch(`/api/gdpr/export?userId=${encodeURIComponent(userId)}`, {
        headers: { 'X-User-Id': userId }
      });

      if (res.ok) {
        const data = await res.json();
        // Download as JSON file
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `kelion_data_export_${userId}_${new Date().toISOString().split('T')[0]}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        alert('✅ Data exported successfully! Check your downloads.');
      } else {
        throw new Error('Export failed');
      }
    } catch (e) {
      // Fallback to email request
      fetch('/api/gdpr/request', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          userId: userId,
          type: 'export',
          email: localStorage.getItem('k1_email') || 'pending'
        })
      }).then(() => {
        alert('✅ Export request submitted. You will be contacted within 30 days.');
      }).catch(() => {
        alert('❌ Failed to submit request. Please email privacy@kelionai.app directly.');
      });
    }
  }
};

window.requestDataDeletion = async function () {
  const userId = localStorage.getItem('k1_user_id');
  const confirmed = confirm(
    `⚠️ WARNING: Data Deletion Request\n\n` +
    `This will PERMANENTLY DELETE ALL data associated with User ID: ${userId}\n\n` +
    `This cannot be undone. Are you sure?`
  );

  if (confirmed) {
    const doubleConfirm = confirm(
      `Please confirm again.\n\n` +
      `Type "DELETE" in the next prompt to confirm deletion.`
    );

    if (doubleConfirm) {
      const typed = prompt('Type DELETE to confirm:');
      if (typed === 'DELETE') {
        try {
          // Use real GDPR delete endpoint
          const res = await fetch('/api/gdpr/delete', {
            method: 'DELETE',
            headers: {
              'Content-Type': 'application/json',
              'X-User-Id': userId
            },
            body: JSON.stringify({
              userId: userId,
              confirmation: 'DELETE'
            })
          });

          const data = await res.json();

          if (res.ok && data.ok) {
            alert(`✅ Data deleted successfully!\n\nDeleted:\n- ${data.deleted?.messages || 0} messages\n- ${data.deleted?.feedback || 0} feedback entries\n\nYour account has been removed.`);
            localStorage.clear();
            window.location.reload();
          } else {
            throw new Error(data.error || 'Deletion failed');
          }
        } catch (e) {
          // Fallback to request system
          fetch('/api/gdpr/request', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              userId: userId,
              type: 'delete',
              email: localStorage.getItem('k1_email') || 'pending'
            })
          }).then(() => {
            alert('✅ Deletion request submitted. Your data will be removed within 30 days.');
            localStorage.clear();
          }).catch(() => {
            alert('❌ Failed to submit request. Please email privacy@kelionai.app directly.');
          });
        }
      }
    }
  }
};

window.requestRectification = function () {
  window.location.href = 'mailto:privacy@kelionai.app?subject=Data%20Rectification%20Request';
};

window.requestRestriction = function () {
  const confirmed = confirm(
    'Request processing restriction?\n\n' +
    'This will limit how KELION uses your data. You may experience reduced functionality.'
  );

  if (confirmed) {
    alert('✅ Restriction request noted. Contact privacy@kelionai.app for immediate action.');
  }
};

window.showPolicy = function (type) {
  const policies = {
    privacy: 'Privacy Policy - Full document available at /legal/privacy',
    terms: 'Terms of Service - Full document available at /legal/terms',
    cookies: 'Cookie Policy - We use essential cookies only for session management.',
    dpa: 'Data Processing Agreement - Available for enterprise customers upon request.'
  };

  alert(policies[type] || 'Document not found');
};

// Make globally available
if (typeof window.app === 'undefined') window.app = {};
window.app.loadGDPR = window.loadGDPR;
