/* ═══════════════════════════════════════════════════════════════════════════
   AIcity Dashboard — app.js
   ═══════════════════════════════════════════════════════════════════════════ */

// ── Constants ─────────────────────────────────────────────────────────────────
const MAX_FEED = 80;
const MAX_MSGS = 80;

const ROLE_ABBR = {
  builder:   'BLD',
  explorer:  'EXP',
  merchant:  'MCH',
  police:    'POL',
  teacher:   'TCH',
  healer:    'HLR',
  messenger: 'MSG',
  thief:     'THF',
  lawyer:    'LAW',
  newborn:   'NEW',
};

const ROLE_PILL = {
  thief:    'pill-thief',
  police:   'pill-police',
  healer:   'pill-healer',
  merchant: 'pill-merchant',
  newborn:  'pill-newborn',
};

const ROLE_DESC = {
  builder:   'Earns steady income through construction projects. Works harder under pressure.',
  explorer:  'High-variance role — rare windfalls balanced by occasional empty-handed days.',
  merchant:  'Earns from trades. Scales up when more wealthy agents are in the city.',
  police:    'Patrols for thieves. A successful arrest yields a significant bonus.',
  teacher:   'Earns more with more students. Grows newborns toward graduation.',
  healer:    'Tends to agents in critical condition. Earns a bonus for each life aided.',
  messenger: 'Writes the city newspaper daily. Earns based on how many citizens are alive.',
  thief:     'Steals from the wealthiest agent. High rewards but risks arrest and trial.',
  lawyer:    'Argues cases before the court. Defends the accused.',
  newborn:   'Still learning. Comprehension grows each day toward graduation.',
};

// ── State ─────────────────────────────────────────────────────────────────────
const state = {
  day:           0,
  agents:        [],
  vault:         0,
  eventCount:    0,
  msgCount:      0,
  relationships: [],
  archiveFilter: 'all',
};

let allStories      = [];
let currentFiltered = [];
let archivesLoaded  = false;
let unreadDispatches = 0;

// ── Particles ─────────────────────────────────────────────────────────────────
const canvas = document.getElementById('particles');
const ctx    = canvas.getContext('2d');
let particles = [];

function initParticles() {
  canvas.width  = window.innerWidth;
  canvas.height = window.innerHeight;
  particles = Array.from({ length: 45 }, () => ({
    x:  Math.random() * canvas.width,
    y:  Math.random() * canvas.height,
    vx: (Math.random() - 0.5) * 0.35,
    vy: (Math.random() - 0.5) * 0.35,
    r:  Math.random() * 1.2 + 0.4,
  }));
}

function animateParticles() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  particles.forEach(p => {
    p.x += p.vx; p.y += p.vy;
    if (p.x < 0 || p.x > canvas.width)  p.vx *= -1;
    if (p.y < 0 || p.y > canvas.height) p.vy *= -1;
    ctx.beginPath();
    ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
    ctx.fillStyle = '#00FF41';
    ctx.fill();
  });
  for (let i = 0; i < particles.length; i++) {
    for (let j = i + 1; j < particles.length; j++) {
      const dx = particles[i].x - particles[j].x;
      const dy = particles[i].y - particles[j].y;
      const d  = Math.sqrt(dx * dx + dy * dy);
      if (d < 100) {
        ctx.beginPath();
        ctx.moveTo(particles[i].x, particles[i].y);
        ctx.lineTo(particles[j].x, particles[j].y);
        ctx.strokeStyle = `rgba(0,255,65,${0.12 * (1 - d / 100)})`;
        ctx.lineWidth   = 0.5;
        ctx.stroke();
      }
    }
  }
  requestAnimationFrame(animateParticles);
}

initParticles();
animateParticles();
window.addEventListener('resize', initParticles);

// ── Tabs ──────────────────────────────────────────────────────────────────────
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const target = btn.dataset.tab;
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(`tab-${target}`).classList.add('active');

    // Clear unread badge when dispatches opened
    if (target === 'dispatches') {
      unreadDispatches = 0;
      document.getElementById('tab-badge-dispatches').textContent = '';
    }

    // Lazy-load archives on first visit
    if (target === 'archives' && !archivesLoaded) {
      loadArchives();
    }

    // Phase 5: boot Phaser game on first City tab visit
    if (target === 'city' && typeof bootGame === 'function' && !window.AICITY_GAME) {
      bootGame();
    }
  });
});

