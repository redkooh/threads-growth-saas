// ── Account detail sub-panels (rendered as HTML strings) ──

function renderAccountDetailTargets(detail) {
  return `<div class="detail-section active" id="dt-targets">
    <div class="form-row">
      <div class="form-group">
        <label>🧵 Threads Target</label>
        <div class="progress-row" style="padding:2px 0 8px">
          <div class="progress-track"><div class="progress-fill ${detail.today_threads >= detail.target_threads ? 'green' : detail.today_threads >= detail.target_threads * 0.5 ? 'yellow' : 'red'}" style="width:${Math.min((detail.today_threads / Math.max(detail.target_threads || 1, 1)) * 100, 100)}%"></div></div>
          <span class="progress-num">${detail.today_threads}/${detail.target_threads}</span>
        </div>
        <input type="number" id="target_threads" value="${detail.target_threads}" min="0" max="50" onchange="markDirty()">
        <div class="desc">How many threads to post per day</div>
      </div>
      <div class="form-group">
        <label>💬 Replies Target</label>
        <div class="progress-row" style="padding:2px 0 8px">
          <div class="progress-track"><div class="progress-fill ${detail.today_replies >= detail.target_replies ? 'green' : detail.today_replies >= detail.target_replies * 0.5 ? 'yellow' : 'red'}" style="width:${Math.min((detail.today_replies / Math.max(detail.target_replies || 1, 1)) * 100, 100)}%"></div></div>
          <span class="progress-num">${detail.today_replies}/${detail.target_replies}</span>
        </div>
        <input type="number" id="target_replies" value="${detail.target_replies}" min="0" max="50" onchange="markDirty()">
        <div class="desc">How many replies to post per day</div>
      </div>
    </div>
    <button class="btn btn-primary btn-sm" onclick="saveAccountSettings(${detail.id})" style="margin-top:4px">💾 Save Targets</button>
    <span id="dirtyBadge" style="display:none;color:#eab308;font-size:12px;margin-left:8px">⚠️ Unsaved changes</span>
  </div>`;
}

function renderAccountDetailContent(detail) {
  const linkPromo = detail.plan_config.feature_link_promo
    ? `<label style="display:flex;align-items:center;gap:8px;margin:8px 0;font-size:13px;cursor:pointer"><input type="checkbox" id="linksEnabled" ${detail.links_enabled ? 'checked' : ''}>Enable link-in-bio promotion (posts drive profile visits)</label>`
    : '<div style="font-size:12px;color:#555;margin:8px 0">🔒 Link promotion — Growth plan</div>';
  return `<div class="detail-section" id="dt-content">
    <div class="form-row">
      <div class="form-group">
        <label>Content Style</label>
        <select id="contentStyle">
          <option value="casual" ${detail.content_style === 'casual' ? 'selected' : ''}>😎 Casual — Friendly bestie</option>
          <option value="viral" ${detail.content_style === 'viral' ? 'selected' : ''}>🔥 Viral — Hot takes + hooks</option>
          <option value="professional" ${detail.content_style === 'professional' ? 'selected' : ''}>💼 Professional — Expert voice</option>
          <option value="educational" ${detail.content_style === 'educational' ? 'selected' : ''}>📚 Educational — Teach & explain</option>
          <option value="controversial" ${detail.content_style === 'controversial' ? 'selected' : ''}>🌶 Controversial — Spark debate</option>
        </select>
      </div>
      <div class="form-group">
        <label>Vibe</label>
        <input type="text" id="vibeInput" value="${detail.vibe || ''}" placeholder="e.g. 'skibidi gen z', 'startup founder'">
        <div class="desc">Describe the voice / personality</div>
      </div>
    </div>
    <div class="form-row">
      <div class="form-group"><label>Tone</label><select id="postTone">
        <option value="friendly" ${detail.post_tone === 'friendly' ? 'selected' : ''}>😊 Friendly</option>
        <option value="professional" ${detail.post_tone === 'professional' ? 'selected' : ''}>💼 Professional</option>
        <option value="sarcastic" ${detail.post_tone === 'sarcastic' ? 'selected' : ''}>😏 Sarcastic / Witty</option>
        <option value="inspirational" ${detail.post_tone === 'inspirational' ? 'selected' : ''}>✨ Inspirational</option>
        <option value="controversial" ${detail.post_tone === 'controversial' ? 'selected' : ''}>🌶 Controversial / Hot take</option>
      </select></div>
      <div class="form-group"><label>Post Length</label><select id="postLength">
        <option value="short" ${detail.post_length === 'short' ? 'selected' : ''}>📏 Short (< 100 chars)</option>
        <option value="medium" ${detail.post_length === 'medium' ? 'selected' : ''}>📏 Medium (100-300 chars)</option>
        <option value="long" ${detail.post_length === 'long' ? 'selected' : ''}>📏 Long threads (300+ chars)</option>
      </select></div>
      <div class="form-group"><label>Post Format</label><select id="postFormat">
        <option value="text" ${detail.post_format === 'text' ? 'selected' : ''}>📝 Text only</option>
        <option value="image" ${detail.post_format === 'image' ? 'selected' : ''}>🖼 Image + caption</option>
        <option value="mixed" ${detail.post_format === 'mixed' ? 'selected' : ''}>🔄 Mixed</option>
      </select></div>
    </div>
    <div class="form-group">
      <label>🔑 Topic Keywords</label>
      <textarea id="topicKeywords" placeholder="e.g. AI, startups, productivity, saas, growth">${detail.topic_keywords || ''}</textarea>
      <div class="desc">Topics your content should focus on (comma-separated or JSON array)</div>
    </div>
    <div class="form-group">
      <label>🚫 Avoid Topics</label>
      <textarea id="avoidTopics" placeholder="e.g. politics, religion, covid">${detail.avoid_topics || ''}</textarea>
      <div class="desc">Topics the AI should NEVER write about</div>
    </div>
    ${linkPromo}
    <button class="btn btn-primary btn-sm" onclick="saveAccountSettings(${detail.id})">💾 Save Content Settings</button>
  </div>`;
}

