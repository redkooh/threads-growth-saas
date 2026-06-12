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

// ── Shared helpers (used by accounts.js, account_detail.js) ──
window.sliderHtml = (id, val, min, max) => {
  return `<div class="slider-group">
    <input type="range" id="${id}" value="${val}" min="${min}" max="${max}" oninput="document.getElementById('${id}-val').textContent=this.value;markDirty()">
    <span class="slider-value" id="${id}-val">${val}</span>
  </div>`;
};

window.escHtml = (s) => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');

window.safeParseTags = (s) => {
  try { const p = JSON.parse(s); return Array.isArray(p) ? p : []; }
  catch { return String(s||'').split(',').map(t=>t.trim()).filter(Boolean); }
};

// ── Vibe Presets (shared by onboarding wizard + account detail) ──
window.VIBE_PRESETS = window.VIBE_PRESETS || {}; // ensure exists
var VIBE_PRESETS = {
  'casual-lifestyle': {
    content_style: 'casual', post_tone: 'friendly', post_length: 'medium',
    post_format: 'text', vibe: 'friendly relatable bestie',
    topic_keywords: 'daily life, humor, pop culture, trending topics',
    reply_tone: 'humor', reply_length: 'short',
  },
  'hustle-culture': {
    content_style: 'professional', post_tone: 'professional', post_length: 'medium',
    post_format: 'mixed', vibe: 'ambitious startup founder',
    topic_keywords: 'startups, SaaS, AI, entrepreneurship, business, growth',
    reply_tone: 'value_add', reply_length: 'medium',
  },
  'professional-expert': {
    content_style: 'professional', post_tone: 'professional', post_length: 'long',
    post_format: 'mixed', vibe: 'authoritative industry expert',
    topic_keywords: 'industry insights, thought leadership, analysis, trends',
    reply_tone: 'value_add', reply_length: 'medium',
    avoid_topics: 'politics, religion',
  },
  'hot-takes': {
    content_style: 'controversial', post_tone: 'controversial', post_length: 'short',
    post_format: 'text', vibe: 'spicy opinionated takes',
    topic_keywords: 'unpopular opinions, debate, hot takes, trending',
    reply_tone: 'disagree', reply_length: 'short',
  },
  'educational': {
    content_style: 'educational', post_tone: 'friendly', post_length: 'long',
    post_format: 'mixed', vibe: 'patient teacher explaining things',
    topic_keywords: 'tutorials, how to, explainers, deep dives, learning',
    reply_tone: 'value_add', reply_length: 'medium',
  },
  'funny': {
    content_style: 'casual', post_tone: 'sarcastic', post_length: 'short',
    post_format: 'text', vibe: 'witty comedian roasting gently',
    topic_keywords: 'memes, humor, comedy, relatable jokes, pop culture',
    reply_tone: 'humor', reply_length: 'short',
  },
};

window.SCHEDULE_PRESETS = window.SCHEDULE_PRESETS || {};
var SCHEDULE_PRESETS = {
  'popular': { label: 'Popular Times', localHours: [9, 12, 16, 20], maxSlots: 4 },
  'morning': { label: 'Early Bird', localHours: [6, 8, 10, 12], maxSlots: 4 },
  'evening': { label: 'Evening Crew', localHours: [17, 19, 21, 23], maxSlots: 4 },
  'spread':  { label: 'All Day Spread', localHours: [6, 10, 14, 18, 22], maxSlots: 5 },
};

window.AUDIENCE_PRESETS = window.AUDIENCE_PRESETS || {};
var AUDIENCE_PRESETS = {
  'general': {
    target_niche: 'General / broad audience', reply_keywords: 'trending, viral, funny, relatable, popular',
  },
  'tech-saas': {
    target_niche: 'Tech enthusiasts, developers, SaaS founders', reply_keywords: 'startup, AI, coding, tech, founder, software',
  },
  'fitness-health': {
    target_niche: 'Fitness and health community', reply_keywords: 'workout, gym, health, nutrition, fitness, wellness',
  },
  'business': {
    target_niche: 'Business owners, entrepreneurs, marketers', reply_keywords: 'business, marketing, sales, strategy, entrepreneur',
  },
  'finance-investing': {
    target_niche: 'Finance, investing, crypto, personal finance', reply_keywords: 'investing, crypto, stock, money, finance, trading',
  },
  'gaming': {
    target_niche: 'Gamers, esports, game developers', reply_keywords: 'gaming, esports, game, twitch, steam, pro player',
  },
  'fashion-beauty': {
    target_niche: 'Fashion, beauty, skincare, style enthusiasts', reply_keywords: 'fashion, beauty, skincare, makeup, style, outfit',
  },
  'food-cooking': {
    target_niche: 'Food lovers, home cooks, chefs, recipes', reply_keywords: 'food, cooking, recipe, chef, restaurant, kitchen',
  },
  'travel': {
    target_niche: 'Travelers, digital nomads, explorers', reply_keywords: 'travel, wanderlust, trip, vacation, explore, adventure',
  },
  'parenting': {
    target_niche: 'Parents, moms, dads, family content', reply_keywords: 'parenting, mom, dad, kids, family, baby',
  },
  'music': {
    target_niche: 'Music lovers, musicians, producers', reply_keywords: 'music, song, album, artist, concert, producer',
  },
  'sports': {
    target_niche: 'Sports fans, athletes, fitness competitors', reply_keywords: 'sports, football, basketball, soccer, athlete, training',
  },
  'motivation': {
    target_niche: 'Inspirational, self-improvement, mindset', reply_keywords: 'motivation, mindset, success, growth, discipline, inspire',
  },
};