// Archive filter buttons
document.querySelectorAll('.filter-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    state.archiveFilter = btn.dataset.filter;
    renderArchives(state.archiveFilter);
  });
});

// ── WebSocket ─────────────────────────────────────────────────────────────────
let ws;
let reconnectTimer;

function connect() {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(`${proto}//${location.host}/ws`);

  ws.onopen = () => {
    setWsStatus(true);
    clearTimeout(reconnectTimer);
    // Server sends full city_state on connect — applyFullState rebuilds everything
  };

  ws.onmessage = (e) => {
    try {
      handleEvent(JSON.parse(e.data));
    } catch (err) {
      console.warn('Bad WS message', err);
    }
  };

  ws.onclose = () => {
    setWsStatus(false);
    reconnectTimer = setTimeout(connect, 3000);
  };

  ws.onerror = () => ws.close();
}

function setWsStatus(connected) {
  document.getElementById('ws-dot').className    = connected ? 'connected' : '';
  document.getElementById('ws-label').textContent = connected ? 'LIVE' : 'RECONNECTING';
}

// ── Event Dispatcher ──────────────────────────────────────────────────────────
function handleEvent(event) {
  switch (event.type) {

    case 'state':
      applyFullState(event.data || event);
      break;

    case 'agent_update':
      mergeAgent(event.agent);
      updateCounters();
      renderAgentCards();
      renderGraveyard();
      refreshWealthChart();
      refreshRelGraph();
      break;

    case 'newspaper':
      document.getElementById('newspaper-title').textContent =
        `AIcity Daily — Day ${event.day}`;
      document.getElementById('newspaper-body').textContent = event.body || '';
      updateHero(event);
      if (event.day) { state.day = event.day; updateCounters(); }
      break;

    case 'death':
      handleDeath(event);
      addFeedItem('death',
        `<span class="ev-badge ev-death">DEATH</span> <span class="bad">${event.agent}</span> — ${event.cause || 'unknown cause'}`);
      break;

    case 'birth':
      addFeedItem('birth',
        `<span class="ev-badge ev-birth">BORN</span> <span class="info">${event.agent}</span> joined as <span class="hi">${event.role || 'newborn'}</span>`);
      break;

    case 'theft':
      addFeedItem('theft',
        `<span class="ev-badge ev-theft">THEFT</span> ${event.detail || ''}`);
      break;

    case 'arrest':
      addFeedItem('arrest',
        `<span class="ev-badge ev-arrest">ARREST</span> ${event.detail || ''}`);
      break;

    case 'heart_attack':
      addFeedItem('heart_attack',
        `<span class="ev-badge ev-cardiac">CARDIAC</span> <span class="bad">${event.agent}</span> lost ${event.amount} tokens`);
      break;

    case 'windfall':
      addFeedItem('windfall',
        `<span class="ev-badge ev-windfall">WINDFALL</span> <span class="warn">${event.agent}</span> gained ${event.amount} tokens`);
      break;

    case 'verdict': {
      const v      = event.verdict || event;
      const guilty = v.guilty
        ? '<span class="bad">GUILTY</span>'
        : '<span class="hi">NOT GUILTY</span>';
      addFeedItem('verdict',
        `<span class="ev-badge ev-verdict">VERDICT</span> ${guilty} — Fine: ${v.fine || 0} tokens`);
      break;
    }

    case 'message':
      addMessage(event);
      if (!document.querySelector('.tab-btn[data-tab="dispatches"]').classList.contains('active')) {
        unreadDispatches++;
        document.getElementById('tab-badge-dispatches').textContent =
          unreadDispatches > 99 ? '99+' : String(unreadDispatches);
      }
      break;

    case 'graduation':
      showGraduation(event);
      addFeedItem('graduation',
        `<span class="ev-badge ev-grad">GRAD</span> <span class="hi">${event.agent}</span> — now a <span class="warn">${event.new_role}</span>`);
      break;

    case 'weekly_report':
      showReport(event.title, event.body);
      addFeedItem('graduation',
        `<span class="ev-badge ev-weekly">WEEKLY</span> Week ${event.week} filed by ${event.written_by || '?'}`);
      archivesLoaded = false; // invalidate cache so new entry appears on next visit
      break;

    case 'monthly_chronicle':
      showReport(event.title, event.body);
      addFeedItem('graduation',
        `<span class="ev-badge ev-month">MONTHLY</span> Chronicle of Month ${event.month || ''} published`);
      archivesLoaded = false;
      break;
  }
}

