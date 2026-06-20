# CLAUDE.md — Health Dashboard (CM6 i2 training)

ผู้ใช้สื่อสารภาษาไทย — ตอบไทยเสมอ

## เป้าหมายโปรเจกต์
ติดตามสุขภาพ + การซ้อมของนักวิ่งเทรลที่กำลังเตรียม **CM6 i2** (trail ultra)
- **วันแข่ง:** 8 ส.ค. 2026 · 40 กม. / +2,380 ม. / cutoff 13 ชม. · ออกตัว 05:30 (เชียงใหม่)
- **เป้า:** จบ ~12:00 · ทน 10+ ชม. โดยไม่ถล่มที่ชั่วโมงที่ 3
- นักกีฬา: อายุ 44, น้ำหนักเริ่ม ~95 กก. (เป้า 90-91 วันแข่ง)
- แผนละเอียดอยู่ใน `CM6_i2_ตารางซ้อม.md`, `CM6_i2_7week_plan.md`, `CM6_i2_แผนทุกมิติ.md`, `CM6_i2_บันทึกวิเคราะห์.md`, `CM6_i2_เมนูอาหาร.md`

## สถาปัตยกรรม (3 ส่วน)

**① Morning digest อัตโนมัติ → Telegram** (rule-based ล้วน, ไม่มี AI)
- `morning_digest.py` + `.github/workflows/morning-digest.yml`
- **cron หลายรอบ 06:00–09:30 ICT (ทุก 30 นาที)** — เพราะแหวน Oura sync เข้าคลาวด์หลังตื่น/เปิดมือถือ ไม่ใช่ 6 โมงเป๊ะ
  - รอบที่ Oura ยังไม่มีข้อมูลวันนี้ (`readiness` & `sleep_h` = None) → **ข้าม ไม่ส่งของว่าง**
  - รอบแรกที่ข้อมูลพร้อม → ส่ง 1 ครั้ง แล้ว **claim ผ่าน worker `/digest-claim` (KV) กันส่งซ้ำ** · `workflow_dispatch` = force ส่งทันที ข้าม gate
- ดึง Oura + Garmin(token) + Strava → สรุปนอน/HRV/RHR/readiness/stress/resilience + activity + **สรุป 7 วัน (วินัยโซน ≤150 + ไต่รวม + จับช่วงหาย ≥3 วัน)** + แผนวันนี้ → ส่ง Telegram
- **Adherence v1** (`fetch_strava_week`/`training_review`): จับ gray-zone + ช่วงหาย อิงพฤติกรรมจริง (ดู `CM6_i2_adherence_research.md`) · ถัดไป: streak (ต้อง KV), check-back ✅/❌ รายวัน, session-specific accountability
- ปรัชญา: ส่งข้อเท็จจริง + ธงเตือน เท่านั้น **ไม่ใส่คำแนะนำ AI รายวัน** (เคยตัดสินใจแล้วว่าเป็น noise)

**② Telegram command bot** (`cf-worker/src/index.js` — webhook `POST /telegram`, owner-only + `TELEGRAM_WEBHOOK_SECRET`)
- คำสั่งสด: `/today` `/readiness` `/plan` (Oura+Strava สด) · `/token` · `/help`
- **📚 ส่งการบ้าน (check-back ④):** `/done <ทำอะไรไป>` → Gemini คอมเมนต์แบบโค้ช (เทียบแผนวันนี้) + เก็บ KV `hw:<date>` · `/homework` = สรุป 7 วัน · **cron 20:00 ICT** (`scheduled()` + `[triggers] crons`) เตือนส่งการบ้านตอนเย็น
- **📸 ส่งรูปใบเสร็จ** → Gemini 3 Flash อ่านรายการ/ราคา/แคล (ข้อมูลล้วน ไม่มีคำแนะนำ) · **โหมดทดสอบ ยังไม่บันทึก meal data**
- แก้ใบเสร็จ 2 ทาง: **ตาราง Mini App** (ปุ่ม → `/edit`, แตะแก้ในช่อง, บันทึกผ่าน `/api/receipt` ตรวจ initData HMAC) หรือ **ภาษาพูด** ("หาร 5 คน", "ลบโค้ก") · per-person split อัตโนมัติ
- โค้ด JS port logic จาก `morning_digest.py` — **ต้อง sync กัน** (แผน/Oura)
- **ข้อจำกัด:** worker ทำ Garmin(token)/Strava-MCP/Claude ไม่ได้ → `/today` มีแค่ Oura+Strava (ไม่มี stress/body battery; อันนั้นอยู่ใน digest 6 โมง)

