// ── Dashboard tab: stats row, recent activity feed, mini account grid ──

async function loadDashboard() {
  try {
    const stats = await api('/api/stats');
    const accts = App.accounts || [];
    document.getElementById('statsRow').innerHTML = `
      <div class="stat-card"><div class="val">${stats.accounts}</div><div class="lbl">Accounts ${tip("All Threads accounts you've connected")}</div></div>
      <div class="stat-card"><div class="val">${stats.active_accounts}</div><div class="lbl">Active ${tip('Currently running on auto-pilot')}</div></div>
      <div class="stat-card"><div class="val">${stats.today_threads}</div><div class="lbl">Threads Today ${tip('Posts created today by the AI')}</div></div>
      <div class="stat-card"><div class="val">${stats.today_replies}</div><div class="lbl">Replies Today ${tip('Replies to trending posts today')}</div></div>
    `;

    renderDashboardAccounts();
    loadDashboardPosts();

    if (accts.length > 0 && !App.selectedAccountId) {
      selectAccount(accts[0].id);
    }
  } catch (e) {
    toast('error', 'Failed to load dashboard');
  }
}

function renderDashboardAccounts() {
  const el = document.getElementById('dashAccountList');
  const accounts = App.accounts;
  if (!accounts.length) {
    el.innerHTML = `
      <div class="dash-empty">
        <div class="empty-icon">🚀</div>
        <h3>Ready to Grow?</h3>
        <p>Connect your first Threads account and start posting automatically. AI writes your content, schedules it, and engages with your audience.</p>
        <div class="steps-preview">
          <div class="step-pill"><span class="num">1</span> Enter your Threads login</div>
          <div class="step-pill"><span class="num">2</span> Pick your proxy region</div>
          <div class="step-pill"><span class="num">3</span> AI runs on auto-pilot</div>
        </div>
        <button class="btn btn-primary" onclick="showAddAccount()" style="font-size:15px;padding:12px 32px">+ Add Your First Account</button>
        <p style="font-size:12px;color:#555;margin-top:12px">Takes 30 seconds. Threads login + proxy. We handle the rest.</p>
      </div>`;
    return;
  }
  el.innerHTML = '<div class="acct-grid">' + accounts.map(a => `
    <div class="acct-card" onclick="switchTab('accounts');selectAccount(${a.id})">
      <div class="top">
        <div><div class="name">${a.display_name || a.username || 'Unnamed'}</div>
        <div class="username">@${a.username || '—'}</div></div>
        <span class="badge ${a.active ? 'badge-active' : 'badge-paused'}">${a.active ? 'Active' : 'Paused'}</span>
      </div>
      <div class="metrics">
        <span>🧵 ${a.today_threads}</span>
        <span>💬 ${a.today_replies}</span>
        <span>📅 ${a.schedules_active} slots</span>
      </div>
    </div>
  `).join('') + '</div>';
}

const RELATIVE_TIME = (iso) => {
  if (!iso) return '';
  const d = new Date(iso);
  const now = new Date();
  const diff = (now - d) / 1000;
  if (diff < 60) return 'just now';
  if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
  if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
  if (diff < 172800) return 'yesterday';
  return Math.floor(diff / 86400) + 'd ago';
};

const POST_TYPE_ICON = { 'thread': '🧵', 'fun_fact': '💡', 'reply': '💬', 'image': '🖼️', 'quote': '🔄' };

async function loadDashboardPosts() {
  const el = document.getElementById('dashPostList');
  try {
    const posts = await api('/api/posts');
    if (!posts.length) {
      el.innerHTML = '<div class="feed-empty"><div class="empty-icon">📝</div>No activity yet — posts will appear once your schedules run</div>';
      return;
    }
    el.innerHTML = posts.map(p => {
      const icon = POST_TYPE_ICON[p.type] || '📄';
      const time = RELATIVE_TIME(p.posted_at);
      const typeLabel = p.type.replace(/_/g, ' ');
      const code = p.code ? `<span class="feed-code">t/${p.code}</span>` : '';
      const preview = p.preview || '';
      return `<div class="feed-item">
        <div class="feed-left">
          <div class="feed-icon ${p.type}">${icon}</div>
          <div class="feed-line"></div>
        </div>
        <div class="feed-card">
          <div class="feed-card-top">
            <div class="feed-account-row">
              ${p.account_name ? `<span class="feed-account">${escHtml(p.account_name)}</span>` : ''}
              <span class="feed-type-badge ${p.type}">${typeLabel}</span>
              ${code}
            </div>
            <span class="feed-time">${time}</span>
          </div>
          ${preview ? `<div class="feed-preview">${preview}</div>` : ''}
          <div class="feed-stats">
            <span>❤️ ${p.likes || 0}</span>
            <span>💬 ${p.replies || 0}</span>
          </div>
        </div>
      </div>`;
    }).join('');
  } catch (e) { el.innerHTML = '<div class="feed-empty">Failed to load</div>'; }
}
