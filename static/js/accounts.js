// ── Accounts tab: CRUD, detail panel, settings, schedules ──

function renderAccountGrid() {
  const el = document.getElementById('accountGrid');
  const accounts = App.accounts;
  if (!accounts.length) {
    el.innerHTML = '<div class="empty" style="grid-column:1/-1"><div class="empty-icon">📱</div>No accounts yet<div class="empty-cta"><button class="btn btn-primary btn-sm" onclick="showAddAccount()">+ Add Account</button></div></div>';
    return;
  }
  el.innerHTML = accounts.map(a => {
    const tPct = Math.min((a.today_threads / Math.max(a.target_threads || 1, 1)) * 100, 100);
    const rPct = Math.min((a.today_replies / Math.max(a.target_replies || 1, 1)) * 100, 100);
    const tColor = tPct >= 100 ? 'green' : tPct >= 50 ? 'yellow' : 'red';
    const rColor = rPct >= 100 ? 'green' : rPct >= 50 ? 'yellow' : 'red';
    return `<div class="acct-card ${App.selectedAccountId === a.id ? 'selected' : ''}" onclick="selectAccount(${a.id})">
      <div class="top">
        <div><div class="name">${a.display_name || a.username || 'Unnamed'}</div>
        <div class="username">@${a.username || '—'} ${a.niche ? '· ' + a.niche.replace(/_/g, ' ') : ''}</div></div>
        <span class="badge ${a.active ? 'badge-active' : 'badge-paused'}">${a.active ? 'Active' : 'Paused'}</span>
      </div>
      <div class="progress-row" style="padding:2px 0">
        <span class="progress-label">🧵 Threads</span>
        <div class="progress-track"><div class="progress-fill ${tColor}" style="width:${tPct}%"></div></div>
        <span class="progress-num" style="color:${tPct >= 100 ? '#22c55e' : tPct >= 50 ? '#eab308' : '#ef4444'}">${a.today_threads}${a.target_threads > 0 ? '/' + a.target_threads : ''}</span>
      </div>
      <div class="progress-row" style="padding:2px 0">
        <span class="progress-label">💬 Replies</span>
        <div class="progress-track"><div class="progress-fill ${rColor}" style="width:${rPct}%"></div></div>
        <span class="progress-num" style="color:${rPct >= 100 ? '#22c55e' : rPct >= 50 ? '#eab308' : '#ef4444'}">${a.today_replies}${a.target_replies > 0 ? '/' + a.target_replies : ''}</span>
      </div>
      <div style="font-size:11px;color:#555;margin-top:4px">📅 ${a.schedules_active} schedules</div>
    </div>`;
  }).join('');
}

async function selectAccount(id) {
  App.selectedAccountId = id;
  renderAccountGrid();
  const el = document.getElementById('detailPanel');
  el.innerHTML = skelBlock(3);

  try {
    const detail = await api(`/api/accounts/${id}/detail`);
    const scheds = await api(`/api/accounts/${id}/schedules`);
    const posts = await api(`/api/accounts/${id}/posts`);

    el.innerHTML = `
      <div class="detail-panel">
        <div class="detail-header">
          <div><div class="name">${detail.display_name || detail.username || 'Unnamed'}</div>
          <div class="username">@${detail.username || '—'} · ${detail.niche || 'universal_usa'}</div></div>
          <div class="detail-actions">
            <button class="btn btn-primary btn-sm" onclick="runAccountNow(${id})">▶️ Run Now</button>
            <button class="btn btn-primary btn-sm" onclick="toggleAccount(${id})">${detail.active ? '⏸ Pause' : '▶ Activate'}</button>
            <button class="btn btn-danger btn-sm" onclick="showDeleteAccount(${id})">🗑 Delete</button>
          </div>
        </div>

        <div class="detail-metrics">
          <div class="detail-metric"><div class="val">${detail.today_threads}/${detail.target_threads}</div><div class="lbl">Today Threads</div></div>
          <div class="detail-metric"><div class="val">${detail.today_replies}/${detail.target_replies}</div><div class="lbl">Today Replies</div></div>
          <div class="detail-metric"><div class="val">${detail.total_posts}</div><div class="lbl">Total Posts</div></div>
          <div class="detail-metric"><div class="val">${detail.total_likes}</div><div class="lbl">Total Likes</div></div>
        </div>

        <div class="detail-tabs">
          <button class="detail-tab active" onclick="switchDetailTab(this,'targets')">📈 Targets</button>
          <button class="detail-tab" onclick="switchDetailTab(this,'content')">🎨 Content</button>
          <button class="detail-tab" onclick="switchDetailTab(this,'audience')">🌐 Audience</button>
          <button class="detail-tab" onclick="switchDetailTab(this,'replies')">💬 Replies</button>
          <button class="detail-tab" onclick="switchDetailTab(this,'limits')">⚙️ Limits</button>
          <button class="detail-tab" onclick="switchDetailTab(this,'schedules')">⏰ Schedules</button>
          <button class="detail-tab" onclick="switchDetailTab(this,'posts')">📝 Posts</button>
        </div>

        ${renderAccountDetailTargets(detail)}
        ${renderAccountDetailContent(detail)}
        ${renderAccountDetailAudience(detail)}
        ${renderAccountDetailReplies(detail)}
        ${renderAccountDetailLimits(detail)}
        ${renderAccountDetailSchedules(scheds)}
        ${renderAccountDetailPosts(posts)}
      </div>`;
  } catch (e) {
    el.innerHTML = '<div class="empty">Failed to load account details</div>';
  }
}

