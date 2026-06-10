// ── Account settings save + schedule CRUD ──

let dirtySettings = false;
function markDirty() { dirtySettings = true; const el = document.getElementById('dirtyBadge'); if (el) el.style.display = 'inline'; }

async function saveAccountSettings(accountId) {
  try {
    const body = {};
    ['target_threads', 'target_replies', 'max_threads', 'max_replies',
      'sleep_hours_start', 'sleep_hours_end', 'viral_threshold'].forEach(f => {
        const el = document.getElementById(f);
        if (el) body[f] = parseInt(el.value) || 0;
      });
    ['content_style', 'vibe', 'post_tone', 'post_length', 'post_format',
      'topic_keywords', 'avoid_topics', 'target_niche', 'target_locations',
      'reply_keywords', 'reply_tone', 'reply_length'].forEach(f => {
        const idMap = {
          vibe: 'vibeInput', content_style: 'contentStyle', post_tone: 'postTone',
          post_length: 'postLength', post_format: 'postFormat', topic_keywords: 'topicKeywords',
          avoid_topics: 'avoidTopics', target_niche: 'targetNiche', target_locations: 'targetLocations',
          reply_keywords: 'replyKeywords', reply_tone: 'replyTone', reply_length: 'replyLength',
        };
        const el = document.getElementById(idMap[f] || f);
        if (el) body[f] = el.value;
      });
    const linksEl = document.getElementById('linksEnabled');
    if (linksEl) body['links_enabled'] = linksEl.checked;

    await api(`/api/accounts/${accountId}/settings`, { method: 'PUT', body: JSON.stringify(body) });
    toast('success', 'Settings saved');
    dirtySettings = false;
    const badge = document.getElementById('dirtyBadge'); if (badge) badge.style.display = 'none';
    App.accounts = await api('/api/accounts');
    selectAccount(accountId);
  } catch (e) { toast('error', e.message || 'Failed to save settings'); }
}

async function toggleSchedule(accountId, scheduleId) {
  try {
    const r = await api(`/api/accounts/${accountId}/schedules/${scheduleId}/toggle`, { method: 'POST' });
    toast('info', r.enabled ? 'Schedule enabled' : 'Schedule disabled');
    selectAccount(accountId);
  } catch (e) { toast('error', 'Failed to toggle schedule'); }
}

// ── Schedule Add/Delete Modal ──

let scheduleAccountId = null;

function showAddSchedule(accountId) {
  scheduleAccountId = accountId;
  document.getElementById('schedHour').value = '12';
  document.getElementById('schedError').style.display = 'none';
  document.getElementById('schedModal').classList.add('show');
}

function closeSchedModal() {
  document.getElementById('schedModal').classList.remove('show');
  scheduleAccountId = null;
}

async function saveSchedule() {
  const hour = parseInt(document.getElementById('schedHour').value);
  if (isNaN(hour) || hour < 0 || hour > 23) {
    const el = document.getElementById('schedError');
    el.textContent = 'Enter a valid hour (0-23)';
    el.style.display = 'block';
    return;
  }
  try {
    await api(`/api/accounts/${scheduleAccountId}/schedules`, { method: 'POST', body: JSON.stringify({ hour_utc: hour }) });
    toast('success', `Slot at UTC ${hour}:00 added`);
    closeSchedModal();
    selectAccount(scheduleAccountId);
  } catch (e) {
    const el = document.getElementById('schedError');
    el.textContent = e.message;
    el.style.display = 'block';
  }
}

async function deleteSchedule(accountId, scheduleId) {
  if (!confirm('Delete this schedule slot?')) return;
  try {
    await api(`/api/accounts/${accountId}/schedules/${scheduleId}`, { method: 'DELETE' });
    toast('success', 'Slot deleted');
    selectAccount(accountId);
  } catch (e) { toast('error', 'Failed to delete slot'); }
}
