// Cloudflare Worker — Health Dashboard API Proxy + Telegram command bot
// Secrets (npx wrangler secret put <NAME>):
//   OURA_TOKEN              — Oura personal access token
//   GEMINI_KEY              — Google Gemini API key (dashboard เก่า)
//   TELEGRAM_BOT_TOKEN      — บอท Telegram (สำหรับตอบคำสั่ง)
//   TELEGRAM_WEBHOOK_SECRET — (optional) ตรวจ header กัน request ปลอม
//   STRAVA_CLIENT_ID / STRAVA_CLIENT_SECRET / STRAVA_REFRESH_TOKEN — activity (cloud)
// คำสั่ง Telegram (ระดับ 1, ดึง Oura สด): /today /readiness /plan /help

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
}
function cors(body, status = 200, extra = {}) {
  return new Response(body, { status, headers: { ...CORS, 'Content-Type': 'application/json', ...extra } })
}

const OWNER_CHAT_ID = 957180305          // ตอบเฉพาะเจ้าของ
// เรต Gemini 3 Flash (USD ต่อ 1M token) + อัตราแลกเปลี่ยน — ปรับได้
const GEM_IN_USD = 0.50, GEM_OUT_USD = 3.00, USD_THB = 35
const costTHB = (u) => ((u.in / 1e6) * GEM_IN_USD + (u.out / 1e6) * GEM_OUT_USD) * USD_THB
const RACE_ISO = '2026-08-08'
const EASY_HR_CAP = 150
const ZONES = [[130, 148, 'Z2'], [149, 160, 'Z3'], [161, 172, 'Z4']]
const DOW = ['จ', 'อ', 'พ', 'พฤ', 'ศ', 'ส', 'อา']
const MON = ['', 'ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.']

// ── แผนซ้อม (ตรงกับ morning_digest.py — map ด้วยวันจริง) ─────────────
const S = (s, d, h) => ({ s, d, h })
const W1 = {
  '2026-06-18': S('Vertical baseline (ลู่)', 'เริ่ม 8-10% หา speed ที่ HR 130-145 · จดชัน/speed/m-hr', '≤150'),
  '2026-06-19': S('เวท + core', 'squat, step-down eccentric, calf, core', '—'),
  '2026-06-20': S('Long Vertical 2.5-3 ชม. (ลู่)', 'สะสม +900 ม. สลับเดินราบ · กฎครบ 5 ข้อ · เป้า: ไม่หมดที่ 3 ชม.', 'ขึ้น ≤150'),
  '2026-06-21': S('วิ่ง/เดินราบ 6-8 กม. (ฟื้น)', 'time-on-feet เบา', 'Z2'),
}
// weekday: 0=จ..6=อา
const WEEKS = {
  '2026-06-23': { 0: S('พัก', '—', '—'), 1: S('ลู่ชัน intervals 6×4 นาที', 'ขึ้นหนัก-เดินฟื้น (ดัน m/hr)', 'Z4 ช่วงดัน'), 2: S('เวท + core', '+ step-down eccentric', '—'), 3: S('ราบ Z2 8 กม.', '—', '≤148'), 4: S('เวทเบา / พัก', '—', '—'), 5: S('Long Vertical 3-3.5 ชม. (ลู่)', 'สะสม +1,200 ม. + ราบ', 'ขึ้น ≤150'), 6: S('ราบยาว 10 กม. (ขาล้า)', 'time-on-feet', 'Z2') },
  '2026-06-30': { 0: S('พัก', '—', '—'), 1: S('ลู่ชัน climb-sim (~600 ม.)', 'ใส่เป้ถ่วงเริ่มชินน้ำหนัก', 'Z4'), 2: S('เวท + core', '—', '—'), 3: S('ราบ Z2 10 กม. (+ลู่ชัน tempo)', '—', 'Z2-Z3'), 4: S('เวทเบา / พัก', '—', '—'), 5: S('🏔️ เขาจริง: LR 26 กม. / +1,500', 'ใส่เป้+อุปกรณ์จริง · ซ้อมกินครบ · โฟกัสขาลง', 'ขึ้น ≤150'), 6: S('B2B เขา/ราบ 12 กม.', 'ขาล้า (ถ้ายังอยู่เขา)', 'Z2') },
  '2026-07-07': { 0: S('พัก', '—', '—'), 1: S('ลู่ชันเบา 4 เที่ยว', 'ไม่ดันหนัก', '≤Z3'), 2: S('เวทเบา', '—', '—'), 3: S('ราบ Z2 8 กม.', '—', '≤148'), 4: S('พัก', '—', '—'), 5: S('Vertical เบา ~2 ชม. (+700 ม. ลู่)', 'เก็บความสด', 'ขึ้น ≤150'), 6: S('พัก / เดินเบา', '—', '—') },
  '2026-07-14': { 0: S('พัก', '—', '—'), 1: S('ลู่ชัน 6×5 นาที', 'คมความเร็วไต่', 'Z4'), 2: S('เวท + core', '—', '—'), 3: S('ราบ Z2 8 กม.', '—', '≤148'), 4: S('พัก (เตรียม sim)', 'นอนเต็มที่', '—'), 5: S('🏔️ RACE SIM เขาจริง 30-33 กม. / +2,000', 'เสมือนแข่งครบ · เป้า 7-8 ชม.', 'ขึ้น ≤150'), 6: S('เดินฟื้น 5 กม.', '—', '—') },
  '2026-07-21': { 0: S('พัก', '—', '—'), 1: S('ลู่ชัน 5×3 นาที เร็วสุด', 'ดัน m/hr', 'Z4'), 2: S('เวท + core', '—', '—'), 3: S('ราบ Z2 8 กม.', '—', '≤148'), 4: S('เวทเบา / พัก', '—', '—'), 5: S('🏔️ เขาจริง: LR 20 กม. / +1,000', 'คงฟิต + ขาลงครั้งสุดท้ายก่อนเทเปอร์', 'ขึ้น ≤150'), 6: S('เดินเบา', '—', '—') },
}
const W7 = {
  '2026-07-28': S('พัก', '—', '—'),
  '2026-07-29': S('กระตุ้นเบา (ลู่ชัน 3 เที่ยวสั้น)', '—', '—'),
  '2026-07-30': S('เวทเบามาก / พัก', '—', '—'),
  '2026-07-31': S('ราบสั้น 5 กม. สบาย', '—', '—'),
  '2026-08-01': S('Vertical เบา ~1.5 ชม. (+400 ม. ลู่)', 'ซ้อมระบบกิน/น้ำครั้งสุดท้าย', '—'),
  '2026-08-08': S('🏁 RACE — CM6 i2', 'ออก 05:30 · กฎ 5 ข้อ · pacing ตามแผน', 'ขึ้น ≤150'),
}