async function toggleAccount(id) {
  try {
    await api(`/api/accounts/${id}/toggle`, { method: 'POST' });
    toast('success', 'Account toggled');
    App.accounts = await api('/api/accounts');
    selectAccount(id);
  } catch (e) { toast('error', 'Failed to toggle account'); }
}

function switchDetailTab(btn, section) {
  document.querySelectorAll('.detail-tab').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.detail-section').forEach(s => s.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('dt-' + section).classList.add('active');
}

// ── Account Add ──

function showAddAccount() {
  document.getElementById('inputThreadsUser').value = '';
  document.getElementById('inputThreadsPass').value = '';
  document.getElementById('modalError').style.display = 'none';
  detectCountry();
  document.getElementById('addModal').classList.add('show');
}

function closeModal() { document.getElementById('addModal').classList.remove('show'); }

function detectCountry() {
  const select = document.getElementById('inputCountry');
  const map = {
    'United States': 'UnitedStates', 'Canada': 'Canada', 'United Kingdom': 'UnitedKingdom',
    'Germany': 'Germany', 'France': 'France', 'Australia': 'Australia',
    'Netherlands': 'Netherlands', 'Singapore': 'Singapore', 'Japan': 'Japan',
    'India': 'India', 'Brazil': 'Brazil', 'Mexico': 'Mexico', 'Argentina': 'Argentina',
    'Spain': 'Spain', 'Italy': 'Italy', 'Sweden': 'Sweden', 'Switzerland': 'Switzerland',
    'Belgium': 'Belgium', 'Ireland': 'Ireland', 'Norway': 'Norway', 'Denmark': 'Denmark',
    'Finland': 'Finland', 'Portugal': 'Portugal', 'Austria': 'Austria', 'Poland': 'Poland',
    'Romania': 'Romania', 'Greece': 'Greece', 'Hungary': 'Hungary', 'Ukraine': 'Ukraine',
    'Turkey': 'Turkey', 'South Africa': 'SouthAfrica', 'Israel': 'Israel',
    'South Korea': 'SouthKorea', 'Malaysia': 'Malaysia', 'Indonesia': 'Indonesia',
    'Philippines': 'Philippines', 'Thailand': 'Thailand', 'Vietnam': 'Vietnam',
    'Colombia': 'Colombia', 'Chile': 'Chile', 'Peru': 'Peru', 'New Zealand': 'NewZealand',
  };
  api('/api/me/geo').then(data => { const val = map[data.country_name]; if (val) select.value = val; }).catch(() => {});
}

async function saveAccount() {
  const threadsUser = document.getElementById('inputThreadsUser').value.trim();
  const threadsPass = document.getElementById('inputThreadsPass').value;
  const country = document.getElementById('inputCountry').value;
  const btn = document.getElementById('connectBtn');
  const errEl = document.getElementById('modalError');

  if (!threadsUser || !threadsPass) { errEl.textContent = 'Please enter your Threads email and password'; errEl.style.display = 'block'; return; }

  btn.textContent = 'Logging in...';
  btn.disabled = true;

  let cookies = [];
  try {
    const result = await api('/api/threads/login', { method: 'POST', body: JSON.stringify({ username: threadsUser, password: threadsPass }) });
    if (result.ok && result.cookies) {
      cookies = Object.entries(result.cookies).map(([name, value]) => ({ name, value }));
    } else {
      errEl.textContent = result.error || 'Login failed';
      errEl.style.display = 'block';
      btn.textContent = 'Connect Account'; btn.disabled = false;
      return;
    }
  } catch (e) {
    errEl.textContent = e.message;
    errEl.style.display = 'block';
    btn.textContent = 'Connect Account'; btn.disabled = false;
    return;
  }

  const proxy = `proxy.packetstream.io:31112:redkoohh:f2f6ef17346136e8_country-${country}`;

  try {
    await api('/api/accounts', { method: 'POST', body: JSON.stringify({ username: threadsUser, display_name: threadsUser, niche: 'universal_usa', cookies, proxy }) });
    toast('success', `Connected via ${country}!`);
    closeModal();
    App.accounts = await api('/api/accounts');
    renderAccountGrid();
    if (App.accounts.length > 0) selectAccount(App.accounts[0].id);
  } catch (e) {
    errEl.textContent = e.message;
    errEl.style.display = 'block';
  }
  btn.textContent = 'Connect Account';
  btn.disabled = false;
}

