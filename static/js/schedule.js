// ── Schedule tab: 24h timeline + per-account slot cards ──
// Relies on core.js globals (api, toast, App, switchTab, toLocalTime)

const ICONS = { thread: '🧵', reply: '💬', fun_fact: '🎉' };
const LABELS = { thread: 'Thread', reply: 'Reply', fun_fact: 'Fun Fact' };

let scheduleData = [];
let scheduleSleepStart = 2;
let scheduleSleepEnd = 8;
let scheduleAccountId = null;

// ═══ Main Load ═══

async function loadScheduleTab() {
  const timelineEl = document.getElementById('scheduleTimeline');
  const nextRunEl = document.getElementById('scheduleNextRun');
  const accountsEl = document.getElementById('scheduleAccounts');

  try {
    scheduleData = await api('/api/schedules/all');

    // Load sleep config from first account that has it
    if (scheduleData.length > 0) {
      const firstDetail = await api(`/api/accounts/${scheduleData[0].account_id}/detail`);
      scheduleSleepStart = firstDetail.sleep_hours_start || 2;
      scheduleSleepEnd = firstDetail.sleep_hours_end || 8;
      document.getElementById('sleepStartInput').value = scheduleSleepStart;
      document.getElementById('sleepEndInput').value = scheduleSleepEnd;
      scheduleAccountId = firstDetail.id;
    }

    renderTimeline(timelineEl, scheduleData);
    renderNextRun(nextRunEl, scheduleData);
    renderAccountSlots(accountsEl, scheduleData);
  } catch (e) {
    timelineEl.innerHTML = '<div class="empty">Failed to load schedule</div>';
  }
}

// ═══ 24h Timeline ═══

function getSlotStatus(s) {
  if (!s.enabled) return 'inactive';
  if (s.ran_today) return 'done';
  const nowHour = new Date().getUTCHours();
  const slept = isSleepHour(s.hour_utc, scheduleSleepStart, scheduleSleepEnd);
  if (slept) return 'inactive';
  if (s.hour_utc <= nowHour && !s.ran_today) return 'pending';
  return 'upcoming';
}

function isSleepHour(h, start, end) {
  if (start === end) return false;
  if (start < end) return h >= start && h <= end;
  return h >= start || h <= end; // wraps midnight
}

function renderTimeline(el, data) {
  if (!data.length) {
    el.innerHTML = '<div class="empty" style="padding:20px">No schedules yet. Add a slot below.</div>';
    return;
  }

  // Sleep zone
  const sleepStartPct = (scheduleSleepStart / 24) * 100;
  const sleepEndPct = (scheduleSleepEnd / 24) * 100;
  let sleepStyle, sleepLeft, sleepWidth;
  if (scheduleSleepStart < scheduleSleepEnd) {
    sleepLeft = sleepStartPct;
    sleepWidth = sleepEndPct - sleepStartPct;
  } else if (scheduleSleepStart > scheduleSleepEnd) {
    sleepLeft = sleepStartPct;
    sleepWidth = 100 - sleepStartPct + sleepEndPct;
  } else {
    sleepLeft = 0; sleepWidth = 0;
  }

  let html = '<div class="timeline-bar">';

  // Sleep zone (split for wrapping)
  if (scheduleSleepStart === scheduleSleepEnd) {
    // no sleep zone
  } else if (scheduleSleepStart < scheduleSleepEnd) {
    html += `<div class="sleep-zone" style="left:${sleepStartPct}%;width:${sleepEndPct - sleepStartPct}%">🌙 SLEEP</div>`;
  } else {
    html += `<div class="sleep-zone" style="left:${sleepStartPct}%;width:${100 - sleepStartPct}%">🌙 SLEEP</div>`;
    html += `<div class="sleep-zone" style="left:0%;width:${sleepEndPct}%">🌙 SLEEP</div>`;
  }

  // Slot markers
  data.forEach(s => {
    const pct = (s.hour_utc / 24) * 100;
    const status = getSlotStatus(s);
    const icon = ICONS[s.post_type] || '🧵';
    html += `<div class="timeline-slot ${status}" style="left:${pct}%;margin-left:-16px" title="${s.username || ''} — ${LABELS[s.post_type]}: ${s.hour_utc}:00 UTC (${status})" onclick="selectSlotOnTimeline(${s.hour_utc})">
      <span class="slot-icon">${icon}</span>
    </div>`;
  });

  html += '</div>';

  // Hour labels
  html += '<div class="timeline-hours">';
  for (let h = 0; h < 24; h++) {
    html += `<span>${h}</span>`;
  }
  html += '</div>';

  html += '<div class="timeline-hint">🕐 All times UTC — click any slot to edit · drag to reposition (coming soon)</div>';

  el.innerHTML = html;
}

