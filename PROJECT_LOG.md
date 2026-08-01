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

## Update: 2026-06-20 — ระบบบันทึกอาหารจากใบเสร็จ + token tracking (Telegram)

ต่อยอด Telegram bot ให้รับรูป + จัดการมื้ออาหารแบบกลุ่ม (ทั้งหมดอยู่ใน `cf-worker/src/index.js`)

### 1. อ่านใบเสร็จ (แทนการเดารูปอาหาร)
- ส่งรูป**ใบเสร็จ** → Gemini 3 Flash Vision → `{shop, datetime, people, items[name/qty/price/kcal], total_price, total_kcal}`
- **ข้อมูลล้วน ไม่มีคำแนะนำ/ความเห็น** (ผู้ใช้ขอ) · kcal ประเมินจากชื่อรายการ
- เปลี่ยนจาก "ถ่ายรูปอาหาร" เพราะ Gemini เดาผิด (เคยมั่วกาแฟดำเป็น "อเมริกาโน่ท็อปครีม 12g ไขมัน")

### 2. มื้อกลุ่ม — หารคน
- `people` อ่านอัตโนมัติจากใบ (เช่น `TABLE 5 (5)`) · ไม่มีก็ตั้งเองได้
- แสดง **ส่วนของคุณ** = ยอด ÷ คน (฿/คน + kcal/คน)

### 3. แก้ไขใบเสร็จ 2 ทาง (OCR ผิดได้)
- **ตาราง Mini App** (`/edit`): ปุ่ม "✏️ แก้ไขเป็นตาราง" → หน้าเว็บในแอป Telegram แตะแก้ในช่อง/เพิ่ม-ลบแถว/ตั้งจำนวนคน/ยอดหารสด → บันทึกผ่าน `POST /api/receipt` (ตรวจ `initData` HMAC-SHA256 + owner)
- **ภาษาพูด**: พิมพ์ "หาร 5 คน" / "ลบโค้ก" / "กะเพรา 60" → `editReceipt` (Gemini) แก้ JSON
- draft เก็บใน **KV `draft:<chatid>`** (TTL 6 ชม.)

### 4. Token + ค่าใช้จ่าย
- แต่ละครั้งที่เรียก Gemini → ต่อท้าย `🪙 N tokens · ฿X` · **`/token`** = สรุปรวม/เฉลี่ย/รายครั้ง
- เรต: Gemini 3 Flash **$0.50/1M in · $3.00/1M out · ฿35/$** (constant ปรับได้) · stats สะสมใน KV `STATS`

### Cloudflare ที่เพิ่ม
- Worker secrets: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, `STRAVA_CLIENT_ID/SECRET/REFRESH_TOKEN`
- KV namespace `STATS` (id `98f0afee46464354b075755e090a8616`) — token stats + receipt drafts
- Routes ใหม่: `POST /telegram` (webhook), `GET /edit` (Mini App), `POST /api/receipt`

### ⚠️ ยังเป็นโหมดทดสอบ
- meal data **ยังไม่บันทึกถาวร** (draft 6 ชม.) — เปิดเก็บจริงเมื่อพอใจ → สรุป ฿/วัน + แคล/วัน เข้า digest/`/health`

---

## Update: 2026-06-20 (b) — แก้ปัญหา Oura ยังไม่ sync ตอน 6 โมง

**ปัญหา:** แหวน Oura sync เข้าคลาวด์หลังผู้ใช้ตื่น/เปิดมือถือ ไม่ใช่ 6 โมงเป๊ะ → cron เดิม (ยิงครั้งเดียว 06:00) เจอข้อมูลว่าง