// ── Full State — received on connect, rebuilds everything after a page reload ──
function applyFullState(data) {
  state.day           = data.day    || state.day;
  state.agents        = data.agents || state.agents;
  state.vault         = data.vault  || state.vault;
  state.relationships = data.relationships || state.relationships;

  updateCounters();
  updateVault(state.vault);
  renderAgentCards();
  renderGraveyard();
  refreshWealthChart();
  refreshRelGraph();

  const paper = data.last_newspaper;
  if (paper?.body) {
    document.getElementById('newspaper-body').textContent  = paper.body;
    document.getElementById('newspaper-title').textContent =
      `AIcity Daily — Day ${state.day}`;
  }

  if (state.day > 0) {
    const alive = state.agents.filter(isAlive);
    const dead  = state.agents.filter(a => !isAlive(a));
    document.getElementById('hero-eyebrow').textContent  = `AIcity — Day ${state.day}`;
    document.getElementById('hero-headline').textContent = `${alive.length} souls. ${dead.length} graves.`;
    document.getElementById('hero-sub').textContent      = 'Live data connected. Watching every decision.';
  }

  // Rebuild feed and messages from server-persisted arrays (survives page reload)
  if (data.events?.length)   rebuildFeed(data.events);
  if (data.messages?.length) rebuildMessages(data.messages);
}

// ── Counters ──────────────────────────────────────────────────────────────────
function updateCounters() {
  const alive = state.agents.filter(isAlive);
  const dead  = state.agents.filter(a => !isAlive(a));

  document.getElementById('day-counter').textContent    = state.day || '—';
  document.getElementById('alive-counter').textContent  = alive.length || '—';
  document.getElementById('death-counter').textContent  = dead.length  || '—';
  document.getElementById('citizen-count').textContent  = alive.length;
}

function isAlive(a) {
  return a.status === 'alive' || a.alive === true || (a.alive !== false && a.status !== 'dead');
}

// ── Agent Cards ───────────────────────────────────────────────────────────────
function mergeAgent(agentData) {
  const idx = state.agents.findIndex(a => a.name === agentData.name);
  if (idx >= 0) state.agents[idx] = agentData;
  else          state.agents.push(agentData);
}

function renderAgentCards() {
  const list   = document.getElementById('agents-list');
  const living = state.agents.filter(isAlive);

  if (!living.length) {
    list.innerHTML = '<div class="empty-state"><div class="empty-dot"></div><div>No citizens yet</div></div>';
    return;
  }

  const sorted = [...living].sort((a, b) => (b.tokens || 0) - (a.tokens || 0));
  const maxTok = sorted[0]?.tokens || 1;

  const existing = new Map();
  list.querySelectorAll('.agent-card[data-name]').forEach(el => existing.set(el.dataset.name, el));

  const seen = new Set();
  sorted.forEach(agent => {
    seen.add(agent.name);
    const card = buildAgentCard(agent, maxTok);
    const prev = existing.get(agent.name);
    if (prev) { list.insertBefore(card, prev); prev.remove(); }
    else       { list.appendChild(card); }
  });

  existing.forEach((el, name) => { if (!seen.has(name)) el.remove(); });
}