function renderAccountDetailAudience(detail) {
  return `<div class="detail-section" id="dt-audience">
    <div class="form-group">
      <label>Target Niche</label>
      <input type="text" id="targetNiche" value="${detail.target_niche || ''}" placeholder="e.g. SaaS founders, fitness enthusiasts">
      <div class="desc">Describe your ideal audience niche</div>
    </div>
    <div class="form-group">
      <label>Target Locations</label>
      <input type="text" id="targetLocations" value="${detail.target_locations || ''}" placeholder='e.g. ["United States","Canada"]'>
      <div class="desc">JSON array of target countries — leave empty for global</div>
    </div>
    <button class="btn btn-primary btn-sm" onclick="saveAccountSettings(${detail.id})">💾 Save Audience Settings</button>
  </div>`;
}

function renderAccountDetailReplies(detail) {
  return `<div class="detail-section" id="dt-replies">
    <div class="form-row">
      <div class="form-group"><label>Reply Tone</label><select id="replyTone">
        <option value="value_add" ${detail.reply_tone === 'value_add' ? 'selected' : ''}>💡 Add value / Inform</option>
        <option value="agree" ${detail.reply_tone === 'agree' ? 'selected' : ''}>👍 Agree + amplify</option>
        <option value="disagree" ${detail.reply_tone === 'disagree' ? 'selected' : ''}>👎 Disagree / Debate</option>
        <option value="question" ${detail.reply_tone === 'question' ? 'selected' : ''}>❓ Ask a question</option>
        <option value="humor" ${detail.reply_tone === 'humor' ? 'selected' : ''}>😂 Humor / Witty</option>
      </select></div>
      <div class="form-group"><label>Reply Length</label><select id="replyLength">
        <option value="short" ${detail.reply_length === 'short' ? 'selected' : ''}>Short — quick takes</option>
        <option value="medium" ${detail.reply_length === 'medium' ? 'selected' : ''}>Medium — add context</option>
        <option value="long" ${detail.reply_length === 'long' ? 'selected' : ''}>Long — deep dives</option>
      </select></div>
      <div class="form-group"><label>Viral Threshold</label><input type="number" id="viralThreshold" value="${detail.viral_threshold}" min="0" max="10000"><div class="desc">Min likes on a post before replying</div></div>
    </div>
    <div class="form-group">
      <label>🔑 Reply Keywords</label>
      <textarea id="replyKeywords" placeholder="e.g. AI, ChatGPT, startup idea">${detail.reply_keywords || ''}</textarea>
      <div class="desc">Only reply to posts mentioning these keywords</div>
    </div>
    <button class="btn btn-primary btn-sm" onclick="saveAccountSettings(${detail.id})">💾 Save Reply Strategy</button>
  </div>`;
}