**แก้:** poll-and-send-once
- cron เปลี่ยนเป็นหลายรอบ **06:00–09:30 ICT ทุก 30 นาที** (`0,30 23 * * *` + `0,30 0-2 * * *`)
- `morning_digest.py`: ถ้า Oura วันนี้ยังไม่มี (`readiness` & `sleep_h` = None) → ข้าม ไม่ส่ง · รอบแรกที่ข้อมูลพร้อม → `claim_send()` ขอสิทธิ์ผ่าน worker `POST /digest-claim` (KV `digest_sent:<date>`, TTL 2 วัน) → ส่งครั้งเดียว
- `workflow_dispatch` (กดมือ) = force ส่งทันที ข้าม gate
- secret ใหม่: `DIGEST_SECRET` (GitHub + Cloudflare) · ทดสอบแล้ว: claim 1st `go:true`, 2nd `go:false`, ปลอม 403

---

## Update: 2026-06-20 (c) — Adherence v1: วินัยโซน + จับช่วงหาย (อิงพฤติกรรมจริง)

**ที่มา:** deep-research (`CM6_i2_adherence_research.md`) + วิเคราะห์ Strava 1 ปี (~71 กิจกรรม) พบพฤติกรรมจริง 4 ข้อ: (1) หายเป็นช่วง 1-2 สัปดาห์, (2) ทำของง่าย (วิ่งสั้นราบ) ข้ามของจำเป็น (long vertical/interval), (3) **"easy day ไม่ easy"** — วิ่งสั้นซัด Z3-Z4 (1 มี.ค. วิ่ง 10 กม. avg HR 170!), (4) หลังอีเวนต์ = detrain. สรุป: ไม่ได้ขี้เกียจ แต่ทำผิด session + ผิดโซน + หายเป็นช่วง.

**สร้าง (②③ อัตโนมัติ ใน `morning_digest.py`):**
- `fetch_strava_week()` + `training_review()` → สรุป 7 วันใน digest:
  - **วินัยโซน** "คุมโซน ≤150: X/Y ครั้ง" (จับ gray-zone)
  - **ไต่รวม** 7 วัน (จับว่าทำงาน vertical พอไหม)
  - **③ จับช่วงหาย** "ไม่ได้ขยับมา N วัน" (N≥3 → ธงเตือน)
- คำนวณสด จาก Strava ไม่ต้อง persistence · ทำงานอัตโนมัติแม้ผู้ใช้เงียบ
- ฟัน = คะแนน+ธงเตือน เท่านั้น (ผู้ใช้ปฏิเสธเดิมพันเงิน/social)
- **ยังไม่ทำ:** streak (ต้อง KV), check-back ✅/❌ รายวัน (④), session-specific accountability (①⑤)

---

## Update: 2026-06-20 (d) — ระบบส่งการบ้าน + คอมเมนต์โค้ช (check-back ④)

ตัวที่เปลี่ยนบอทจาก one-way → two-way (หลักฐานแข็งสุดในงานวิจัย adherence) — ใน `cf-worker/src/index.js`:
- **`/done <ทำอะไรไป>`** → ส่งการบ้านวันนี้ → Gemini 3 Flash คอมเมนต์แบบโค้ช (เทียบ `planFor(today)`, ชม/เตือนโซน/problem-solving ถ้าพลาด, สั้น 1-2 บรรทัด) → เก็บ KV `hw:<date>` (60 วัน)
- **`/homework`** → สรุป 7 วัน "ส่งแล้ว X/7"
- **cron 20:00 ICT** (`scheduled()` handler + `[triggers] crons=["0 13 * * *"]`) → เย็นเตือน "ส่งการบ้านวันนี้: [แผน] · /done ..."
- token ของ comment นับใน /token เหมือนกัน
- หลักการ: คะแนน+คอมเมนต์ (ไม่มีเดิมพันเงิน/social ตามที่ผู้ใช้เลือก)

---

## Update: 2026-06-20 (e) — ล็อกแผนใหม่ (realistic, post-injury) + /week + Telegram menu

