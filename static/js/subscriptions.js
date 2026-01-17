// KELION Admin - Subscriptions Management Module
// Create, edit, delete subscription tiers

window.loadSubscriptions = async function () {
    const dashView = document.getElementById('k1DashView');
    if (!dashView) return;

    dashView.innerHTML = `
    <div class="k1-admin-panel">
      <div class="k1-admin-header">
        <h3>💳 SUBSCRIPTION TIERS</h3>
        <button class="k1-btn-add" onclick="showAddTierModal()">+ Add Tier</button>
      </div>
      <div id="subsContent" class="k1-subs-content">
        <div class="k1-loading">
          <div class="k1-spinner"></div>
          <span>Loading subscriptions...</span>
        </div>
      </div>
    </div>
    
    <!-- Add/Edit Modal -->
    <div id="tierModal" class="k1-modal" style="display:none;">
      <div class="k1-modal-content">
        <div class="k1-modal-header">
          <h3 id="tierModalTitle">Add Subscription Tier</h3>
          <button class="k1-close-btn" onclick="closeTierModal()">×</button>
        </div>
        <div class="k1-modal-body">
          <input type="hidden" id="tierId">
          <div class="k1-form-group">
            <label>Tier Name</label>
            <input type="text" id="tierName" class="k1-input" placeholder="e.g., PRO">
          </div>
          <div class="k1-form-group">
            <label>Display Name</label>
            <input type="text" id="tierDisplayName" class="k1-input" placeholder="e.g., Professional Plan">
          </div>
          <div class="k1-form-group">
            <label>Price ($/month)</label>
            <input type="number" id="tierPrice" class="k1-input" step="0.01" placeholder="9.99">
          </div>
          <div class="k1-form-group">
            <label>Features (one per line)</label>
            <textarea id="tierFeatures" class="k1-textarea" rows="5" placeholder="Unlimited messages
Priority support
Advanced AI features"></textarea>
          </div>
          <div class="k1-form-group">
            <label>Messages/Day Limit (0 = unlimited)</label>
            <input type="number" id="tierLimit" class="k1-input" placeholder="100">
          </div>
          <div class="k1-form-group">
            <label>
              <input type="checkbox" id="tierActive" checked> Active
            </label>
          </div>
        </div>
        <div class="k1-modal-footer">
          <button class="k1-btn-secondary" onclick="closeTierModal()">Cancel</button>
          <button class="k1-btn-primary" onclick="saveTier()">Save Tier</button>
        </div>
      </div>
    </div>
  `;

    loadTiersList();
};

async function loadTiersList() {
    const content = document.getElementById('subsContent');
    const adminToken = localStorage.getItem('k1_admin_token');

    if (!adminToken) {
        content.innerHTML = '<div class="k1-error">Admin token required</div>';
        return;
    }

    try {
        const res = await fetch('/pricing', { method: 'GET' });
        const data = await res.json();
        const tiers = data.tiers || [];

        if (tiers.length === 0) {
            content.innerHTML = `
            <div class="k1-empty">
              <p>No subscription tiers configured</p>
              <button class="k1-btn-add" onclick="showAddTierModal()">+ Create First Tier</button>
            </div>
          `;
            return;
        }

        content.innerHTML = `
        <div class="k1-tiers-grid">
          ${tiers.map(tier => `
            <div class="k1-tier-card ${tier.popular ? 'popular' : ''}">
              ${tier.popular ? '<div class="k1-tier-badge">POPULAR</div>' : ''}
              <h4>${tier.name || tier.id}</h4>
              <div class="k1-tier-price">
                <span class="k1-price-amount">$${tier.price || 0}</span>
                <span class="k1-price-period">/month</span>
              </div>
              <ul class="k1-tier-features">
                ${(tier.features || []).map(f => `<li>✓ ${f}</li>`).join('')}
              </ul>
              <div class="k1-tier-actions">
                <button class="k1-btn-edit" onclick="editTier('${tier.id}')">✏️ Edit</button>
                <button class="k1-btn-delete" onclick="deleteTier('${tier.id}')">🗑️ Delete</button>
              </div>
            </div>
          `).join('')}
        </div>
      `;
    } catch (e) {
        content.innerHTML = `<div class="k1-error">Failed to load tiers: ${e.message}</div>`;
    }
}

