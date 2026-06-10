// ── API helper + toast + global state ──
window.App = {
  accounts: [],
  selectedAccountId: null,
  deleteTargetId: null,
  filterMode: 'all',
  refreshTimer: null,
};

window.toast = (type, msg) => {
  const c = document.getElementById('toastContainer');
  const t = document.createElement('div');
  t.className = 'toast ' + type;
  t.textContent = msg;
  c.appendChild(t);
  requestAnimationFrame(() => t.classList.add('show'));
  setTimeout(() => { t.classList.remove('show'); setTimeout(() => t.remove(), 300) }, 3500);
};

window.api = async (path, opts = {}) => {
  const r = await fetch(path, { ...opts, headers: { 'Content-Type': 'application/json', ...opts.headers } });
  const data = await r.json();
  if (!r.ok && !data.ok) throw new Error(data.error || 'Request failed');
  return data;
};

window.tip = (text) => `<span class="help-tip">?<span class="tip-text">${text}</span></span>`;

window.toLocalTime = (utcHour) => {
  const now = new Date();
  const utcDate = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(), utcHour, 0, 0));
  return utcDate.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }) + ' ';
};

window.switchTab = (name) => {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
  const btn = document.querySelector(`.tab-btn[data-tab="${name}"]`);
  if (btn) btn.classList.add('active');
  document.getElementById('tab-' + name).classList.add('active');
  if (name === 'accounts') refreshAccounts();
  if (name === 'analytics') loadAnalytics();
};

window.skelLine = (n = 3) => Array.from({ length: n }, (_, i) => `<div class="skel skel-line" style="width:${60 + Math.random() * 30}%"></div>`).join('');
window.skelBlock = (n = 2) => Array.from({ length: n }, () => '<div class="skel skel-block"></div>').join('');
