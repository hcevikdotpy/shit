// Access to the VS Battles Wiki (https://vsbattles.fandom.com) via the MediaWiki API.

const WIKI = 'https://vsbattles.fandom.com';
const API = `${WIKI}/api.php`;
// Fandom rejects requests without a descriptive User-Agent.
const USER_AGENT = 'VSBattleOracle/1.0 (character comparison tool; +https://vsbattles.fandom.com)';

export const TIERS = [
  '0', 'High 1-A', '1-A', 'Low 1-A', 'High 1-B', '1-B', 'High 1-C', '1-C', 'Low 1-C',
  '2-A', '2-B', '2-C', 'Low 2-C', '3-A', 'High 3-A', '3-B', '3-C',
  '4-A', '4-B', '4-C', 'High 4-C', 'Low 4-C', '5-A', 'High 5-A', '5-B', 'Low 5-B', '5-C',
  '6-A', 'High 6-A', '6-B', 'High 6-B', 'Low 6-B', '6-C', 'High 6-C',
  '7-A', 'High 7-A', '7-B', 'Low 7-B', '7-C', 'High 7-C', 'Low 7-C',
  '8-A', '8-B', '8-C', 'High 8-C', '9-A', '9-B', '9-C', '10-A', '10-B', '10-C',
];

export const MEDIA = [
  'Anime Characters', 'Manga Characters', 'Manhwa Characters', 'Light Novel Characters',
  'Video Game Characters', 'Game Characters', 'Comic Book Characters', 'Webcomic Characters',
  'Cartoon Characters', 'Movie Characters', 'TV Characters', 'Book Characters',
  'Internet Characters', 'Visual Novel Characters',
];

export const ALIGNMENTS = ['Good Characters', 'Neutral Characters', 'Evil Characters'];

// ---------------------------------------------------------------- helpers

const cache = new Map();
async function cached(key, ttlMs, fn) {
  const hit = cache.get(key);
  if (hit && hit.expires > Date.now()) return hit.value;
  const value = fn();
  cache.set(key, { value, expires: Date.now() + ttlMs });
  try {
    return await value;
  } catch (err) {
    cache.delete(key);
    throw err;
  }
}

async function api(params) {
  const url = new URL(API);
  for (const [k, v] of Object.entries({ format: 'json', formatversion: '2', ...params })) {
    if (v !== undefined && v !== null) url.searchParams.set(k, String(v));
  }
  const res = await fetch(url, {
    headers: { 'User-Agent': USER_AGENT, Accept: 'application/json' },
    signal: AbortSignal.timeout(20000),
  });
  if (!res.ok) throw new Error(`Wiki API ${res.status}`);
  const data = await res.json();
  if (data.error) throw new Error(`Wiki API: ${data.error.info || data.error.code}`);
  return data;
}

// Follows `continue` tokens until `max` items are collected.
async function apiList(params, listKey, max = 5000) {
  const items = [];
  let cont = {};
  while (items.length < max) {
    const data = await api({ ...params, ...cont });
    items.push(...(data.query?.[listKey] || []));
    if (!data.continue) break;
    cont = data.continue;
  }
  return items.slice(0, max);
}

const HOUR = 3600e3;
export const pageUrl = (title) => `${WIKI}/wiki/${encodeURIComponent(title.replace(/ /g, '_'))}`;
const stripCat = (t) => t.replace(/^Category:/, '');

function thumbUrl(src, width) {
  // Fandom thumbnails look like .../revision/latest/scale-to-width-down/84?cb=...
  if (!src) return null;
  return src.replace(/scale-to-width-down\/\d+/, `scale-to-width-down/${width}`);
}

// ---------------------------------------------------------------- verses

export function getVerses() {
  return cached('verses', 24 * HOUR, async () => {
    const members = await apiList(
      { action: 'query', list: 'categorymembers', cmtitle: 'Category:Characters by Verse', cmtype: 'subcat', cmlimit: 500 },
      'categorymembers',
      20000,
    );
    return members.map((m) => stripCat(m.title)).sort((a, b) => a.localeCompare(b));
  });
}

export async function searchVerses(q, limit = 15) {
  const verses = await getVerses();
  const needle = q.trim().toLowerCase();
  if (!needle) return verses.slice(0, limit);
  const starts = [];
  const wordStarts = [];
  const contains = [];
  for (const v of verses) {
    const l = v.toLowerCase();
    if (l.startsWith(needle)) starts.push(v);
    else if (l.includes(' ' + needle)) wordStarts.push(v);
    else if (l.includes(needle)) contains.push(v);
  }
  return [...starts, ...wordStarts, ...contains].slice(0, limit);
}

