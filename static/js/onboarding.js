// ── Onboarding wizard (first-time) + Post-Connect Setup Wizard ──

let onboardStep = 0;

function onboardStart() {
  onboardStep = 0;
  document.getElementById('onboardOverlay').classList.add('show');
  showOnboardStep(0);
}

function showOnboardStep(i) {
  onboardStep = i;
  document.querySelectorAll('.onboard-step').forEach(s => s.style.display = 'none');
  document.getElementById('onStep' + (i + 1)).style.display = 'block';
  document.querySelectorAll('#onboardDots .step-dot').forEach((d, idx) => {
    d.classList.toggle('active', idx === i);
  });
}

function onboardNext() { if (onboardStep < 3) showOnboardStep(onboardStep + 1); }
function onboardPrev() { if (onboardStep > 0) showOnboardStep(onboardStep - 1); }

function closeOnboard() {
  document.getElementById('onboardOverlay').classList.remove('show');
  if (onboardStep === 2) showAddAccount();
}

function copyCookieCode() {
  const code = "document.cookie.split('; ').map(c=>{let[a,b]=c.split('=');return{name:a,value:b}})";
  navigator.clipboard.writeText(code).then(() => toast('success', 'Code copied! Paste it in your browser Console'))
    .catch(() => toast('info', 'Select and copy the code manually'));
}

function switchBrowserTab(el, name) {
  document.querySelectorAll('.browser-tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.browser-panel').forEach(p => p.classList.remove('active'));
  el.classList.add('active');
  document.getElementById('browser-' + name).classList.add('active');
}


// ════════════════════════════════════════════════════════════
//  POST-CONNECT SETUP WIZARD
// ════════════════════════════════════════════════════════════

// ── Wizard state ──
const WIZ = { accountId: null, vibe: null, schedule: null, audience: null };

function openSetupWizard(accountId) {
  WIZ.accountId = accountId;
  WIZ.vibe = null; WIZ.schedule = null; WIZ.audience = null;
  // Default schedule already selected
  document.querySelectorAll('.sched-preset-card').forEach(c => c.classList.remove('selected'));
  document.querySelector('.sched-preset-card[data-sched="popular"]').classList.add('selected');
  WIZ.schedule = 'popular';
  // Default audience selected
  document.querySelectorAll('.audience-card').forEach(c => c.classList.remove('selected'));
  document.querySelector('.audience-card[data-audience="general"]').classList.add('selected');
  WIZ.audience = 'general';
  // Reset vibe selection
  document.querySelectorAll('.vibe-card').forEach(c => c.classList.remove('selected'));
  document.getElementById('wizBtn1').disabled = true;
  showWizStep(1);
  document.getElementById('setupWizard').classList.add('show');
}

function showWizStep(n) {
  document.querySelectorAll('.wiz-step').forEach(s => s.classList.remove('active'));
  document.getElementById('wizStep' + n).classList.add('active');
  document.querySelectorAll('.wiz-step-dot').forEach(d => d.classList.toggle('active', parseInt(d.dataset.step) === n));
  document.querySelectorAll('.wiz-step-line').forEach(l => l.classList.toggle('active', parseInt(l.dataset.step || '0') < n));
  document.querySelectorAll('.wiz-step-label-row span').forEach(s => s.classList.toggle('active', parseInt(s.dataset.step) === n || parseInt(s.dataset.step) < n));
}

function wizNext() {
  const current = document.querySelector('.wiz-step.active');
  const id = current ? parseInt(current.id.replace('wizStep', '')) : 1;
  if (id === 1 && !WIZ.vibe) { toast('info', 'Pick a vibe first!'); return; }
  showWizStep(id + 1);
}

function wizPrev() {
  const current = document.querySelector('.wiz-step.active');
  const id = current ? parseInt(current.id.replace('wizStep', '')) : 1;
  if (id > 1) showWizStep(id - 1);
}

function wizSkip(step) {
  showWizStep(step + 1);
}

function wizSelectVibe(el, vibe) {
  document.querySelectorAll('.vibe-card').forEach(c => c.classList.remove('selected'));
  el.classList.add('selected');
  WIZ.vibe = vibe;
  document.getElementById('wizBtn1').disabled = false;
}

function wizSelectSched(el, sched) {
  document.querySelectorAll('.sched-preset-card').forEach(c => c.classList.remove('selected'));
  el.classList.add('selected');
  WIZ.schedule = sched;
}

function wizSelectAudience(el, audience) {
  document.querySelectorAll('.audience-card').forEach(c => c.classList.remove('selected'));
  el.classList.add('selected');
  WIZ.audience = audience;
}

async function wizFinish() {
  const accountId = WIZ.accountId;
  if (!accountId) { toast('error', 'No account selected'); return; }

  const btn = document.querySelector('#wizStep4 .btn-primary');
  btn.textContent = '⏳ Saving...'; btn.disabled = true;

  try {
    // 1. Apply vibe settings
    const vibeSettings = VIBE_PRESETS[WIZ.vibe] || {};
    // 2. Apply audience settings
    const audienceSettings = AUDIENCE_PRESETS[WIZ.audience] || {};
    // 3. Merge and save to account
    const merged = { ...vibeSettings, ...audienceSettings };
    await api(`/api/accounts/${accountId}/settings`, { method: 'PUT', body: JSON.stringify(merged) });

    // 4. Apply schedule — convert local hours to UTC
    const schedSettings = SCHEDULE_PRESETS[WIZ.schedule] || SCHEDULE_PRESETS['popular'];
    const offset = -(new Date().getTimezoneOffset() / 60);
    const localHours = schedSettings.localHours;

    // First, remove all existing schedules
    const existing = await api(`/api/accounts/${accountId}/schedules`);
    for (const s of existing) {
      if (s.id) {
        try { await api(`/api/accounts/${accountId}/schedules/${s.id}`, { method: 'DELETE' }); }
        catch(e) { /* ignore — may already be deleted */ }
      }
    }

    // Create new schedule slots for each local hour
    for (let i = 0; i < localHours.length; i++) {
      let utcHour = (localHours[i] - offset + 24) % 24;
      utcHour = Math.round(utcHour) % 24;
      const name = `slot-${i+1}`;
      try {
        await api(`/api/accounts/${accountId}/schedules`, {
          method: 'POST', body: JSON.stringify({ hour_utc: utcHour, slot_name: name })
        });
      } catch(e) { /* slot may already exist — skip */ }
    }

    toast('success', 'Account configured! 🎉');
    document.getElementById('setupWizard').classList.remove('show');
    btn.textContent = '🚀 Take Me to Dashboard'; btn.disabled = false;

    // Refresh everything
    App.accounts = await api('/api/accounts');
    renderAccountGrid();
    refreshAll();
  } catch (e) {
    toast('error', 'Failed to apply settings: ' + (e.message || 'unknown'));
    btn.textContent = '🚀 Take Me to Dashboard'; btn.disabled = false;
  }
}
