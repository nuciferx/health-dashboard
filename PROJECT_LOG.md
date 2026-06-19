# Health Dashboard — Project Log

## URL
- **Dashboard**: https://nuciferx.github.io/health-dashboard/
- **Cloudflare Worker (API proxy)**: https://health-proxy.ideaplanstudio.workers.dev
- **Garmin Google Sheet**: https://docs.google.com/spreadsheets/d/1e4nwtSKIY3mbPB_H_iX-zTwKG9R8sq7AFTCJUroDL_E/edit

---

## สิ่งที่ทำงานได้ (Deployed & Working)

### 1. Health Dashboard (GitHub Pages)
- Single-file web app (`index.html`) — Vanilla JS, no framework
- Dark theme, Thai language, mobile-first
- ข้อมูลที่แสดง:
  - **Readiness Score** (Oura) — traffic light สีตามโซน
  - **Sleep Score** (Oura) — Deep / REM / Light / Awake bars
  - **HRV** — `average_hrv` จาก daily_sleep (ms จริง)
  - **Body Battery** (Garmin)
  - **Activity**: Steps, Active Calories, min HR วันนี้, Activity Score
  - **7-Day Trend Chart** — Canvas API, Readiness + Sleep
  - **AI Coach** — Gemini 2.0 Flash วิเคราะห์และแนะนำการออกกำลังกาย
  - **COMMUTE** — บันทึกเวลาออกบ้าน/ถึงงาน/ออกงาน/ถึงบ้าน (manual)
  - **Travel level** — WFH / ปานกลาง / เยอะมาก (ส่งให้ AI)
  - **Garmin section** — Body Battery + กิจกรรมล่าสุด

### 2. Cloudflare Worker — `health-proxy`
- Route: `https://health-proxy.ideaplanstudio.workers.dev`
- Endpoints:
  - `GET /oura/*` → proxy ไป Oura API v2 (token ซ่อนใน Worker)
  - `POST /gemini` → proxy ไป Gemini 2.0 Flash (key ซ่อนใน Worker)
- Secrets ที่เก็บใน Worker (ไม่อยู่ใน code):
  - `OURA_TOKEN` — set via `npx wrangler secret put OURA_TOKEN`
  - `GEMINI_KEY` — set via `npx wrangler secret put GEMINI_KEY`

### 3. PWA (Progressive Web App)
- `manifest.json` — ชื่อ, icon, theme color
- `sw.js` — Service Worker: cache assets, network-first สำหรับ API
- สามารถ "Add to Home Screen" ได้บนมือถือ

### 4. Garmin — 3 วิธีดึงข้อมูล

#### 4a. GitHub Action → Google Sheets (แนะนำ — ทำงานอัตโนมัติ)
- **Workflow**: `.github/workflows/log-garmin.yml` — cron ทุก 15 นาที (UTC)
- **Script**: `log_garmin.py` — login Garmin → ดึงข้อมูล → เขียน Google Sheets (smart logic)
- **Smart Logic**:
  - ถ้าไม่มีข้อมูล有意义 (body_battery, steps, hrv = null ทั้งหมด) → ข้าม ไม่เขียน sheet
  - Dedup: ถ้าข้อมูลหลักเหมือนแถวสุดท้าย → ข้าม (ป้องกันเขียนซ้ำ)
  - เมื่อใส่ Garmin แล้วมีข้อมูลใหม่ → จะถูกบันทึกทันทีในรอบถัดไป (ภายใน 15 นาที)
- **ข้อมูลที่ได้**: timestamp, body_battery, steps, hrv_last_night, resting_hr, spo2, stress, activity
- **Dashboard อ่านจาก**: Google Sheets Published CSV URL (ตั้งค่าใน `config.js → GARMIN_SHEET_URL`)
- **Secrets ที่ต้องตั้งใน GitHub**:
  - `GARMIN_EMAIL` — email
  - `GARMIN_PASSWORD` — password
  - `GCP_SA_KEY` — Google Service Account JSON
  - `SHEET_ID` — Google Sheets ID

#### 4b. Local Flask Server (`garmin_server.py`)
- Flask server รัน `http://localhost:5001/garmin`
- ดึง: body_battery, steps, HRV last night, last_activity
- Cache 5 นาที
- รัน: `py -3 garmin_server.py`
- Credentials: เก็บใน `.env`

#### 4c. Manual Paste
- CLI: `py -3 garmin_export.py <email> <password>`
- Copy JSON output → paste ลงช่อง "Paste Garmin JSON" ใน dashboard

