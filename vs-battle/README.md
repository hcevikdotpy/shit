# ⚔ VS Battle Oracle

Zwei Charaktere eingeben, das LLM sagt, wer gewinnt und warum.
Die Charakterdaten kommen live aus dem [VS Battles Wiki](https://vsbattles.fandom.com/wiki/), das Urteil
kommt von einem beliebigen Modell über [OpenRouter](https://openrouter.ai).

## Features

- **Autocomplete mit Bild**: Beim Tippen werden passende Wiki-Profile mit Thumbnail und Version angezeigt
  (z. B. *Son Goku – Dragon Ball*). Bedienbar mit Pfeiltasten, Enter und Esc.
- **Filter pro Kämpfer**:
  - **Universum**: Autocomplete über alle ca. 4.000 Verse-Kategorien des Wikis (Naruto, Marvel Comics, …)
  - **Tier**: 0 bis 10-C
  - **Medium**: Anime, Manga, Videospiel, Comic, Film …
  - **Gesinnung**: gut, neutral oder böse
- 🎲 **Zufälliger Charakter**, der die aktiven Filter berücksichtigt.
- **Charakterkarte** mit Bild, Tier, Herkunft, Angriffskraft, Geschwindigkeit und Haltbarkeit, dazu ein optionales Feld
  für Key/Version (z. B. „Sage Mode“).
- **Szenario-Optionen**: bloodlusted, speed-equalized, Vorbereitungszeit und freie Zusatzbedingungen.
- **Ergebnis**: Sieger mit Bild, Sicherheit in Prozent, Vergleichstabelle (Tier, AP, Speed, Durability,
  Hax/Resistenzen, …), ausführliche Begründung und die Win-Condition des Verlierers.
- Wählbares Modell (Liste oder eigene OpenRouter-ID), Erklärung auf Deutsch oder Englisch.
- Teilbare URLs: `?a=Saitama&b=Son Goku (Dragon Ball)`.

## Starten

Benötigt Node.js ≥ 18, sonst nichts (keine npm-Abhängigkeiten).

```bash
cd vs-battle
cp .env.example .env        # OPENROUTER_API_KEY eintragen
npm start                   # → http://localhost:3000
```

Ohne `OPENROUTER_API_KEY` in der `.env` fragt die Seite in den Einstellungen nach einem Key. Dieser wird nur im
`localStorage` des Browsers gespeichert und pro Anfrage an den eigenen Server weitergereicht.

| Variable | Standard | Beschreibung |
| --- | --- | --- |
| `OPENROUTER_API_KEY` | – | Key vom Server (empfohlen fürs Hosting) |
| `DEFAULT_MODEL` | `google/gemini-3.8-flash` | vorausgewähltes Modell |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | für andere OpenAI-kompatible Endpunkte |
| `PORT` | `3000` | |

## Wie es funktioniert

```
Browser ──► /api/search, /api/verses, /api/random ──► MediaWiki-API (vsbattles.fandom.com/api.php)
        ──► /api/character  ── Wikitext holen, bereinigen, Felder parsen (Tier, AP, Speed, …)
        ──► /api/battle     ── beide Profile (gekürzt auf ca. 30k Zeichen) + Szenario ──► OpenRouter ──► JSON-Urteil
```

- `lib/wiki.js`: Suche (Prefix- und Volltextsuche), Filter über Wiki-Kategorien (`Category:Tier 2-C`,
  `Category:Anime Characters`, Verse-Kategorien aus `Category:Characters by Verse`) und das Parsen der Profile.
  Antworten werden im Speicher gecacht.
- `lib/llm.js`: Prompt nach den Standard-Kampfannahmen des VS Battles Wikis, OpenRouter-Aufruf und robustes Parsen
  der JSON-Antwort.
- `public/`: statisches Frontend (HTML, CSS und JS, kein Build-Schritt).

Die Urteile sind KI-generiert. Sie stützen sich auf die Wiki-Profile, können aber trotzdem falsch sein.
Inhalte des VS Battles Wikis stehen unter CC BY-SA.