- **แผนรายสัปดาห์ใหม่** (3 keystone/wk, ไต่ค่อยๆ, easy ≤145, เป้าจบไม่เจ็บ) — rewrite `WEEKS` dict ทั้งใน `morning_digest.py` + `cf-worker` ให้ตรงกัน + section ใหม่ใน `CM6_i2_ตารางซ้อม.md` · OVERRIDE 20-24 มิ.ย. = พักเอ็น
- **`/week`** — แผน 7 วันข้างหน้า (เว้นบรรทัดอ่านง่าย) ใน Telegram
- **Telegram command menu** — `setMyCommands` (today/plan/week/done/homework/readiness/token/help) → กดปุ่ม ☰ เลือกได้ · `setChatMenuButton` = commands
- ส่งแผน (7 วัน + ภาพรวม 7 สัปดาห์) เข้า Telegram ผ่าน bot sendMessage โดยตรง

---

## Update: 2026-06-22 — GTM kaizen: KV อ่าน local แทน remote (defect = environment mismatch)

**เหตุการณ์ (Understanding Condition):** ผู้ใช้ถามว่า `/done` 21-22 มิ.ย. มีบันทึกไหม. ผมรัน `wrangler kv key get/list` **ไม่ใส่ `--remote`** → เห็นแค่ record ทดสอบใน local store (`hw:2026-06-20`) → ฟันธงผิดว่า "21-22 ไม่มี" + เดาว่าเป็นบั๊ก Gemini. ผู้ใช้ทักว่า `/homework` ในเทเลแกรมขึ้นว่ามี → ใส่ `--remote` แล้วเจอจริง (`hw:2026-06-21` = "หายเจ็บขาแล้ว", `hw:2026-06-22` = "อาการเจ็บดีขึ้น").

**Defect Factors Analysis (root cause):**
1. **environment mismatch** — `wrangler kv` ดีฟอลต์อ่าน local miniflare ไม่ใช่โปรดักชันที่บอตใช้จริง
2. **judgment defect** — ขัดหลักฐานที่ผู้ใช้เห็นในแอปจริง โดยไปสงสัยผู้ใช้/เดาบั๊ก แทนที่จะสงสัย read-path ของตัวเองก่อน

**Eliminating + Setting Condition (countermeasure ที่ lock ไว้):**
- **🛡️ hook บังคับ (poka-yoke):** `.claude/settings.json` (PreToolUse/Bash) → `.claude/hooks/check-wrangler-kv-remote.py` **block ทุก `wrangler kv` ที่ไม่มี `--remote`/`--local`/`--preview`** — กันพลาดระดับ tool-call ทุกครั้ง ไม่พึ่งความจำ
- `CLAUDE.md` (dev-workflow callout 🔍 + 🛡️): ตรวจ KV จริงต้องใส่ `--remote` + ถ้าขัดกับสิ่งที่ผู้ใช้เห็นในเทเลแกรม ให้สงสัย read-path เราก่อน
- memory `kv-remote-flag-gotcha` (feedback): กฎเชิงพฤติกรรมเดียวกัน
- worker source (`cf-worker/src/index.js`) **ไม่เปลี่ยน** — เพิ่มเฉพาะ hook/docs

**Verification:** `npx wrangler kv key list --remote` คืน 5 keys รวม `hw:2026-06-21/22` จริง · local list คืนแค่ `hw:2026-06-20` → ยืนยัน root cause = local/remote split · **hook ทดสอบสด:** ไม่มี flag → โดน deny, มี `--remote` → ผ่าน (4 pipe-test เคสผ่าน)

**Known gaps / Next action:** record local `hw:2026-06-20` เป็น test artifact (ไม่มีในรีโมต) ปล่อยไว้ได้ · hook ใช้ Python (เครื่องนี้ไม่มี jq) · ถ้าจะกัน Gemini-พัง-แล้วเงียบใน `/done` (เซฟ raw ก่อนเรียก Gemini) = sprint แยก ยังไม่ทำรอบนี้ → คิวเป็น `B1` ใน `BACKLOG.md`

---

## Update: 2026-06-22 (b) — รับ GTM dev loop จาก BMA-Plan (ปรับให้เข้าโปรเจกต์)

