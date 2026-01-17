/**
 * SUPER AI MODULE - Frontend Integration
 * Connects all Super AI features to the interface
 */

window.loadSuperAI = async function (feature) {
  const view = document.getElementById('k1DashView');
  if (!view) return;

  const adminToken = localStorage.getItem('k1_admin_token') || '';

  switch (feature) {
    case 'vision':
      await loadVisionPanel(view, adminToken);
      break;
    case 'memory':
      await loadMemoryPanel(view, adminToken);
      break;
    case 'finance':
      await loadFinancePanel(view, adminToken);
      break;
    case 'search':
      await loadSearchPanel(view, adminToken);
      break;
    case 'translate':
      await loadTranslatePanel(view, adminToken);
      break;
    case 'security':
      await loadSecurityPanel(view, adminToken);
      break;
    default:
      view.innerHTML = '<p>Feature not found</p>';
  }
};

// ============================================
// VISION PANEL - Webcam Capture & Analysis
// ============================================
async function loadVisionPanel(view, adminToken) {
  view.innerHTML = `
    <div class="k1-super-panel">
      <h2>👁️ VISION - Image Analysis</h2>
      <div class="k1-vision-container">
        <video id="k1Webcam" autoplay playsinline style="width:100%;max-width:400px;border-radius:8px;display:none;"></video>
        <canvas id="k1Canvas" style="display:none;"></canvas>
        <img id="k1Preview" style="width:100%;max-width:400px;border-radius:8px;display:none;">
        <div class="k1-vision-controls" style="margin-top:15px;">
          <button id="k1StartCam" class="k1-btn">📷 Start Camera</button>
          <button id="k1Capture" class="k1-btn" style="display:none;">📸 Capture</button>
          <button id="k1Analyze" class="k1-btn k1-btn-primary" style="display:none;">🔍 Analyze with AI</button>
        </div>
        <div id="k1VisionResult" class="k1-result-box" style="margin-top:20px;"></div>
      </div>
    </div>
  `;

  const webcam = document.getElementById('k1Webcam');
  const canvas = document.getElementById('k1Canvas');
  const preview = document.getElementById('k1Preview');
  const startBtn = document.getElementById('k1StartCam');
  const captureBtn = document.getElementById('k1Capture');
  const analyzeBtn = document.getElementById('k1Analyze');
  const result = document.getElementById('k1VisionResult');

  let stream = null;
  let imageData = null;

  startBtn.onclick = async () => {
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: true });
      webcam.srcObject = stream;
      webcam.style.display = 'block';
      startBtn.style.display = 'none';
      captureBtn.style.display = 'inline-block';
    } catch (e) {
      result.innerHTML = `<p style="color:#ff4444;">❌ Camera access denied: ${e.message}</p>`;
    }
  };

  captureBtn.onclick = () => {
    canvas.width = webcam.videoWidth;
    canvas.height = webcam.videoHeight;
    canvas.getContext('2d').drawImage(webcam, 0, 0);
    imageData = canvas.toDataURL('image/jpeg', 0.8);
    preview.src = imageData;
    preview.style.display = 'block';
    webcam.style.display = 'none';
    captureBtn.style.display = 'none';
    analyzeBtn.style.display = 'inline-block';
    if (stream) stream.getTracks().forEach(t => t.stop());
  };

  analyzeBtn.onclick = async () => {
    result.innerHTML = '<p>🔄 Analyzing with Claude Vision...</p>';
    try {
      const res = await fetch('/api/super/vision/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image: imageData, context: 'Describe what you see' })
      });
      const data = await res.json();
      if (data.error) {
        result.innerHTML = `<p style="color:#ff4444;">❌ ${data.error}</p>`;
      } else {
        result.innerHTML = `
          <h4>🔍 Analysis Result:</h4>
          <p>${data.description || data.analysis || JSON.stringify(data)}</p>
        `;
      }
    } catch (e) {
      result.innerHTML = `<p style="color:#ff4444;">❌ Error: ${e.message}</p>`;
    }
  };
}

