// ── Content Presets ──

async function loadPresets() {
  try { return await api('/api/presets'); }
  catch { return []; }
}

function renderPresets(presets) {
  if (!presets.length) {
    return `<div class="empty" style="font-size:12px">No saved presets — configure an account then save as preset</div>`;
  }
  return `<div class="preset-grid">${presets.map(p => `
    <div class="preset-card" onclick="applyPreset(${p.id}, '${escHtml(p.name)}')">
      <button class="preset-del" onclick="event.stopPropagation();deletePreset(${p.id})" title="Delete preset">✕</button>
      <div class="preset-name">${escHtml(p.name)}</div>
      <div class="preset-desc">${Object.keys(p.settings).length} settings · ${escHtml(p.settings.content_style || '—')}</div>
      <div class="preset-apply">Click to apply →</div>
    </div>`).join('')}</div>`;
}

function escHtml(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

async function applyPreset(presetId, name) {
  const aid = App.selectedAccountId;
  if (!aid) return toast('error', 'Select an account first');
  if (!confirm(`Apply "${name}" to this account? It will overwrite current content settings.`)) return;
  try {
    const r = await api(`/api/presets/${presetId}/apply/${aid}`, { method: 'POST' });
    toast('success', `Applied ${r.applied_fields.length} settings from "${name}"`);
    selectAccount(aid);
  } catch (e) { toast('error', e.message || 'Failed to apply preset'); }
}

async function deletePreset(presetId) {
  if (!confirm('Delete this preset?')) return;
  try {
    await api(`/api/presets/${presetId}`, { method: 'DELETE' });
    toast('success', 'Preset deleted');
    const presets = await loadPresets();
    const container = document.getElementById('presetGridContainer');
    if (container) container.innerHTML = renderPresets(presets);
  } catch (e) { toast('error', e.message || 'Failed to delete'); }
}

async function loadPresetsIntoPanel() {
  const container = document.getElementById('presetGridContainer');
  if (!container) return;
  const presets = await loadPresets();
  container.innerHTML = renderPresets(presets);
}

function htmlToElements(html) {
  const t = document.createElement('template');
  t.innerHTML = html.trim();
  return t.content.firstChild;
}

async function saveCurrentAsPreset() {
  const aid = App.selectedAccountId;
  if (!aid) return toast('error', 'Select an account first');
  try {
    const detail = await api(`/api/accounts/${aid}/detail`);
    const settings = {
      content_style: detail.content_style, vibe: detail.vibe, post_tone: detail.post_tone,
      post_length: detail.post_length, post_format: detail.post_format,
      topic_keywords: detail.topic_keywords, avoid_topics: detail.avoid_topics,
      links_enabled: detail.links_enabled,
      target_niche: detail.target_niche, target_locations: detail.target_locations,
      target_follower_min: detail.target_follower_min, target_follower_max: detail.target_follower_max,
      reply_keywords: detail.reply_keywords, reply_tone: detail.reply_tone,
      reply_length: detail.reply_length, viral_threshold: detail.viral_threshold,
      target_threads: detail.target_threads, target_replies: detail.target_replies,
      max_threads: detail.max_threads, max_replies: detail.max_replies,
      sleep_hours_start: detail.sleep_hours_start, sleep_hours_end: detail.sleep_hours_end,
    };
    const name = prompt('Name this preset:', `Custom - ${detail.niche || 'USA'} - ${detail.content_style}`);
    if (!name) return;
    await api('/api/presets', { method: 'POST', body: JSON.stringify({ name, settings }) });
    toast('success', `Preset "${name}" saved`);
    const presets = await loadPresets();
    const el = document.getElementById('dt-presets');
    if (el) {
      const grid = el.querySelector('.preset-grid');
      if (grid) grid.outerHTML = renderPresets(presets);
    }
  } catch (e) { toast('error', e.message || 'Failed to save preset'); }
}


// ── Account Tags ──

function renderTags(tags) {
  if (!tags || !tags.length) return `<div style="font-size:12px;color:#555">No tags — add labels to organize accounts</div>`;
  return `<div class="tag-chips">${tags.map(t => `<span class="tag-chip">${escHtml(t)}</span>`).join('')}
    <span class="tag-chip" style="cursor:pointer;background:rgba(168,85,247,0.2)" onclick="addTagFromDetail()">+ Add Tag</span>
  </div>`;
}

function renderTagInput() {
  return `<div class="tag-input">
    <input id="tagInputField" placeholder="e.g. client-1, test, vip" onkeydown="if(event.key==='Enter')addTagFromDetail()">
    <button onclick="addTagFromDetail()">Add</button>
  </div>`;
}

async function addTagFromDetail() {
  const aid = App.selectedAccountId;
  if (!aid) return;
  const input = document.getElementById('tagInputField');
  const tag = (input?.value || '').trim().toLowerCase().replace(/\s+/g, '-');
  if (!tag) return;
  try {
    const detail = await api(`/api/accounts/${aid}/detail`);
    let tags = safeParseTags(detail.account_tags);
    if (tags.includes(tag)) { toast('info', 'Tag already exists'); return; }
    tags.push(tag);
    await api(`/api/accounts/${aid}/settings`, { method: 'PUT', body: JSON.stringify({ account_tags: tags }) });
    toast('success', `Tag "${tag}" added`);
    selectAccount(aid);
  } catch (e) { toast('error', e.message || 'Failed to add tag'); }
}

async function removeTag(tag) {
  const aid = App.selectedAccountId;
  if (!aid) return;
  try {
    const detail = await api(`/api/accounts/${aid}/detail`);
    let tags = safeParseTags(detail.account_tags).filter(t => t !== tag);
    await api(`/api/accounts/${aid}/settings`, { method: 'PUT', body: JSON.stringify({ account_tags: tags }) });
    toast('info', `Tag "${tag}" removed`);
    selectAccount(aid);
  } catch (e) { toast('error', e.message || 'Failed to remove tag'); }
}

function safeParseTags(s) {
  try { const p = JSON.parse(s); return Array.isArray(p) ? p : []; }
  catch { return String(s||'').split(',').map(t=>t.trim()).filter(Boolean); }
}


// ── Risk Score ──

async function renderRisk(aid) {
  if (!aid) return `<div class="empty" style="font-size:12px">Select an account to see risk</div>`;
  try {
    const r = await api(`/api/accounts/${aid}/risk`);
    const levelClass = r.level === 'low' ? 'safe' : r.level === 'medium' ? 'warning' : 'danger';
    return `<div class="risk-meter ${levelClass}">
      <div class="risk-score" style="color:${r.level === 'low' ? '#22c55e' : r.level === 'medium' ? '#eab308' : '#ef4444'}">${r.score}</div>
      <div class="risk-bar"><div class="risk-fill ${r.level}" style="width:${r.score}%"></div></div>
      <div class="risk-label">${r.level === 'low' ? '✅ Low Risk' : r.level === 'medium' ? '⚠️ Medium Risk' : '🔴 High Risk'}</div>
    </div>
    <div class="risk-details">${r.reasons.map(x => '• ' + x).join('<br>')}</div>`;
  } catch {
    return `<div class="empty" style="font-size:12px">Could not calculate risk</div>`;
  }
}

async function loadAndRenderRisk(aid) {
  const el = document.getElementById('dt-risk-content');
  if (!el) return;
  el.innerHTML = await renderRisk(aid);
}


// ── 24h Timeline ──

function renderTimeline(schedules) {
  if (!schedules || !schedules.length) return `<div class="empty">No schedules configured</div>`;
  const hours = Array.from({length:24}, (_,i) => i);
  const active = schedules.filter(s => s.enabled);
  return `<div class="time-vis">${active.map(s => {
    const left = (s.hour_utc / 24) * 100;
    const w = 4.16; // ≈ 1 hour width
    const type = ['slot-1','slot-3','slot-5','slot-6'].includes(s.slot_name) ? 'thread' : 'reply';
    return `<div class="time-slot ${type}" style="left:${left}%;width:${w}%" title="${s.slot_name} @ ${s.hour_utc}:00 UTC (${toLocalTime(s.hour_utc)})">${s.slot_name.replace('slot-','S')}</div>`;
  }).join('')}</div>
  <div class="time-labels">${[0,3,6,9,12,15,18,21].map(h => `<span>${toLocalTime(h)}</span>`).join('')}</div>
  <div style="display:flex;gap:12px;font-size:11px;color:#555;margin-top:6px">
    <span>🟣 Thread</span>
    <span>🔵 Reply</span>
    <span>💗 Mixed</span>
  </div>`;
}

function toLocalTime(utcHour) {
  const offset = -(new Date().getTimezoneOffset() / 60);
  let local = (utcHour + offset + 24) % 24;
  const ampm = local >= 12 ? 'PM' : 'AM';
  local = local % 12 || 12;
  return `${local}${ampm}`;
}


// ── Batch Mode ──

let batchMode = false;
let batchSelected = new Set();

function toggleBatchMode() {
  batchMode = !batchMode;
  batchSelected.clear();
  document.querySelector('.acct-grid')?.classList.toggle('batch-mode', batchMode);
  const bar = document.getElementById('batchBar');
  if (bar) bar.style.display = batchMode ? 'flex' : 'none';
  if (!batchMode) {
    document.querySelectorAll('.batch-check').forEach(c => c.classList.remove('checked'));
    document.querySelectorAll('.acct-card').forEach(c => c.style.borderColor = '');
  }
  renderBatchCount();
}

function toggleBatchSelect(id) {
  if (!batchMode) return;
  if (batchSelected.has(id)) batchSelected.delete(id);
  else batchSelected.add(id);
  const card = document.querySelector(`.acct-card[data-id="${id}"]`);
  if (card) {
    card.querySelector('.batch-check')?.classList.toggle('checked');
    card.style.borderColor = batchSelected.has(id) ? '#a855f7' : '';
  }
  renderBatchCount();
}

function renderBatchCount() {
  const el = document.getElementById('batchCount');
  if (el) el.textContent = `${batchSelected.size} selected`;
}

const BATCH_PRESETS = {
  'general': { content_style: 'auto', post_tone: 'friendly', post_length: 'auto', target_niche: 'General / broad audience', topic_keywords: 'trending, viral, lifestyle, popular, relatable, daily life', reply_keywords: 'trending, viral, relatable, popular, thoughts, opinion', target_threads: 4, target_replies: 8, sleep_hours_start: 23, sleep_hours_end: 6, reply_tone: 'value_add' },
  'tech-saas': { content_style: 'auto', post_tone: 'professional', post_length: 'auto', target_niche: 'Tech / SaaS founders', topic_keywords: 'startups, SaaS, AI, entrepreneurship, growth', reply_keywords: 'startup, SaaS, AI, funding, product', target_threads: 3, target_replies: 10, sleep_hours_start: 23, sleep_hours_end: 5 },
  'fitness': { content_style: 'auto', post_tone: 'inspirational', post_length: 'auto', target_niche: 'Fitness / health enthusiasts', topic_keywords: 'workout, fitness, health, nutrition, gym', reply_keywords: 'workout, gym, fitness, diet, protein', target_threads: 3, target_replies: 8, sleep_hours_start: 0, sleep_hours_end: 6 },
  'business': { content_style: 'auto', post_tone: 'professional', post_length: 'auto', target_niche: 'Business owners / entrepreneurs', topic_keywords: 'business, marketing, sales, leadership, growth', reply_keywords: 'business, revenue, marketing, sales, strategy', target_threads: 3, target_replies: 8, sleep_hours_start: 23, sleep_hours_end: 5 },
  'casual': { content_style: 'auto', post_tone: 'friendly', post_length: 'auto', target_niche: 'General audience', target_threads: 4, target_replies: 10, sleep_hours_start: 23, sleep_hours_end: 6 },
  'reset': { content_style: 'auto', post_tone: 'friendly', post_length: 'auto', post_format: 'text', target_threads: 4, target_replies: 8, max_threads: 10, max_replies: 20, sleep_hours_start: 23, sleep_hours_end: 6, viral_threshold: 0, reply_tone: 'value_add', reply_length: 'medium', topic_keywords: '', avoid_topics: '', reply_keywords: '', target_niche: '', links_enabled: false },
};

function showBatchApply() {
  if (batchSelected.size === 0) { toast('error', 'Select accounts first'); return; }
  document.getElementById('batchSettingsJson').value = JSON.stringify(BATCH_PRESETS['general'], null, 2);
  document.getElementById('batchModal').classList.add('show');
}

function batchPreset(name) {
  const settings = BATCH_PRESETS[name];
  if (settings) {
    document.getElementById('batchSettingsJson').value = JSON.stringify(settings, null, 2);
    toast('info', `Loaded "${name}" preset — click Apply to confirm`);
  }
}

async function batchApply() {
  const ids = [...batchSelected];
  let settings;
  try {
    settings = JSON.parse(document.getElementById('batchSettingsJson').value);
  } catch {
    toast('error', 'Invalid JSON in settings');
    return;
  }
  try {
    const r = await api('/api/accounts/batch-apply', {
      method: 'POST',
      body: JSON.stringify({ account_ids: ids, settings })
    });
    toast('success', `Applied to ${r.updated} accounts`);
    document.getElementById('batchModal').classList.remove('show');
    toggleBatchMode();
    refreshAll();
  } catch (e) { toast('error', e.message); }
}