// ── Delete Account ──

function showDeleteAccount(id) { App.deleteTargetId = id; document.getElementById('deleteModal').classList.add('show'); }
function closeDeleteModal() { document.getElementById('deleteModal').classList.remove('show'); App.deleteTargetId = null; }

async function confirmDeleteAccount() {
  if (!App.deleteTargetId) return;
  try {
    await api(`/api/accounts/${App.deleteTargetId}`, { method: 'DELETE' });
    toast('success', 'Account deleted');
    closeDeleteModal();
    App.selectedAccountId = null;
    App.accounts = await api('/api/accounts');
    renderAccountGrid();
    document.getElementById('detailPanel').innerHTML = '<div class="empty">Select an account to view details</div>';
  } catch (e) {
    document.getElementById('deleteError').textContent = e.message;
    document.getElementById('deleteError').style.display = 'block';
  }
}

// ── Refresh ──

function updateLastUpdated() {
  document.getElementById('lastUpdated').innerHTML = `Last updated: ${new Date().toLocaleTimeString()} <button onclick="refreshAll()">↻ Refresh</button>`;
}

async function refreshAll() {
  App.accounts = await api('/api/accounts');
  renderAccountGrid();
  updateLastUpdated();
  if (App.selectedAccountId && App.accounts.find(a => a.id === App.selectedAccountId)) {
    selectAccount(App.selectedAccountId);
  } else if (App.accounts.length) {
    selectAccount(App.accounts[0].id);
  }
  toast('info', 'Refreshed');
}

async function refreshAccounts() {
  if (!App.accounts.length) return;
  App.accounts = await api('/api/accounts');
  renderAccountGrid();
  updateLastUpdated();
  if (App.selectedAccountId) {
    const exists = App.accounts.find(a => a.id === App.selectedAccountId);
    if (exists) selectAccount(App.selectedAccountId);
    else { App.selectedAccountId = null; document.getElementById('detailPanel').innerHTML = '<div class="empty">Select an account to view details</div>'; }
  }
}

// ── Run Now ──

async function runAccountNow(id) {
  const btn = event.target;
  btn.textContent = '⏳ Running...';
  btn.disabled = true;
  try {
    const r = await api(`/api/scheduler/run-now/${id}`, { method: 'POST' });
    toast('success', `Run triggered — ${r.slots_triggered} slot(s)`);
    // Refresh after a few seconds so results show
    setTimeout(() => refreshAccounts(), 3000);
  } catch (e) {
    toast('error', e.message || 'Failed to run scheduler');
  }
  btn.textContent = '▶️ Run Now';
  btn.disabled = false;
}

// ── Filter ──

function filterAccounts() {
  const q = (document.getElementById('accountSearch').value || '').toLowerCase();
  document.querySelectorAll('#accountGrid .acct-card').forEach(c => {
    const text = c.textContent.toLowerCase();
    const isActive = !c.querySelector('.badge-paused');
    const matchesFilter = App.filterMode === 'all' || (App.filterMode === 'active' && isActive) || (App.filterMode === 'paused' && !isActive);
    c.style.display = matchesFilter && (!q || text.includes(q)) ? '' : 'none';
  });
}

function toggleFilter(el, mode) {
  App.filterMode = mode;
  document.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
  el.classList.add('active');
  filterAccounts();
}

function exportCSV() {
  if (!App.accounts.length) { toast('error', 'No accounts to export'); return; }
  let csv = 'Username,Display Name,Niche,Status,Threads Today,Replies Today\n';
  App.accounts.forEach(a => csv += `${a.username || ''},${a.display_name || ''},${a.niche || ''},${a.active ? 'Active' : 'Paused'},${a.today_threads},${a.today_replies}\n`);
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a'); a.href = url; a.download = 'threads_accounts.csv'; a.click();
  URL.revokeObjectURL(url);
  toast('success', 'CSV exported');
}