// ============================================
// MEMORY PANEL - Keywords & Facts
// ============================================
async function loadMemoryPanel(view, adminToken) {
  view.innerHTML = '<p>Loading memory...</p>';

  try {
    const [keywordsRes, factsRes] = await Promise.all([
      fetch('/api/super/memory/keywords'),
      fetch('/api/super/memory/facts')
    ]);
    const keywords = await keywordsRes.json();
    const facts = await factsRes.json();

    view.innerHTML = `
      <div class="k1-super-panel">
        <h2>🧠 MEMORY - Keywords & Facts</h2>
        
        <div class="k1-memory-section">
          <h3>📝 Learned Keywords (${Object.keys(keywords.keywords || {}).length})</h3>
          <div class="k1-memory-grid">
            ${Object.entries(keywords.keywords || {}).map(([k, v]) => `
              <div class="k1-memory-item">
                <strong>"${k}"</strong> → ${v}
              </div>
            `).join('') || '<p>No keywords learned yet. Say "Când zic X, vreau Y" to teach Kelion.</p>'}
          </div>
        </div>
        
        <div class="k1-memory-section" style="margin-top:20px;">
          <h3>📋 User Facts (${Object.keys(facts.facts || {}).length})</h3>
          <div class="k1-memory-grid">
            ${Object.entries(facts.facts || {}).map(([k, v]) => `
              <div class="k1-memory-item">
                <strong>${k}:</strong> ${v}
              </div>
            `).join('') || '<p>No facts stored yet.</p>'}
          </div>
        </div>
        
        <div class="k1-memory-actions" style="margin-top:20px;">
          <button class="k1-btn" onclick="addKeywordPrompt()">➕ Add Keyword</button>
          <button class="k1-btn" onclick="addFactPrompt()">➕ Add Fact</button>
        </div>
      </div>
    `;
  } catch (e) {
    view.innerHTML = `<p style="color:#ff4444;">❌ Error: ${e.message}</p>`;
  }
}

window.addKeywordPrompt = async () => {
  const keyword = prompt('Enter keyword (e.g., "cod roșu"):');
  const meaning = prompt('Enter meaning (e.g., "oprește tot"):');
  if (keyword && meaning) {
    await fetch('/api/super/memory/keywords', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ keyword, meaning })
    });
    loadSuperAI('memory');
  }
};

window.addFactPrompt = async () => {
  const key = prompt('Fact name (e.g., "favorite_color"):');
  const value = prompt('Fact value (e.g., "blue"):');
  if (key && value) {
    await fetch('/api/super/memory/facts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key, value })
    });
    loadSuperAI('memory');
  }
};

// ============================================
// FINANCE PANEL - Crypto & Portfolio
// ============================================
async function loadFinancePanel(view, adminToken) {
  view.innerHTML = '<p>Loading financial data...</p>';

  try {
    const [btcRes, ethRes, portfolioRes] = await Promise.all([
      fetch('/api/super/finance/crypto/bitcoin'),
      fetch('/api/super/finance/crypto/ethereum'),
      fetch('/api/super/finance/portfolio')
    ]);
    const btc = await btcRes.json();
    const eth = await ethRes.json();
    const portfolio = await portfolioRes.json();

    view.innerHTML = `
      <div class="k1-super-panel">
        <h2>💰 FINANCIAL GUARDIAN</h2>
        
        <div class="k1-crypto-grid" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:15px;">
          <div class="k1-crypto-card" style="background:linear-gradient(135deg,#f7931a22,#0a0f1a);padding:20px;border-radius:8px;border:1px solid #f7931a;">
            <h3>₿ Bitcoin</h3>
            <p style="font-size:24px;color:#f7931a;">$${(btc.price || 0).toLocaleString()}</p>
            <small>${btc.change_24h > 0 ? '📈' : '📉'} ${btc.change_24h || 0}%</small>
          </div>
          <div class="k1-crypto-card" style="background:linear-gradient(135deg,#627eea22,#0a0f1a);padding:20px;border-radius:8px;border:1px solid #627eea;">
            <h3>Ξ Ethereum</h3>
            <p style="font-size:24px;color:#627eea;">$${(eth.price || 0).toLocaleString()}</p>
            <small>${eth.change_24h > 0 ? '📈' : '📉'} ${eth.change_24h || 0}%</small>
          </div>
        </div>
        
        <div class="k1-portfolio" style="margin-top:30px;">
          <h3>📊 Your Portfolio</h3>
          <p>Total Value: <strong style="color:#00d4ff;">$${(portfolio.total_value || 0).toLocaleString()}</strong></p>
          ${portfolio.holdings ? Object.entries(portfolio.holdings).map(([symbol, data]) => `
            <div style="padding:10px;border-bottom:1px solid #333;">
              ${symbol.toUpperCase()}: ${data.amount} units @ $${data.buy_price}
            </div>
          `).join('') : '<p>No holdings yet.</p>'}
        </div>
      </div>
    `;
  } catch (e) {
    view.innerHTML = `<p style="color:#ff4444;">❌ Error: ${e.message}</p>`;
  }
}

