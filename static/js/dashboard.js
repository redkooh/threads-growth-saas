// ── Dashboard tab: stats row, recent posts, mini account grid ──

async function loadDashboard() {
  try {
    const stats = await api('/api/stats');
    document.getElementById('statsRow').innerHTML = `
      <div class="stat-card"><div class="val">${stats.accounts}</div><div class="lbl">Total Accounts ${tip('All Threads accounts you\'ve connected')}</div></div>
      <div class="stat-card"><div class="val">${stats.active_accounts}</div><div class="lbl">Active ${tip('Accounts currently running on auto-pilot')}</div></div>
      <div class="stat-card"><div class="val">${stats.today_threads}</div><div class="lbl">Threads Today ${tip('Posts created today by the AI')}</div></div>
      <div class="stat-card"><div class="val">${stats.today_replies}</div><div class="lbl">Replies Today ${tip('Replies to trending posts today')}</div></div>
    `;

    renderDashboardAccounts();
    loadDashboardPosts();

    if (App.accounts.length > 0 && !App.selectedAccountId) {
      selectAccount(App.accounts[0].id);
    } else if (App.accounts.length === 0) {
      setTimeout(() => onboardStart(), 500);
    }
  } catch (e) {
    toast('error', 'Failed to load dashboard');
  }
}

function renderDashboardAccounts() {
  const el = document.getElementById('dashAccountList');
  const accounts = App.accounts;
  if (!accounts.length) {
    el.innerHTML = '<div class="empty"><div class="empty-icon">📱</div>No accounts yet<div class="empty-cta"><button class="btn btn-primary btn-sm" onclick="showAddAccount()">+ Add Your First Account</button></div></div>';
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

async function loadDashboardPosts() {
  const el = document.getElementById('dashPostList');
  try {
    const posts = await api('/api/posts');
    if (!posts.length) { el.innerHTML = '<div class="empty"><div class="empty-icon">📝</div>No activity yet — posts will appear here once your schedules run</div>'; return; }
    el.innerHTML = posts.map(p => `
      <div class="post-item">
        <div class="post-meta">
          <span class="post-type ${p.type}">${p.type.replace('_', ' ')}</span>
          <span class="post-time">${new Date(p.posted_at).toLocaleString()}</span>
          ${p.likes > 0 ? '<span>❤️ ' + p.likes + '</span>' : ''}
          ${p.replies > 0 ? '<span>💬 ' + p.replies + '</span>' : ''}
        </div>
        <div class="post-preview">${p.preview || '(no preview)'}</div>
      </div>
    `).join('');
  } catch (e) { el.innerHTML = '<div class="empty">Failed to load posts</div>'; }
}
