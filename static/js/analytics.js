// ── Analytics tab ──

async function loadAnalytics() {
  const statsEl = document.getElementById('analyticsStats');
  const chartEl = document.getElementById('analyticsChart');
  const acctsEl = document.getElementById('analyticsAccounts');
  const { accounts } = App;

  try {
    const stats = await api('/api/stats');
    statsEl.innerHTML = `
      <div class="stat-card"><div class="val">${stats.today_threads}</div><div class="lbl">Threads Today</div></div>
      <div class="stat-card"><div class="val">${stats.today_replies}</div><div class="lbl">Replies Today</div></div>
      <div class="stat-card"><div class="val">${stats.active_accounts}/${stats.accounts}</div><div class="lbl">Active Accounts</div></div>
    `;

    const history = await api('/api/stats/history');
    if (history.length) {
      const maxPosts = Math.max(...history.map(h => h.posts), 1);
      chartEl.innerHTML = '<div class="chart-bars">' + history.slice().reverse().map(h => {
        const pct = Math.max((h.posts / maxPosts) * 100, 4);
        return `<div class="chart-bar" style="height:${pct}%" title="${h.day}: ${h.posts} posts, ${h.likes} likes">
          <div class="bar-val">${h.posts}</div>
          <div class="bar-lbl">${h.day.slice(5)}</div>
        </div>`;
      }).join('') + '</div>';
    } else {
      chartEl.innerHTML = '<div class="empty">No data yet — posts will appear once your schedules run</div>';
    }

    if (accounts.length) {
      acctsEl.innerHTML = accounts.map(a => `
        <div class="post-item" style="display:flex;justify-content:space-between;align-items:center">
          <div><strong>${a.display_name || a.username || 'Unnamed'}</strong>
            <span style="color:#555;font-size:12px;margin-left:8px">@${a.username || '—'}</span>
          </div>
          <div style="display:flex;gap:16px;font-size:13px;color:#888">
            <span>🧵 ${a.today_threads}</span>
            <span>💬 ${a.today_replies}</span>
            <span class="badge ${a.active ? 'badge-active' : 'badge-paused'}">${a.active ? 'Active' : 'Paused'}</span>
          </div>
        </div>
      `).join('');
    } else {
      acctsEl.innerHTML = '<div class="empty">Add an account to see performance</div>';
    }
  } catch (e) { statsEl.innerHTML = '<div class="empty">Failed to load analytics</div>'; }
}