นำ **GTM Infinite Loop** + **autonomous dev-loop** ของ BMA-Plan มาปรับใช้ (ผู้ใช้เลือก "ทั้งสอง" + full-auto commit):
- **`CLAUDE.md` → section "Dev Operating Loop — GTM Infinite Loop"** — 8 หลักการ (Understand→Restore→Defect→Eliminate→SetCondition→Kaizen→Manage→Gate) เป็นวินัยต่อทุกงาน
- **`BACKLOG.md` (ใหม่)** — roadmap แหล่งความจริงเดียว · seed B1-B5 (`/done` save-raw, streak, check-back ✅/❌, session-accountability, meal persist) + Discovered + Done
- **`.claude/skills/health-dev-loop/SKILL.md` (ใหม่)** — 1 รอบ 1 item จาก BACKLOG · PLAN→SCOPE→BUILD→TEST→LEARN→SHIP→LOOP · รัน `/loop /health-dev-loop`
- **gate ปรับเป็นของจริง:** `python morning_digest.py` (dry-run) + `node --check cf-worker/src/index.js` + sync 2 ที่ (dict↔worker)
- **autonomy:** full-auto commit master · **ห้าม auto-push/deploy/secret** (outward-facing → handoff/STOP) · stop conditions: SECRET/DESIGN/GATE/TEST/DONE
- เป็น docs/process + skill เท่านั้น — worker/digest source ไม่เปลี่ยน

---

## Update: 2026-06-22 (c) — [/health-dev-loop รอบ 1] B6: flag deep/REM สั้น + หาเหตุ ใน digest

งานแรกที่ทำผ่าน autonomous loop (จาก /idea 2026-06-22):
- `morning_digest.py` `fetch_oura`: ดึง `deep_sleep_duration`/`rem_sleep_duration` → `deep_h`/`rem_h`
- `build_message`: บรรทัด `🛌 deep Xh · REM Yh` (🔴 ถ้า deep<0.9h หรือ REM<1.0h) + ธงเตือน "deep/REM สั้น (อาจจาก เครียดเมื่อคืน/readiness ต่ำ)" — rule-based, ไม่มี AI/Gemini, เข้าปรัชญา digest (fact+flag)
- **TEST:** py_compile OK · dry-run แสดง `🛌 deep 0.5h 🔴 · REM 0.7h 🔴` + ธง (วันนี้ไม่เครียด→ไม่ใส่เหตุ ซื่อตรง) · ไม่แตะ worker
- **SCOPE decisions:** digest (ไม่ใช่ /health) เพราะเป็น fact+flag · v1 = stress+readiness เป็นเหตุ (มีข้อมูลจริง)
- **Discovered → BACKLOG:** D1 worker /today parity · D2 ตัวแปรเหตุเพิ่ม (alcohol/late-eat/HRV-dip) · D3 คาลิเบรตเกณฑ์ตาม baseline
- **handoff:** ฟีเจอร์อยู่ใน digest cron 6 โมงอัตโนมัติ ไม่ต้อง deploy · จะเห็นผลจริงรอบ digest พรุ่งนี้

---

## Update: 2026-07-25 — ปรับแผน 14 วันสุดท้าย (จากวิเคราะห์ /health)

**ข้อมูลที่พบ (Oura 14 วัน + Strava 12-25 ก.ค.):** RACE SIM 18 ก.ค. ทำจริง 9.2 กม./+549 ม. (แผน 30/+2,000 — Go/No-Go ไม่เคยทดสอบ) · ปริมาณ ~19 กม. ≈ 25-30% ของแผน · ขึ้นเขา avgHR 167-175 เกินกฎ ≤150 · อัตราไต่ ~400 ม./ชม. @HR~170 · นอนเฉลี่ย 4.9 ชม. · resilience "limited" ตั้งแต่ 18 ก.ค. · จุดบวก: วิ่งราบ 23 ก.ค. avgHR 147 คุมโซนได้ · วันนี้ readiness 68 / HRV 33 / RHR 63 ดีสุดในรอบ 2 สัปดาห์