function renderAccountDetailLimits(detail) {
  return `<div class="detail-section" id="dt-limits">
    <div class="form-row">
      <div class="form-group"><label>Max Threads / Day</label><input type="number" id="max_threads" value="${detail.max_threads}" min="1" max="100"><div class="desc">Hard cap on daily threads (plan max: ${detail.plan_config.max_posts_day})</div></div>
      <div class="form-group"><label>Max Replies / Day</label><input type="number" id="max_replies" value="${detail.max_replies}" min="1" max="100"><div class="desc">Hard cap on daily replies</div></div>
    </div>
    <div class="form-row">
      <div class="form-group"><label>🌙 Sleep Start (UTC)</label><input type="number" id="sleep_hours_start" value="${detail.sleep_hours_start}" min="0" max="23"><div class="desc">No activity after this UTC hour</div></div>
      <div class="form-group"><label>🌅 Sleep End (UTC)</label><input type="number" id="sleep_hours_end" value="${detail.sleep_hours_end}" min="0" max="23"><div class="desc">Activity resumes at this UTC hour</div></div>
    </div>
    <button class="btn btn-primary btn-sm" onclick="saveAccountSettings(${detail.id})">💾 Save Limits</button>
  </div>`;
}

function renderAccountDetailSchedules(scheds) {
  return `<div class="detail-section" id="dt-schedules">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">
      <span style="font-size:13px;color:#888">Posting schedule for auto-pilot</span>
      <button class="btn btn-primary btn-sm" onclick="showAddSchedule(${App.selectedAccountId})">+ Add Slot</button>
    </div>
    ${scheds.length ? '<div class="sched-grid">' + scheds.map(s => {
      const hourPct = ((s.hour_utc + 24) % 24) / 24 * 100;
      const statusColor = s.last_status === 'ok' ? '#22c55e' : s.last_status === 'error' ? '#ef4444' : '#555';
      return `<div class="sched-row">
        <div class="sched-label">${s.slot_name}</div>
        <div class="sched-vis"><div class="sched-bar ${s.enabled ? 'on' : ''}" style="width:${s.enabled ? hourPct + 4 : 4}%"></div></div>
        <div style="width:100px;font-size:12px;color:#555">${toLocalTime(s.hour_utc)}</div>
        <div style="width:50px;font-size:12px;color:${statusColor}">${s.last_status || 'never'}</div>
        <button class="toggle-btn" onclick="toggleSchedule(${App.selectedAccountId},${s.id})">${s.enabled ? 'On' : 'Off'}</button>
        <button class="btn-icon" onclick="deleteSchedule(${App.selectedAccountId},${s.id})" title="Delete slot">✕</button>
      </div>`;
    }).join('') + '</div>' : '<div class="empty">No schedules configured</div>'}
  </div>`;
}

function renderAccountDetailPosts(posts) {
  return `<div class="detail-section" id="dt-posts">
    <span style="font-size:13px;color:#888;display:block;margin-bottom:8px">${posts.length} recent posts by this account</span>
    ${posts.length ? posts.map(p => `
      <div class="post-item">
        <div class="post-meta">
          <span class="post-type ${p.type}">${p.type.replace('_', ' ')}</span>
          <span class="post-time">${new Date(p.posted_at).toLocaleString()}</span>
        </div>
        <div class="post-preview">${p.preview || '(no preview)'}</div>
        <div class="post-stats">
          ${p.code ? '<span>📎 t/' + p.code + '</span>' : ''}
          <span>❤️ ${p.likes || 0}</span>
          <span>💬 ${p.replies || 0}</span>
        </div>
      </div>
    `).join('') : '<div class="empty">No posts yet</div>'}</div>`;
}

function renderAccountDetailPresets() {
  return `<div class="detail-section" id="dt-presets">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
      <span style="font-size:13px;color:#888">Saved content configurations — apply in one click</span>
      <button class="btn btn-primary btn-sm" onclick="saveCurrentAsPreset()">💾 Save Current</button>
    </div>
    <div id="presetGridContainer">Loading presets...</div>
  </div>`;
}

function renderAccountDetailTags(detail) {
  const tags = safeParseTags(detail.account_tags || '[]');
  return `<div class="detail-section" id="dt-tags">
    <span style="font-size:13px;color:#888;display:block;margin-bottom:8px">Labels to organize accounts — filter and group by tag</span>
    <div class="tag-chips">${tags.map(t => `<span class="tag-chip">${escHtml(t)} <button class="tag-del" onclick="removeTag('${escHtml(t)}')">✕</button></span>`).join('')}
      <span class="tag-chip" style="cursor:pointer;background:rgba(168,85,247,0.2)" onclick="this.replaceWith(htmlToElements('${escHtml(renderTagInput())}'))">+ Add Tag</span>
    </div>
  </div>`;
}
