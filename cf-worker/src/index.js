// Cloudflare Worker — Health Dashboard API Proxy
// Secrets (set via: npx wrangler secret put OURA_TOKEN / GEMINI_KEY):
//   OURA_TOKEN  — Oura Ring personal access token
//   GEMINI_KEY  — Google Gemini API key

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
}

function cors(body, status = 200, extra = {}) {
  return new Response(body, {
    status,
    headers: { ...CORS, 'Content-Type': 'application/json', ...extra },
  })
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url)
    const path = url.pathname

    // Preflight
    if (request.method === 'OPTIONS') return new Response(null, { headers: CORS })

    // ── /oura/* ── proxy to Oura v2 API
    if (path.startsWith('/oura/')) {
      const ouraPath = path.replace('/oura', '')
      const ouraURL = `https://api.ouraring.com/v2${ouraPath}${url.search}`
      const res = await fetch(ouraURL, {
        headers: { Authorization: `Bearer ${env.OURA_TOKEN}` },
      })
      const data = await res.text()
      return cors(data, res.status)
    }

    // ── /gemini ── proxy to Gemini generateContent
    if (path === '/gemini' && request.method === 'POST') {
      const body = await request.text()
      const GEMINI_MODEL = 'gemini-2.5-pro'
      const geminiURL = `https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent?key=${env.GEMINI_KEY}`
      const res = await fetch(geminiURL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body,
      })
      const data = await res.text()
      return cors(data, res.status)
    }

    return cors(JSON.stringify({ error: 'not found' }), 404)
  },
}
