// ── Accounts tab: Simplified for non-techie users ──

function renderAccountGrid() {
  const el = document.getElementById('accountGrid');
  const accounts = App.accounts;
  if (!accounts.length) {
    el.innerHTML = '<div class="empty" style="grid-column:1/-1"><div class="empty-icon">📱</div>No accounts yet<div class="empty-cta"><button class="btn btn-primary btn-sm" onclick="showAddAccount()">+ Add Account</button></div></div>';
    return;
  }
  el.innerHTML = accounts.map(a => {
    const done = a.today_threads >= a.target_threads && a.today_replies >= a.target_replies;
    return `<div class="acct-card ${App.selectedAccountId === a.id ? 'selected' : ''}" data-id="${a.id}" onclick="selectAccount(${a.id})">
      <div class="top">
        <div><div class="name">${a.display_name || a.username || 'Unnamed'}</div>
        <div class="username">@${a.username || '—'}</div></div>
        <span class="badge ${a.active ? 'badge-active' : 'badge-paused'}">${a.active ? 'Active' : 'Paused'}</span>
      </div>
      <div class="mini-stats">
        <span class="mini-stat ${a.today_threads >= a.target_threads ? 'done' : ''}">🧵 ${a.today_threads}/${a.target_threads}</span>
        <span class="mini-stat ${a.today_replies >= a.target_replies ? 'done' : ''}">💬 ${a.today_replies}/${a.target_replies}</span>
        <span class="mini-stat">📅 ${a.schedules_active}</span>
        <button class="quick-setup-btn" onclick="event.stopPropagation();openSetupWizard(${a.id})" title="Quick Setup">⚡</button>
      </div>
      ${done ? '<div class="done-badge">✅ All caught up!</div>' : ''}
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

    const activeScheds = scheds.filter(s => s.enabled).length;

    el.innerHTML = `
      <div class="detail-panel">
        <div class="detail-header">
          <div class="detail-name-row">
            <div class="name">${detail.display_name || detail.username || 'Unnamed'}</div>
            <span class="badge ${detail.active ? 'badge-active' : 'badge-paused'}">${detail.active ? 'Active' : 'Paused'}</span>
            <span class="detail-username mobile-hide">@${detail.username || '—'}</span>
          </div>
          <div class="detail-actions">
            <button class="btn btn-primary btn-sm mobile-hide" onclick="openSetupWizard(${id})">⚡ Quick Setup</button>
            <button class="btn btn-sm" style="background:transparent;border:1px solid #2a2a3a;color:#aaa" onclick="toggleAccount(${id})">${detail.active ? '⏸' : '▶'}</button>
            <div class="more-menu" onclick="toggleMoreMenu(this)">
              <button class="btn btn-sm" style="background:transparent;border:1px solid #2a2a3a;color:#888">•••</button>
              <div class="more-menu-items" style="display:none">
                <button onclick="openSetupWizard(${id})">⚡ Quick Setup</button>
                <button onclick="runAccountNow(${id})">▶️ Run Now</button>
                <button onclick="exportSingleCSV(${id})">📥 Export</button>
                <button onclick="showDeleteAccount(${id})" style="color:#ef4444">🗑 Delete</button>
              </div>
            </div>
          </div>
        </div>

        <div class="detail-metrics">
          <div class="detail-metric big">
            <div class="val ${detail.today_threads >= detail.target_threads ? 'green' : ''}">${detail.today_threads}/${detail.target_threads}</div>
            <div class="lbl">threads today</div>
          </div>
          <div class="detail-metric big">
            <div class="val ${detail.today_replies >= detail.target_replies ? 'green' : ''}">${detail.today_replies}/${detail.target_replies}</div>
            <div class="lbl">replies today</div>
          </div>
          <div class="detail-metric small"><div class="val">${detail.total_posts}</div><div class="lbl">total</div></div>
          <div class="detail-metric small"><div class="val">❤️ ${detail.total_likes}</div><div class="lbl">likes</div></div>
          <div class="detail-metric small"><div class="val">🕐 ${activeScheds}</div><div class="lbl">slots</div></div>
        </div>

        <div class="detail-tabs">
          <button class="detail-tab active" onclick="switchDetailTab(this,'content')">🎨 Style</button>
          <button class="detail-tab" onclick="switchDetailTab(this,'schedules')">⏰ Posting</button>
          <button class="detail-tab" onclick="switchDetailTab(this,'targets')">📊 Goals</button>
          <button class="detail-tab" onclick="switchDetailTab(this,'posts')">📝 Activity</button>
          <button class="detail-tab" onclick="switchDetailTab(this,'logs')">📋 Logs</button>
          <button class="detail-tab" onclick="switchDetailTab(this,'advanced')">⚙️ More</button>
        </div>

        ${renderContentTab(detail)}
        ${renderSchedulesTab(scheds)}
        ${renderGoalsTab(detail)}
        ${renderPostsTab(posts)}
        <div class="detail-section" id="dt-logs">${renderLogsTab(detail.id)}</div>
        <div class="detail-section" id="dt-advanced">${renderAdvancedTab(detail)}</div>
      </div>`;
  } catch (e) {
    el.innerHTML = '<div class="empty">Couldn\'t load account — hit refresh</div>';
  }
}

async function toggleAccount(id) {
  try {
    await api(`/api/accounts/${id}/toggle`, { method: 'POST' });
    toast('success', 'Account toggled');
    App.accounts = await api('/api/accounts');
    selectAccount(id);
  } catch (e) { toast('error', 'Failed'); }
}

function switchDetailTab(btn, section) {
  document.querySelectorAll('.detail-tab').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.detail-section').forEach(s => s.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('dt-' + section).classList.add('active');
}

function toggleMoreMenu(el) {
  const menu = el.querySelector('.more-menu-items');
  menu.style.display = menu.style.display === 'none' ? 'flex' : 'none';
  document.addEventListener('click', function close(e) { if (!el.contains(e.target)) { menu.style.display = 'none'; document.removeEventListener('click', close); } });
}

// ── Content tab (vibe cards + collapsed advanced) ──
function renderContentTab(detail) {
  const currentVibe = Object.entries(VIBE_PRESETS).find(([k, v]) =>
    v.content_style === detail.content_style && v.post_tone === detail.post_tone
  );
  const currentVibeName = currentVibe ? currentVibe[0] : '';

  const cards = [
    { id:'casual-lifestyle', emoji:'😎', name:'Casual', desc:'Friendly bestie, funny & relatable' },
    { id:'hustle-culture', emoji:'🚀', name:'Hustler', desc:'Ambitious entrepreneur, growth-focused' },
    { id:'professional-expert', emoji:'💼', name:'Expert', desc:'Professional, authoritative insights' },
    { id:'hot-takes', emoji:'🌶️', name:'Hot Takes', desc:'Spicy opinions that spark debate' },
    { id:'educational', emoji:'📚', name:'Teacher', desc:'Educate & explain, deep dives' },
    { id:'funny', emoji:'😂', name:'Joker', desc:'Humor & wit, entertain the crowd' },
  ];

  return `<div class="detail-section active" id="dt-content">
    <div class="section-hdr"><span>Choose a style — the AI matches your voice</span> <span class="local-time-badge" onclick="toggleVibeAdvanced(this)" style="cursor:pointer">🔧 Fine-tune</span></div>
    <div class="vibe-picker" id="detailVibePicker" style="grid-template-columns:repeat(3,1fr)">
      ${cards.map(c => `<div class="vibe-card ${currentVibeName === c.id ? 'selected' : ''}" data-vibe="${c.id}" onclick="selectDetailVibe(this,'${c.id}');applyVibeFromDetail()">
        <div class="vibe-emoji">${c.emoji}</div>
        <div class="vibe-name">${c.name}</div>
        <div class="vibe-desc">${c.desc}</div>
      </div>`).join('')}
    </div>
    <div id="contentAdvanced" style="display:none" class="advanced-panel">
      ${renderAdvancedContentForm(detail)}
    </div>
  </div>`;
}

function toggleVibeAdvanced(btn) {
  const panel = document.getElementById('contentAdvanced');
  panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
  btn.textContent = panel.style.display === 'block' ? '🔧 Hide fine-tune' : '🔧 Fine-tune';
}

function renderAdvancedContentForm(detail) {
  const linkPromo = detail.plan_config.feature_link_promo
    ? `<label class="toggle-switch" style="margin:8px 0"><input type="checkbox" id="linksEnabled" ${detail.links_enabled?'checked':''}><span class="toggle-slider"></span> Promote link in bio</label>`
    : '<div style="font-size:12px;color:#555;margin:8px 0">🔒 Link promotion — Growth+ plan</div>';
  return `<div class="form-row">
    <div class="form-group"><label>Style</label><select id="contentStyle">${['auto','casual','viral','professional','educational','controversial'].map(s => `<option value="${s}" ${(detail.content_style||'auto')===s?'selected':''}>${s === 'auto' ? '🎯 Auto (AI picks)' : s}</option>`).join('')}</select></div>
    <div class="form-group"><label>Tone</label><select id="postTone">${['friendly','professional','sarcastic','inspirational','controversial'].map(s => `<option value="${s}" ${detail.post_tone===s?'selected':''}>${s}</option>`).join('')}</select></div>
    <div class="form-group"><label>Length</label><select id="postLength">${['auto','short','medium','long'].map(s => `<option value="${s}" ${(detail.post_length||'auto')===s?'selected':''}>${s === 'auto' ? '🎯 Auto (AI picks)' : s}</option>`).join('')}</select></div>
    <div class="form-group"><label>Format</label><select id="postFormat">${['text','image','mixed'].map(s => `<option value="${s}" ${detail.post_format===s?'selected':''}>${s}</option>`).join('')}</select></div>
  </div>
  <div style="font-size:11px;color:#a855f7;margin:6px 0 4px;padding:6px 8px;background:rgba(168,85,247,0.06);border-radius:6px;border-left:3px solid #a855f7">
    🤖 Smart mode — AI automatically picks style, tone, and length based on your topic and niche
  </div>
  <div class="form-group"><label>Topics to post about</label><textarea id="topicKeywords" placeholder="e.g. AI, startups, fitness">${detail.topic_keywords||''}</textarea></div>
  <div class="form-group"><label>Topics to avoid</label><textarea id="avoidTopics" placeholder="e.g. politics, religion">${detail.avoid_topics||''}</textarea></div>
  <div class="form-group"><label>Vibe description</label><input type="text" id="vibeInput" value="${detail.vibe||''}" placeholder="Custom voice (optional)"></div>
  ${linkPromo}
  <button class="btn btn-primary btn-sm" onclick="saveAccountSettings(${detail.id})">💾 Save</button>`;
}

// ── Schedules tab — redesigned for non-techies ──
function renderSchedulesTab(scheds) {
  const existingHours = scheds.filter(s=>s.enabled).map(s=>s.hour_utc);
  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const offset = -(new Date().getTimezoneOffset() / 60);
  const localScheds = scheds.sort((a,b)=>a.hour_utc-b.hour_utc).map(s => {
    const localHour = Math.round(((s.hour_utc + offset + 24) % 24));
    return {...s, localHour};
  });

  // Generate 24h timeline dots
  let timelineHtml = '';
  for (let h = 0; h < 24; h++) {
    const isActive = localScheds.some(s => s.enabled && s.localHour === h);
    const label = h === 0 ? '12a' : h === 12 ? '12p' : h < 12 ? `${h}a` : `${h-12}p`;
    timelineHtml += `<div class="tl-hour ${isActive?'tl-active':''}" title="${h}:00 ${tz}">
      <div class="tl-dot ${isActive?'tl-dot-on':''}"></div>
      <div class="tl-label">${label}</div>
    </div>`;
  }

  const presets = [
    { id: 'popular', emoji: '📊', label: 'Popular Times', times: '9am · 12pm · 4pm · 8pm' },
    { id: 'morning', emoji: '🌅', label: 'Early Bird', times: '6am · 8am · 10am · 12pm' },
    { id: 'evening', emoji: '🌙', label: 'Evening Crew', times: '5pm · 7pm · 9pm · 11pm' },
    { id: 'spread', emoji: '📋', label: 'Spread Out', times: '6am · 10am · 2pm · 6pm · 10pm' },
  ];

  const activePreset = presets.find(p => {
    const data = SCHEDULE_PRESETS[p.id];
    return data && existingHours.length === data.localHours.length &&
      data.localHours.every(h => existingHours.includes(Math.round((h - offset + 24) % 24) % 24));
  });

  return `<div class="detail-section" id="dt-schedules">
    <div class="section-hdr" style="margin-bottom:4px"><span>⏰ When does your AI post?</span></div>
    <div style="font-size:12px;color:#666;margin-bottom:12px">Pick times your audience is most active. Your timezone: <strong>${tz}</strong></div>

    <div style="font-size:12px;color:#888;margin-bottom:6px;">Quick pick a schedule:</div>
    <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:6px;margin-bottom:14px">
      ${presets.map(p => `
        <div class="sched-preset-card ${activePreset?.id === p.id ? 'selected' : ''}" onclick="applySchedPreset(this,'${p.id}')" style="padding:10px;border-radius:10px">
          <div style="font-size:13px;font-weight:600;color:#e0e0e0">${p.emoji} ${p.label}</div>
          <div style="font-size:11px;color:#a855f7">${p.times}</div>
        </div>`).join('')}
    </div>

    <div style="font-size:12px;color:#888;margin-bottom:6px;">Your active posting times (${tz}):</div>
    <div class="timeline">${timelineHtml}</div>

    <div class="sched-list">
      ${localScheds.length ? localScheds.map(s => {
        const ampm = s.localHour === 0 ? '12am' : s.localHour === 12 ? '12pm' : s.localHour < 12 ? `${s.localHour}am` : `${s.localHour-12}pm`;
        return `<div class="sched-item">
          <div class="sched-info">
            <span style="font-weight:600;font-size:14px;width:70px">${ampm}</span>
            <span class="sched-status" style="color:${s.enabled?'#22c55e':'#555'}">${s.enabled ? '✅ Posting' : '⏸️ Skipped'}</span>
          </div>
          <label class="toggle-switch" style="font-size:0"><input type="checkbox" ${s.enabled?'checked':''} onchange="toggleSchedule(${App.selectedAccountId},${s.id})"><span class="toggle-slider"></span></label>
        </div>`;
      }).join('') : '<div class="empty" style="padding:12px">No times set — pick a quick schedule above</div>'}
    </div>
  </div>`;
}

// ── Goals tab (targets only) ──
function renderGoalsTab(detail) {
  return `<div class="detail-section" id="dt-targets">
    <div class="section-hdr"><span>Daily posting goals</span></div>
    <div class="form-group"><label>🧵 Threads per day</label>${sliderHtml('target_threads', detail.target_threads, 0, 10)}<div class="desc">${detail.today_threads} posted today</div></div>
    <div class="form-group"><label>💬 Replies per day</label>${sliderHtml('target_replies', detail.target_replies, 0, 50)}<div class="desc">${detail.today_replies} replied today</div></div>
    <button class="btn btn-primary btn-sm" onclick="saveAccountSettings(${detail.id})">💾 Save Goals</button>
  </div>`;
}

// ── Posts tab ──
function renderPostsTab(posts) {
  const REL_TIME = (iso) => {
    if (!iso) return '';
    const d = new Date(iso);
    const diff = (new Date() - d) / 1000;
    if (diff < 60) return 'just now';
    if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
    if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
    if (diff < 172800) return 'yesterday';
    return Math.floor(diff / 86400) + 'd ago';
  };
  const ICON = { 'thread': '🧵', 'fun_fact': '💡', 'reply': '💬', 'image': '🖼️', 'quote': '🔄' };
  return `<div class="detail-section" id="dt-posts">
    ${posts.length ? posts.map((p, i) => {
      const icon = ICON[p.type] || '📄';
      const lastLine = i === posts.length - 1 ? ' style="background:transparent;min-height:0"' : '';
      return `<div class="feed-item" style="padding:0">
        <div class="feed-left">
          <div class="feed-icon ${p.type}">${icon}</div>
          <div class="feed-line"${lastLine}></div>
        </div>
        <div class="feed-card">
          <div class="feed-card-top">
            <div class="feed-account-row">
              <span class="feed-type-badge ${p.type}">${p.type.replace(/_/g, ' ')}</span>
              ${p.code ? `<span class="feed-code">t/${p.code}</span>` : ''}
            </div>
            <span class="feed-time">${REL_TIME(p.posted_at)}</span>
          </div>
          <div class="feed-preview">${escHtml(p.preview || '')}</div>
          <div class="feed-stats"><span>❤️ ${p.likes||0}</span><span>💬 ${p.replies||0}</span></div>
        </div>
      </div>`;
    }).join('') : '<div class="feed-empty"><div class="empty-icon">📝</div>No posts yet</div>'}
  </div>`;
}

// ── Logs tab (activity timeline) ──
function renderLogsTab(aid) {
  api(`/api/accounts/${aid}/activity?limit=50`).then(data => {
    const el = document.getElementById('dt-logs');
    if (!el) return;
    el.innerHTML = renderLogsInner(data.items || [], data.total || 0);
  }).catch(() => {
    const el = document.getElementById('dt-logs');
    if (el) el.innerHTML = '<div class="feed-empty"><div class="empty-icon">⚠️</div>Failed to load logs</div>';
  });
  return '<div class="feed-empty"><div class="empty-icon">⏳</div>Loading...</div>';
}

function renderLogsInner(items, total) {
  if (!items.length) return '<div class="feed-empty"><div class="empty-icon">📋</div>No activity yet — logs appear as the bot runs</div>';

  const FILTERS = ['all','post','reply','style_learn','style_upgrade','auth_fail','error','schedule_skip'];
  const FILTER_EMOJIS = {'all':'📋','post':'🧵','reply':'💬','style_learn':'🧠','style_upgrade':'⬆️','auth_fail':'🔴','error':'⚠️','schedule_skip':'⏭️'};

  const REL_TIME = (iso) => {
    if (!iso) return '';
    const d = new Date(iso);
    const diff = (new Date() - d) / 1000;
    if (diff < 60) return 'just now';
    if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
    if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
    if (diff < 172800) return 'yesterday';
    return Math.floor(diff / 86400) + 'd ago';
  };

  const ICONS = {
    'post': '🧵', 'reply': '💬', 'follow': '👥', 'dm': '✉️',
    'style_learn': '🧠', 'style_upgrade': '⬆️',
    'auth_fail': '🔴', 'post_error': '❌', 'reply_error': '❌',
    'schedule_skip': '⏭️', 'error': '⚠️',
    'fun_fact': '💡',
  };

  return `
    <div style="display:flex;gap:4px;flex-wrap:wrap;margin-bottom:8px">
      ${FILTERS.map(f => `<span class="filter-chip ${f==='all'?'active':''}" data-logfilter="${f}" onclick="switchLogFilter(this,'${f}')">${FILTER_EMOJIS[f]||'📄'} ${f.replace(/_/g,' ')}</span>`).join('')}
    </div>
    <div id="logsCounter" style="font-size:11px;color:#888;margin:0 0 8px">${total} total events</div>
    ${items.map((p, i) => {
      const icon = ICONS[p.action] || '📄';
      const isError = p.action.endsWith('_error') || p.action === 'error' || p.action === 'auth_fail';
      const isSuccess = p.action === 'post' || p.action === 'reply' || p.action.startsWith('style_');
      return `<div class="feed-item" style="padding:0">
        <div class="feed-left">
          <div class="feed-icon ${isError ? 'error' : isSuccess ? 'success' : ''}" style="${isError ? 'color:#ef4444' : isSuccess ? 'color:#22c55e' : ''}">${icon}</div>
          <div class="feed-line"></div>
        </div>
        <div class="feed-card">
          <div class="feed-card-top">
            <span class="feed-type-badge" style="${isError ? 'background:rgba(239,68,68,0.15);color:#ef4444' : isSuccess ? 'background:rgba(34,197,94,0.15);color:#22c55e' : 'background:rgba(113,113,122,0.15);color:#a1a1aa'}">${p.action.replace(/_/g, ' ')}</span>
            <span class="feed-time">${REL_TIME(p.posted_at)}</span>
          </div>
          <div class="feed-preview">${escHtml(p.detail)}</div>
          ${p.thread_code ? `<a href="https://threads.net/t/${p.thread_code}" target="_blank" style="font-size:11px;color:#a855f7;text-decoration:none">View thread →</a>` : ''}
        </div>
      </div>`;
    }).join('')}
  `;
}

function switchLogFilter(el, filter) {
  document.querySelectorAll('#dt-logs .filter-chip').forEach(c => c.classList.remove('active'));
  el.classList.add('active');
  const aid = App.selectedAccountId;
  if (!aid) return;
  api(`/api/accounts/${aid}/activity?limit=50${filter !== 'all' ? '&action=' + filter : ''}`).then(data => {
    document.getElementById('dt-logs').innerHTML = renderLogsInner(data.items || [], data.total || 0);
  });
}

// ── Advanced tab (audience, replies, limits, tags, risk, presets collapsed) ──
function renderAdvancedTab(detail) {
  return `
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px">
      <button class="filter-chip active" onclick="switchAdvancedSub(this,'audience')">🌐 Audience</button>
      <button class="filter-chip" onclick="switchAdvancedSub(this,'replies')">💬 Replies</button>
      <button class="filter-chip" onclick="switchAdvancedSub(this,'style')">🎨 Style</button>
      <button class="filter-chip" onclick="switchAdvancedSub(this,'presets')">💾 Presets</button>
      <button class="filter-chip" onclick="switchAdvancedSub(this,'timeline')">🕐 Timeline</button>
    </div>
    <div class="advanced-sub active" id="ad-audience">
      <div class="section-hdr" style="font-size:12px;margin-bottom:8px"><span>🌐 What's your account about?</span></div>
      <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:4px;margin-bottom:8px" id="nicheGrid">
        ${Object.entries(AUDIENCE_PRESETS).map(([k, v]) => {
          const emojis = {'general':'🌍','tech-saas':'💻','fitness-health':'💪','business':'📊','finance-investing':'💰','gaming':'🎮','fashion-beauty':'💅','food-cooking':'🍳','travel':'✈️','parenting':'👶','music':'🎵','sports':'⚽','motivation':'🔥'};
          const labelMap = {'general':'General','tech-saas':'Tech & SaaS','fitness-health':'Fitness','business':'Business','finance-investing':'Finance','gaming':'Gaming','fashion-beauty':'Fashion','food-cooking':'Food','travel':'Travel','parenting':'Parenting','music':'Music','sports':'Sports','motivation':'Motivation'};
          const isSelected = detail.target_niche === v.target_niche || (!detail.target_niche && k === 'general');
          return `<div class="audience-card ${isSelected?'selected':''}" data-niche="${k}" onclick="selectNicheCard(this)" style="padding:8px 10px;border-radius:8px">
            <div style="display:flex;align-items:center;gap:8px">
              <span style="font-size:18px">${emojis[k]||'🌐'}</span>
              <span style="font-size:12px;font-weight:600;color:#e0e0e0">${labelMap[k]||k}</span>
            </div>
          </div>`;
        }).join('')}
      </div>
      <div style="font-size:11px;color:#666;margin:0 0 8px">📍 Location is controlled by proxy — pick the right country when connecting</div>
    </div>
    <div class="advanced-sub" id="ad-style">
      <div style="margin-bottom:10px;font-size:12px;color:#aaa;line-height:1.5">AI reads your Threads posts and writes like YOU — tone, slang, emoji habits, everything. Keep upgrading as your voice evolves.</div>
      <div id="styleStatus">
        ${detail.writing_style ? `<div style="background:rgba(34,197,94,0.08);border:1px solid rgba(34,197,94,0.2);border-radius:8px;padding:10px 12px;font-size:12px;color:#22c55e;margin-bottom:10px">✅ Style learned</div>` : '<div style="background:rgba(168,85,247,0.06);border:1px solid rgba(168,85,247,0.15);border-radius:8px;padding:10px 12px;font-size:12px;color:#a855f7;margin-bottom:10px">🤖 Not yet learned — click below to analyze your last 70 posts</div>'}
      </div>
      <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px">
        <button class="btn btn-primary btn-sm" onclick="learnStyle(${detail.id})">🧠 ${detail.writing_style ? 'Re-learn' : 'Learn My Style'}</button>
        ${detail.writing_style ? `<button class="btn btn-primary btn-sm" onclick="showUpgradeStyle(${detail.id})">⬆️ Upgrade</button>` : ''}
        ${detail.writing_style ? `<button class="btn btn-primary btn-sm" onclick="toggleStyleEdit(${detail.id})">✏️ Edit</button>` : ''}
      </div>
      <div id="styleResult" style="font-size:12px;color:#888;margin-bottom:8px"></div>

      <!-- Upgrade panel (hidden) -->
      <div id="styleUpgradePanel" style="display:none;background:#12121a;border:1px solid #2a2a3a;border-radius:10px;padding:12px;margin-bottom:10px">
        <div style="font-size:13px;font-weight:600;margin-bottom:8px">⬆️ Upgrade Your Style</div>
        <div style="font-size:12px;color:#aaa;margin-bottom:10px;line-height:1.5">Tell the AI how you want to evolve your voice. Pick a direction or write your own:</div>
        <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px" id="upgradePresets">
          <button class="filter-chip" onclick="setUpgradeDir(this,'Make it funnier and more casual')">😂 Funnier</button>
          <button class="filter-chip" onclick="setUpgradeDir(this,'Make it more professional and authoritative')">💼 Professional</button>
          <button class="filter-chip" onclick="setUpgradeDir(this,'More hot takes — spicier, controversial')">🌶️ Spicier</button>
          <button class="filter-chip" onclick="setUpgradeDir(this,'Shorter punchier lines, less text')">✂️ Shorter</button>
          <button class="filter-chip" onclick="setUpgradeDir(this,'More emojis and visual style')">😎 More emoji</button>
          <button class="filter-chip" onclick="setUpgradeDir(this,'Warmer and more inspirational')">✨ Inspirational</button>
        </div>
        <textarea id="upgradeCustomDir" placeholder="Or write your own direction..." style="width:100%;padding:8px;border-radius:8px;border:1px solid #2a2a3a;background:#0f0f13;color:#e0e0e0;font-size:12px;min-height:50px;resize:vertical;outline:none;margin-bottom:8px"></textarea>
        <div style="display:flex;gap:6px">
          <button class="btn btn-primary btn-sm" onclick="upgradeStyle(${detail.id})">⬆️ Upgrade</button>
          <button class="btn btn-sm" onclick="hideUpgradeStyle()" style="border:1px solid #2a2a3a;background:transparent;color:#888">Cancel</button>
        </div>
        <div id="upgradeResult" style="margin-top:8px;font-size:12px;color:#888"></div>
      </div>

      <!-- Style textarea (editable) -->
      <div id="styleEditContainer" style="display:none;margin-bottom:10px">
        <textarea id="styleEditText" style="width:100%;padding:8px;border-radius:8px;border:1px solid #2a2a3a;background:#0f0f13;color:#e0e0e0;font-size:12px;min-height:120px;resize:vertical;outline:none;font-family:monospace">${escHtml(detail.writing_style || '')}</textarea>
        <div style="display:flex;gap:6px;margin-top:6px">
          <button class="btn btn-primary btn-sm" onclick="saveStyleEdit(${detail.id})">💾 Save</button>
          <button class="btn btn-sm" onclick="toggleStyleEdit(${detail.id})" style="border:1px solid #2a2a3a;background:transparent;color:#888">Cancel</button>
        </div>
      </div>

      ${detail.writing_style ? `<div id="stylePreviewBox" style="margin-top:12px;background:#0f0f13;border:1px solid #222234;border-radius:8px;padding:10px;font-size:12px;color:#aaa;line-height:1.6;max-height:200px;overflow-y:auto">${escHtml(detail.writing_style)}</div>` : ''}
    </div>
    <div class="advanced-sub" id="ad-replies">
      <div style="font-size:11px;color:#a855f7;margin:0 0 8px;padding:6px 8px;background:rgba(168,85,247,0.06);border-radius:6px;border-left:3px solid #a855f7">🤖 AI picks reply style and length automatically — change anytime</div>
      <div class="form-row"><div class="form-group"><label>Reply style</label><select id="replyTone">${['auto','value_add','agree','disagree','question','humor'].map(s => `<option value="${s}" ${(detail.reply_tone||'auto')===s?'selected':''}>${s === 'auto' ? '🎯 Auto (AI picks)' : s}</option>`).join('')}</select></div>
      <div class="form-group"><label>Length</label><select id="replyLength">${['auto','short','medium','long'].map(s => `<option value="${s}" ${(detail.reply_length||'auto')===s?'selected':''}>${s === 'auto' ? '🎯 Auto (AI picks)' : s}</option>`).join('')}</select></div>
      <div class="form-group"><label>Min likes to reply</label><input type="number" id="viralThreshold" value="${detail.viral_threshold}" min="0"></div></div>
      <button class="btn btn-primary btn-sm" onclick="saveAccountSettings(${detail.id})">💾 Save</button>
    </div>
    <div class="advanced-sub" id="ad-presets"><div id="presetGridContainer">Loading...</div></div>
    <div class="advanced-sub" id="ad-timeline">${renderTimeline([])}</div>
  `;
}

function renderTagsHtml(detail) {
  const tags = safeParseTags(detail.account_tags||'[]');
  return `<span style="font-size:13px;color:#888;display:block;margin-bottom:6px">Labels to organize accounts</span>
    <div class="tag-chips">${tags.map(t => `<span class="tag-chip">${escHtml(t)} <button class="tag-del" onclick="removeTag('${escHtml(t)}')">✕</button></span>`).join('')}
    <span class="tag-chip" style="cursor:pointer" onclick="addTagFromDetail()">+ Add</span></div>`;
}

// ── Advanced sub-tab switching ──
let advancedSub = 'audience';
function switchAdvancedSub(btn, section) {
  advancedSub = section;
  document.querySelectorAll('#dt-advanced .filter-chip').forEach(c => c.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('#dt-advanced .advanced-sub').forEach(s => s.classList.remove('active'));
  document.getElementById('ad-' + section).classList.add('active');
  if (section === 'presets') loadPresetsIntoPanel();
  if (section === 'timeline') {
    api(`/api/accounts/${App.selectedAccountId}/schedules`).then(scheds => {
      const el = document.getElementById('ad-timeline');
      if (el) el.innerHTML = renderTimeline(scheds);
    });
  }
}

// ── Helper functions ──
function selectDetailVibe(el, vibeId) {
  document.querySelectorAll('#detailVibePicker .vibe-card').forEach(c => c.classList.remove('selected'));
  el.classList.add('selected');
}

function applyVibeFromDetail() {
  const el = document.querySelector('#detailVibePicker .vibe-card.selected');
  if (!el) { toast('info', 'Click a vibe card'); return; }
  const vibeId = el.dataset.vibe;
  const settings = VIBE_PRESETS[vibeId];
  if (!settings) return;
  const aid = App.selectedAccountId;
  api(`/api/accounts/${aid}/settings`, { method: 'PUT', body: JSON.stringify(settings) })
    .then(() => { toast('success', 'Style updated!'); selectAccount(aid); })
    .catch(e => toast('error', e.message));
}

// ── Niche card click — auto-saves ──
function selectNicheCard(el) {
  document.querySelectorAll('#nicheGrid .audience-card').forEach(c => c.classList.remove('selected'));
  el.classList.add('selected');
  const nicheKey = el.dataset.niche;
  const preset = AUDIENCE_PRESETS[nicheKey];
  if (!preset) return;
  const aid = App.selectedAccountId;
  api(`/api/accounts/${aid}/settings`, { method: 'PUT', body: JSON.stringify({ target_niche: preset.target_niche, reply_keywords: preset.reply_keywords }) })
    .then(() => { toast('success', `Niche set to ${preset.target_niche}`); refreshAccounts(); })
    .catch(e => toast('error', e.message));
}

async function applySchedPreset(el, preset) {
  document.querySelectorAll('.sched-preset-pill').forEach(c => c.classList.remove('active'));
  el.classList.add('active');
  const presetData = SCHEDULE_PRESETS[preset] || SCHEDULE_PRESETS['popular'];
  const aid = App.selectedAccountId;
  if (!aid || !confirm(`Replace schedule with "${presetData.label}"?`)) return;
  try {
    const existing = await api(`/api/accounts/${aid}/schedules`);
    for (const s of existing) { try { await api(`/api/accounts/${aid}/schedules/${s.id}`, { method: 'DELETE' }); } catch(e) {} }
    const offset = -(new Date().getTimezoneOffset() / 60);
    for (let i = 0; i < presetData.localHours.length; i++) {
      let utcHour = Math.round((presetData.localHours[i] - offset + 24) % 24) % 24;
      await api(`/api/accounts/${aid}/schedules`, { method: 'POST', body: JSON.stringify({ hour_utc: utcHour, slot_name: `slot-${i+1}` }) }).catch(()=>{});
    }
    toast('success', `Set to "${presetData.label}"`);
    refreshAccounts();
  } catch(e) { toast('error', e.message); }
}

function exportSingleCSV(aid) {
  const a = App.accounts.find(x => x.id === aid);
  if (!a) return;
  const csv = `Username,Display,Niche,Status,Threads,Replies\n${a.username||''},${a.display_name||''},${a.niche||''},${a.active?'Active':'Paused'},${a.today_threads},${a.today_replies}`;
  const blob = new Blob([csv], {type:'text/csv'}), url = URL.createObjectURL(blob);
  const el = document.createElement('a'); el.href = url; el.download = `${a.username||'account'}.csv`; el.click();
  URL.revokeObjectURL(url);
}

// ── Show/hide ──
function showAddAccount() {
  document.getElementById('inputThreadsUser').value = '';
  document.getElementById('inputThreadsPass').value = '';
  document.getElementById('modalError').style.display = 'none';
  detectCountry();
  document.getElementById('addModal').classList.add('show');
}
function closeModal() { document.getElementById('addModal').classList.remove('show'); }

function saveAccount() {
  const threadsUser = document.getElementById('inputThreadsUser').value.trim();
  const threadsPass = document.getElementById('inputThreadsPass').value;
  const country = document.getElementById('inputCountry').value;
  const btn = document.getElementById('connectBtn');
  const errEl = document.getElementById('modalError');
  if (!threadsUser || !threadsPass) { errEl.textContent = 'Enter your Threads login'; errEl.style.display='block'; return; }
  btn.textContent='Logging in...'; btn.disabled=true;
  let cookies = [];
  api('/api/threads/login', { method:'POST', body:JSON.stringify({username:threadsUser, password:threadsPass, country}) })
    .then(result => {
      if (result.ok && result.cookies) cookies = Object.entries(result.cookies).map(([n,v])=>({name:n,value:v}));
      else throw new Error(result.error||'Login failed');
      const proxy = `proxy.packetstream.io:31112:redkoohh:f2f6ef17346136e8_country-${country}`;
      return api('/api/accounts', { method:'POST', body:JSON.stringify({username:threadsUser, display_name:threadsUser, niche:'general', cookies, proxy}) });
    })
    .then(() => {
      toast('success', 'Connected!'); closeModal();
      return api('/api/accounts');
    })
    .then(accts => {
      App.accounts = accts; renderAccountGrid();
      const a = accts[accts.length-1];
      if (a) { App.selectedAccountId = a.id; setTimeout(() => openSetupWizard(a.id), 500); }
      // Fire-and-forget: learn writing style in background
      api(`/api/accounts/${a.id}/learn-and-go`, { method: 'POST' }).catch(()=>{});
    })
    .catch(e => { errEl.textContent=e.message; errEl.style.display='block'; })
    .finally(() => { btn.textContent='Connect Account'; btn.disabled=false; });
}

function detectCountry() {
  const select = document.getElementById('inputCountry');
  const map = {'United States':'UnitedStates','Canada':'Canada','United Kingdom':'UnitedKingdom','Germany':'Germany','France':'France','Australia':'Australia','Netherlands':'Netherlands','Singapore':'Singapore','Japan':'Japan','India':'India','Brazil':'Brazil','Mexico':'Mexico','Argentina':'Argentina','Spain':'Spain','Italy':'Italy','Sweden':'Sweden','Switzerland':'Switzerland','Belgium':'Belgium','Ireland':'Ireland','Norway':'Norway','Denmark':'Denmark','Finland':'Finland','Portugal':'Portugal','Austria':'Austria','Poland':'Poland','Romania':'Romania','Greece':'Greece','Hungary':'Hungary','Ukraine':'Ukraine','Turkey':'Turkey','South Africa':'SouthAfrica','Israel':'Israel','South Korea':'SouthKorea','Malaysia':'Malaysia','Indonesia':'Indonesia','Philippines':'Philippines','Thailand':'Thailand','Vietnam':'Vietnam','Colombia':'Colombia','Chile':'Chile','Peru':'Peru','New Zealand':'NewZealand'};
  api('/api/me/geo').then(d => { const v=map[d.country_name]; if(v) select.value=v; }).catch(()=>{});
}

function showDeleteAccount(id) { App.deleteTargetId=id; document.getElementById('deleteModal').classList.add('show'); }
function closeDeleteModal() { document.getElementById('deleteModal').classList.remove('show'); App.deleteTargetId=null; }

async function confirmDeleteAccount() {
  if(!App.deleteTargetId) return;
  try {
    await api(`/api/accounts/${App.deleteTargetId}`, {method:'DELETE'});
    toast('success','Deleted'); closeDeleteModal(); App.selectedAccountId=null;
    App.accounts = await api('/api/accounts'); renderAccountGrid();
    document.getElementById('detailPanel').innerHTML='<div class="empty">Select an account</div>';
  } catch(e) { document.getElementById('deleteError').textContent=e.message; document.getElementById('deleteError').style.display='block'; }
}

function refreshAll() {
  api('/api/accounts').then(accts => { App.accounts=accts; renderAccountGrid(); updateLastUpdated(); if(App.selectedAccountId&&App.accounts.find(a=>a.id===App.selectedAccountId)) selectAccount(App.selectedAccountId); else if(App.accounts.length) selectAccount(App.accounts[0].id); }).then(()=>toast('info','Refreshed'));
}
async function refreshAccounts() {
  if(!App.accounts.length) return;
  App.accounts = await api('/api/accounts'); renderAccountGrid(); updateLastUpdated();
  if(App.selectedAccountId) { if(App.accounts.find(a=>a.id===App.selectedAccountId)) selectAccount(App.selectedAccountId); else { App.selectedAccountId=null; document.getElementById('detailPanel').innerHTML='<div class="empty">Select an account</div>'; } }
}
function updateLastUpdated() { document.getElementById('lastUpdated').innerHTML=`Updated: ${new Date().toLocaleTimeString()} <button onclick="refreshAll()">↻</button>`; }

async function runAccountNow(id) {
  const btn = event.target; btn.textContent='⏳'; btn.disabled=true;
  try { const r=await api(`/api/scheduler/run-now/${id}`,{method:'POST'}); toast('success',`Ran ${r.slots_triggered} slot(s)`); setTimeout(()=>refreshAccounts(),3000); }
  catch(e) { toast('error',e.message); }
  btn.textContent='▶️'; btn.disabled=false;
}

async function toggleSchedule(aid, sid) {
  try { await api(`/api/accounts/${aid}/schedules/${sid}/toggle`,{method:'POST'}); refreshAccounts(); }
  catch(e) { toast('error','Failed'); }
}
async function deleteSchedule(aid, sid) {
  if(!confirm('Delete this slot?')) return;
  try { await api(`/api/accounts/${aid}/schedules/${sid}`,{method:'DELETE'}); toast('success','Deleted'); refreshAccounts(); }
  catch(e) { toast('error','Failed'); }
}

function filterAccounts() {
  const q=(document.getElementById('accountSearch').value||'').toLowerCase();
  document.querySelectorAll('#accountGrid .acct-card').forEach(c => {
    const txt=c.textContent.toLowerCase();
    const isActive=!c.querySelector('.badge-paused');
    const match=App.filterMode==='all'||(App.filterMode==='active'&&isActive)||(App.filterMode==='paused'&&!isActive);
    c.style.display=match&&(!q||txt.includes(q))?'':'none';
  });
}
function toggleFilter(el,mode) {
  App.filterMode=mode; document.querySelectorAll('.filter-chip').forEach(c=>c.classList.remove('active')); el.classList.add('active'); filterAccounts();
}

// ── Add Schedule Slot ──
async function addScheduleSlot(aid, hour) {
  try {
    const existing=await api(`/api/accounts/${aid}/schedules`);
    if(existing.some(s=>s.hour_utc===hour&&s.enabled)) { toast('info','Already scheduled'); return; }
    await api(`/api/accounts/${aid}/schedules`,{method:'POST',body:JSON.stringify({hour_utc:hour,slot_name:`slot-${hour}`})});
    toast('success',`Added ${toLocalTime(hour)}`); refreshAccounts();
  } catch(e) { toast('error',e.message); }
}

// ── Style Learning ──
async function learnStyle(aid) {
  const resultEl = document.getElementById('styleResult');
  const statusEl = document.getElementById('styleStatus');
  resultEl.innerHTML = '🧠 Analyzing your last 70 posts... this takes a moment';
  try {
    const res = await api(`/api/accounts/${aid}/learn-style`, { method: 'POST' });
    if (res.style) {
      resultEl.innerHTML = `<span style="color:#22c55e">✅ Learned! ${res.posts_analyzed} posts analyzed</span>`;
      statusEl.innerHTML = '<div style="background:rgba(34,197,94,0.08);border:1px solid rgba(34,197,94,0.2);border-radius:8px;padding:10px 12px;font-size:12px;color:#22c55e;margin-bottom:10px">✅ Style learned</div>';
      // Refresh detail to show the style text
      refreshAccounts();
    } else {
      resultEl.innerHTML = res.message || 'Not enough posts with content (need 5+)';
    }
  } catch(e) {
    resultEl.innerHTML = `<span style="color:#ef4444">Failed: ${e.message}</span>`;
  }
}

// ── Style Upgrade ──
function showUpgradeStyle() {
  document.getElementById('styleUpgradePanel').style.display = 'block';
}
function hideUpgradeStyle() {
  document.getElementById('styleUpgradePanel').style.display = 'none';
  document.getElementById('upgradeResult').innerHTML = '';
  document.querySelectorAll('#upgradePresets .filter-chip').forEach(c => c.classList.remove('active'));
  document.getElementById('upgradeCustomDir').value = '';
}
function setUpgradeDir(btn, dir) {
  document.querySelectorAll('#upgradePresets .filter-chip').forEach(c => c.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('upgradeCustomDir').value = dir;
}
async function upgradeStyle(aid) {
  const dir = document.getElementById('upgradeCustomDir').value.trim();
  if (!dir) { toast('info', 'Pick a direction or write one'); return; }
  const el = document.getElementById('upgradeResult');
  el.innerHTML = '🧠 Upgrading style...';
  try {
    const res = await api(`/api/accounts/${aid}/upgrade-style`, { method: 'POST', body: JSON.stringify({ direction: dir }) });
    if (res.style) {
      el.innerHTML = `<span style="color:#22c55e">✅ Upgraded!</span>`;
      document.getElementById('stylePreviewBox').textContent = res.style;
      document.getElementById('styleEditText').value = res.style;
      hideUpgradeStyle();
    } else {
      el.innerHTML = res.message || 'Upgrade failed';
    }
  } catch(e) {
    el.innerHTML = `<span style="color:#ef4444">${e.message}</span>`;
  }
}

// ── Style Edit ──
function toggleStyleEdit() {
  const c = document.getElementById('styleEditContainer');
  c.style.display = c.style.display === 'none' ? 'block' : 'none';
}
async function saveStyleEdit(aid) {
  const text = document.getElementById('styleEditText').value.trim();
  if (!text) { toast('info', 'Style can\'t be empty'); return; }
  try {
    await api(`/api/accounts/${aid}/update-style`, { method: 'POST', body: JSON.stringify({ style: text }) });
    toast('success', 'Style saved');
    refreshAccounts();
  } catch(e) {
    toast('error', e.message);
  }
}