### 5. Location Parser (`location_parse.py`)
- รัน: `py -3 location_parse.py`
- Input: `data/semantic/*.json` (จาก Google Takeout)
- Output: `data/commute.json` — วันที่, ออกบ้าน, ถึงงาน, ออกงาน, ถึงบ้าน, commute_min

---

## วิธีตั้งค่า Google Sheets สำหรับ Garmin

ใช้ Sheet ใหม่แยกจาก air-quality (`1e4nwtSKIY3mbPB_H_iX-zTwKG9R8sq7AFTCJUroDL_E`) — script จะสร้าง tab "Garmin" ให้อัตโนมัติ

1. เปิด Google Sheet: https://docs.google.com/spreadsheets/d/1e4nwtSKIY3mbPB_H_iX-zTwKG9R8sq7AFTCJUroDL_E/edit
2. ตรวจสอบว่า service account `nucifer-sheets-bot@nucifer-data-sheet-api.iam.gserviceaccount.com` มีสิทธิ์ Editor
3. **Publish to web**: File → Share → Publish to web → เลือก tab "Garmin" → Comma-separated values (.csv) → Publish
4. ตั้งค่า GitHub Secrets (Settings → Secrets and variables → Actions):
   - `GARMIN_EMAIL` = Garmin account email
   - `GARMIN_PASSWORD` = Garmin account password
   - `GCP_SA_KEY` = JSON content ของ service account (ทั้งก้อน)
   - `SHEET_ID` = `1e4nwtSKIY3mbPB_H_iX-zTwKG9R8sq7AFTCJUroDL_E`
5. ทดสอบ: Actions → Log Garmin → Run workflow — tab "Garmin" จะถูกสร้างอัตโนมัติ

**Dashboard CSV URL** (ตั้งค่าใน `config.js` แล้ว):
```
https://docs.google.com/spreadsheets/d/1e4nwtSKIY3mbPB_H_iX-zTwKG9R8sq7AFTCJUroDL_E/gviz/tq?sheet=Garmin&tqx=out:csv
```

---

## สิ่งที่ยังไม่ได้ทำ / Limitations

| รายการ | เหตุผล |
|--------|--------|
| Auto location tracking รายวัน | Data Portability API ต้อง Google Verification (หลายสัปดาห์) |
| Commute auto-fill จาก GPS | ยังไม่มีระบบ — manual entry ใน dashboard |
| GitHub Actions manual run จากเครื่องนี้ | `gh` CLI ยังไม่ได้ login จึงยังสั่ง `workflow_dispatch` จาก local ไม่ได้ |

---

## Update: 2026-04-30 — Garmin GitHub Action Fix

### สถานะล่าสุด
- Push ขึ้น GitHub แล้วที่ commit `c2372ef` (`fix: validate garmin sheet secrets before sync`)
- Local run สำเร็จ: `python log_garmin.py`
- Script สร้าง worksheet `Garmin` ใน Google Sheet แล้ว
- เขียนข้อมูล Garmin ลง sheet ได้จริง 1 row
- Google Sheet มี tab `Garmin` และ header ครบ:
  - `timestamp`
  - `body_battery`
  - `steps`
  - `hrv_last_night`
  - `resting_hr`
  - `spo2`
  - `stress_high_min`
  - `recovery_high_min`
  - `activity_type`
  - `activity_distance_km`
  - `activity_duration_min`
  - `activity_avg_hr`

### สิ่งที่แก้ในโค้ด
- `.github/workflows/log-garmin.yml`
  - เพิ่ม step `Check required secrets`
  - ถ้า GitHub Actions secret ขาด จะ error ชัดเจนก่อนติดตั้ง dependency/รัน Python
- `log_garmin.py`
  - ตรวจ `GARMIN_EMAIL`, `GARMIN_PASSWORD`, `GCP_SA_KEY`, `SHEET_ID` ก่อน sync
  - เปิด Google Sheet ก่อน login Garmin เพื่อเลี่ยงการยิง Garmin login ซ้ำเมื่อ Google config ยังไม่พร้อม
  - เพิ่ม `::error::...` เพื่อให้ GitHub Actions แสดง error อ่านง่าย
- `.gitignore`
  - ignore `.venv*/`
  - ignore `setup-secrets.bat` เพราะมีข้อมูลส่วนตัว