function getCategoryPages(category) {
  return cached(`cat:${category}`, 6 * HOUR, async () => {
    const members = await apiList(
      { action: 'query', list: 'categorymembers', cmtitle: `Category:${category}`, cmtype: 'page', cmnamespace: 0, cmlimit: 500 },
      'categorymembers',
      3000,
    );
    return members.map((m) => m.title);
  });
}

// ---------------------------------------------------------------- character search

function rankTitles(titles, q) {
  const needle = q.trim().toLowerCase();
  if (!needle) return titles;
  const score = (t) => {
    const l = t.toLowerCase();
    if (l.startsWith(needle)) return 0;
    if (l.split(/[\s(]+/).some((w) => w.startsWith(needle))) return 1;
    if (l.includes(needle)) return 2;
    return 3;
  };
  return titles
    .map((t, i) => ({ t, i, s: score(t) }))
    .sort((a, b) => a.s - b.s || a.i - b.i)
    .map((x) => x.t);
}

async function candidateTitles({ q, verse, tier, media, alignment }) {
  if (verse) {
    const pages = await getCategoryPages(verse);
    const needle = q.trim().toLowerCase();
    const matching = needle ? pages.filter((t) => t.toLowerCase().includes(needle)) : pages;
    return rankTitles(matching, q).slice(0, 150);
  }
  if (q.trim()) {
    const [prefix, full] = await Promise.all([
      api({ action: 'query', list: 'prefixsearch', pssearch: q, pslimit: 40, psnamespace: 0 }),
      api({ action: 'query', list: 'search', srsearch: q, srlimit: 40, srnamespace: 0, srprop: '' }),
    ]);
    const titles = [
      ...(prefix.query?.prefixsearch || []).map((p) => p.title),
      ...(full.query?.search || []).map((p) => p.title),
    ];
    const ranked = rankTitles([...new Set(titles)], q);
    // Drop fuzzy hits whose title doesn't contain the query when there are enough real matches.
    const needle = q.trim().toLowerCase();
    const direct = ranked.filter((t) => t.toLowerCase().includes(needle));
    return direct.length >= 3 ? direct : ranked;
  }
  // No text and no verse: browse the most selective category filter.
  const category = tier ? `Tier ${tier}` : media || alignment;
  if (!category) return [];
  const pages = await getCategoryPages(category);
  return pages.slice(0, 150);
}

// Loads thumbnails + filter-relevant categories for up to 50 titles per request.
async function describeTitles(titles, requiredCats) {
  const checkCats = ['Category:Characters', 'Category:Disambiguations', ...requiredCats];
  const out = [];
  for (let i = 0; i < titles.length; i += 50) {
    const chunk = titles.slice(i, i + 50);
    const data = await api({
      action: 'query',
      titles: chunk.join('|'),
      redirects: 1,
      prop: 'pageimages|categories',
      piprop: 'thumbnail',
      pithumbsize: 120,
      pilimit: 50,
      clcategories: checkCats.join('|'),
      cllimit: 500,
    });
    const byTitle = new Map((data.query?.pages || []).map((p) => [p.title, p]));
    const redirects = new Map((data.query?.redirects || []).map((r) => [r.from, r.to]));
    for (const t of chunk) {
      const p = byTitle.get(redirects.get(t) || t);
      if (p && !p.missing) out.push(p);
    }
  }
  return out;
}

export async function searchCharacters({ q = '', verse = '', tier = '', media = '', alignment = '', limit = 12 }) {
  const required = [];
  if (tier) required.push(`Category:Tier ${tier}`);
  if (media) required.push(`Category:${media}`);
  if (alignment) required.push(`Category:${alignment}`);

  const titles = await candidateTitles({ q, verse, tier, media, alignment });
  const results = [];
  const seen = new Set();
  // Describe in batches so we can stop early once enough matches passed the filters.
  for (let i = 0; i < titles.length && results.length < limit; i += 50) {
    const pages = await describeTitles(titles.slice(i, i + 50), required);
    for (const p of pages) {
      if (seen.has(p.title)) continue;
      seen.add(p.title);
      const cats = new Set((p.categories || []).map((c) => c.title));
      if (!cats.has('Category:Characters') || cats.has('Category:Disambiguations')) continue;
      if (!required.every((c) => cats.has(c))) continue;
      results.push(toSummary(p));
      if (results.length >= limit) break;
    }
  }
  return results;
}

function toSummary(p) {
  const m = p.title.match(/^(.*?)\s*\(([^()]+)\)$/);
  return {
    title: p.title,
    name: m ? m[1] : p.title,
    variant: m ? m[2] : '',
    thumb: thumbUrl(p.thumbnail?.source, 120),
    url: pageUrl(p.title),
  };
}

export async function randomCharacter(filters) {
  const required = [];
  if (filters.tier) required.push(`Category:Tier ${filters.tier}`);
  if (filters.media) required.push(`Category:${filters.media}`);
  if (filters.alignment) required.push(`Category:${filters.alignment}`);

  for (let attempt = 0; attempt < 4; attempt++) {
    let pool;
    if (filters.verse) {
      pool = await getCategoryPages(filters.verse);
    } else if (required.length) {
      // Start at a random sort key so large categories are not always sampled from "A".
      const category = required[0];
      const letter = String.fromCharCode(65 + Math.floor(Math.random() * 26));
      const data = await api({
        action: 'query', list: 'categorymembers', cmtitle: category, cmtype: 'page',
        cmnamespace: 0, cmlimit: 200, cmstartsortkeyprefix: letter,
      });
      pool = (data.query?.categorymembers || []).map((m) => m.title);
    } else {
      const data = await api({ action: 'query', list: 'random', rnnamespace: 0, rnlimit: 50 });
      pool = (data.query?.random || []).map((m) => m.title);
    }
    const shuffled = [...pool].sort(() => Math.random() - 0.5).slice(0, 50);
    if (!shuffled.length) return null;
    const pages = await describeTitles(shuffled, required);
    const ok = pages.filter((p) => {
      const cats = new Set((p.categories || []).map((c) => c.title));
      return cats.has('Category:Characters') && !cats.has('Category:Disambiguations') && required.every((c) => cats.has(c));
    });
    if (ok.length) return toSummary(ok[Math.floor(Math.random() * ok.length)]);
  }
  return null;
}

// ---------------------------------------------------------------- profile parsing

const FIELDS = [
  'Tier', 'Key', 'Name', 'Origin', 'Gender', 'Age', 'Classification', 'Powers and Abilities',
  'Attack Potency', 'Speed', 'Lifting Strength', 'Striking Strength', 'Durability', 'Stamina',
  'Range', 'Standard Equipment', 'Optional Equipment', 'Intelligence', 'Weaknesses',
  'Notable Attacks/Techniques', 'Feats', 'Note', 'Others',
];

// Per-field character budgets for the LLM prompt. Stats are kept in full-ish,
// the (often enormous) ability lists are trimmed.
const FIELD_BUDGET = {
  'Powers and Abilities': 9000,
  'Notable Attacks/Techniques': 5000,
  Feats: 1500,
  Note: 1200,
  Others: 1000,
};
const DEFAULT_BUDGET = 3000;
const TOTAL_BUDGET = 30000;

function replaceTemplates(text) {
  // Resolve innermost templates repeatedly.
  for (let i = 0; i < 15; i++) {
    const next = text.replace(/\{\{([^{}]*)\}\}/g, (_, inner) => {
      const parts = inner.split('|');
      const name = parts[0].trim();
      if (name === '!') return '|';
      if (/^#tag:tabber/i.test(name)) return '\n' + parts.slice(1).join('|') + '\n';
      const content = parts.find((p) => /^\s*Content\s*=/.test(p));
      if (content) return parts.slice(parts.indexOf(content)).join('|').replace(/^\s*Content\s*=/, '');
      if (/^(Quote|Cquote)$/i.test(name)) return parts[1] ? `"${parts[1].trim()}"` : '';
      if (/^(Spoiler|Clr|Clear|Reflist|Toc|DISPLAYTITLE|Main|See also|Tabbercontainer|Mobile)/i.test(name)) {
        return parts.slice(1).filter((p) => !p.includes('=')).join(' ');
      }
      if (parts.length === 1) return name; // e.g. {{7-B}} tier templates
      return parts.slice(1).map((p) => p.replace(/^\s*[\w ]+\s*=/, '')).join(' ');
    });
    if (next === text) break;
    text = next;
  }
  return text;
}

export function cleanWikitext(wt) {
  let t = wt;
  t = t.replace(/<!--[\s\S]*?-->/g, '');
  t = t.replace(/<ref[^>]*\/>/gi, '');
  t = t.replace(/<ref[^>]*>[\s\S]*?<\/ref>/gi, '');
  t = t.replace(/<gallery[^>]*>[\s\S]*?<\/gallery>/gi, '');
  t = t.replace(/\[\[(?:Category|Kategorie):[^\]]*\]\]/gi, '');
  // File links can contain nested [[links]] in captions.
  for (let i = 0; i < 3; i++) t = t.replace(/\[\[(?:File|Image|Datei):(?:[^[\]]|\[\[[^\]]*\]\])*\]\]/gi, '');
  t = replaceTemplates(t);
  t = t.replace(/\[\[[^\]|]*\|([^\]]*)\]\]/g, '$1');
  t = t.replace(/\[\[([^\]]*)\]\]/g, '$1');
  t = t.replace(/\[https?:\/\/[^\s\]]+\s+([^\]]*)\]/g, '$1');
  t = t.replace(/\[https?:\/\/[^\]]*\]/g, '');
  t = t.replace(/\|-\|([^=\n]+)=/g, '\n[$1] ');
  t = t.replace(/<br\s*\/?>/gi, '\n');
  t = t.replace(/<\/?[a-z][^>]*>/gi, '');
  t = t.replace(/'''''|'''|''/g, '');
  t = t.replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&quot;/g, '"');
  t = t.replace(/__[A-Z]+__/g, '');
  t = t.replace(/[ \t]+/g, ' ');
  t = t.replace(/^ +| +$/gm, '');
  t = t.replace(/\n{3,}/g, '\n\n');
  return t.trim();
}

