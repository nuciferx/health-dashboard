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
async function tgSend(token, chatId, text) {
  await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chat_id: chatId, text }),
  })
}
const HELP = ['🤖 คำสั่ง CM6 Health', '/today — สรุปสุขภาพวันนี้ (Oura สด)', '/readiness — นอน/HRV/readiness', '/plan — แผนซ้อมวันนี้', '📸 ส่งรูปอาหาร — AI วิเคราะห์แคล/มาโคร (โหมดทดสอบ)', '/token — สรุป token + ค่าใช้จ่าย Gemini', '/help — คำสั่งทั้งหมด', '', '🔎 วิเคราะห์ลึก/activity → คุยกับ Claude'].join('\n')

// ── รูปอาหาร → Gemini Vision (โหมดทดสอบ: ยังไม่บันทึก log) ───────────
async function analyzeMeal(env, b64, caption) {
  const prompt = `คุณคือนักโภชนาการที่แม่นยำ ช่วยนักวิ่งเทรลลดน้ำหนัก (95→เป้า 90-91 กก.).
ดูรูปนี้อย่างละเอียดก่อนประเมิน:
1) อ่านตัวอักษร/แบรนด์บนแก้ว/บรรจุภัณฑ์ถ้ามี
2) ถ้าเป็นเครื่องดื่ม: ดูสี — "ใส/โปร่งแสง" = กาแฟดำ/ชา/โทนิค (ไม่มีนม ไขมัน~0) · "ขุ่น/สีครีม" = มีนม
3) ห้ามเดาท็อปปิ้ง/ส่วนผสมที่มองไม่เห็นชัด (ฟองบนกาแฟดำ = crema ไม่ใช่ครีม)
4) ถ้าไม่ชัดว่าหวานไหม ประเมินแบบไม่หวาน แล้วระบุในสมมติฐาน${caption ? '\nผู้ใช้ระบุ (เชื่อถือเป็นหลัก): ' + caption : ''}
ตอบ JSON ล้วน ไม่มีข้อความอื่น: {"food":"ชื่อไทยสั้นๆ","kcal":number,"protein":number,"carb":number,"fat":number,"confidence":"สูง|กลาง|ต่ำ","assume":"สมมติฐานสั้นๆ","tip":"คำแนะนำลดน้ำหนักสั้นๆ"}`
  const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key=${env.GEMINI_KEY}`
  const body = { contents: [{ parts: [{ inline_data: { mime_type: 'image/jpeg', data: b64 } }, { text: prompt }] }] }
  const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  if (!r.ok) return { text: `📸 วิเคราะห์ไม่ได้ (Gemini ${r.status})`, usage: null }
  const j = await r.json()
  const um = j.usageMetadata || {}
  const usage = { in: um.promptTokenCount || 0, out: um.candidatesTokenCount || 0, total: um.totalTokenCount || 0 }
  const txt = j.candidates?.[0]?.content?.parts?.[0]?.text || ''
  const m = txt.match(/\{[\s\S]*\}/)
  if (!m) return { text: '📸 อ่านผลไม่ได้:\n' + txt.slice(0, 300), usage }
  let d
  try { d = JSON.parse(m[0]) } catch (e) { return { text: '📸 อ่านผลไม่ได้ (parse)', usage } }
  const L = ['📸 มื้อนี้ — 🧪 โหมดทดสอบ (ยังไม่บันทึก)', `🍽️ ${d.food || '?'}`,
    `≈ ${d.kcal ?? '?'} kcal  ·  P ${d.protein ?? '?'}g · C ${d.carb ?? '?'}g · F ${d.fat ?? '?'}g`]
  if (d.confidence || d.assume) L.push(`🎯 มั่นใจ: ${d.confidence || '?'}${d.assume ? ` · สมมติ: ${d.assume}` : ''}`)
  if (d.tip) L.push(`💡 ${d.tip}`)
  L.push('✏️ ไม่ตรง? ส่งรูปใหม่พร้อมแคปชั่นชื่ออาหาร เช่น "อเมริกาโน่ดำ ไม่หวาน"')
  return { text: L.join('\n'), usage }
}

async function recordTokens(env, u, thb) {
  if (!env.STATS) return
  const raw = await env.STATS.get('meal_tokens')
  const s = raw ? JSON.parse(raw) : { count: 0, in: 0, out: 0, total: 0, thb: 0, items: [] }
  s.count++; s.in += u.in; s.out += u.out; s.total += u.total; s.thb += thb
  s.items.push({ total: u.total, thb: Number(thb.toFixed(4)) })
  if (s.items.length > 50) s.items = s.items.slice(-50)
  await env.STATS.put('meal_tokens', JSON.stringify(s))
}

async function tokenSummary(env) {
  if (!env.STATS) return '📊 ยังไม่ได้ตั้ง storage'
  const raw = await env.STATS.get('meal_tokens')
  if (!raw) return '📊 ยังไม่มีการวิเคราะห์รูปอาหาร'
  const s = JSON.parse(raw)
  const L = ['📊 สรุปการใช้ Gemini (รูปอาหาร)',
    `รูปทั้งหมด: ${s.count} รูป`,
    `โทเค็นรวม: ${s.total.toLocaleString()} (in ${s.in.toLocaleString()} · out ${s.out.toLocaleString()})`,
    `💰 ค่าใช้จ่ายรวม: ฿${s.thb.toFixed(2)}`,
    `เฉลี่ย/รูป: ${Math.round(s.total / s.count).toLocaleString()} tok · ฿${(s.thb / s.count).toFixed(2)}`,
    '', '🖼️ รายรูปล่าสุด:']
  s.items.slice(-10).forEach((it, i) => L.push(`${i + 1}. ${it.total.toLocaleString()} tok · ฿${it.thb.toFixed(2)}`))
  L.push('', `เรต: in $${GEM_IN_USD}/1M · out $${GEM_OUT_USD}/1M · ฿${USD_THB}/$`)
  return L.join('\n')
}

async function handlePhoto(msg, env) {
  const token = env.TELEGRAM_BOT_TOKEN
  await tgSend(token, msg.chat.id, '🔍 กำลังวิเคราะห์รูปอาหาร...')
  try {
    const photos = msg.photo
    const fileId = photos[photos.length - 1].file_id          // ใหญ่สุด
    const gf = await (await fetch(`https://api.telegram.org/bot${token}/getFile?file_id=${fileId}`)).json()
    const imgRes = await fetch(`https://api.telegram.org/file/bot${token}/${gf.result.file_path}`)
    const buf = new Uint8Array(await imgRes.arrayBuffer())
    let bin = ''
    for (let i = 0; i < buf.length; i++) bin += String.fromCharCode(buf[i])
    const b64 = btoa(bin)
    const res = await analyzeMeal(env, b64, msg.caption || '')
    let reply = res.text
    if (res.usage && res.usage.total) {
      const thb = costTHB(res.usage)
      reply += `\n\n🪙 ${res.usage.total.toLocaleString()} tokens (in ${res.usage.in}/out ${res.usage.out}) · ฿${thb.toFixed(2)}`
      await recordTokens(env, res.usage, thb)
    }
    await tgSend(token, msg.chat.id, reply)
  } catch (e) {
    await tgSend(token, msg.chat.id, '📸 ขออภัย วิเคราะห์รูปไม่สำเร็จ ลองใหม่อีกครั้ง')
  }
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
  } else {
    await tgSend(token, msg.chat.id, HELP)
  }
}

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
}
