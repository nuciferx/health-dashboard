# CLAUDE.md — Health Dashboard (CM6 i2 training)

ผู้ใช้สื่อสารภาษาไทย — ตอบไทยเสมอ

## เป้าหมายโปรเจกต์
ติดตามสุขภาพ + การซ้อมของนักวิ่งเทรลที่กำลังเตรียม **CM6 i2** (trail ultra)
- **วันแข่ง:** 8 ส.ค. 2026 · 40 กม. / +2,380 ม. / cutoff 13 ชม. · ออกตัว 05:30 (เชียงใหม่)
- **เป้า:** จบ ~12:00 · ทน 10+ ชม. โดยไม่ถล่มที่ชั่วโมงที่ 3
- นักกีฬา: อายุ 44, น้ำหนักเริ่ม ~95 กก. (เป้า 90-91 วันแข่ง)
- แผนละเอียดอยู่ใน `CM6_i2_ตารางซ้อม.md`, `CM6_i2_7week_plan.md`, `CM6_i2_แผนทุกมิติ.md`, `CM6_i2_บันทึกวิเคราะห์.md`, `CM6_i2_เมนูอาหาร.md`

## สถาปัตยกรรม (2 ส่วน)

**① Morning digest อัตโนมัติ → Telegram** (rule-based ล้วน, ไม่มี AI)
- `morning_digest.py` + `.github/workflows/morning-digest.yml`
- cron `0 23 * * *` (= 06:00 น. ไทย) ทุกวัน
- ดึง Oura → สรุปนอน/HRV/RHR/readiness + activity ล่าสุด + แผนวันนี้ → ส่ง Telegram
- ปรัชญา: ส่งข้อเท็จจริง + ธงเตือน เท่านั้น **ไม่ใส่คำแนะนำ AI รายวัน** (เคยตัดสินใจแล้วว่าเป็น noise)

**② วิเคราะห์เชิงลึก on-demand กับ Claude** (`/health` skill)
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
- **GitHub Actions** (สำหรับ digest): `OURA_TOKEN`, `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`, `STRAVA_REFRESH_TOKEN`, `GARMIN_TOKENS`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- **Local** `.env`: `OURA_TOKEN`, `GARMIN_EMAIL`, `GARMIN_PASSWORD` (+ `SHEET_ID`, `GCP_SA_KEY` legacy)
- **Cloudflare** worker `health-proxy` (`cf-worker/`): `OURA_TOKEN`, `GEMINI_KEY` — proxy ให้ dashboard เก่า `index.html`
- ตั้ง GitHub secret: `printf '%s' "<val>" | gh secret set <NAME>` (ต้อง `gh auth login` ก่อน)

## ไฟล์หลัก
- `morning_digest.py` — digest รายวัน (Oura-primary, Garmin best-effort, แผนฝังในสคริปต์)
- `health_pull.py` — ดึง Oura หลายวันเป็น JSON สำหรับวิเคราะห์เชิงลึก
- `.claude/skills/health/SKILL.md` — `/health` วิเคราะห์ on-demand
- `.claude/agents/health-analyst.md` — subagent ดึง+วิเคราะห์ข้อมูล
- `cf-worker/` — Cloudflare proxy (Oura/Gemini) ของ dashboard เก่า
- `index.html` — dashboard เก่า (PWA) — legacy ยังใช้งานได้

## "แผนวันนี้" ทำงานยังไง
แผนซ้อมฝังใน `morning_digest.py` (`W1_BY_DATE`, `WEEKS`, `W7_BY_DATE`)
- **map ด้วยชื่อวันจริงในสัปดาห์** (เสาร์=long run เสมอ) — **ห้ามเชื่อ label วันใน `CM6_i2_ตารางซ้อม.md`** เพราะมันเลื่อนผิดตั้งแต่ W2 (สัปดาห์เป็นบล็อก 7 วันเริ่มวันอังคาร)
- ถ้าแก้ตารางซ้อม → ต้องแก้ทั้ง `.md` (อ่านง่าย) **และ** dict ใน `morning_digest.py` (ตัวที่ digest ใช้จริง)

## กระบวนการพัฒนา (Dev workflow)
1. **แก้โค้ด** ในเครื่อง
2. **ทดสอบ dry-run ก่อนเสมอ:** `python morning_digest.py` (ไม่ตั้ง `TELEGRAM_*` = print แทนส่ง) — เช็คหน้าตา/ตัวเลขก่อน
3. **commit** (master, repo ส่วนตัว commit ตรง master ได้)
4. **push** → cron จะทำงานเองเช้าถัดไป · ทดสอบ cloud ทันทีด้วย `gh workflow run morning-digest.yml` แล้ว `gh run watch <id>`
5. แก้ secret ผ่าน `gh secret set` — **ห้าม commit ค่า secret ลงไฟล์**

## Legacy / สิ่งที่เลิกใช้
- ~~`.github/workflows/log-garmin.yml`~~ — **ปลดระวางแล้ว** (cron 15 นาทีเขียน Google Sheet ที่ fail เงียบ: Garmin บล็อก CI + secrets `GCP_SA_KEY`/`SHEET_ID` ไม่เคยตั้ง)
- `log_garmin.py` — เก็บไว้เป็น tool รัน local ได้ (ถ้าอยาก log Garmin ลง Sheet เอง) แต่ไม่มี cron แล้ว
- Google Sheet "Garmin" tab — stale, digest ไม่พึ่งพา

## กฎ 5 ข้อของนักกีฬา (ใช้ตอนวิเคราะห์)
1. ขึ้น HR ≤150 (30 นาทีแรกของ session ยาว ≤140) · โซน: Z2 130-148 · Z3 149-160 · Z4 161-172 (max 186)
2. น้ำ 500-750 มล./ชม. 3. เกลือแร่ ทุก 45-60 นาที 4. กิน 250-300 kcal/ชม. (session >75 นาที)
5. นอน 7 ชม. · readiness <55 = พัก/เดินเบา