**③ วิเคราะห์เชิงลึก on-demand กับ Claude** (`/health` skill)
- เวลาต้องการเจาะลึก/ปรับแผน → ใช้ `/health` หรือคุยกับ Claude
- ดึงข้อมูลเต็ม (Oura + Strava + Garmin local) → วิเคราะห์เทียบแผน 7 สัปดาห์ → ปรับตาราง
- **AI วิเคราะห์เฉพาะตอน on-demand เท่านั้น ไม่เคย automate**

## แหล่งข้อมูล + ความเสถียร

| แหล่ง | ใช้ดู | เสถียรภาพ |
|------|------|-----------|
| **Oura** (`OURA_TOKEN`) | นอน/HRV/RHR/readiness + **stress/resilience/contributors** (ใส่แหวน 24ชม.) | ✅ REST API เสถียรมาก — แหล่งฟื้นตัวหลัก |
| **Strava API** (`STRAVA_CLIENT_ID/SECRET/REFRESH_TOKEN`) | activity (cloud!) — Garmin sync เข้า Strava อัตโนมัติ | ✅ ดึงจาก cloud ได้ (OAuth refresh token) — **แหล่ง activity หลักของ digest** |
| **Strava MCP** (`mcp__claude_ai_Strava__*`) | activity เต็ม HR/stream/zone | ✅ ใช้ตอนคุยกับ Claude (/health) |
| **Garmin FR255** (`GARMIN_TOKENS`) | stress / body battery / RHR กลางวัน / VO2max | ✅ **cloud ได้ผ่าน token!** (login-รหัสโดนบล็อก แต่ token-resume ผ่าน) |

> ⚠️ **Garmin trick:** login ด้วย email/password จาก cloud โดนบล็อก 429/403 — **แต่** login ด้วย token (จาก `client.dumps()` ที่ดึง local) **ผ่าน** ทั้ง local + cloud. digest ใช้ `GARMIN_TOKENS` ดึง **body battery(เช้านี้)** (stress ใช้ Oura แทน — cloud-native). Activity ใช้ Strava (Garmin → Strava → อ่าน). VO2max/training-status ลึก ๆ ดึงผ่าน /health.
>
> 🔑 **token หมดอายุ ~1 ปี** (oauth1) — ถ้าวันไหน stress/body battery หาย ให้ re-dump: `python` → `Garmin(email,pw).login()` → `client.dumps()` → `gh secret set GARMIN_TOKENS`