**ปรับแผน (sync 3 ที่: `CM6_i2_ตารางซ้อม.md` + `morning_digest.py` + `cf-worker/src/index.js`):**
- OVERRIDE 25-26 ก.ค. = 🎯 MINI RACE SIM 15-18 กม./+800-1,000 (เดินขึ้น ≤150 เข้ม + ระบบกิน/น้ำ/เป้เต็ม แทน sim ที่พลาด) + วันฟื้น
- W7 เทเปอร์: เพิ่มโฟกัสนอน ≥7 ชม./คืน (เลเวอร์หลัก — จาก 4.9) · 1 ส.ค. = dress rehearsal เต็มรูปแบบ · HR cap กำกับทุกวัน
- เป้าวันแข่งรีเซ็ต: จบก่อน cutoff ไม่เจ็บ (~12:30-13:00) · pacing table ใหม่ (สะสม 3:15/6:30/9:45/12:45)

**Test:** `python morning_digest.py` dry-run PASS (โชว์ MINI RACE SIM ถูกวัน) · `node --check cf-worker/src/index.js` PASS
**Gap:** ยังไม่ push / ยังไม่ deploy worker (รออนุมัติ) — digest cron บน GitHub + `/plan` บน worker จะยังเห็นแผนเก่าจนกว่าจะ push+deploy · memory `cm6-i2-training` สร้างใหม่แล้ว (ของเดิมหาย)

## Update: 2026-07-27 — MINI SIM พลาด → ใส่ time-on-feet 4-5 ชม. (1 ส.ค.) + deploy worker สำเร็จ

**สิ่งที่พบ:** MINI RACE SIM 25-26 ก.ค. ไม่เกิด — สุดสัปดาห์เป็นวิ่งราบล้วน (26 ก.ค. 4 กม., 27 ก.ค. 8.5 กม. avg HR 143 คุมโซนดี) · ช่องว่างที่เหลือ = การไต่ + time-on-feet ล้วน
**ผู้ใช้ขอ:** time-on-feet 4-5 ชม.
**ปรับ (sync 3 ไฟล์):** เปลี่ยน 1 ส.ค. (เสาร์, 7 วันก่อนแข่ง) จาก dress rehearsal เบา +400 → **🥾 Time-on-feet 4-5 ชม. (long session ตัวสุดท้าย + dress rehearsal รวมกัน)** เดินเป็นหลัก vertical +500-800 พอ (กันเอ็น) ระบบเต็มเหมือนวันแข่ง avg ≤145 · taper 2-7 ส.ค. เน้นฟื้นจาก long session (โดยเฉพาะ 2-3 ส.ค.) · แก้ day label 1 ส.ค. = เสาร์ (เดิมเขียน ศ ผิด)
**Test:** plan_for(1 ส.ค.)/plan_for(2 ส.ค.) ถูกต้อง · node --check PASS
**Deploy:** wrangler login (ผ่านหลัง timeout 3 ครั้ง — callback localhost:8976 ต้องรันในเทอร์มินัลผู้ใช้/นอก sandbox) → **`wrangler deploy` สำเร็จ version 388b711a** (บอท /plan /today /week ใช้แผนใหม่แล้ว) · account ideaplanstudio@gmail.com
**Open decision:** ผู้ใช้เลือกวันได้ — ถ้าอยากได้ recovery buffer มากขึ้นย้าย 4-5 ชม. ไป 30 ก.ค. (พฤ, 9 วันก่อนแข่ง) แทน 1 ส.ค. (7 วัน)

## Update: 2026-08-01 — ดึงเส้นทาง CM6 i2 ของจริง (GPX + CP) → พบสเปกสนาม/pacing ผิด

**คำถามผู้ใช้:** "10 โลแรกใน CM6 มีแผนที่หรือไม่ จากข้อมูลในโฟลเดอร์นี้" → **ไม่มี** โปรเจกต์ไม่เคยมีข้อมูลเส้นทางเลย มีแค่ตาราง pacing แบ่งช่วง 10 กม. (`CM6_i2_7week_plan.md` บันทึกไว้เองว่าเคยเปิดหน้า i2 แล้วอ่านไม่ได้เพราะเป็นรูป)