window.showAddTierModal = function () {
    document.getElementById('tierModalTitle').textContent = 'Add Subscription Tier';
    document.getElementById('tierId').value = '';
    document.getElementById('tierName').value = '';
    document.getElementById('tierDisplayName').value = '';
    document.getElementById('tierPrice').value = '';
    document.getElementById('tierFeatures').value = '';
    document.getElementById('tierLimit').value = '';
    document.getElementById('tierActive').checked = true;
    document.getElementById('tierModal').style.display = 'flex';
};

window.closeTierModal = function () {
    document.getElementById('tierModal').style.display = 'none';
};

window.editTier = async function (tierId) {
    const adminToken = localStorage.getItem('k1_admin_token');

    try {
        const res = await fetch('/pricing');
        const data = await res.json();
        const tier = (data.tiers || []).find(t => t.id === tierId);

        if (!tier) {
            alert('Tier not found');
            return;
        }

        document.getElementById('tierModalTitle').textContent = 'Edit Subscription Tier';
        document.getElementById('tierId').value = tier.id;
        document.getElementById('tierName').value = tier.id || '';
        document.getElementById('tierDisplayName').value = tier.name || '';
        document.getElementById('tierPrice').value = tier.price || '';
        document.getElementById('tierFeatures').value = (tier.features || []).join('\n');
        document.getElementById('tierLimit').value = tier.limit || '';
        document.getElementById('tierActive').checked = tier.active !== false;
        document.getElementById('tierModal').style.display = 'flex';
    } catch (e) {
        alert('Error loading tier: ' + e.message);
    }
};

window.saveTier = async function () {
    const adminToken = localStorage.getItem('k1_admin_token');
    if (!adminToken) {
        alert('Admin token required');
        return;
    }

    const tierId = document.getElementById('tierId').value;
    const tierData = {
        id: document.getElementById('tierName').value.trim().toUpperCase().replace(/\s+/g, '_'),
        name: document.getElementById('tierDisplayName').value.trim(),
        price: parseFloat(document.getElementById('tierPrice').value) || 0,
        features: document.getElementById('tierFeatures').value.split('\n').filter(f => f.trim()),
        limit: parseInt(document.getElementById('tierLimit').value) || 0,
        active: document.getElementById('tierActive').checked
    };

    if (!tierData.id || !tierData.name) {
        alert('Please fill in tier name and display name');
        return;
    }

    try {
        const res = await fetch('/admin/tiers', {
            method: tierId ? 'PUT' : 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Admin-Token': adminToken
            },
            body: JSON.stringify(tierId ? { ...tierData, original_id: tierId } : tierData)
        });

        const data = await res.json();
        if (res.ok) {
            alert('✅ Tier saved successfully!');
            closeTierModal();
            loadTiersList();
        } else {
            alert('❌ Error: ' + (data.error || 'Failed to save'));
        }
    } catch (e) {
        alert('❌ Error: ' + e.message);
    }
};

window.deleteTier = async function (tierId) {
    if (!confirm(`Are you sure you want to delete the "${tierId}" tier?`)) {
        return;
    }

    const adminToken = localStorage.getItem('k1_admin_token');
    if (!adminToken) {
        alert('Admin token required');
        return;
    }

    try {
        const res = await fetch('/admin/tiers/' + tierId, {
            method: 'DELETE',
            headers: { 'X-Admin-Token': adminToken }
        });

        if (res.ok) {
            alert('✅ Tier deleted');
            loadTiersList();
        } else {
            const data = await res.json();
            alert('❌ Error: ' + (data.error || 'Failed to delete'));
        }
    } catch (e) {
        alert('❌ Error: ' + e.message);
    }
};

// Make globally available
if (typeof window.app === 'undefined') window.app = {};
window.app.loadSubscriptions = window.loadSubscriptions;