### Local `.env`
- `.env` ถูก gitignore และไม่ควร commit
- มี key ครบสำหรับ local run:
  - `GARMIN_EMAIL`
  - `GARMIN_PASSWORD`
  - `OURA_TOKEN`
  - `SHEET_ID`
  - `GCP_SA_KEY`

### Service Account
- Project: `nucifer-data-sheet-api`
- Service account: `nucifer-sheets-bot@nucifer-data-sheet-api.iam.gserviceaccount.com`
- Local key source ที่ตรวจพบ:
  - `G:\drive\01 project\ai\air-quality\nucifer-data-sheet-api-cbfb9be2a194.json`
- ทดสอบแล้วว่า service account เปิด sheet ได้

### GitHub Secrets ที่ต้องตั้ง
ตั้งใน GitHub repo: Settings → Secrets and variables → Actions

```text
GARMIN_EMAIL
GARMIN_PASSWORD
GCP_SA_KEY
SHEET_ID
```

ค่าของ `SHEET_ID`:

```text
1e4nwtSKIY3mbPB_H_iX-zTwKG9R8sq7AFTCJUroDL_E
```

หลังตั้ง secrets แล้วให้ทดสอบ:
1. ไปที่ GitHub → Actions
2. เลือก workflow `Log Garmin`
3. กด `Run workflow`
4. ถ้าผ่าน จะเห็น job เขียนข้อมูลลง tab `Garmin`

---

## Update: 2026-06-19 — ระบบติดตามสุขภาพอัตโนมัติ + Telegram bot (ยกเครื่องใหญ่)

ยกเครื่องจาก dashboard เก่า → **ระบบ 3 ชั้น** สำหรับเป้า CM6 i2 (8 ส.ค. 2026):

```
อัตโนมัติ 06:00  → Oura + Garmin(token) + Strava → Telegram   (rule-based)
สั่งสดใน Telegram → /today /readiness /plan /token + รูปอาหาร   (Cloudflare Worker)
วิเคราะห์ลึก      → /health + Claude (Oura+Strava+Garmin local + AI)
```