**ดึงมาใหม่จาก https://cm6.run/divi/en/i2-en/** → `course/CM6_i2_2026.gpx` (Garmin Connect, 3,423 trkpt) + `course/CM6_elevation.jpg` + `course/CM6_map.jpg` · สรุปไว้ที่ **`CM6_i2_เส้นทาง.md`** (ไฟล์ใหม่)

**🚨 พบ 3 เรื่องที่เอกสารเดิมผิด:**
1. **ระยะ/ไต่ผิด** — เอกสารทุกใบเขียน 40 กม./+2,380 ม. · ของจริง **42.9 กม./+2,483 ม.** (วัดจาก GPX ได้ 42.84 กม./+2,355 ม.) → ระยะขาดไป ~3 กม.
2. **ตาราง pacing ชนเวลาตัด** — แผน 25 ก.ค. ตั้งเป้า กม.20 ที่ 6:30 ซึ่ง **เท่ากับเวลาตัด CP A1 (กม.20.3 @ 12:00 = 6:30) พอดี = กันชน 0 นาที** → ต้องขยับเป็นถึง A1 ก่อน 6:00
3. **ไม่เคยรู้ตำแหน่ง CP** — ของจริง: HQ กม.10.0 ตัด 09:00 (3:30) · A1 กม.20.3 ตัด 12:00 (6:30) · HQ กม.31.1 ตัด 16:05 (10:35) · FINISH กม.42.9 ตัด 18:30 (13:00)

**โครงสนาม (จาก GPX):** ขึ้น 2 ลูกใหญ่สลับลงยาว · กม.1-10 **+1,064** / กม.11-20 −1,173 / กม.21-30 +1,040 / กม.31-43 −1,076 · ระดับ 324–1,370 ม.
**10 กม.แรก = 45% ของการไต่ทั้งสนาม** · 3 กม.แรกราบ (กับดัก) แล้ว กม.5-7 ชัน **19-22% ติดกัน 3 กม.** · CP1 อยู่บนยอดพอดี
**อัตราไต่ที่ต้องทำ:** ลูกแรก ~360-400 ม./ชม. · ลูกสอง ~320 ม./ชม. ตอนล้า — เทียบของจริง 29 ก.ค. ไต่ได้ ~400 ม./ชม. ตอนสด ตกเหลือ ~250 ตอนล้า → **ช่องว่างอยู่ครึ่งหลัง**

**ยังไม่ได้ทำ (next action):** sync ตัวเลข 42.9 กม./+2,483 ม. + ตาราง pacing ใหม่กลับเข้า `CM6_i2_ตารางซ้อม.md`, `CM6_i2_7week_plan.md`, `CM6_i2_แผนทุกมิติ.md`, `CLAUDE.md` และ `morning_digest.py`/`cf-worker` (ถ้ามีอ้างระยะ) · ยังไม่ push

## Update: 2026-08-01 (b) — ขุดสถิติ CM6 2024 ที่ DNF จาก Garmin

**ผู้ใช้ขอ:** ดูสถิติเดิมใน Garmin — CM2 ปี 2024 ที่เคย DNF
**เจอ:** Garmin activity `16663941948` ชื่อ **"CM6 # CM2. DNF"** · 3 ส.ค. 2024 ออก 05:00 · **33.07 กม./+2,287 ม./elapsed 11:30/avg HR 152/max 179** (Strava id 12051944813)
**วิธีดึง:** Garmin login email+password จาก local ผ่าน (ตามที่ CLAUDE.md ระบุ) · `get_activities_by_date` · ⚠️ ต้องตั้ง `PYTHONIOENCODING=utf-8` ไม่งั้นชื่อกิจกรรมภาษาไทย crash (cp1252)