## Secrets
- **GitHub Actions** (สำหรับ digest): `OURA_TOKEN`, `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`, `STRAVA_REFRESH_TOKEN`, `GARMIN_TOKENS`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `DIGEST_SECRET` (claim กันส่งซ้ำ)
- **Local** `.env`: `OURA_TOKEN`, `GARMIN_EMAIL`, `GARMIN_PASSWORD` (+ `SHEET_ID`, `GCP_SA_KEY` legacy)
- **Cloudflare** worker `health-proxy` (`cf-worker/`): `OURA_TOKEN`, `GEMINI_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, `STRAVA_CLIENT_ID/SECRET/REFRESH_TOKEN`, `DIGEST_SECRET` + **KV namespace `STATS`** (token-cost stats · receipt draft `draft:<chatid>` · digest claim `digest_sent:<date>`)
- ตั้ง Cloudflare secret: `printf '%s' "<val>" | npx wrangler secret put <NAME>` (ใน `cf-worker/`)
- ตั้ง GitHub secret: `printf '%s' "<val>" | gh secret set <NAME>` (ต้อง `gh auth login` ก่อน)

## ไฟล์หลัก
- `morning_digest.py` — digest รายวัน (Oura-primary, Garmin best-effort, แผนฝังในสคริปต์)
- `health_pull.py` — ดึง Oura หลายวันเป็น JSON สำหรับวิเคราะห์เชิงลึก
- `.claude/skills/health/SKILL.md` — `/health` วิเคราะห์ on-demand
- `.claude/agents/health-analyst.md` — subagent ดึง+วิเคราะห์ข้อมูล
- `cf-worker/src/index.js` — Worker: proxy (Oura/Gemini) + Telegram bot + ใบเสร็จ Gemini + Mini App ตาราง (`/edit`,`/api/receipt`) + `/token`
- `index.html` — dashboard เก่า (PWA) — legacy ยังใช้งานได้

## "แผนวันนี้" ทำงานยังไง
แผนซ้อมฝังใน `morning_digest.py` (`W1_BY_DATE`, `WEEKS`, `W7_BY_DATE`)
- **map ด้วยชื่อวันจริงในสัปดาห์** (เสาร์=long run เสมอ) — **ห้ามเชื่อ label วันใน `CM6_i2_ตารางซ้อม.md`** เพราะมันเลื่อนผิดตั้งแต่ W2 (สัปดาห์เป็นบล็อก 7 วันเริ่มวันอังคาร)
- ถ้าแก้ตารางซ้อม → ต้องแก้ทั้ง `.md` (อ่านง่าย) **และ** dict ใน `morning_digest.py` (ตัวที่ digest ใช้จริง)

## กระบวนการพัฒนา (Dev workflow)
1. **แก้โค้ด** ในเครื่อง
2. **ทดสอบก่อนเสมอ:** digest → `python morning_digest.py` (dry-run, print แทนส่ง) · worker → `node --check cf-worker/src/index.js`
3. **อัปเดตไฟล์บันทึกในคอมมิตเดียวกันทุกครั้ง** ⭐ — `PROJECT_LOG.md` (section ตามวันที่), `CLAUDE.md` (ถ้าเปลี่ยนสถาปัตยกรรม/secret/ไฟล์), และ memory (`cm6-i2-training`, `morning-digest`). ฟีเจอร์ใหม่/secret ใหม่/เลิกใช้ของเก่า = ต้องสะท้อนในเอกสารเสมอ
4. **commit** (master, repo ส่วนตัว commit ตรง master ได้) + **push**
5. **deploy:** worker → `cd cf-worker && npx wrangler deploy` · digest cron รันเอง 6 โมง (ทดสอบทันที: `gh workflow run morning-digest.yml` → `gh run watch <id>`)
6. แก้ secret ผ่าน `gh secret set` / `wrangler secret put` — **ห้าม commit ค่า secret ลงไฟล์**

> ⚠️ แก้ตารางซ้อม → sync **2 ที่**: `morning_digest.py` (dict) + `cf-worker/src/index.js` (`/plan`,`/today`)
> 💸 **กฎ: ทุก call ที่เสียเงิน (Gemini เท่านั้น — Oura/Strava/Garmin/Telegram ฟรี) ต้องโชว์ราคา** — เรียกผ่าน `usageLine(env, usage)` ต่อท้ายข้อความเสมอ (โชว์ tokens + ฿ ครั้งนี้ + ยอดสะสม) และนับเข้า `/token`. ฟีเจอร์ใหม่ที่เรียก Gemini = ห้ามลืม usageLine

## Legacy / สิ่งที่เลิกใช้
- ~~`.github/workflows/log-garmin.yml`~~ — **ปลดระวางแล้ว** (cron 15 นาทีเขียน Google Sheet ที่ fail เงียบ: Garmin บล็อก CI + secrets `GCP_SA_KEY`/`SHEET_ID` ไม่เคยตั้ง)
- `log_garmin.py` — เก็บไว้เป็น tool รัน local ได้ (ถ้าอยาก log Garmin ลง Sheet เอง) แต่ไม่มี cron แล้ว
- Google Sheet "Garmin" tab — stale, digest ไม่พึ่งพา

## กฎ 5 ข้อของนักกีฬา (ใช้ตอนวิเคราะห์)
1. ขึ้น HR ≤150 (30 นาทีแรกของ session ยาว ≤140) · โซน: Z2 130-148 · Z3 149-160 · Z4 161-172 (max 186)
2. น้ำ 500-750 มล./ชม. 3. เกลือแร่ ทุก 45-60 นาที 4. กิน 250-300 kcal/ชม. (session >75 นาที)
5. นอน 7 ชม. · readiness <55 = พัก/เดินเบา
