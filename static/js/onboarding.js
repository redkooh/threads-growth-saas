// ── Onboarding wizard ──

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