// ── date helpers (ทำงานบน ICT) ──────────────────────────────────────
function ictTodayISO() { return new Date(Date.now() + 7 * 3600e3).toISOString().slice(0, 10) }
function asUTC(iso) { return new Date(iso + 'T00:00:00Z') }
function addDays(iso, n) { return new Date(asUTC(iso).getTime() + n * 86400e3).toISOString().slice(0, 10) }
function pyWeekday(iso) { return (asUTC(iso).getUTCDay() + 6) % 7 }   // 0=จ..6=อา
function daysBetween(a, b) { return Math.round((asUTC(b) - asUTC(a)) / 86400e3) }

function planFor(iso) {
  if (W1[iso]) return W1[iso]
  if (W7[iso]) return W7[iso]
  if (iso >= '2026-08-02' && iso <= '2026-08-07') return S('พักให้สด / เดินเบา', 'นอนเยอะ · เพิ่มคาร์บ 2-3 วันสุดท้าย · เช็กอุปกรณ์', '—')
  for (const tue of Object.keys(WEEKS)) {
    if (iso >= tue && iso <= addDays(tue, 6)) return WEEKS[tue][pyWeekday(iso)]
  }
  return null
}

// ── Oura ────────────────────────────────────────────────────────────
async function ouraGet(token, path, start, end) {
  const u = `https://api.ouraring.com/v2/usercollection/${path}?start_date=${start}&end_date=${end}`
  const r = await fetch(u, { headers: { Authorization: `Bearer ${token}` } })
  if (!r.ok) return []
  return (await r.json()).data || []
}
async function fetchOura(token, today) {
  const start = addDays(today, -8)
  const out = { readiness: null, sleep_score: null, sleep_h: null, hrv: null, hrv_avg7: null, rhr: null, rhr_avg7: null }
  const rd = await ouraGet(token, 'daily_readiness', start, today)
  for (const x of rd) if (x.day === today) out.readiness = x.score
  const ds = await ouraGet(token, 'daily_sleep', start, today)
  for (const x of ds) if (x.day === today) out.sleep_score = x.score
  const sl = await ouraGet(token, 'sleep', start, today)
  const byDay = {}
  for (const s of sl) {
    if (s.type !== 'long_sleep' && s.type !== 'sleep') continue
    const d = s.day
    if (!byDay[d] || (s.total_sleep_duration || 0) > (byDay[d].total_sleep_duration || 0)) byDay[d] = s
  }
  const ts = byDay[today]
  if (ts) {
    out.sleep_h = ts.total_sleep_duration ? Math.round(ts.total_sleep_duration / 360) / 10 : null
    out.hrv = ts.average_hrv
    out.rhr = ts.lowest_heart_rate
  }
  const prev = Object.entries(byDay).filter(([k]) => k !== today).map(([, v]) => v)
  const hrvs = prev.map(s => s.average_hrv).filter(Boolean)
  const rhrs = prev.map(s => s.lowest_heart_rate).filter(Boolean)
  if (hrvs.length) out.hrv_avg7 = Math.round(hrvs.reduce((a, b) => a + b) / hrvs.length)
  if (rhrs.length) out.rhr_avg7 = Math.round(rhrs.reduce((a, b) => a + b) / rhrs.length)
  return out
}

