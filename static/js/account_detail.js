// ── Stub — all render functions moved to accounts.js ──
// Kept for backward compat: tag/risk helpers

async function removeTag(tag) {
  const aid = App.selectedAccountId;
  if (!aid) return;
  try {
    const detail = await api(`/api/accounts/${aid}/detail`);
    let tags = safeParseTags(detail.account_tags).filter(t => t !== tag);
    await api(`/api/accounts/${aid}/settings`, { method: 'PUT', body: JSON.stringify({ account_tags: tags }) });
    toast('info', `Tag "${tag}" removed`);
    selectAccount(aid);
  } catch (e) { toast('error', e.message || 'Failed'); }
}

async function addTagFromDetail() {
  const aid = App.selectedAccountId;
  if (!aid) return;
  const tag = prompt('Enter tag name:');
  if (!tag || !tag.trim()) return;
  try {
    const detail = await api(`/api/accounts/${aid}/detail`);
    let tags = safeParseTags(detail.account_tags);
    if (tags.includes(tag.trim())) { toast('info', 'Tag exists'); return; }
    tags.push(tag.trim().toLowerCase().replace(/\s+/g, '-'));
    await api(`/api/accounts/${aid}/settings`, { method: 'PUT', body: JSON.stringify({ account_tags: tags }) });
    toast('success', `Tag "${tag}" added`);
    selectAccount(aid);
  } catch (e) { toast('error', e.message || 'Failed'); }
}

async function loadAndRenderRisk(aid) {
  const el = document.getElementById('dt-risk-content');
  if (!el) return;
  try {
    const r = await api(`/api/accounts/${aid}/risk`);
    const levelClass = r.level === 'low' ? 'safe' : r.level === 'medium' ? 'warning' : 'danger';
    el.innerHTML = `<div class="risk-meter ${levelClass}">
      <div class="risk-score" style="color:${r.level === 'low' ? '#22c55e' : r.level === 'medium' ? '#eab308' : '#ef4444'}">${r.score}</div>
      <div class="risk-bar"><div class="risk-fill ${r.level}" style="width:${r.score}%"></div></div>
      <div class="risk-label">${r.level === 'low' ? '✅ Low Risk' : r.level === 'medium' ? '⚠️ Medium Risk' : '🔴 High Risk'}</div>
    </div>
    <div class="risk-details">${r.reasons.map(x => '• ' + x).join('<br>')}</div>`;
  } catch { el.innerHTML = '<div class="empty">Could not calculate risk</div>'; }
}

async function loadPresetsIntoPanel() {
  const container = document.getElementById('presetGridContainer');
  if (!container) return;
  try {
    const presets = await api('/api/presets');
    if (!presets.length) { container.innerHTML = '<div class="empty" style="font-size:12px">No saved presets</div>'; return; }
    container.innerHTML = '<div class="preset-grid">' + presets.map(p => `
      <div class="preset-card" onclick="applyPreset(${p.id}, '${escHtml(p.name)}')">
        <button class="preset-del" onclick="event.stopPropagation();deletePreset(${p.id})">✕</button>
        <div class="preset-name">${escHtml(p.name)}</div>
        <div class="preset-desc">${Object.keys(p.settings).length} settings</div>
      </div>`).join('') + '</div>';
  } catch { container.innerHTML = '<div class="empty">Failed to load</div>'; }
}

async function loadPresets() { try { return await api('/api/presets'); } catch { return []; } }

async function saveCurrentAsPreset() {
  const aid = App.selectedAccountId;
  if (!aid) return toast('error', 'Select an account first');
  try {
    const detail = await api(`/api/accounts/${aid}/detail`);
    const settings = { content_style: detail.content_style, vibe: detail.vibe, post_tone: detail.post_tone, post_length: detail.post_length, post_format: detail.post_format, topic_keywords: detail.topic_keywords, avoid_topics: detail.avoid_topics, links_enabled: detail.links_enabled, target_niche: detail.target_niche, target_follower_min: detail.target_follower_min, target_follower_max: detail.target_follower_max, reply_keywords: detail.reply_keywords, reply_tone: detail.reply_tone, reply_length: detail.reply_length, viral_threshold: detail.viral_threshold, target_threads: detail.target_threads, target_replies: detail.target_replies, max_threads: detail.max_threads, max_replies: detail.max_replies, sleep_hours_start: detail.sleep_hours_start, sleep_hours_end: detail.sleep_hours_end };
    const name = prompt('Name this preset:', `Custom - ${detail.niche || 'USA'}`);
    if (!name) return;
    await api('/api/presets', { method: 'POST', body: JSON.stringify({ name, settings }) });
    toast('success', `Preset "${name}" saved`);
    if (document.getElementById('presetGridContainer')) loadPresetsIntoPanel();
  } catch (e) { toast('error', e.message); }
}

async function applyPreset(presetId, name) {
  const aid = App.selectedAccountId;
  if (!aid) return toast('error', 'Select an account first');
  if (!confirm(`Apply "${name}" to this account?`)) return;
  try {
    const r = await api(`/api/presets/${presetId}/apply/${aid}`, { method: 'POST' });
    toast('success', `Applied ${r.applied_fields.length} settings`);
    selectAccount(aid);
  } catch (e) { toast('error', e.message); }
}

async function deletePreset(presetId) {
  if (!confirm('Delete this preset?')) return;
  try {
    await api(`/api/presets/${presetId}`, { method: 'DELETE' });
    toast('success', 'Deleted');
    if (document.getElementById('presetGridContainer')) loadPresetsIntoPanel();
  } catch (e) { toast('error', e.message); }
}

function renderTimeline(schedules) {
  if (!schedules || !schedules.length) return '<div class="empty">No schedules</div>';
  const active = schedules.filter(s => s.enabled);
  return `<div class="time-vis">${active.map(s => {
    const left = (s.hour_utc / 24) * 100;
    return `<div class="time-slot thread" style="left:${left}%;width:4.16%" title="${s.slot_name} @ ${toLocalTime(s.hour_utc)}">${s.slot_name.replace('slot-','S')}</div>`;
  }).join('')}</div>
  <div class="time-labels">${[0,3,6,9,12,15,18,21].map(h => `<span>${toLocalTime(h)}</span>`).join('')}</div>`;
}