function renderNextRun(el, data) {
  const nowHour = new Date().getUTCHours();
  const upcoming = data
    .filter(s => s.enabled && s.hour_utc > nowHour && s.active && !s.ran_today)
    .sort((a, b) => a.hour_utc - b.hour_utc);

  if (upcoming.length) {
    const next = upcoming[0];
    const hoursUntil = next.hour_utc - nowHour;
    el.innerHTML = `Next run: <strong>${next.hour_utc}:00 UTC</strong> · @${next.username} 🧵 · in ~${hoursUntil}h`;
  } else {
    // Check tomorrow
    const tomorrow = data.filter(s => s.enabled && s.active).sort((a, b) => a.hour_utc - b.hour_utc);
    if (tomorrow.length) {
      const next = tomorrow[0];
      el.innerHTML = `Next run: <strong>tomorrow ${next.hour_utc}:00 UTC</strong> · @${next.username} 🧵`;
    } else {
      el.innerHTML = 'No upcoming slots scheduled';
    }
  }
}

function renderAccountSlots(el, data) {
  if (!data.length) {
    el.innerHTML = '<div class="empty">No schedules configured</div>';
    return;
  }

  // Group by account_id
  const grouped = {};
  data.forEach(s => {
    if (!grouped[s.account_id]) grouped[s.account_id] = { name: s.display_name || s.username || 'Unnamed', username: s.username, active: s.active, slots: [] };
    grouped[s.account_id].slots.push(s);
  });

  let html = '<div class="schedule-accounts">';
  for (const [accountId, group] of Object.entries(grouped)) {
    const sorted = group.slots.sort((a, b) => a.hour_utc - b.hour_utc);
    html += `<div class="schedule-account-card">
      <div class="schedule-account-header" onclick="this.nextElementSibling.classList.toggle('collapsed')">
        <div class="acct-name">
          <span>${group.active ? '🟢' : '🔴'}</span>
          <span>${group.name}</span>
          <span style="font-size:12px;color:#888">@${group.username}</span>
        </div>
        <div class="acct-meta">
          <span>${sorted.filter(s => s.ran_today).length}/${sorted.length} done</span>
          <span style="font-size:18px">▼</span>
        </div>
      </div>
      <div class="schedule-account-body">`;

    sorted.forEach(s => {
      const status = getSlotStatus(s);
      const statusLabel = status === 'done' ? '✅ Done' : status === 'pending' ? '⏳ Due' : status === 'inactive' && !s.enabled ? '⏸ Off' : '⬜ Upcoming';
      const statusClass = status === 'done' ? 'done' : status === 'pending' ? 'pending' : 'upcoming';
      const icon = ICONS[s.post_type] || '🧵';
      html += `<div class="schedule-slot-row">
        <span class="slot-type-icon">${icon}</span>
        <div class="slot-info">
          <div class="slot-label">${LABELS[s.post_type]} · ${s.hour_utc}:00 UTC (${toLocalTime(s.hour_utc)})</div>
          <div class="slot-detail">${s.slot_name}${s.last_status && s.last_status !== 'never' ? ' · ' + s.last_status : ''}</div>
        </div>
        <span class="slot-status ${statusClass}">${statusLabel}</span>
        <label class="toggle-switch">
          <input type="checkbox" ${s.enabled ? 'checked' : ''} onchange="toggleSlot(${s.account_id},${s.id},this.checked)">
          <span class="toggle-slider"></span>
        </label>
        <button class="btn-icon" onclick="deleteSlot(${s.account_id},${s.id})" title="Delete">✕</button>
      </div>`;
    });

    html += '</div></div>';
  }
  html += '</div>';
  el.innerHTML = html;
}

