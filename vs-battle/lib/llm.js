// Battle judgement via OpenRouter (https://openrouter.ai/docs).

const OPENROUTER_URL = `${(process.env.OPENROUTER_BASE_URL || 'https://openrouter.ai/api/v1').replace(/\/$/, '')}/chat/completions`;

export const MODELS = [
  { id: 'google/gemini-3.8-flash', label: 'Gemini 3.8 Flash (schnell, günstig)' },
  { id: 'anthropic/claude-sonnet-5.5', label: 'Claude Sonnet 5.5' },
  { id: 'anthropic/claude-opus-5.5', label: 'Claude Opus 5.5' },
  { id: 'openai/gpt-5.6-terra', label: 'GPT-5.6 Terra' },
  { id: 'x-ai/grok-4.7', label: 'Grok 4.7' },
  { id: 'deepseek/deepseek-v4-pro', label: 'DeepSeek V4 Pro' },
];

const LANGUAGES = { de: 'German', en: 'English' };

function systemPrompt(lang) {
  return `You are an expert debater from the VS Battles Wiki (vsbattles.fandom.com). You judge hypothetical fights between two fictional characters strictly using the VS Battles Wiki profiles provided, following the wiki's standard battle assumptions and tiering system.

Judging rules:
- Base every claim on the provided profile text. Do not invent feats or abilities. If data is missing, say so.
- Unless the user's scenario says otherwise: both fighters are in character, start ~10 meters apart, have no prior knowledge of each other, and the fight ends by death, knockout, incapacitation or ring-out-free victory. Each character uses the key/version stated in the scenario; if "strongest", use the strongest key listed in their profile (and say which one).
- Weigh: Tier and Attack Potency vs. opponent's Durability, Speed (reaction/combat vs. travel), hax (reality warping, soul/mind manipulation, time stop, non-physical interaction, etc.) vs. the opponent's resistances, immortality/regeneration, Stamina, Range, Intelligence/battle experience, Weaknesses and equipment.
- A large tier/AP gap usually decides the fight unless hax the opponent cannot resist bypasses it. Explain such cases explicitly.
- Be decisive but honest: if it's truly close, say it's close and lower the confidence. Use "draw" only when neither can realistically win (e.g., mutual inability to harm each other).

Write all prose values in ${LANGUAGES[lang] || 'German'} (keep character, ability and tier names as in the wiki).

Respond with ONLY a JSON object, no markdown fences, matching exactly this shape:
{
  "winner": "A" | "B" | "draw",
  "confidence": <integer 0-100, how sure you are of this outcome>,
  "verdict": "<one punchy sentence stating who wins and the main reason>",
  "key_a": "<key/version of fighter A used>",
  "key_b": "<key/version of fighter B used>",
  "tier_a": "<tier of fighter A in that key>",
  "tier_b": "<tier of fighter B in that key>",
  "categories": [
    { "name": "<category, e.g. Attack Potency>", "a": "<short value for A>", "b": "<short value for B>", "edge": "A" | "B" | "even" }
  ],
  "explanation": "<detailed reasoning in Markdown, 3-6 paragraphs; use **bold** for key points and bullet lists where helpful>",
  "loser_win_condition": "<what the losing side would need to win, or empty string for a draw>"
}
The categories array must cover: Tier, Attack Potency, Speed, Durability, Hax & Resistances, Stamina & Regeneration, Range, Intelligence/Skill.`;
}

function userPrompt(a, b, scenario) {
  const lines = [];
  lines.push('Scenario settings:');
  lines.push(`- Key/version for A: ${scenario.keyA || 'strongest'}`);
  lines.push(`- Key/version for B: ${scenario.keyB || 'strongest'}`);
  lines.push(`- Mindset: ${scenario.bloodlusted ? 'both bloodlusted (fight to kill, no holding back)' : 'in character'}`);
  lines.push(`- Speed: ${scenario.speedEqualized ? 'speed-equalized (both at equal speed)' : 'normal (not equalized)'}`);
  lines.push(`- Prep time: ${scenario.prep ? 'both have prep time and knowledge of the opponent' : 'no prep, no knowledge'}`);
  if (scenario.notes) lines.push(`- Extra conditions from the user: ${scenario.notes}`);
  lines.push('');
  lines.push(`=== FIGHTER A: ${a.title} (${a.url}) ===`);
  lines.push(a.profileText);
  lines.push('');
  lines.push(`=== FIGHTER B: ${b.title} (${b.url}) ===`);
  lines.push(b.profileText);
  lines.push('');
  lines.push('Who wins? Answer with the JSON object only.');
  return lines.join('\n');
}

export function extractJson(text) {
  if (!text) throw new Error('Leere Antwort vom Modell');
  let t = text.trim().replace(/^```(?:json)?\s*/i, '').replace(/```\s*$/, '');
  const start = t.indexOf('{');
  const end = t.lastIndexOf('}');
  if (start < 0 || end < start) throw new Error('Modell hat kein JSON geliefert');
  t = t.slice(start, end + 1);
  return JSON.parse(t);
}

function normalize(result) {
  const winner = ['A', 'B', 'draw'].includes(result.winner) ? result.winner : String(result.winner || '').toUpperCase() === 'B' ? 'B' : String(result.winner || '').toLowerCase() === 'draw' ? 'draw' : 'A';
  const conf = Math.max(0, Math.min(100, Math.round(Number(result.confidence) || 50)));
  return {
    winner,
    confidence: conf,
    verdict: String(result.verdict || ''),
    keyA: String(result.key_a || ''),
    keyB: String(result.key_b || ''),
    tierA: String(result.tier_a || ''),
    tierB: String(result.tier_b || ''),
    categories: Array.isArray(result.categories)
      ? result.categories.slice(0, 12).map((c) => ({
          name: String(c.name || ''),
          a: String(c.a || ''),
          b: String(c.b || ''),
          edge: ['A', 'B'].includes(c.edge) ? c.edge : 'even',
        }))
      : [],
    explanation: String(result.explanation || ''),
    loserWinCondition: String(result.loser_win_condition || ''),
  };
}

export async function judgeBattle({ a, b, scenario = {}, model, apiKey, lang = 'de', referer }) {
  if (!apiKey) throw Object.assign(new Error('Kein OpenRouter API-Key konfiguriert'), { status: 400 });
  const body = {
    model,
    temperature: 0.3,
    max_tokens: 4000,
    response_format: { type: 'json_object' },
    messages: [
      { role: 'system', content: systemPrompt(lang) },
      { role: 'user', content: userPrompt(a, b, scenario) },
    ],
  };
  const res = await fetch(OPENROUTER_URL, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${apiKey}`,
      'Content-Type': 'application/json',
      'HTTP-Referer': referer || 'http://localhost',
      'X-Title': 'VS Battle Oracle',
    },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(180000),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || data.error) {
    const msg = data.error?.message || `HTTP ${res.status}`;
    throw Object.assign(new Error(`OpenRouter: ${msg}`), { status: res.status >= 400 && res.status < 500 ? res.status : 502 });
  }
  const content = data.choices?.[0]?.message?.content;
  let parsed;
  try {
    parsed = extractJson(typeof content === 'string' ? content : JSON.stringify(content));
  } catch (err) {
    throw Object.assign(new Error(`Antwort des Modells konnte nicht gelesen werden: ${err.message}`), { status: 502 });
  }
  return { ...normalize(parsed), model: data.model || model, usage: data.usage || null };
}