// ============================================
// SEARCH PANEL - Web Search
// ============================================
async function loadSearchPanel(view, adminToken) {
  view.innerHTML = `
    <div class="k1-super-panel">
      <h2>🔍 WEB SEARCH</h2>
      <div class="k1-search-box" style="display:flex;gap:10px;margin-bottom:20px;">
        <input type="text" id="k1SearchInput" placeholder="Search the web..." 
          style="flex:1;padding:12px;background:#1a1f2e;border:1px solid #333;border-radius:6px;color:#fff;">
        <button id="k1SearchBtn" class="k1-btn k1-btn-primary">Search</button>
      </div>
      <div id="k1SearchResults"></div>
    </div>
  `;

  document.getElementById('k1SearchBtn').onclick = async () => {
    const query = document.getElementById('k1SearchInput').value;
    if (!query) return;

    const results = document.getElementById('k1SearchResults');
    results.innerHTML = '<p>🔄 Searching...</p>';

    try {
      const res = await fetch('/api/super/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query })
      });
      const data = await res.json();

      if (data.results && data.results.length) {
        results.innerHTML = data.results.map(r => `
          <div style="padding:15px;margin-bottom:10px;background:#1a1f2e;border-radius:8px;border-left:3px solid #00d4ff;">
            <h4 style="margin:0 0 5px;color:#00d4ff;">${r.title}</h4>
            <p style="margin:0;color:#aaa;">${r.snippet || r.description || ''}</p>
            ${r.url ? `<a href="${r.url}" target="_blank" style="color:#888;font-size:12px;">${r.url}</a>` : ''}
          </div>
        `).join('');
      } else {
        results.innerHTML = '<p>No results found.</p>';
      }
    } catch (e) {
      results.innerHTML = `<p style="color:#ff4444;">❌ ${e.message}</p>`;
    }
  };
}

// ============================================
// TRANSLATE PANEL - Live Translation
// ============================================
async function loadTranslatePanel(view, adminToken) {
  view.innerHTML = `
    <div class="k1-super-panel">
      <h2>🌐 LIVE TRANSLATOR</h2>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;">
        <div>
          <label>From:</label>
          <select id="k1LangFrom" style="width:100%;padding:10px;background:#1a1f2e;border:1px solid #333;color:#fff;">
            <option value="auto">Auto-detect</option>
            <option value="en">English</option>
            <option value="ro">Română</option>
            <option value="de">Deutsch</option>
            <option value="fr">Français</option>
            <option value="es">Español</option>
          </select>
          <textarea id="k1TextFrom" rows="6" placeholder="Enter text to translate..."
            style="width:100%;margin-top:10px;padding:12px;background:#1a1f2e;border:1px solid #333;color:#fff;"></textarea>
        </div>
        <div>
          <label>To:</label>
          <select id="k1LangTo" style="width:100%;padding:10px;background:#1a1f2e;border:1px solid #333;color:#fff;">
            <option value="en">English</option>
            <option value="ro">Română</option>
            <option value="de">Deutsch</option>
            <option value="fr">Français</option>
            <option value="es">Español</option>
          </select>
          <div id="k1TextTo" style="width:100%;margin-top:10px;padding:12px;background:#0a0f1a;border:1px solid #00d4ff;min-height:140px;color:#00d4ff;"></div>
        </div>
      </div>
      <button id="k1TranslateBtn" class="k1-btn k1-btn-primary" style="margin-top:15px;width:100%;">🌐 Translate</button>
    </div>
  `;

  document.getElementById('k1TranslateBtn').onclick = async () => {
    const text = document.getElementById('k1TextFrom').value;
    const source = document.getElementById('k1LangFrom').value;
    const target = document.getElementById('k1LangTo').value;
    const output = document.getElementById('k1TextTo');

    output.innerHTML = '🔄 Translating...';

    try {
      const res = await fetch('/api/super/voice/translate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, source, target })
      });
      const data = await res.json();
      output.innerHTML = data.translated || data.translation || data.error || 'No translation';
    } catch (e) {
      output.innerHTML = `❌ ${e.message}`;
    }
  };
}

