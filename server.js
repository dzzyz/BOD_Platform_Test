import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';

dotenv.config();

const app = express();
app.use(cors());
app.use(express.json({ limit: '50mb' }));

const ANTHROPIC_API_KEY = process.env.ANTHROPIC_API_KEY;
const MODEL = process.env.MODEL || 'claude-sonnet-4-20250514';

if (!ANTHROPIC_API_KEY) {
  console.error('❌ ANTHROPIC_API_KEY is not set. Create a .env file (see .env.example)');
  process.exit(1);
}

// ─── Translation endpoint ───
app.post('/api/translate', async (req, res) => {
  const { texts, direction = 'ko2en', context = '' } = req.body;

  if (!texts || !Array.isArray(texts) || texts.length === 0) {
    return res.status(400).json({ error: 'texts array is required' });
  }

  const systemPrompt = direction === 'ko2en'
    ? `You are a professional Korean-to-English translator for board of directors (이사회) meeting materials at a major Korean corporation.
Rules:
1. Use formal, concise business English suitable for board-level communication.
2. Keep proper nouns, company names, abbreviations, and numbers as-is (e.g., KRAFTON, ADK, PMI, 3Q24).
3. Numbers, dates, and currency should follow English conventions where appropriate.
4. Be concise — board slides have limited space. Match the brevity of the original.
5. If a text item is already in English or is a number/symbol, return it unchanged.
6. Translate naturally, not word-for-word. Prioritize clarity for non-Korean board members.
7. Return ONLY a JSON array of translated strings in the exact same order as input. No markdown fences, no explanation.
${context ? `\nAdditional context about this document: ${context}` : ''}`
    : `You are a professional English-to-Korean translator for board of directors (이사회) meeting materials.
Rules:
1. Use formal Korean suitable for 이사회 자료.
2. Keep proper nouns, company names, abbreviations as-is.
3. Return ONLY a JSON array of translated strings in the exact same order as input. No markdown, no explanation.
${context ? `\nAdditional context: ${context}` : ''}`;

  try {
    const response = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': ANTHROPIC_API_KEY,
        'anthropic-version': '2023-06-01',
      },
      body: JSON.stringify({
        model: MODEL,
        max_tokens: 4096,
        system: systemPrompt,
        messages: [{
          role: 'user',
          content: `Translate each text block. Return a JSON array of strings:\n${JSON.stringify(texts)}`
        }]
      })
    });

    if (!response.ok) {
      const err = await response.text();
      console.error('Anthropic API error:', response.status, err);
      return res.status(response.status).json({ error: `API error: ${response.status}` });
    }

    const data = await response.json();
    const raw = data.content[0].text.replace(/```json|```/g, '').trim();
    const translated = JSON.parse(raw);

    res.json({ translated });
  } catch (err) {
    console.error('Translation error:', err);
    res.status(500).json({ error: 'Translation failed' });
  }
});

// ─── Health check ───
app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', model: MODEL });
});

const PORT = process.env.PORT || 3001;
app.listen(PORT, () => {
  console.log(`✅ BOD Translator API running on http://localhost:${PORT}`);
});