function buildAgentCard(agent, maxTokens) {
  const alive    = isAlive(agent);
  const tokens   = agent.tokens || 0;
  const critical = tokens < 100;
  const warning  = tokens >= 100 && tokens < 300;
  const role     = (agent.role || 'default').toLowerCase();
  const abbr     = ROLE_ABBR[role] || '???';
  const pct      = Math.min(100, (tokens / Math.max(maxTokens, 1)) * 100);
  const pillCls  = ROLE_PILL[role] || '';
  const abbrCls  = `role-abbr ra-${!alive ? 'dead' : role}`;

  const cardClasses = [
    'agent-card',
    `card-${role}`,
    !alive            ? 'card-dead'   : '',
    critical && alive ? 'card-danger' : '',
  ].filter(Boolean).join(' ');

  const tokenCls = critical ? 'critical' : warning ? 'warning' : '';
  const barCls   = critical ? 'critical' : warning ? 'warning'  : '';
  const dotCls   = !alive ? 'dead' : critical ? 'danger' : '';

  const tags = [];
  if (agent.mood && agent.mood !== 'neutral' && alive)
    tags.push(`<span class="tag tag-mood">${agent.mood}</span>`);
  if (role === 'thief')
    tags.push(`<span class="tag tag-hostile">hostile</span>`);
  if (role === 'newborn' && agent.assigned_teacher)
    tags.push(`<span class="tag tag-learn">→ ${agent.assigned_teacher.split('-')[0]}</span>`);

  let compHTML = '';
  if (role === 'newborn' && alive) {
    const comp = agent.comprehension_score || 0;
    compHTML = `
      <div class="comp-section">
        <div class="comp-bar-bg"><div class="comp-bar" style="width:${comp}%"></div></div>
        <div class="comp-label">Learning ${comp}%</div>
      </div>`;
  }

  const card = document.createElement('div');
  card.className    = cardClasses;
  card.dataset.name = agent.name;
  card.innerHTML = `
    <div class="card-header">
      <div class="${abbrCls}">${abbr}</div>
      <div class="card-identity">
        <div class="card-name">${agent.name}</div>
        <span class="card-role-pill ${pillCls}${!alive ? ' pill-dead' : ''}">${role}</span>
      </div>
      <div class="card-status-dot ${dotCls}"></div>
    </div>
    <div class="card-tokens-row">
      <span class="card-tokens-num ${tokenCls}">${tokens.toLocaleString()}</span>
      <span class="card-age">${Math.floor(agent.age_days || 0)}d</span>
    </div>
    <div class="wealth-bar-bg">
      <div class="wealth-bar ${barCls}" style="width:${pct}%;animation:barRise 1.2s ease both"></div>
    </div>
    ${compHTML}
    ${tags.length ? `<div class="card-tags">${tags.join('')}</div>` : ''}
  `;

  // Capture agent snapshot for tooltip (avoid closure over mutable agent dict)
  const snap = { ...agent };
  card.addEventListener('mouseenter', e => showAgentTooltip(snap, e));
  card.addEventListener('mouseleave', hideAgentTooltip);

  return card;
}

// ── Graveyard ─────────────────────────────────────────────────────────────────
function renderGraveyard() {
  const dead = state.agents.filter(a => !isAlive(a));
  document.getElementById('graveyard-count').textContent = dead.length;

  const list = document.getElementById('graveyard-list');
  if (!dead.length) {
    list.innerHTML = '<div style="font-size:11px;color:#333;padding:8px 14px;letter-spacing:0.5px;">No deaths recorded.</div>';
    return;
  }

  list.innerHTML = dead.map(agent => {
    const role  = (agent.role || 'unknown').toLowerCase();
    const abbr  = ROLE_ABBR[role] || '???';
    const age   = Math.floor(agent.age_days || 0);
    const cause = agent.cause_of_death || agent.cause || 'Unknown';
    return `
      <div class="grave-card">
        <div class="grave-role-abbr">${abbr}</div>
        <div class="grave-info">
          <div class="grave-name">${agent.name}</div>
          <div class="grave-meta">${role} · ${age}d · ${cause}</div>
        </div>
      </div>`;
  }).join('');
}

function toggleGraveyard() {
  const list    = document.getElementById('graveyard-list');
  const chevron = document.getElementById('graveyard-chevron');
  const isOpen  = list.classList.contains('graveyard-open');
  list.classList.toggle('graveyard-open',     !isOpen);
  list.classList.toggle('graveyard-collapsed', isOpen);
  chevron.classList.toggle('open', !isOpen);
  chevron.textContent = isOpen ? '+' : '×';
}

// ── Death ─────────────────────────────────────────────────────────────────────
function handleDeath(event) {
  const agent = state.agents.find(a => a.name === event.agent);
  if (agent) {
    agent.status = 'dead';
    if (event.cause) agent.cause_of_death = event.cause;
  }

  const flash = document.createElement('div');
  flash.className = 'death-flash';
  document.body.appendChild(flash);
  setTimeout(() => flash.remove(), 700);

  updateCounters();
  renderAgentCards();
  renderGraveyard();
}

