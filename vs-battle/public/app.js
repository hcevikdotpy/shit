const $ = (sel, root = document) => root.querySelector(sel);

const store = {
  get(key, fallback = '') {
    try { return localStorage.getItem(key) ?? fallback; } catch { return fallback; }
  },
  set(key, value) {
    try { localStorage.setItem(key, value); } catch { /* storage unavailable */ }
  },
};

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

async function getJson(url, opts) {
  const res = await fetch(url, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

function debounce(fn, ms) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

// Minimal, safe Markdown: escapes HTML first, then applies a small subset.
function markdown(src) {
  const inline = (s) => s
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^*])\*(?!\s)(.+?)\*/g, '$1<em>$2</em>')
    .replace(/`([^`]+)`/g, '<code>$1</code>');
  const out = [];
  let list = null;
  const closeList = () => { if (list) { out.push(`</${list}>`); list = null; } };
  for (const raw of esc(src).split('\n')) {
    const line = raw.trim();
    let m;
    if (!line) { closeList(); continue; }
    if ((m = line.match(/^#{1,4}\s+(.*)/))) { closeList(); out.push(`<h4>${inline(m[1])}</h4>`); continue; }
    if ((m = line.match(/^[-*•]\s+(.*)/))) {
      if (list !== 'ul') { closeList(); out.push('<ul>'); list = 'ul'; }
      out.push(`<li>${inline(m[1])}</li>`); continue;
    }
    if ((m = line.match(/^\d+[.)]\s+(.*)/))) {
      if (list !== 'ol') { closeList(); out.push('<ol>'); list = 'ol'; }
      out.push(`<li>${inline(m[1])}</li>`); continue;
    }
    closeList();
    out.push(`<p>${inline(line)}</p>`);
  }
  closeList();
  return out.join('');
}

// ------------------------------------------------------------ autocomplete

function autocomplete({ input, list, fetchItems, renderItem, onSelect, openOnFocus = false }) {
  let items = [];
  let active = -1;
  let controller = null;
  let seq = 0;

  const close = () => {
    list.hidden = true;
    input.setAttribute('aria-expanded', 'false');
    active = -1;
  };

  const highlight = (i) => {
    active = i;
    [...list.children].forEach((li, idx) => li.classList.toggle('active', idx === i));
    list.children[i]?.scrollIntoView({ block: 'nearest' });
  };

  const show = (state) => {
    list.innerHTML = '';
    if (state === 'loading') {
      list.innerHTML = '<li class="ac-status"><span class="spinner"></span> Suche …</li>';
    } else if (state === 'error') {
      list.innerHTML = '<li class="ac-status">Fehler beim Laden – nochmal versuchen.</li>';
    } else if (!items.length) {
      list.innerHTML = '<li class="ac-status">Keine Treffer</li>';
    } else {
      items.forEach((item, i) => {
        const li = document.createElement('li');
        li.setAttribute('role', 'option');
        li.innerHTML = renderItem(item);
        li.addEventListener('mousedown', (e) => { e.preventDefault(); choose(i); });
        li.addEventListener('mousemove', () => active !== i && highlight(i));
        list.appendChild(li);
      });
    }
    list.hidden = false;
    input.setAttribute('aria-expanded', 'true');
  };

  const choose = (i) => {
    const item = items[i];
    if (!item) return;
    close();
    onSelect(item);
  };

  const run = async () => {
    const q = input.value.trim();
    if (!q && !openOnFocus()) { close(); return; }
    controller?.abort();
    controller = new AbortController();
    const my = ++seq;
    show('loading');
    try {
      items = await fetchItems(q, controller.signal);
      if (my === seq) { show(); if (items.length) highlight(0); }
    } catch (err) {
      if (err.name !== 'AbortError' && my === seq) show('error');
    }
  };
  const debounced = debounce(run, 220);

  input.addEventListener('input', debounced);
  input.addEventListener('focus', () => { if (input.value.trim() || openOnFocus()) run(); });
  input.addEventListener('blur', () => setTimeout(close, 120));
  input.addEventListener('keydown', (e) => {
    if (list.hidden && e.key === 'ArrowDown') { run(); return; }
    if (list.hidden) return;
    if (e.key === 'ArrowDown') { e.preventDefault(); highlight(Math.min(items.length - 1, active + 1)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); highlight(Math.max(0, active - 1)); }
    else if (e.key === 'Enter') { e.preventDefault(); choose(active < 0 ? 0 : active); }
    else if (e.key === 'Escape') { close(); }
  });

  return { refresh: run, close };
}

// ------------------------------------------------------------ fighters

const state = { config: null, fighters: {} };

function fillSelect(select, values, label = (v) => v) {
  for (const v of values) {
    const o = document.createElement('option');
    o.value = v;
    o.textContent = label(v);
    select.appendChild(o);
  }
}

function createFighter(root, side) {
  root.appendChild($('#fighterTpl').content.cloneNode(true));
  const f = {
    side,
    root,
    character: null,
    filters: { verse: '', tier: '', media: '', alignment: '' },
    key: '',
  };
  $('.side-tag', root).textContent = `Kämpfer ${side}`;

  const filterBtn = $('.filter-btn', root);
  const filtersEl = $('.filters', root);
  const tierSel = $('.tier-select', root);
  const mediaSel = $('.media-select', root);
  const alignSel = $('.align-select', root);
  const verseInput = $('.verse-input', root);
  const charInput = $('.char-input', root);

  fillSelect(tierSel, state.config.tiers, (t) => `Tier ${t}`);
  fillSelect(mediaSel, state.config.media, (m) => m.replace(/ Characters$/, ''));
  fillSelect(alignSel, state.config.alignments, (a) => ({ 'Good Characters': 'Gut', 'Neutral Characters': 'Neutral', 'Evil Characters': 'Böse' }[a] || a));

  const hasFilters = () => Object.values(f.filters).some(Boolean);
  const updateFilterBadge = () => {
    const n = Object.values(f.filters).filter(Boolean).length;
    const badge = $('.filter-count', root);
    badge.hidden = !n;
    badge.textContent = n;
    charInput.placeholder = f.filters.verse ? `In ${f.filters.verse} suchen …` : 'Charakter suchen …';
  };

  filterBtn.addEventListener('click', () => {
    filtersEl.hidden = !filtersEl.hidden;
    filterBtn.setAttribute('aria-expanded', String(!filtersEl.hidden));
  });

  const onFilterChange = () => {
    updateFilterBadge();
    if (document.activeElement === charInput) charAc.refresh();
  };
  tierSel.addEventListener('change', () => { f.filters.tier = tierSel.value; onFilterChange(); });
  mediaSel.addEventListener('change', () => { f.filters.media = mediaSel.value; onFilterChange(); });
  alignSel.addEventListener('change', () => { f.filters.alignment = alignSel.value; onFilterChange(); });
  verseInput.addEventListener('input', () => {
    // Free text only counts once a verse was picked from the list.
    if (f.filters.verse && verseInput.value !== f.filters.verse) { f.filters.verse = ''; updateFilterBadge(); }
  });

  autocomplete({
    input: verseInput,
    list: $('.verse-ac .ac-list', root),
    openOnFocus: () => false,
    fetchItems: async (q, signal) => (await getJson(`/api/verses?q=${encodeURIComponent(q)}`, { signal })).verses,
    renderItem: (v) => `<span class="ac-title">${esc(v)}</span>`,
    onSelect: (v) => {
      f.filters.verse = v;
      verseInput.value = v;
      updateFilterBadge();
      charInput.focus();
    },
  });

  $('.reset-filters', root).addEventListener('click', () => {
    f.filters = { verse: '', tier: '', media: '', alignment: '' };
    verseInput.value = '';
    tierSel.value = mediaSel.value = alignSel.value = '';
    updateFilterBadge();
  });

  const query = (q) => {
    const p = new URLSearchParams({ q, ...f.filters });
    for (const [k, v] of [...p]) if (!v) p.delete(k);
    return p.toString();
  };

  const charAc = autocomplete({
    input: charInput,
    list: $('.char-ac .ac-list', root),
    openOnFocus: hasFilters,
    fetchItems: async (q, signal) => (await getJson(`/api/search?${query(q)}`, { signal })).results,
    renderItem: (c) => `
      ${c.thumb ? `<img src="${esc(c.thumb)}" alt="" loading="lazy" referrerpolicy="no-referrer">` : '<span class="ac-noimg">?</span>'}
      <span class="ac-text"><span class="ac-title">${esc(c.name)}</span>${c.variant ? `<span class="ac-sub">${esc(c.variant)}</span>` : ''}</span>`,
    onSelect: (c) => { charInput.value = ''; select(c.title); },
  });

  const randomBtn = $('.random-btn', root);
  randomBtn.addEventListener('click', async () => {
    randomBtn.disabled = true;
    randomBtn.classList.add('spinning');
    try {
      const { character } = await getJson(`/api/random?${query('')}`);
      await select(character.title);
    } catch (err) {
      renderCardError(err.message);
    } finally {
      randomBtn.disabled = false;
      randomBtn.classList.remove('spinning');
    }
  });

  const card = () => $('.card', root);

  function renderCardError(msg) {
    card().className = 'card empty';
    card().innerHTML = `<div class="placeholder"><span>!</span><p>${esc(msg)}</p></div>`;
  }

  async function select(title) {
    f.character = null;
    onFightersChanged();
    card().className = 'card loading';
    card().innerHTML = '<div class="placeholder"><span class="spinner big"></span><p>Lade Profil …</p></div>';
    try {
      const { character } = await getJson(`/api/character?title=${encodeURIComponent(title)}`);
      f.character = character;
      f.key = '';
      renderCard();
    } catch (err) {
      renderCardError(err.message);
    }
    onFightersChanged();
  }

  function renderCard() {
    const c = f.character;
    const el = card();
    el.className = 'card';
    const stat = (label, value) => value ? `<div class="stat"><dt>${label}</dt><dd>${esc(value)}</dd></div>` : '';
    el.innerHTML = `
      <div class="portrait">
        ${c.image ? `<img src="${esc(c.image)}" alt="${esc(c.title)}" referrerpolicy="no-referrer">` : '<span class="noimg">?</span>'}
      </div>
      <div class="card-body">
        <h3>${esc(c.name)}</h3>
        ${c.variant ? `<p class="variant">${esc(c.variant)}</p>` : ''}
        <dl class="stats">
          ${stat('Tier', c.stats.tier)}
          ${stat('Herkunft', c.stats.origin)}
          ${stat('Angriffskraft', c.stats.attackPotency)}
          ${stat('Geschwindigkeit', c.stats.speed)}
          ${stat('Haltbarkeit', c.stats.durability)}
        </dl>
        <label class="key-label">Key / Version
          <input class="key-input" type="text" maxlength="150" placeholder="stärkste (Standard)" value="${esc(f.key)}">
        </label>
        <div class="card-actions">
          <a href="${esc(c.url)}" target="_blank" rel="noopener">Wiki-Profil ↗</a>
          <button class="link-btn clear-btn">Entfernen</button>
        </div>
      </div>`;
    $('.key-input', el).addEventListener('input', (e) => { f.key = e.target.value; });
    $('.clear-btn', el).addEventListener('click', () => {
      f.character = null;
      el.className = 'card empty';
      el.innerHTML = '<div class="placeholder"><span>?</span><p>Noch kein Kämpfer gewählt</p></div>';
      onFightersChanged();
    });
  }

  f.select = select;
  f.renderCard = renderCard;
  return f;
}

// ------------------------------------------------------------ battle

const fightBtn = $('#fightBtn');
const fightHint = $('#fightHint');
const resultEl = $('#result');

function onFightersChanged() {
  const { A, B } = state.fighters;
  const ready = Boolean(A?.character && B?.character);
  fightBtn.disabled = !ready;
  fightHint.textContent = ready
    ? `${A.character.name} vs. ${B.character.name}`
    : 'Wähle zwei Charaktere aus.';
  const params = new URLSearchParams();
  if (A?.character) params.set('a', A.character.title);
  if (B?.character) params.set('b', B.character.title);
  const qs = params.toString();
  history.replaceState(null, '', qs ? `?${qs}` : location.pathname);
}

function currentModel() {
  return $('#customModel').value.trim() || $('#modelSelect').value;
}

async function fight() {
  const { A, B } = state.fighters;
  if (!A.character || !B.character) return;
  if (!state.config.hasServerKey && !$('#apiKey').value.trim()) {
    openSettings();
    $('#apiKey').focus();
    showError('Bitte zuerst einen OpenRouter API-Key in den Einstellungen eintragen.');
    return;
  }
  fightBtn.disabled = true;
  fightBtn.classList.add('busy');
  fightBtn.querySelector('.fight-label').textContent = 'Das Orakel urteilt …';
  resultEl.hidden = false;
  resultEl.innerHTML = `
    <div class="result-loading">
      <div class="clash">
        <img src="${esc(A.character.image || '')}" alt="" referrerpolicy="no-referrer">
        <span class="spark">⚡</span>
        <img src="${esc(B.character.image || '')}" alt="" referrerpolicy="no-referrer">
      </div>
      <p>Profile werden analysiert und der Kampf simuliert …</p>
    </div>`;
  resultEl.scrollIntoView({ behavior: 'smooth', block: 'start' });

  try {
    const headers = { 'Content-Type': 'application/json' };
    const key = $('#apiKey').value.trim();
    if (key) headers['X-OpenRouter-Key'] = key;
    const data = await getJson('/api/battle', {
      method: 'POST',
      headers,
      body: JSON.stringify({
        a: A.character.title,
        b: B.character.title,
        model: currentModel(),
        lang: $('#langSelect').value,
        scenario: {
          keyA: A.key.trim(),
          keyB: B.key.trim(),
          bloodlusted: $('#optBloodlust').checked,
          speedEqualized: $('#optSpeedEq').checked,
          prep: $('#optPrep').checked,
          notes: $('#optNotes').value.trim(),
        },
      }),
    });
    renderResult(data);
  } catch (err) {
    showError(err.message);
  } finally {
    fightBtn.disabled = false;
    fightBtn.classList.remove('busy');
    fightBtn.querySelector('.fight-label').textContent = 'Kampf starten';
  }
}

function showError(msg) {
  resultEl.hidden = false;
  resultEl.innerHTML = `<div class="result-error"><strong>Fehler:</strong> ${esc(msg)}</div>`;
}

function renderResult({ a, b, result: r }) {
  const winner = r.winner === 'A' ? a : r.winner === 'B' ? b : null;
  const loser = r.winner === 'A' ? b : r.winner === 'B' ? a : null;
  const edgeClass = (e) => (e === 'A' ? 'edge-a' : e === 'B' ? 'edge-b' : 'edge-even');
  const edgeLabel = (e) => (e === 'A' ? `◀ ${esc(a.name)}` : e === 'B' ? `${esc(b.name)} ▶` : 'ausgeglichen');

  resultEl.innerHTML = `
    <div class="winner-banner ${winner ? `win-${r.winner.toLowerCase()}` : 'win-draw'}">
      ${winner ? `
        <div class="winner-img">${winner.image ? `<img src="${esc(winner.image)}" alt="" referrerpolicy="no-referrer">` : ''}</div>
        <div class="winner-text">
          <span class="crown">🏆 Sieger</span>
          <h2>${esc(winner.name)}</h2>
          ${winner.variant ? `<p class="variant">${esc(winner.variant)}</p>` : ''}
          <p class="verdict">${esc(r.verdict)}</p>
        </div>` : `
        <div class="winner-text">
          <span class="crown">🤝 Unentschieden</span>
          <h2>${esc(a.name)} = ${esc(b.name)}</h2>
          <p class="verdict">${esc(r.verdict)}</p>
        </div>`}
      <div class="confidence">
        <div class="conf-label"><span>Sicherheit</span><strong>${r.confidence}%</strong></div>
        <div class="conf-bar"><div style="width:${r.confidence}%"></div></div>
      </div>
    </div>

    <div class="keys">
      <div><span class="dot dot-a"></span><strong>${esc(a.name)}</strong> ${r.tierA ? `· Tier ${esc(r.tierA)}` : ''} ${r.keyA ? `<small>(${esc(r.keyA)})</small>` : ''}</div>
      <div><span class="dot dot-b"></span><strong>${esc(b.name)}</strong> ${r.tierB ? `· Tier ${esc(r.tierB)}` : ''} ${r.keyB ? `<small>(${esc(r.keyB)})</small>` : ''}</div>
    </div>

    ${r.categories.length ? `
    <div class="table-wrap">
      <table class="compare">
        <thead><tr><th>Kategorie</th><th class="col-a">${esc(a.name)}</th><th class="col-b">${esc(b.name)}</th><th>Vorteil</th></tr></thead>
        <tbody>
          ${r.categories.map((c) => `
            <tr class="${edgeClass(c.edge)}">
              <th scope="row">${esc(c.name)}</th>
              <td class="col-a">${esc(c.a)}</td>
              <td class="col-b">${esc(c.b)}</td>
              <td class="edge">${edgeLabel(c.edge)}</td>
            </tr>`).join('')}
        </tbody>
      </table>
    </div>` : ''}

    <article class="explanation">
      <h3>Begründung</h3>
      ${markdown(r.explanation)}
      ${loser && r.loserWinCondition ? `<div class="wincon"><strong>Wie ${esc(loser.name)} gewinnen könnte:</strong> ${esc(r.loserWinCondition)}</div>` : ''}
    </article>
    <p class="model-note">Modell: ${esc(r.model)}${r.usage?.total_tokens ? ` · ${r.usage.total_tokens.toLocaleString('de-DE')} Tokens` : ''}</p>`;
}

// ------------------------------------------------------------ settings

function openSettings(force = true) {
  const el = $('#settings');
  el.hidden = force === 'toggle' ? !el.hidden : !force;
  $('#settingsBtn').setAttribute('aria-expanded', String(!el.hidden));
}

function initSettings() {
  const { models, defaultModel, hasServerKey } = state.config;
  const sel = $('#modelSelect');
  const all = models.some((m) => m.id === defaultModel) ? models : [{ id: defaultModel, label: defaultModel }, ...models];
  for (const m of all) {
    const o = document.createElement('option');
    o.value = m.id;
    o.textContent = m.label;
    sel.appendChild(o);
  }
  sel.value = store.get('model', defaultModel);
  if (!sel.value) sel.value = defaultModel;
  $('#customModel').value = store.get('customModel');
  $('#langSelect').value = store.get('lang', 'de');
  $('#apiKeyWrap').hidden = hasServerKey;
  $('#apiKey').value = store.get('apiKey');

  sel.addEventListener('change', () => store.set('model', sel.value));
  $('#customModel').addEventListener('input', (e) => store.set('customModel', e.target.value.trim()));
  $('#langSelect').addEventListener('change', (e) => store.set('lang', e.target.value));
  $('#apiKey').addEventListener('input', (e) => store.set('apiKey', e.target.value.trim()));
  $('#settingsBtn').addEventListener('click', () => openSettings('toggle'));
  if (!hasServerKey && !store.get('apiKey')) openSettings(true);
}

// ------------------------------------------------------------ boot

async function init() {
  try {
    state.config = await getJson('/api/config');
  } catch (err) {
    document.querySelector('main').innerHTML = `<div class="result-error">Server nicht erreichbar: ${esc(err.message)}</div>`;
    return;
  }
  initSettings();
  for (const el of document.querySelectorAll('.fighter')) {
    state.fighters[el.dataset.side] = createFighter(el, el.dataset.side);
  }
  fightBtn.addEventListener('click', fight);

  $('#swapBtn').addEventListener('click', () => {
    const { A, B } = state.fighters;
    [A.character, B.character] = [B.character, A.character];
    [A.key, B.key] = [B.key, A.key];
    for (const f of [A, B]) {
      if (f.character) f.renderCard();
      else {
        const card = f.root.querySelector('.card');
        card.className = 'card empty';
        card.innerHTML = '<div class="placeholder"><span>?</span><p>Noch kein Kämpfer gewählt</p></div>';
      }
    }
    onFightersChanged();
  });

  const params = new URLSearchParams(location.search);
  if (params.get('a')) state.fighters.A.select(params.get('a'));
  if (params.get('b')) state.fighters.B.select(params.get('b'));
}

init();