// ============================================
// SECURITY PANEL - Freeze/Unfreeze
// ============================================
async function loadSecurityPanel(view, adminToken) {
  try {
    const res = await fetch('/api/super/status');
    const status = await res.json();

    view.innerHTML = `
      <div class="k1-super-panel">
        <h2>🛡️ SECURITY CONTROL</h2>
        
        <div class="k1-security-status" style="padding:20px;background:${status.frozen ? '#ff444422' : '#00ff5522'};border-radius:8px;margin-bottom:20px;">
          <h3>System Status: <span style="color:${status.frozen ? '#ff4444' : '#00ff55'};">${status.frozen ? '🔒 FROZEN' : '✅ ACTIVE'}</span></h3>
        </div>
        
        <div class="k1-security-actions" style="display:grid;gap:15px;">
          <div style="padding:15px;background:#1a1f2e;border-radius:8px;">
            <h4>🔒 Freeze System (Kill Switch)</h4>
            <p style="color:#888;">Stops all AI operations immediately.</p>
            <input type="password" id="k1FreezePass" placeholder="Master Password" 
              style="width:100%;padding:10px;background:#0a0f1a;border:1px solid #333;color:#fff;margin:10px 0;">
            <button id="k1FreezeBtn" class="k1-btn" style="background:#ff4444;">🔒 FREEZE NOW</button>
          </div>
          
          <div style="padding:15px;background:#1a1f2e;border-radius:8px;">
            <h4>🔓 Unfreeze System</h4>
            <p style="color:#888;">Reactivates AI operations.</p>
            <input type="password" id="k1UnfreezePass" placeholder="Master Password" 
              style="width:100%;padding:10px;background:#0a0f1a;border:1px solid #333;color:#fff;margin:10px 0;">
            <button id="k1UnfreezeBtn" class="k1-btn" style="background:#00ff55;color:#000;">🔓 UNFREEZE</button>
          </div>

          <div style="padding:15px;background:#1a1f2e;border-radius:8px;border:1px solid #00d4ff;">
            <h4>📦 System Backup</h4>
            <p style="color:#888;">Download full project archive.</p>
            <button id="k1DownloadBtn" class="k1-btn" style="background:#00d4ff;color:#000;margin-top:10px;">⬇️ DOWNLOAD FULL ARCHIVE</button>
          </div>
        </div>
        
        <div id="k1SecurityResult" style="margin-top:20px;"></div>
      </div>
    `;

    document.getElementById('k1FreezeBtn').onclick = async () => {
      const password = document.getElementById('k1FreezePass').value;
      const result = document.getElementById('k1SecurityResult');
      try {
        const res = await fetch('/api/super/freeze', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ password })
        });
        const data = await res.json();
        result.innerHTML = data.success ? '<p style="color:#ff4444;">🔒 System FROZEN</p>' : `<p style="color:#ff4444;">❌ ${data.error}</p>`;
        if (data.success) loadSecurityPanel(view, adminToken);
      } catch (e) {
        result.innerHTML = `<p style="color:#ff4444;">❌ ${e.message}</p>`;
      }
    };

    document.getElementById('k1UnfreezeBtn').onclick = async () => {
      const password = document.getElementById('k1UnfreezePass').value;
      const result = document.getElementById('k1SecurityResult');
      try {
        const res = await fetch('/api/super/unfreeze', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ password })
        });
        const data = await res.json();
        result.innerHTML = data.success ? '<p style="color:#00ff55;">✅ System ACTIVE</p>' : `<p style="color:#ff4444;">❌ ${data.error}</p>`;
        if (data.success) loadSecurityPanel(view, adminToken);
      } catch (e) {
        result.innerHTML = `<p style="color:#ff4444;">❌ ${e.message}</p>`;
      }
    };

    // DOWNLOAD ARCHIVE Handler
    const dlBtn = document.getElementById('k1DownloadBtn');
    if (dlBtn) {
      dlBtn.onclick = () => {
        window.location.href = '/api/super/admin/download-archive';
      };
    }
  } catch (e) {
    view.innerHTML = `<p style="color:#ff4444;">❌ ${e.message}</p>`;
  }
}

// Expose to app namespace
if (window.app) {
  window.app.loadSuperAI = window.loadSuperAI;
}

console.log('✅ Super AI Module loaded');