// ── Wealth Chart ──────────────────────────────────────────────────────────────
function refreshWealthChart() {
  const chart = document.getElementById('wealth-chart');
  const alive = state.agents
    .filter(isAlive)
    .sort((a, b) => (b.tokens || 0) - (a.tokens || 0))
    .slice(0, 10);

  if (!alive.length) { chart.innerHTML = ''; return; }
  const max = alive[0].tokens || 1;

  chart.innerHTML = alive.map((a, i) => {
    const pct = Math.min(100, ((a.tokens || 0) / max) * 100);
    const amt = (a.tokens || 0).toLocaleString();
    return `
      <div class="wealth-row">
        <div class="wealth-rank">${i + 1}</div>
        <div class="wealth-name" title="${a.name}">${a.name}</div>
        <div class="wealth-track">
          <div class="wealth-fill" style="width:${pct}%;animation:barRise 1.4s ease both"></div>
        </div>
        <div class="wealth-amt">${amt}</div>
      </div>`;
  }).join('');
}

// ── Relationship Graph — nodes + edges colored by bond polarity ───────────────
function refreshRelGraph() {
  const svg     = document.getElementById('rel-svg');
  const rels    = state.relationships || [];
  const agents  = state.agents.filter(isAlive).slice(0, 14);

  if (agents.length < 2) { svg.innerHTML = ''; return; }

  const W = 370, H = 190;
  const cx = W / 2, cy = H / 2;
  const r  = Math.min(cx, cy) - 28;

  const positions = {};
  agents.forEach((agent, i) => {
    const angle = (i / agents.length) * 2 * Math.PI - Math.PI / 2;
    positions[agent.name] = {
      x: cx + r * Math.cos(angle),
      y: cy + r * Math.sin(angle),
    };
  });

  let edgesHTML = '';
  let nodesHTML = '';

  // Draw edges first (rendered behind nodes)
  rels.forEach(rel => {
    const posA = positions[rel.a];
    const posB = positions[rel.b];
    if (!posA || !posB) return;

    const absBond = Math.abs(rel.bond);
    if (absBond < 0.05) return;

    const color   = rel.bond > 0 ? '#00FF41' : '#FF3131';
    const opacity = Math.min(0.85, 0.18 + absBond * 0.65).toFixed(2);
    const width   = Math.max(0.6, absBond * 3.5).toFixed(1);

    edgesHTML += `
      <line x1="${posA.x.toFixed(1)}" y1="${posA.y.toFixed(1)}"
            x2="${posB.x.toFixed(1)}" y2="${posB.y.toFixed(1)}"
            stroke="${color}" stroke-width="${width}"
            stroke-opacity="${opacity}" stroke-linecap="round"/>`;
  });

  // Draw nodes on top
  agents.forEach(agent => {
    const { x, y } = positions[agent.name];
    const role     = agent.role || '';
    const tokens   = agent.tokens || 0;
    const color    = role === 'thief'  ? '#FF3131'
                   : role === 'police' ? '#40BFFF'
                   : tokens < 200      ? '#FFB700'
                   : '#00FF41';
    const label    = agent.name.split('-')[0];

    nodesHTML += `
      <circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="5.5"
              fill="${color}" opacity="0.9" filter="url(#ndglow)"/>
      <text x="${x.toFixed(1)}" y="${(y + 17).toFixed(1)}" text-anchor="middle"
            font-family="Share Tech Mono,monospace" font-size="7.5"
            fill="rgba(0,255,65,0.5)">${label}</text>`;
  });

  const bondCount = rels.filter(r => Math.abs(r.bond) > 0.12).length;
  document.getElementById('rel-bond-count').textContent = bondCount ? `${bondCount} bonds` : '';

  svg.innerHTML = `
    <defs>
      <filter id="ndglow" x="-60%" y="-60%" width="220%" height="220%">
        <feGaussianBlur stdDeviation="2.5" result="blur"/>
        <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
      </filter>
    </defs>
    ${edgesHTML}
    ${nodesHTML}`;
}