// ── Strava (activity จาก cloud) ─────────────────────────────────────
async function fetchStrava(env) {
  const cid = env.STRAVA_CLIENT_ID, secret = env.STRAVA_CLIENT_SECRET, refresh = env.STRAVA_REFRESH_TOKEN
  if (!cid || !secret || !refresh) return null
  try {
    const tok = await fetch('https://www.strava.com/oauth/token', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ client_id: cid, client_secret: secret, refresh_token: refresh, grant_type: 'refresh_token' }),
    })
    if (!tok.ok) return null
    const access = (await tok.json()).access_token
    const r = await fetch('https://www.strava.com/api/v3/athlete/activities?per_page=1', { headers: { Authorization: `Bearer ${access}` } })
    if (!r.ok) return null
    const acts = await r.json()
    if (!acts.length) return null
    const a = acts[0], dur = a.moving_time || a.elapsed_time || 0, gain = a.total_elevation_gain || 0
    return {
      type: a.sport_type || a.type, date: (a.start_date_local || '').slice(0, 10),
      km: a.distance ? Math.round(a.distance / 100) / 10 : null,
      min: dur ? Math.round(dur / 60) : null,
      gain_m: gain ? Math.round(gain) : null,
      avg_hr: a.average_heartrate ? Math.round(a.average_heartrate) : null,
      vert: (gain && dur) ? Math.round(gain / (dur / 3600)) : null,
    }
  } catch (e) { return null }
}

// ── formatters ──────────────────────────────────────────────────────
function zoneOf(hr) { for (const [lo, hi, n] of ZONES) if (hr >= lo && hr <= hi) return n; return hr < ZONES[0][0] ? 'Z1' : 'Z4+' }
function activityLines(act) {
  if (!act) return ['🏃 activity: n/a — (ดูเต็ม → /health กับ Claude)']
  const parts = []
  if (act.km) parts.push(`${act.km} กม.`)
  if (act.min) parts.push(`${act.min} นาที`)
  if (act.gain_m) parts.push(`+${act.gain_m} ม.`)
  const L = [`🏃 ล่าสุด (${act.date || '?'}): ${parts.length ? parts.join(' · ') : (act.type || 'กิจกรรม')}`]
  if (act.avg_hr) { const m = act.avg_hr <= EASY_HR_CAP ? ' ✅ คุมโซนดี' : ' ⚠️ HR สูง — ระวัง pacing'; L.push(`   avgHR ${act.avg_hr} (${zoneOf(act.avg_hr)})${m}`) }
  if (act.vert) { const vm = act.vert >= 550 ? ' ✅' : (act.vert >= 400 ? ' 🟡' : ' 🔴 (เป้า 550-650)'); L.push(`   ไต่ ${act.vert} ม/ชม${vm}`) }
  return L
}
function arrow(now, avg) {
  if (now == null || avg == null) return ''
  if (now > avg * 1.03) return ' ↑'
  if (now < avg * 0.97) return ' ↓'
  return ' →'
}
function header(iso) {
  const d = asUTC(iso)
  return `🌅 ${DOW[pyWeekday(iso)]} ${d.getUTCDate()} ${MON[d.getUTCMonth() + 1]} — เหลือ ${daysBetween(iso, RACE_ISO)} วัน CM6 i2`
}
function recoveryLines(o) {
  const L = [], flags = []
  if (o.sleep_h != null) { const w = o.sleep_h < 7 ? ' 🔴' : ' ✅'; L.push(`😴 นอน ${o.sleep_h} ชม.${w}  (เป้า 7)`); if (o.sleep_h < 7) flags.push('นอนน้อย') }
  else L.push('😴 นอน: n/a')
  if (o.hrv != null) L.push(`💗 HRV ${o.hrv}${arrow(o.hrv, o.hrv_avg7)}  (avg7 ${o.hrv_avg7 ?? '–'})`)
  if (o.rhr != null) L.push(`❤️ RHR ${o.rhr}${arrow(o.rhr, o.rhr_avg7)}  (avg7 ${o.rhr_avg7 ?? '–'})`)
  if (o.readiness != null) {
    let f = ' ✅'; if (o.readiness < 55) { f = ' 🔴 พัก/เดินเบา'; flags.push('readiness ต่ำ') } else if (o.readiness < 70) f = ' 🟡'
    L.push(`💚 Readiness ${o.readiness}${f}`)
  }
  if (o.sleep_score != null) L.push(`🛌 Sleep score ${o.sleep_score}`)
  return { L, flags }
}
function planLines(p) {
  if (!p) return ['📋 แผนวันนี้: (นอกช่วงตารางซ้อม)']
  const L = [`📋 แผนวันนี้: ${p.s}`]
  if (p.d && p.d !== '—') L.push(`   ${p.d}`)
  if (p.h && p.h !== '—') L.push(`   เป้า HR: ${p.h}`)
  return L
}
function digestText(iso, o, act, p) {
  const { L, flags } = recoveryLines(o)
  if (act && act.avg_hr && act.avg_hr > EASY_HR_CAP) flags.push('HR ซ้อมสูง')
  const out = [header(iso), '', ...L, '', ...activityLines(act), '', ...planLines(p)]
  if (flags.length) { out.push(''); out.push('⚠️ ธงเตือน: ' + flags.join(' · ')) }
  return out.join('\n')
}