function parseProfile(clean) {
  const summaryMatch = clean.match(/==\s*Summary\s*==\s*([\s\S]*?)(?=\n==[^=]|$)/i);
  const statsStart = clean.search(/==\s*Powers and Stats\s*==/i);
  const statsText = statsStart >= 0 ? clean.slice(statsStart) : clean;

  const fieldRe = new RegExp(`^(?:==+\\s*)?(${FIELDS.map((f) => f.replace(/[/]/g, '\\/')).join('|')})\\s*(?::|==+)`, 'gim');
  const hits = [];
  let m;
  while ((m = fieldRe.exec(statsText))) {
    hits.push({ name: FIELDS.find((f) => f.toLowerCase() === m[1].toLowerCase()), start: m.index, bodyStart: fieldRe.lastIndex });
  }
  const fields = {};
  hits.forEach((h, i) => {
    const end = i + 1 < hits.length ? hits[i + 1].start : statsText.length;
    let body = statsText.slice(h.bodyStart, end);
    // Stop at a new level-2 section that isn't a known field (e.g. "Others" tables, "Gallery").
    const nextSection = body.search(/\n==[^=\n]+==\s*\n/);
    if (nextSection >= 0 && h.name !== 'Notable Attacks/Techniques') body = body.slice(0, nextSection);
    body = body.trim();
    if (!body) return;
    fields[h.name] = fields[h.name] ? `${fields[h.name]}\n${body}` : body;
  });
  return { summary: summaryMatch ? summaryMatch[1].trim() : '', fields };
}