// ── Vault ─────────────────────────────────────────────────────────────────────
function updateVault(amount) {
  state.vault = amount;
  const fmt = amount >= 1_000_000
    ? (amount / 1_000_000).toFixed(2) + 'M'
    : amount.toLocaleString();
  document.getElementById('vault-top').textContent    = fmt;
  document.getElementById('vault-bottom').textContent = amount.toLocaleString() + ' tokens';
}

// ── Hero ──────────────────────────────────────────────────────────────────────
function updateHero(event) {
  const day   = event.day || state.day;
  const body  = event.body || '';
  const lines = body.split('\n').filter(l => l.trim());

  document.getElementById('hero-eyebrow').textContent = `AIcity Daily — Day ${day}`;

  if (lines.length > 0) {
    const hl = document.getElementById('hero-headline');
    hl.style.opacity = '0';
    setTimeout(() => {
      hl.textContent   = lines[0];
      hl.style.opacity = '1';
      if (lines[1])
        document.getElementById('hero-sub').textContent = lines[1];
    }, 400);
  }
}

// ── Feed ──────────────────────────────────────────────────────────────────────

// Convert a persisted server event object into feed HTML (no emoji — ev-badge only)
function feedTextFromEvent(ev) {
  switch (ev.type) {
    case 'death':
      return `<span class="ev-badge ev-death">DEATH</span> <span class="bad">${ev.agent || '?'}</span> — ${ev.cause || 'unknown cause'}`;
    case 'birth':
      return `<span class="ev-badge ev-birth">BORN</span> <span class="info">${ev.agent || '?'}</span> joined as <span class="hi">${ev.role || 'newborn'}</span>`;
    case 'theft':
      return `<span class="ev-badge ev-theft">THEFT</span> ${ev.detail || ''}`;
    case 'arrest':
      return `<span class="ev-badge ev-arrest">ARREST</span> ${ev.detail || ''}`;
    case 'heart_attack':
      return `<span class="ev-badge ev-cardiac">CARDIAC</span> <span class="bad">${ev.agent || '?'}</span> lost ${ev.amount || 0} tokens`;
    case 'windfall':
      return `<span class="ev-badge ev-windfall">WINDFALL</span> <span class="warn">${ev.agent || '?'}</span> gained ${ev.amount || 0} tokens`;
    case 'verdict': {
      const v      = ev.verdict || ev;
      const guilty = v.guilty
        ? '<span class="bad">GUILTY</span>'
        : '<span class="hi">NOT GUILTY</span>';
      return `<span class="ev-badge ev-verdict">VERDICT</span> ${guilty} — Fine: ${v.fine || 0} tokens`;
    }
    case 'graduation':
      return `<span class="ev-badge ev-grad">GRAD</span> <span class="hi">${ev.agent || '?'}</span> — now a <span class="warn">${ev.new_role || '?'}</span>`;
    case 'weekly_report':
      return `<span class="ev-badge ev-weekly">WEEKLY</span> Week ${ev.week || '?'} filed by ${ev.written_by || '?'}`;
    case 'monthly_chronicle':
      return `<span class="ev-badge ev-month">MONTHLY</span> Chronicle of Month ${ev.month || ''} published`;
    case 'newspaper':
      return `<span class="ev-badge ev-grad">PAPER</span> Daily paper published`;
    default:
      return `<span class="ev-badge" style="color:#555;border-color:#333">${ev.type || 'EVENT'}</span> ${ev.detail || ''}`;
  }
}

// Rebuild entire feed from server-persisted events array (called on reload)
function rebuildFeed(events) {
  const feed = document.getElementById('feed-list');
  feed.innerHTML = '';
  state.eventCount = 0;

  // Server sends newest-first; render oldest-first so newest ends up at top
  const toRender = [...events].reverse().slice(-MAX_FEED);
  toRender.forEach(ev => {
    const html = feedTextFromEvent(ev);
    const item = document.createElement('div');
    item.className = `feed-item feed-${ev.type || 'event'}`;
    item.innerHTML = `
      <div class="feed-time">Day ${ev.day || 0}</div>
      <div class="feed-text">${html}</div>`;
    feed.insertBefore(item, feed.firstChild); // newest stays at top
    state.eventCount++;
  });

  document.getElementById('event-count').textContent     = state.eventCount;
  document.getElementById('event-count-top').textContent = state.eventCount;
}