### 1. Morning Digest อัตโนมัติ → Telegram
- **`morning_digest.py`** + **`.github/workflows/morning-digest.yml`** (cron `0 23 * * *` = 06:00 ICT)
- rule-based ล้วน (ไม่มี AI รายวัน — สรุปแล้วว่าเป็น noise)
- เนื้อหา: นอน/HRV/RHR/Readiness/**Stress/Resilience** (Oura) · **Body Battery** (Garmin) · activity+HR zone+**vertical speed** (Strava) · แผนวันนี้ · ธงเตือน · **🔎 auto จุดอ่อน** (2 contributors ต่ำสุด เช่น REM, recovery index)

### 2. Telegram Command Bot — `cf-worker/src/index.js`
- webhook `POST /telegram` (owner-only chat_id 957180305 + `TELEGRAM_WEBHOOK_SECRET`)
- **`/today`** (Oura+Strava สด) · **`/readiness`** · **`/plan`** · **`/token`** · **`/help`**
- **📸 ส่งรูปอาหาร** → Gemini 3 Flash Vision → kcal/มาโคร/คำแนะนำ (**โหมดทดสอบ — ยังไม่บันทึก meal data**)
- per-photo **token + ค่าใช้จ่าย (฿)** · `/token` สรุปรวม+รายรูป (เก็บ stats ใน **KV namespace STATS**)

### 3. แหล่งข้อมูล — แก้ปัญหา Garmin บล็อก cloud
- **Oura** = แหล่งฟื้นตัวหลัก (cloud เสถียร) — ใช้ depth เต็ม: daily_stress, daily_resilience, contributors
- **Strava API** = แหล่ง activity (Garmin sync → Strava → อ่าน) — `STRAVA_CLIENT_ID/SECRET/REFRESH_TOKEN`, ทำงานบน cloud ได้
- **Garmin token trick** ⭐ = login email/password โดนบล็อกจาก datacenter (429/403) **แต่** login ด้วย token (`client.dumps()` ดึง local) **ผ่าน** ทั้ง local+cloud → stress/body battery/RHR เข้า digest ได้ · secret `GARMIN_TOKENS` · token oauth1 หมดอายุ ~1 ปี

### 4. Infra ใหม่
- **`CLAUDE.md`** — สถาปัตยกรรม, แหล่งข้อมูล+ความเสถียร, secrets, dev workflow, legacy
- **`.claude/skills/health/SKILL.md`** — `/health` วิเคราะห์ลึก on-demand
- **`.claude/agents/health-analyst.md`** — subagent ดึง+วิเคราะห์ (Oura+Strava+Garmin)
- **`health_pull.py`** — ดึง Oura หลายวันเป็น JSON (รวม stress/resilience/contributors) สำหรับ `/health`
- **Cloudflare KV** `STATS` (id `98f0afee46464354b075755e090a8616`) — token/cost stats (+ อนาคต: meal log)

### 5. ปลดระวาง legacy
- ❌ ลบ `.github/workflows/log-garmin.yml` — cron 15 นาทีที่ fail เงียบ (Garmin บล็อก CI + secrets `GCP_SA_KEY`/`SHEET_ID` ไม่เคยตั้ง)
- `log_garmin.py` เก็บไว้เป็น tool รัน local · Google Sheet stale ไม่พึ่งพา
- gitignore `desktop.ini` + `cf-worker/.wrangler/`

### Secrets ที่เพิ่ม/เปลี่ยน
- **GitHub Actions**: `OURA_TOKEN`, `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`, `STRAVA_REFRESH_TOKEN`, `GARMIN_TOKENS`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- **Cloudflare Worker**: + `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, `STRAVA_CLIENT_ID/SECRET/REFRESH_TOKEN` (เดิมมี `OURA_TOKEN`, `GEMINI_KEY`)

### ข้อควรดูแล (Maintenance)
- **แก้ตารางซ้อม → sync 2 ที่**: `morning_digest.py` (dict แผน) + `cf-worker/src/index.js` (`/plan`) — แผน map ด้วยวันจริง (label ใน .md เลื่อนตั้งแต่ W2)
- `GARMIN_TOKENS` หมด ~1 ปี → re-dump local: `Garmin(email,pw).login()` → `client.dumps()` → `gh secret set GARMIN_TOKENS`
- เรต Gemini/อัตราแลก: constant ใน worker (`GEM_IN_USD=0.50`, `GEM_OUT_USD=3.00`, `USD_THB=35`)
- รูปอาหารยัง **test mode** — เปิดบันทึกจริง (KV) เมื่อพอใจผล

---

## วิธี Deploy อัพเดต

```bash
# แก้ไฟล์ใดก็ได้ แล้ว:
cd G:/drive/01 project/ai/health-dashboard
git add <ไฟล์>
git commit -m "..."
git push
# GitHub Pages อัพเดตใน ~30 วิ
```

## อัพเดต Cloudflare Worker

```bash
cd G:/drive/01 project/ai/health-dashboard/cf-worker
npx wrangler deploy
# อัพเดต secret:
echo "NEW_VALUE" | npx wrangler secret put SECRET_NAME
```

---

## Files

```
health-dashboard/
├── CLAUDE.md            # ⭐ คู่มือโปรเจกต์ (สถาปัตยกรรม/secrets/dev workflow)
├── morning_digest.py    # ⭐ digest 6 โมง → Telegram (Oura+Garmin token+Strava)
├── health_pull.py       # ดึง Oura หลายวัน (JSON) สำหรับ /health
├── index.html           # Dashboard เก่า (all-in-one, legacy)
├── manifest.json        # PWA manifest
├── sw.js                # Service Worker
├── icon-192/512.png     # PWA icons
├── config.js            # Local config (gitignored)
├── log_garmin.py        # Legacy tool รัน local (cron ปลดระวางแล้ว)
├── requirements.txt     # Python deps (requests, garminconnect, ...)
├── garmin_server.py / garmin_export.py / location_*.py  # legacy/manual tools
├── CM6_i2_*.md          # แผนซ้อม/อาหาร/วิเคราะห์ CM6 i2
├── .env                 # credentials (gitignored)
├── .claude/
│   ├── skills/health/SKILL.md      # /health วิเคราะห์ลึก on-demand
│   └── agents/health-analyst.md    # subagent ดึง+วิเคราะห์ข้อมูล
├── .github/workflows/
│   └── morning-digest.yml          # ⭐ cron 06:00 ICT → Telegram (log-garmin.yml ลบแล้ว)
└── cf-worker/
    ├── src/index.js     # Worker: proxy + Telegram bot + meal photo + /token
    └── wrangler.toml    # Worker config + KV binding STATS
```

---

## Last updated: 2026-06-19 — Telegram digest+bot, Strava/Garmin-token cloud data, Oura depth, meal-photo (test) + /token
