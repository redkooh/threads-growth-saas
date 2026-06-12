// ── Analytics tab ──

async function loadAnalytics() {
  const statsEl = document.getElementById('analyticsStats');
  const chartEl = document.getElementById('analyticsChart');
  const acctsEl = document.getElementById('analyticsAccounts');
  const { accounts } = App;

  try {
    const stats = await api('/api/stats');
    const history = await api('/api/stats/history');
    const allPosts = await api('/api/posts');

    // ── Stats row ──
    let trendHtml = '';
    if (history.length >= 2) {
      const today = history[history.length - 1];
      const yesterday = history[history.length - 2];
      const diff = today.posts - yesterday.posts;
      const diffLikes = today.likes - yesterday.likes;
      const trendClass = diff > 0 ? 'trend-up' : diff < 0 ? 'trend-down' : 'trend-flat';
      const arrow = diff > 0 ? '↑' : diff < 0 ? '↓' : '→';
      const likesArrow = diffLikes > 0 ? '↑' : diffLikes < 0 ? '↓' : '→';
      const likesClass = diffLikes > 0 ? 'trend-up' : diffLikes < 0 ? 'trend-down' : 'trend-flat';
      trendHtml = `
        <div class="day-compare">
          <span class="${trendClass}">Posts: ${arrow} ${Math.abs(diff)} vs yesterday</span>
          <span class="${likesClass}">Likes: ${likesArrow} ${Math.abs(diffLikes)} vs yesterday</span>
        </div>`;
    }

    statsEl.innerHTML = `
      <div class="stat-card"><div class="val">${stats.today_threads}</div><div class="lbl">Threads Today</div></div>
      <div class="stat-card"><div class="val">${stats.today_replies}</div><div class="lbl">Replies Today</div></div>
      <div class="stat-card"><div class="val">${stats.active_accounts}/${stats.accounts}</div><div class="lbl">Active Accounts</div></div>
      <div class="stat-card"><div class="val">${history.length ? history.reduce((s,h) => s + h.likes, 0) : 0}</div><div class="lbl">Total Likes (14d)</div></div>
    `;

    // ── Best performing post ──
    const postsWithLikes = allPosts.filter(p => p.likes > 0).sort((a, b) => (b.likes || 0) - (a.likes || 0));
    let bestHtml = '';
    if (postsWithLikes.length) {
      const best = postsWithLikes[0];
      bestHtml = `
        <div class="analytics-best">
          <div class="best-label">🏆 Best Performing Post</div>
          <div class="best-content">
            <div class="best-text">${best.preview || '(no preview)'}</div>
            <div class="best-stats">
              <span>❤️ ${best.likes}</span>
              <span>💬 ${best.replies || 0}</span>
              <span class="post-type ${best.type}">${best.type.replace('_', ' ')}</span>
            </div>
          </div>
          <div style="font-size:11px;color:#555;margin-top:4px">${best.posted_at ? new Date(best.posted_at).toLocaleDateString() : ''} ${best.code ? '· t/' + best.code : ''}</div>
        </div>`;
    }

    // ── Chart ──
    let chartInner = '';
    if (history.length) {
      const maxPosts = Math.max(...history.map(h => h.posts), 1);
      chartInner = '<div class="chart-bars">' + history.slice().reverse().map(h => {
        const pct = Math.max((h.posts / maxPosts) * 100, 4);
        return `<div class="chart-bar" style="height:${pct}%" title="${h.day}: ${h.posts} posts, ${h.likes} likes">
          <div class="bar-val">${h.posts}</div>
          <div class="bar-lbl">${h.day.slice(5)}</div>
        </div>`;
      }).join('') + '</div>' + trendHtml;
    } else {
      chartInner = '<div class="empty">No data yet — posts will appear once your schedules run</div>';
    }
    chartEl.innerHTML = bestHtml + chartInner;

    // ── Per-account list ──
    if (accounts.length) {
      const sorted = [...accounts].sort((a, b) => (b.today_threads + b.today_replies) - (a.today_threads + a.today_replies));
      acctsEl.innerHTML = sorted.map(a => `
        <div class="post-item" style="display:flex;justify-content:space-between;align-items:center">
          <div>
            <strong>${a.display_name || a.username || 'Unnamed'}</strong>
            <span style="color:#555;font-size:12px;margin-left:8px">@${a.username || '—'}</span>
            ${a.niche ? `<span style="font-size:11px;color:#555;margin-left:6px">· ${a.niche.replace(/_/g, ' ')}</span>` : ''}
          </div>
          <div style="display:flex;gap:16px;font-size:13px;color:#888;align-items:center">
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
