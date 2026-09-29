import http from 'node:http';
import { readFile } from 'node:fs/promises';
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  ALIGNMENTS, MEDIA, TIERS, getCharacter, getVerses, randomCharacter, searchCharacters, searchVerses,
} from './lib/wiki.js';
import { MODELS, judgeBattle } from './lib/llm.js';

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const PUBLIC = path.join(ROOT, 'public');

// Minimal .env loader (no dependencies).
const envFile = path.join(ROOT, '.env');
if (existsSync(envFile)) {
  for (const line of readFileSync(envFile, 'utf8').split('\n')) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*?)\s*$/);
    if (m && process.env[m[1]] === undefined) process.env[m[1]] = m[2].replace(/^["']|["']$/g, '');
  }
}

const PORT = Number(process.env.PORT) || 3000;
const SERVER_KEY = process.env.OPENROUTER_API_KEY || '';
const DEFAULT_MODEL = process.env.DEFAULT_MODEL || MODELS[0].id;

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.ico': 'image/x-icon',
};

function send(res, status, body, headers = {}) {
  const isJson = typeof body !== 'string' && !Buffer.isBuffer(body);
  res.writeHead(status, {
    'Content-Type': isJson ? 'application/json; charset=utf-8' : 'text/plain; charset=utf-8',
    ...headers,
  });
  res.end(isJson ? JSON.stringify(body) : body);
}

async function readBody(req, limit = 100_000) {
  let size = 0;
  const chunks = [];
  for await (const chunk of req) {
    size += chunk.length;
    if (size > limit) throw Object.assign(new Error('Request zu groß'), { status: 413 });
    chunks.push(chunk);
  }
  const raw = Buffer.concat(chunks).toString('utf8');
  try {
    return raw ? JSON.parse(raw) : {};
  } catch {
    throw Object.assign(new Error('Ungültiges JSON'), { status: 400 });
  }
}

const str = (v, max = 200) => (typeof v === 'string' ? v.slice(0, max) : '');

function filtersFrom(params) {
  const tier = str(params.get('tier'), 20);
  const media = str(params.get('media'), 60);
  const alignment = str(params.get('alignment'), 60);
  return {
    q: str(params.get('q'), 100),
    verse: str(params.get('verse'), 150),
    tier: TIERS.includes(tier) ? tier : '',
    media: MEDIA.includes(media) ? media : '',
    alignment: ALIGNMENTS.includes(alignment) ? alignment : '',
  };
}

const routes = {
  'GET /api/config': async () => ({
    hasServerKey: Boolean(SERVER_KEY),
    defaultModel: DEFAULT_MODEL,
    models: MODELS,
    tiers: TIERS,
    media: MEDIA,
    alignments: ALIGNMENTS,
  }),

  'GET /api/verses': async (_req, url) => ({ verses: await searchVerses(str(url.searchParams.get('q'), 100)) }),

  'GET /api/search': async (_req, url) => ({ results: await searchCharacters(filtersFrom(url.searchParams)) }),

  'GET /api/random': async (_req, url) => {
    const character = await randomCharacter(filtersFrom(url.searchParams));
    if (!character) throw Object.assign(new Error('Kein Charakter mit diesen Filtern gefunden'), { status: 404 });
    return { character };
  },

  'GET /api/character': async (_req, url) => {
    const title = str(url.searchParams.get('title'), 250);
    if (!title) throw Object.assign(new Error('title fehlt'), { status: 400 });
    const { profileText, ...character } = await getCharacter(title);
    return { character };
  },

  'POST /api/battle': async (req) => {
    const body = await readBody(req);
    const titleA = str(body.a, 250);
    const titleB = str(body.b, 250);
    if (!titleA || !titleB) throw Object.assign(new Error('Zwei Charaktere nötig'), { status: 400 });
    const apiKey = SERVER_KEY || str(req.headers['x-openrouter-key'], 300);
    const model = str(body.model, 120) || DEFAULT_MODEL;
    const s = body.scenario || {};
    const scenario = {
      keyA: str(s.keyA, 150),
      keyB: str(s.keyB, 150),
      bloodlusted: Boolean(s.bloodlusted),
      speedEqualized: Boolean(s.speedEqualized),
      prep: Boolean(s.prep),
      notes: str(s.notes, 500),
    };
    const [a, b] = await Promise.all([getCharacter(titleA), getCharacter(titleB)]);
    const result = await judgeBattle({
      a, b, scenario, model, apiKey,
      lang: body.lang === 'en' ? 'en' : 'de',
      referer: req.headers.origin || `http://localhost:${PORT}`,
    });
    const strip = ({ profileText, ...rest }) => rest;
    return { a: strip(a), b: strip(b), result };
  },
};

async function serveStatic(res, pathname) {
  const rel = pathname === '/' ? 'index.html' : decodeURIComponent(pathname).replace(/^\/+/, '');
  const file = path.normalize(path.join(PUBLIC, rel));
  if (!file.startsWith(PUBLIC + path.sep)) return send(res, 403, 'Forbidden');
  try {
    const data = await readFile(file);
    send(res, 200, data, { 'Content-Type': MIME[path.extname(file)] || 'application/octet-stream' });
  } catch {
    send(res, 404, 'Not found');
  }
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://localhost');
  const handler = routes[`${req.method} ${url.pathname}`];
  if (!handler) {
    if (url.pathname.startsWith('/api/')) return send(res, 404, { error: 'Unbekannter Endpunkt' });
    if (req.method !== 'GET' && req.method !== 'HEAD') return send(res, 405, 'Method not allowed');
    return serveStatic(res, url.pathname);
  }
  try {
    send(res, 200, await handler(req, url));
  } catch (err) {
    const status = err.status || 500;
    if (status >= 500) console.error(`[${req.method} ${url.pathname}]`, err);
    send(res, status, { error: err.message || 'Serverfehler' });
  }
});

server.listen(PORT, () => {
  console.log(`VS Battle Oracle läuft auf http://localhost:${PORT}`);
  console.log(SERVER_KEY ? 'OpenRouter-Key: aus Umgebung' : 'Kein OPENROUTER_API_KEY gesetzt – Nutzer können ihren Key im Browser eintragen.');
  getVerses().then((v) => console.log(`${v.length} Universen geladen`)).catch((e) => console.warn('Universen konnten nicht geladen werden:', e.message));
});