function clip(text, max) {
  if (text.length <= max) return text;
  return text.slice(0, max).replace(/\s+\S*$/, '') + ' […gekürzt]';
}

function oneLine(text, max = 260) {
  return clip((text || '').replace(/\s*\n\s*/g, ' '), max);
}

export function getCharacter(title) {
  return cached(`char:${title}`, 6 * HOUR, async () => {
    const data = await api({
      action: 'query',
      titles: title,
      redirects: 1,
      prop: 'revisions|pageimages',
      rvprop: 'content',
      rvslots: 'main',
      piprop: 'thumbnail',
      pithumbsize: 500,
    });
    const page = data.query?.pages?.[0];
    if (!page || page.missing) throw Object.assign(new Error(`Charakter "${title}" nicht gefunden`), { status: 404 });
    const wikitext = page.revisions?.[0]?.slots?.main?.content || '';
    const clean = cleanWikitext(wikitext);
    const { summary, fields } = parseProfile(clean);

    let profileText = '';
    if (Object.keys(fields).length >= 3) {
      const parts = [];
      if (summary) parts.push(`Summary: ${clip(summary, 1200)}`);
      for (const f of FIELDS) {
        if (fields[f]) parts.push(`${f}: ${clip(fields[f], FIELD_BUDGET[f] || DEFAULT_BUDGET)}`);
      }
      profileText = clip(parts.join('\n\n'), TOTAL_BUDGET);
    } else {
      profileText = clip(clean, TOTAL_BUDGET);
    }

    const s = toSummary(page);
    return {
      ...s,
      image: thumbUrl(page.thumbnail?.source, 500),
      summary: oneLine(summary, 400),
      stats: {
        tier: oneLine(fields.Tier, 220),
        origin: oneLine(fields.Origin, 80),
        classification: oneLine(fields.Classification, 160),
        attackPotency: oneLine(fields['Attack Potency'], 220),
        speed: oneLine(fields.Speed, 220),
        durability: oneLine(fields.Durability, 220),
      },
      profileText,
    };
  });
}