**สาเหตุ DNF (จาก HR รายกิโล):** ลูกแรก กม.2-10 (+1,039 ม.) ลากที่ **HR 163-168 ทุกกิโล** → ถึง กม.10 ที่ 3:26 → กม.28-33 HR ร่วง 130→124→120 ทั้งที่ยังเดิน (หมดไกลโคเจน) → หยุดที่ 33 กม.
**บทเรียนใหญ่:** HR 166-168 ปี 2024 ไต่ได้แค่ ~330 ม./ชม. · HR 144-156 วันที่ 29 ก.ค. 2026 ไต่ได้ ~400 ม./ชม. → **ตอนนี้ฟิตกว่า 2024 และกฎ ≤150 ไม่ได้แลกความเร็ว**

**ประวัติสนามยาว:** CM6 2024 (+2,287, HR 152) ❌DNF · แม่สลอง พ.ย.2024 (36.9/+1,917, HR 147) ✅ · แม่ฟ้าหลวง 22 พ.ย.2025 (42.1/+2,056, elapsed 13:18, HR 150) ✅ → **จบทุกครั้งที่ avg HR ≤150**
**⚠️ ข้อมูลขัดกัน:** เอกสารจด แม่ฟ้าหลวง "12:25" แต่นาฬิกาจับ 13:18 — ต้องเช็กว่าอันไหนคือเวลาทางการ
**⚠️ ของจริง:** CM6 i2 +2,483 ม. = ไต่มากกว่าจุดที่ DNF ปี 2024 ~200 ม. และมากกว่าทุกสนามที่เคยจบ · cutoff 13:00 สั้นกว่าเวลาแม่ฟ้าหลวง

**บันทึกไว้ที่:** `CM6_i2_บันทึกวิเคราะห์.md` section "🔴 Post-mortem CM6 2024 (DNF)"

## Update: 2026-08-01 (c) — การ์ดวันแข่ง (ตอบ "ทำไงให้ HR <150")

**ผู้ใช้ถาม:** ทำยังไงให้ HR ต่ำกว่า 150 → สร้าง **`CM6_i2_การ์ดวันแข่ง.md`** (ปิด backlog "การ์ดวันซ้อม/วันแข่ง" ที่ค้างใน `CM6_i2_บันทึกวิเคราะห์.md`)

**แกนคำตอบ:** บนทางชัน HR ถูกกำหนดโดย **อัตราไต่ (ม./ชม.)** เท่านั้น → อยากลด HR = ลดอัตราไต่ · ที่ 360 ม./ชม. บนชัน 20% = **1.8 กม./ชม. (33 นาที/กม.)** ซึ่งถูกต้องแล้ว ไม่ใช่ช้าเกิน
**ของชิ้นสำคัญที่สุด:** ตั้ง **HR alert 150 บน FR255** (Activities & Apps → Trail Run → Alerts → HR High 150) — สั่น = ช้าลงทันที
**ตัวแปรแฝงที่ดัน HR:** ความร้อน (+10-20 bpm · ลูกสองตกช่วง 11:00-15:00 ร้อนสุด) · ขาดน้ำ (1% น้ำหนัก = +3-5 bpm) · น้ำตาลตก · **หนี้การนอน**
**ตารางเดิน 10 กม.แรก:** คำนวณจาก GPX × 360 ม./ชม. → ถึง CP1 ที่ 3:20 (ตัด 3:30)
**หลักฐานว่ากฎนี้ถูก:** HR 168 (2024) ไต่ 330 ม./ชม. → DNF · HR 148 (29 ก.ค. 2026) ไต่ 400 ม./ชม. → อยู่ได้ 8 ชม.

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

## Last updated: 2026-08-01 — ดึงเส้นทาง CM6 i2 ของจริง (GPX+CP): สนาม 42.9 กม./+2,483 ม. (เอกสารเดิม 40/+2,380 ผิด) + pacing กม.20 ชนเวลาตัด A1; prior: sim พลาด → time-on-feet 4-5 ชม. (1 ส.ค.)