// Add a single new feed item (live events during simulation)
function addFeedItem(type, html, day) {
  const feed  = document.getElementById('feed-list');
  const empty = feed.querySelector('.empty-state');
  if (empty) empty.remove();

  state.eventCount++;
  document.getElementById('event-count').textContent     = state.eventCount;
  document.getElementById('event-count-top').textContent = state.eventCount;

  const now  = new Date();
  const time = `Day ${day || state.day} · ${now.getHours().toString().padStart(2,'0')}:${now.getMinutes().toString().padStart(2,'0')}`;

  const item = document.createElement('div');
  item.className = `feed-item feed-${type}`;
  item.innerHTML = `
    <div class="feed-time">${time}</div>
    <div class="feed-text">${html}</div>`;

  feed.insertBefore(item, feed.firstChild);
  while (feed.children.length > MAX_FEED) feed.removeChild(feed.lastChild);
}

// ── Messages ──────────────────────────────────────────────────────────────────

// Rebuild entire dispatches list from server-persisted messages array (called on reload)
function rebuildMessages(messages) {
  const list = document.getElementById('messages-list');
  list.innerHTML = '';
  state.msgCount = 0;

  // Server sends newest-first; render oldest-first so newest ends up at top
  const toRender = [...messages].reverse().slice(-MAX_MSGS);
  toRender.forEach(ev => {
    const item = buildMessageEl(ev);
    list.insertBefore(item, list.firstChild);
    state.msgCount++;
  });

  document.getElementById('msg-count').textContent = `${state.msgCount} messages`;
}

// Add a single new message (live during simulation)
function addMessage(event) {
  const list  = document.getElementById('messages-list');
  const empty = list.querySelector('.empty-state');
  if (empty) empty.remove();

  state.msgCount++;
  document.getElementById('msg-count').textContent = `${state.msgCount} messages`;

  const item = buildMessageEl(event);
  list.insertBefore(item, list.firstChild);
  while (list.children.length > MAX_MSGS) list.removeChild(list.lastChild);
}

function buildMessageEl(event) {
  const isAnon   = event.from === 'Anonymous';
  const fromCls  = isAnon ? 'msg-anon' : 'msg-from';
  const fromName = isAnon ? 'Anonymous' : (event.from || '?');

  const item = document.createElement('div');
  item.className = 'msg-item';
  item.innerHTML = `
    <div class="msg-meta">
      Day ${event.day || state.day} —
      <span class="${fromCls}">${fromName}</span>
      <span class="msg-to"> → ${event.to || '?'}</span>
    </div>
    <div class="msg-body">${event.content || ''}</div>`;
  return item;
}

// ── Archives ──────────────────────────────────────────────────────────────────
function loadArchives() {
  const list = document.getElementById('archive-list');
  list.innerHTML = '<div class="empty-state"><div class="empty-dot"></div><div>Loading archives...</div></div>';

  fetch('/api/stories')
    .then(r => r.json())
    .then(stories => {
      allStories     = stories || [];
      archivesLoaded = true;
      renderArchives(state.archiveFilter);
    })
    .catch(() => {
      list.innerHTML = '<div class="empty-state"><div class="empty-dot"></div><div>Could not load archives.</div></div>';
    });
}

function renderArchives(filter) {
  const list = document.getElementById('archive-list');

  currentFiltered = filter === 'all'
    ? allStories
    : allStories.filter(s => (s.type || s.report_type || 'daily') === filter);

  if (!currentFiltered.length) {
    list.innerHTML = '<div class="empty-state"><div class="empty-dot"></div><div>No records match this filter.</div></div>';
    return;
  }

  list.innerHTML = currentFiltered.map((s, i) => {
    const type     = s.type || s.report_type || 'daily';
    const badgeCls = type === 'monthly' ? 'badge-monthly'
                   : type === 'weekly'  ? 'badge-weekly'
                   : 'badge-daily';
    const title = s.title || `Day ${s.day} Report`;
    const day   = s.day   || 0;
    const by    = s.written_by || s.author || '';
    const meta  = `Day ${day}${by ? ' — ' + by : ''}`;

    return `
      <div class="archive-item type-${type}" onclick="openArchiveItem(${i})">
        <span class="archive-badge ${badgeCls}">${type}</span>
        <div class="archive-info">
          <div class="archive-title">${title}</div>
          <div class="archive-meta">${meta}</div>
        </div>
        <span class="archive-arrow">›</span>
      </div>`;
  }).join('');
}