// ── Telegram ────────────────────────────────────────────────────────
async function tgSend(token, chatId, text, markup) {
  const body = { chat_id: chatId, text }
  if (markup) body.reply_markup = markup
  await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}
const EDIT_BTN = { inline_keyboard: [[{ text: '✏️ แก้ไขเป็นตาราง', web_app: { url: 'https://health-proxy.ideaplanstudio.workers.dev/edit' } }]] }

// ── ตรวจ Telegram WebApp initData (HMAC) ────────────────────────────
async function hmacRaw(keyBytes, msg) {
  const k = await crypto.subtle.importKey('raw', keyBytes, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign'])
  return new Uint8Array(await crypto.subtle.sign('HMAC', k, new TextEncoder().encode(msg)))
}
const toHex = (b) => [...b].map(x => x.toString(16).padStart(2, '0')).join('')
async function validateInit(initData, botToken) {
  if (!initData) return null
  const p = new URLSearchParams(initData)
  const hash = p.get('hash'); if (!hash) return null
  p.delete('hash')
  const dcs = [...p.entries()].sort((a, b) => a[0] < b[0] ? -1 : 1).map(([k, v]) => `${k}=${v}`).join('\n')
  const secret = await hmacRaw(new TextEncoder().encode('WebAppData'), botToken)
  if (toHex(await hmacRaw(secret, dcs)) !== hash) return null
  try { return JSON.parse(p.get('user') || 'null') } catch (e) { return null }
}
const HELP = ['🤖 คำสั่ง CM6 Health', '/today — สรุปสุขภาพวันนี้ (Oura สด)', '/readiness — นอน/HRV/readiness', '/plan — แผนซ้อมวันนี้', '📚 /done <ทำอะไรไป> — ส่งการบ้าน + รับคอมเมนต์โค้ช', '/homework — สรุปการบ้าน 7 วัน', '🧾 ส่งรูปใบเสร็จ — ดึงรายการ+ราคา+แคล (ทดสอบ)', '/token — สรุป token + ค่าใช้จ่าย Gemini', '/help — คำสั่งทั้งหมด', '', '🔎 วิเคราะห์ลึก/activity → คุยกับ Claude'].join('\n')

// ── ใบเสร็จ → Gemini (โหมดทดสอบ: ยังไม่บันทึก) · แก้ได้ด้วยภาษาพูด ───────
const GEMINI_URL = (env) => `https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key=${env.GEMINI_KEY}`
function geminiUsage(j) { const u = j.usageMetadata || {}; return { in: u.promptTokenCount || 0, out: u.candidatesTokenCount || 0, total: u.totalTokenCount || 0 } }
function extractJSON(txt) { const m = (txt || '').match(/\{[\s\S]*\}/); if (!m) return null; try { return JSON.parse(m[0]) } catch (e) { return null } }

const RECEIPT_SCHEMA = `{"shop":"ชื่อร้าน","datetime":"วันเวลาถ้ามี","people":จำนวนคนถ้าระบุบนใบเช่น TABLE(n) ไม่งั้น null,"items":[{"name":"ชื่อรายการ","qty":number,"price":number,"kcal":number}],"total_price":number,"total_kcal":number}`

async function parseReceipt(env, b64, caption) {
  const prompt = `อ่านใบเสร็จในรูปนี้ ดึงข้อมูลตามจริง ห้ามแสดงความคิดเห็น/คำแนะนำ${caption ? '\nหมายเหตุผู้ใช้: ' + caption : ''}
ตอบ JSON ล้วน ไม่มีข้อความอื่น: ${RECEIPT_SCHEMA}
- name/qty/price อ่านตามจริง อ่านไม่ออกใส่ null · kcal ประเมินจากชื่ออาหาร (ตัวเลขเฉยๆ) รายการไม่ใช่อาหารใส่ null`
  const body = { contents: [{ parts: [{ inline_data: { mime_type: 'image/jpeg', data: b64 } }, { text: prompt }] }] }
  const r = await fetch(GEMINI_URL(env), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  if (!r.ok) return { data: null, usage: null }
  const j = await r.json()
  return { data: extractJSON(j.candidates?.[0]?.content?.parts?.[0]?.text), usage: geminiUsage(j) }
}

async function editReceipt(env, draft, instruction) {
  const prompt = `JSON ใบเสร็จปัจจุบัน: ${JSON.stringify(draft)}
ผู้ใช้สั่งแก้: "${instruction}"
แก้ JSON ตามคำสั่ง: ถ้าสั่งหารคน→ตั้ง field "people"; ลบ/เพิ่ม/แก้รายการหรือราคา ตามสั่ง; คำนวณ total_kcal ใหม่จาก items; total_price คงยอดบิลจริงเว้นแต่ผู้ใช้สั่งแก้.
ตอบ JSON เดิมที่แก้แล้วล้วน ไม่มีข้อความอื่น โครงสร้างเดิม: ${RECEIPT_SCHEMA}`
  const body = { contents: [{ parts: [{ text: prompt }] }] }
  const r = await fetch(GEMINI_URL(env), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  if (!r.ok) return { data: null, usage: null }
  const j = await r.json()
  return { data: extractJSON(j.candidates?.[0]?.content?.parts?.[0]?.text), usage: geminiUsage(j) }
}

function renderReceipt(d) {
  const items = Array.isArray(d.items) ? d.items : []
  const L = ['🧾 ใบเสร็จ — 🧪 โหมดทดสอบ (ยังไม่บันทึก)']
  const head = [d.shop, d.datetime].filter(Boolean).join(' · ')
  if (head) L.push(head)
  for (const it of items) {
    const q = it.qty && it.qty > 1 ? ` x${it.qty}` : ''
    const price = it.price != null ? ` — ฿${it.price}` : ''
    const kc = it.kcal != null ? ` (${it.kcal} kcal)` : ''
    L.push(`• ${it.name || '?'}${q}${price}${kc}`)
  }
  const tp = d.total_price
  L.push(`ยอดบิล: ${tp != null ? '฿' + tp : '?'}${d.total_kcal != null ? ` · ${d.total_kcal} kcal` : ''}`)
  const n = d.people && d.people > 1 ? d.people : null
  if (n) {
    const per = tp != null ? Math.round(tp / n) : null
    const pk = d.total_kcal != null ? Math.round(d.total_kcal / n) : null
    L.push(`👥 หาร ${n} คน → คุณ: ${per != null ? '฿' + per : '?'}${pk != null ? ` · ${pk} kcal` : ''}`)
  }
  L.push('✏️ แก้ได้: พิมพ์บอก เช่น "หาร 5 คน" · "ลบโค้ก" · "กะเพรา 60"')
  return L.join('\n')
}

async function saveDraft(env, chatId, data) {
  if (env.STATS) await env.STATS.put(`draft:${chatId}`, JSON.stringify(data), { expirationTtl: 21600 })
}
async function loadDraft(env, chatId) {
  if (!env.STATS) return null
  const raw = await env.STATS.get(`draft:${chatId}`)
  return raw ? JSON.parse(raw) : null
}

// ── ส่งการบ้าน (check-back ④) + คอมเมนต์โค้ช ─────────────────────────
function planStr(p) {
  if (!p) return '(นอกตารางซ้อม)'
  return `${p.s}${p.d && p.d !== '—' ? ' — ' + p.d : ''}${p.h && p.h !== '—' ? ` (เป้า HR ${p.h})` : ''}`
}
async function homeworkComment(env, plan, submission) {
  const prompt = `คุณคือโค้ชวิ่งเทรลที่เป็นกันเอง พูดสั้นกระชับ.
แผนซ้อมวันนี้: "${planStr(plan)}".
นักวิ่งรายงานผล: "${submission}".
ให้คอมเมนต์ภาษาไทยสั้น 1-2 บรรทัด: ชมถ้าทำตรงแผน/คุมโซนได้, เตือนสั้นถ้าเกินโซน(>150)หรือทำไม่ครบ, ถ้าพัก/พลาดให้ถามสั้นๆว่าติดอะไรพรุ่งนี้แก้ยังไง. โทนให้กำลังใจแต่ตรงไปตรงมา ห้ามเทศนายืดยาว ห้ามใช้ bullet ตอบเป็นข้อความล้วน.`
  const r = await fetch(GEMINI_URL(env), {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ contents: [{ parts: [{ text: prompt }] }] }),
  })
  if (!r.ok) return { comment: '(คอมเมนต์ไม่ได้ตอนนี้)', usage: null }
  const j = await r.json()
  return { comment: (j.candidates?.[0]?.content?.parts?.[0]?.text || '(ไม่มีคอมเมนต์)').trim(), usage: geminiUsage(j) }
}
async function homeworkSummary(env, todayISO) {
  if (!env.STATS) return '📚 ยังไม่ได้ตั้ง storage'
  const rows = [], dates = []
  let done = 0
  for (let i = 0; i < 7; i++) {
    const d = addDays(todayISO, -i)
    dates.push(d)
    const raw = await env.STATS.get(`hw:${d}`)
    if (raw) { done++; rows.push(`✅ ${d.slice(5)}: ${(JSON.parse(raw).text || '').slice(0, 45)}`) }
    else rows.push(`⬜ ${d.slice(5)}: ยังไม่ส่ง`)
  }
  return [`📚 การบ้าน 7 วันล่าสุด — ส่งแล้ว ${done}/7 วัน`, '', ...rows].join('\n')
}

async function recordTokens(env, u, thb) {
  if (!env.STATS) return null
  const raw = await env.STATS.get('meal_tokens')
  const s = raw ? JSON.parse(raw) : { count: 0, in: 0, out: 0, total: 0, thb: 0, items: [] }
  s.count++; s.in += u.in; s.out += u.out; s.total += u.total; s.thb += thb
  s.items.push({ total: u.total, thb: Number(thb.toFixed(4)) })
  if (s.items.length > 50) s.items = s.items.slice(-50)
  await env.STATS.put('meal_tokens', JSON.stringify(s))
  return s.thb   // ยอดสะสมรวม
}

async function tokenSummary(env) {
  if (!env.STATS) return '📊 ยังไม่ได้ตั้ง storage'
  const raw = await env.STATS.get('meal_tokens')
  if (!raw) return '📊 ยังไม่มีการเรียก Gemini'
  const s = JSON.parse(raw)
  const L = ['📊 สรุปการใช้ Gemini (ใบเสร็จ)',
    `เรียกทั้งหมด: ${s.count} ครั้ง`,
    `โทเค็นรวม: ${s.total.toLocaleString()} (in ${s.in.toLocaleString()} · out ${s.out.toLocaleString()})`,
    `💰 ค่าใช้จ่ายรวม: ฿${s.thb.toFixed(2)}`,
    `เฉลี่ย/ครั้ง: ${Math.round(s.total / s.count).toLocaleString()} tok · ฿${(s.thb / s.count).toFixed(2)}`,
    '', '🖼️ ล่าสุด:']
  s.items.slice(-10).forEach((it, i) => L.push(`${i + 1}. ${it.total.toLocaleString()} tok · ฿${it.thb.toFixed(2)}`))
  L.push('', `เรต: in $${GEM_IN_USD}/1M · out $${GEM_OUT_USD}/1M · ฿${USD_THB}/$`)
  return L.join('\n')
}

async function usageLine(env, usage) {
  if (!usage || !usage.total) return ''
  const thb = costTHB(usage)
  const total = await recordTokens(env, usage, thb)
  return `\n\n🪙 Gemini: ${usage.total.toLocaleString()} tokens · ฿${thb.toFixed(2)}` +
    (total != null ? ` (สะสม ฿${total.toFixed(2)})` : '')
}

async function handlePhoto(msg, env) {
  const token = env.TELEGRAM_BOT_TOKEN
  await tgSend(token, msg.chat.id, '🔍 กำลังอ่านใบเสร็จ...')
  try {
    const photos = msg.photo
    const fileId = photos[photos.length - 1].file_id          // ใหญ่สุด
    const gf = await (await fetch(`https://api.telegram.org/bot${token}/getFile?file_id=${fileId}`)).json()
    const imgRes = await fetch(`https://api.telegram.org/file/bot${token}/${gf.result.file_path}`)
    const buf = new Uint8Array(await imgRes.arrayBuffer())
    let bin = ''
    for (let i = 0; i < buf.length; i++) bin += String.fromCharCode(buf[i])
    const { data, usage } = await parseReceipt(env, btoa(bin), msg.caption || '')
    const extra = await usageLine(env, usage)
    if (!data || !(Array.isArray(data.items) && data.items.length)) {
      await tgSend(token, msg.chat.id, '🧾 อ่านใบเสร็จไม่ออก ลองถ่ายให้ชัด/ตรงขึ้น' + extra)
      return
    }
    await saveDraft(env, msg.chat.id, data)
    await tgSend(token, msg.chat.id, renderReceipt(data) + extra, EDIT_BTN)
  } catch (e) {
    await tgSend(token, msg.chat.id, '🧾 ขออภัย อ่านใบเสร็จไม่สำเร็จ ลองใหม่อีกครั้ง')
  }
}

async function handleCorrection(msg, env) {
  const token = env.TELEGRAM_BOT_TOKEN
  const draft = await loadDraft(env, msg.chat.id)
  if (!draft) return false                                   // ไม่มีใบเสร็จค้าง → ไม่ใช่การแก้
  const { data, usage } = await editReceipt(env, draft, msg.text.trim())
  const extra = await usageLine(env, usage)
  if (!data) { await tgSend(token, msg.chat.id, '🧾 แก้ไม่สำเร็จ ลองพิมพ์ใหม่' + extra); return true }
  await saveDraft(env, msg.chat.id, data)
  await tgSend(token, msg.chat.id, renderReceipt(data) + extra, EDIT_BTN)
  return true
}

async function handleTelegram(update, env) {
  const msg = update.message || update.edited_message
  if (!msg) return
  if (msg.chat.id !== OWNER_CHAT_ID) return                 // ตอบเฉพาะเจ้าของ
  if (msg.photo) { await handlePhoto(msg, env); return }    // 📸 รูปอาหาร
  if (!msg.text) return
  const cmd = msg.text.trim().split(/\s+/)[0].split('@')[0].toLowerCase()
  const token = env.TELEGRAM_BOT_TOKEN
  const today = ictTodayISO()

  if (cmd === '/today' || cmd === '/now' || cmd === '/start') {
    const [o, act] = await Promise.all([fetchOura(env.OURA_TOKEN, today), fetchStrava(env)])
    await tgSend(token, msg.chat.id, digestText(today, o, act, planFor(today)))
  } else if (cmd === '/readiness') {
    const o = await fetchOura(env.OURA_TOKEN, today)
    const { L } = recoveryLines(o)
    await tgSend(token, msg.chat.id, [header(today), '', ...L].join('\n'))
  } else if (cmd === '/plan') {
    await tgSend(token, msg.chat.id, [header(today), '', ...planLines(planFor(today))].join('\n'))
  } else if (cmd === '/token') {
    await tgSend(token, msg.chat.id, await tokenSummary(env))
  } else if (cmd === '/done') {
    const submission = msg.text.trim().replace(/^\/done(@\S+)?\s*/i, '').trim()
    const plan = planFor(today)
    if (!submission) {
      await tgSend(token, msg.chat.id, `📚 การบ้านวันนี้: ${plan ? plan.s : '(นอกตาราง)'}\nส่งด้วย: /done <ทำอะไรไป>\nเช่น  /done long vertical 2ชม +650m HR เฉลี่ย 142\nหรือ  /done พักเพราะเอ็นตึง`)
    } else {
      const { comment, usage } = await homeworkComment(env, plan, submission)
      const extra = await usageLine(env, usage)
      if (env.STATS) await env.STATS.put(`hw:${today}`, JSON.stringify({ plan: plan ? plan.s : null, text: submission, comment }), { expirationTtl: 60 * 60 * 24 * 60 })
      await tgSend(token, msg.chat.id, `📚 รับการบ้าน ${today} ✅\n📋 แผน: ${plan ? plan.s : '—'}\n✍️ ${submission}\n💬 โค้ช: ${comment}${extra}`)
    }
  } else if (cmd === '/homework') {
    await tgSend(token, msg.chat.id, await homeworkSummary(env, today))
  } else if (!cmd.startsWith('/') && await handleCorrection(msg, env)) {
    // ข้อความธรรมดา + มีใบเสร็จค้าง = คำสั่งแก้ไข (จัดการใน handleCorrection แล้ว)
  } else {
    await tgSend(token, msg.chat.id, HELP)
  }
}

// ── Telegram Mini App: ตารางแก้ใบเสร็จ ──────────────────────────────
const EDIT_HTML = `<!doctype html><html lang=th><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
body{font-family:-apple-system,sans-serif;padding:12px;background:var(--tg-theme-bg-color,#fff);color:var(--tg-theme-text-color,#000);margin:0}
h3{margin:.3em 0}
.fld{margin:6px 0}
table{width:100%;border-collapse:collapse;font-size:13px;margin-top:6px}
th,td{border:1px solid var(--tg-theme-hint-color,#ccc);padding:1px 3px}
th{font-weight:600}
input{width:100%;box-sizing:border-box;border:none;background:transparent;color:inherit;font-size:13px;padding:6px 2px}
input.num{text-align:right}
.del{color:#e55;cursor:pointer;text-align:center;user-select:none}
#tot{margin:10px 0;font-weight:600}
button{font-size:15px;border-radius:8px;border:none;padding:10px;margin-top:6px;width:100%}
#add{background:var(--tg-theme-secondary-bg-color,#eee);color:inherit}
#save{background:var(--tg-theme-button-color,#2ea6ff);color:var(--tg-theme-button-text-color,#fff)}
</style></head><body>
<h3>🧾 แก้ไขใบเสร็จ</h3>
<div class=fld>ร้าน: <input id=shop placeholder=ชื่อร้าน></div>
<table><thead><tr><th>รายการ</th><th>จำ</th><th>ราคา</th><th>kcal</th><th></th></tr></thead><tbody id=tb></tbody></table>
<button id=add>+ เพิ่มแถว</button>
<div class=fld>👥 จำนวนคน: <input id=people class=num type=number min=1 style="width:70px;border:1px solid #ccc;border-radius:6px"></div>
<div id=tot></div>
<button id=save>บันทึก ✅</button>
<script>
const tg=Telegram.WebApp;tg.expand();tg.ready();
let dt=null;
function row(it={}){const tr=document.createElement('tr');
tr.innerHTML='<td><input class=name></td><td><input class="num qty" type=number></td><td><input class="num price" type=number></td><td><input class="num kcal" type=number></td><td class=del>🗑️</td>';
tr.querySelector('.name').value=it.name||'';tr.querySelector('.qty').value=it.qty==null?1:it.qty;tr.querySelector('.price').value=it.price==null?'':it.price;tr.querySelector('.kcal').value=it.kcal==null?'':it.kcal;
tr.querySelector('.del').onclick=()=>{tr.remove();calc()};
tr.querySelectorAll('input').forEach(i=>i.oninput=calc);document.getElementById('tb').appendChild(tr);}
function num(v){return v===''||v==null?null:+v}
function collect(){const items=[...document.querySelectorAll('#tb tr')].map(tr=>({name:tr.querySelector('.name').value,qty:num(tr.querySelector('.qty').value)||1,price:num(tr.querySelector('.price').value),kcal:num(tr.querySelector('.kcal').value)}));
const people=+document.getElementById('people').value||1;
const total_price=items.reduce((s,i)=>s+(i.price||0),0),total_kcal=items.reduce((s,i)=>s+(i.kcal||0),0);
return{shop:document.getElementById('shop').value,datetime:dt&&dt.datetime,people,items,total_price,total_kcal};}
function calc(){const d=collect();let t='ยอด ฿'+d.total_price+' · '+d.total_kcal+' kcal';if(d.people>1)t+=' | 👥 คุณ ฿'+Math.round(d.total_price/d.people)+' · '+Math.round(d.total_kcal/d.people)+' kcal';document.getElementById('tot').textContent=t;}
async function api(action,data){const r=await fetch('/api/receipt',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({initData:tg.initData,action,data})});return r.json();}
document.getElementById('add').onclick=()=>{row();calc()};
document.getElementById('save').onclick=async()=>{const b=document.getElementById('save');b.disabled=true;b.textContent='กำลังบันทึก...';await api('save',collect());tg.close();};
(async()=>{const res=await api('get');dt=res.draft||{items:[]};document.getElementById('shop').value=dt.shop||'';document.getElementById('people').value=dt.people||1;(dt.items||[]).forEach(row);if(!(dt.items||[]).length)row();calc();})();
</script></body></html>`

export default {
  async fetch(request, env) {
    const url = new URL(request.url)
    const path = url.pathname
    if (request.method === 'OPTIONS') return new Response(null, { headers: CORS })

    // ── /telegram ── webhook รับคำสั่งบอท
    if (path === '/telegram' && request.method === 'POST') {
      if (env.TELEGRAM_WEBHOOK_SECRET &&
          request.headers.get('x-telegram-bot-api-secret-token') !== env.TELEGRAM_WEBHOOK_SECRET) {
        return new Response('forbidden', { status: 403 })
      }
      try { await handleTelegram(await request.json(), env) } catch (e) { /* always 200 to Telegram */ }
      return new Response('ok')
    }

    // ── /edit ── Mini App หน้าตารางแก้ใบเสร็จ
    if (path === '/edit') {
      return new Response(EDIT_HTML, { headers: { 'Content-Type': 'text/html; charset=utf-8' } })
    }

    // ── /api/receipt ── get/save draft จาก Mini App (ตรวจ initData)
    if (path === '/api/receipt' && request.method === 'POST') {
      const { initData, action, data } = await request.json()
      const user = await validateInit(initData, env.TELEGRAM_BOT_TOKEN)
      if (!user || user.id !== OWNER_CHAT_ID) return cors(JSON.stringify({ error: 'forbidden' }), 403)
      if (action === 'get') return cors(JSON.stringify({ draft: await loadDraft(env, user.id) }))
      if (action === 'save') {
        await saveDraft(env, user.id, data)
        await tgSend(env.TELEGRAM_BOT_TOKEN, user.id, renderReceipt(data) + '\n✅ แก้จากตารางแล้ว', EDIT_BTN)
        return cors(JSON.stringify({ ok: true }))
      }
      return cors(JSON.stringify({ error: 'bad action' }), 400)
    }

    // ── /digest-claim ── กันส่ง digest ซ้ำ (cron เช้าหลายรอบ) claim ต่อวัน
    if (path === '/digest-claim' && request.method === 'POST') {
      if (request.headers.get('x-digest-secret') !== env.DIGEST_SECRET) return cors(JSON.stringify({ error: 'forbidden' }), 403)
      const { date } = await request.json()
      const key = `digest_sent:${date}`
      if (await env.STATS.get(key)) return cors(JSON.stringify({ go: false }))
      await env.STATS.put(key, '1', { expirationTtl: 172800 })   // 2 วัน
      return cors(JSON.stringify({ go: true }))
    }

    // ── /oura/* ── proxy to Oura v2 API
    if (path.startsWith('/oura/')) {
      const ouraURL = `https://api.ouraring.com/v2${path.replace('/oura', '')}${url.search}`
      const res = await fetch(ouraURL, { headers: { Authorization: `Bearer ${env.OURA_TOKEN}` } })
      return cors(await res.text(), res.status)
    }

    // ── /gemini ── proxy to Gemini generateContent
    if (path === '/gemini' && request.method === 'POST') {
      const body = await request.text()
      const geminiURL = `https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key=${env.GEMINI_KEY}`
      const res = await fetch(geminiURL, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body })
      return cors(await res.text(), res.status)
    }

    return cors(JSON.stringify({ error: 'not found' }), 404)
  },

  // ── cron: เย็นเตือนส่งการบ้าน (20:00 ICT = 13:00 UTC) ──
  async scheduled(event, env, ctx) {
    const today = ictTodayISO()
    const p = planFor(today)
    const detail = p && p.d && p.d !== '—' ? '\n   ' + p.d : ''
    await tgSend(env.TELEGRAM_BOT_TOKEN, OWNER_CHAT_ID,
      `📚 ส่งการบ้านวันนี้ (${DOW[pyWeekday(today)]} ${asUTC(today).getUTCDate()})\n📋 ${p ? p.s : '(นอกตารางซ้อม)'}${detail}\n\nทำได้แค่ไหน? ส่ง: /done <บอกผล>\nเช่น  /done +650m HR142  ·  /done พักเอ็นตึง`)
  },
}