// ═══ Actions ═══

function selectSlotOnTimeline(hour) {
  document.getElementById('slotHour').value = hour;
  document.getElementById('slotHour').focus();
  toast('info', `Adding slot at UTC ${hour}:00`);
}

function setSlotType(el, type) {
  document.querySelectorAll('#scheduleTab .type-chip').forEach(c => c.classList.remove('selected'));
  el.classList.add('selected');
  document.getElementById('slotType').value = type;
}

async function quickAddSlot() {
  const accountSelect = document.getElementById('slotAccount');
  const accountId = parseInt(accountSelect.value);
  const hour = parseInt(document.getElementById('slotHour').value);
  const type = document.getElementById('slotType').value;
  const name = `${type.replace('_', ' ')} ${hour}:00`;

  if (isNaN(hour) || hour < 0 || hour > 23) {
    toast('error', 'Enter a valid hour (0-23)');
    return;
  }

  try {
    await api(`/api/accounts/${accountId}/schedules`, {
      method: 'POST',
      body: JSON.stringify({ hour_utc: hour, slot_name: name, post_type: type }),
    });
    toast('success', `${LABELS[type]} slot at UTC ${hour}:00 added`);
    loadScheduleTab();
  } catch (e) {
    toast('error', e.message);
  }
}

async function toggleSlot(accountId, scheduleId, enabled) {
  try {
    await api(`/api/accounts/${accountId}/schedules/${scheduleId}/toggle`, { method: 'POST' });
    toast('info', enabled ? 'Slot enabled' : 'Slot disabled');
    loadScheduleTab();
  } catch (e) {
    toast('error', 'Failed to toggle');
  }
}

async function deleteSlot(accountId, scheduleId) {
  if (!confirm('Delete this schedule slot?')) return;
  try {
    await api(`/api/accounts/${accountId}/schedules/${scheduleId}`, { method: 'DELETE' });
    toast('success', 'Slot deleted');
    loadScheduleTab();
  } catch (e) {
    toast('error', 'Failed to delete');
  }
}

async function saveSleepConfig() {
  if (!scheduleAccountId) return;
  const start = parseInt(document.getElementById('sleepStartInput').value) || 0;
  const end = parseInt(document.getElementById('sleepEndInput').value) || 0;
  try {
    await api(`/api/accounts/${scheduleAccountId}/settings`, {
      method: 'PUT',
      body: JSON.stringify({ sleep_hours_start: start, sleep_hours_end: end }),
    });
    scheduleSleepStart = start;
    scheduleSleepEnd = end;
    toast('success', 'Sleep hours saved');
    loadScheduleTab();
  } catch (e) {
    toast('error', e.message);
  }
}

// ── Init ──
document.addEventListener('DOMContentLoaded', () => {
  // Load accounts into the quick-add dropdown when schedule tab becomes visible
  const observer = new MutationObserver(() => {
    const tab = document.getElementById('tab-schedule');
    if (tab && tab.classList.contains('active') && !document.getElementById('slotAccount').children.length) {
      populateQuickAddAccounts();
    }
  });
  const tab = document.getElementById('tab-schedule');
  if (tab) observer.observe(tab, { attributes: true, attributeFilter: ['class'] });
});

async function populateQuickAddAccounts() {
  const accounts = App.accounts.length ? App.accounts : await api('/api/accounts');
  App.accounts = accounts;
  const select = document.getElementById('slotAccount');
  select.innerHTML = accounts.map(a => `<option value="${a.id}">${a.display_name || a.username} (@${a.username})</option>`).join('');
  scheduleAccountId = accounts[0]?.id || null;
}