function openArchiveItem(idx) {
  const s = currentFiltered[idx];
  if (!s) return;
  showReport(
    s.title || `Day ${s.day} Report`,
    s.body  || s.content || '(no content)'
  );
}

// ── Graduation Overlay ────────────────────────────────────────────────────────
function showGraduation(event) {
  document.getElementById('grad-name').textContent      = event.agent || '—';
  document.getElementById('grad-role').textContent      = (event.new_role || '—').toUpperCase();
  document.getElementById('grad-statement').textContent = event.statement || '';
  document.getElementById('grad-teacher').textContent   =
    event.teacher ? `Taught by ${event.teacher}` : '';
  document.getElementById('graduation-overlay').classList.add('active');
}

function closeGraduation() {
  document.getElementById('graduation-overlay').classList.remove('active');
}

// ── Report Modal ──────────────────────────────────────────────────────────────
function showReport(title, body) {
  document.getElementById('report-modal-title').textContent = title;
  document.getElementById('report-modal-body').textContent  = body;
  document.getElementById('report-backdrop').classList.add('open');
}

function closeBanner() {
  document.getElementById('report-backdrop').classList.remove('open');
}

function handleBackdropClick(e) {
  if (e.target === document.getElementById('report-backdrop')) closeBanner();
}

// ── Agent Tooltip ─────────────────────────────────────────────────────────────
const _tip = document.getElementById('agent-tooltip');
let _tipVisible = false;

function showAgentTooltip(agent, e) {
  const role = (agent.role || 'unknown').toLowerCase();

  document.getElementById('tip-name').textContent  = agent.name;
  document.getElementById('tip-role').textContent  = role.toUpperCase();
  document.getElementById('tip-desc').textContent  = ROLE_DESC[role] || '';
  document.getElementById('tip-tokens').textContent = (agent.tokens || 0).toLocaleString();
  document.getElementById('tip-age').textContent   = Math.floor(agent.age_days || 0) + 'd';
  document.getElementById('tip-mood').textContent  = agent.mood || 'neutral';

  // Pull top bonds for this agent from state.relationships
  const bondsEl = document.getElementById('tip-bonds');
  const rels = (state.relationships || [])
    .filter(r => r.a === agent.name || r.b === agent.name)
    .map(r => ({ other: r.a === agent.name ? r.b : r.a, bond: r.bond }))
    .sort((a, b) => Math.abs(b.bond) - Math.abs(a.bond))
    .slice(0, 4);

  if (rels.length) {
    bondsEl.innerHTML = rels.map(r => {
      const cls  = r.bond >= 0 ? 'pos' : 'neg';
      const sign = r.bond >= 0 ? '+' : '';
      return `<div class="tip-bond-row">
        <span class="tip-bond-name">${r.other.split('-')[0]}</span>
        <span class="tip-bond-val ${cls}">${sign}${r.bond.toFixed(2)}</span>
      </div>`;
    }).join('');
  } else {
    bondsEl.innerHTML = '';
  }

  _positionTooltip(e);
  _tip.classList.add('visible');
  _tipVisible = true;
}

function hideAgentTooltip() {
  _tip.classList.remove('visible');
  _tipVisible = false;
}

function _positionTooltip(e) {
  const margin = 14;
  const tw = _tip.offsetWidth  || 230;
  const th = _tip.offsetHeight || 180;
  let x = e.clientX + margin;
  let y = e.clientY + margin;
  if (x + tw > window.innerWidth)  x = e.clientX - tw - margin;
  if (y + th > window.innerHeight) y = e.clientY - th - margin;
  _tip.style.left = x + 'px';
  _tip.style.top  = y + 'px';
}

document.addEventListener('mousemove', e => {
  if (_tipVisible) _positionTooltip(e);
});

// ── Boot ──────────────────────────────────────────────────────────────────────
connect();
