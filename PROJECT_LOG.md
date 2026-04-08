# Health Dashboard — Project Log

## URL
- **Dashboard**: https://nuciferx.github.io/health-dashboard/
- **Cloudflare Worker (API proxy)**: https://health-proxy.ideaplanstudio.workers.dev

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
- **Workflow**: `.github/workflows/log-garmin.yml` — cron ทุก 1 ชม. (UTC)
- **Script**: `log_garmin.py` — login Garmin → ดึงข้อมูล → เขียน Google Sheets
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

ใช้ sheet เดียวกับ air-quality (`1Gi1A-6YHoVOyvaDy_jk3eARSlmTWqRrDrOXVamm4O_Y`) — script จะสร้าง tab "Garmin" ให้อัตโนมัติ

1. เปิด Google Sheet: https://docs.google.com/spreadsheets/d/1Gi1A-6YHoVOyvaDy_jk3eARSlmTWqRrDrOXVamm4O_Y
2. ตรวจสอบว่า service account `nucifer-sheets-bot@nucifer-data-sheet-api.iam.gserviceaccount.com` มีสิทธิ์ Editor (น่าจะมีอยู่แล้วจาก air-quality)
3. **Publish to web**: File → Share → Publish to web → เลือก tab "Garmin" → Comma-separated values (.csv) → Publish
4. ตั้งค่า GitHub Secrets (Settings → Secrets and variables → Actions):
   - `GARMIN_EMAIL` = `nuciferx@gmail.com`
   - `GARMIN_PASSWORD` = `R@inbow40`
   - `GCP_SA_KEY` = JSON content ของ `gcp_sa_key` ใน `air-quality/creds.json`
   - `SHEET_ID` = `1Gi1A-6YHoVOyvaDy_jk3eARSlmTWqRrDrOXVamm4O_Y`
5. ทดสอบ: Actions → Log Garmin → Run workflow — tab "Garmin" จะถูกสร้างอัตโนมัติ

**Dashboard CSV URL** (ตั้งค่าใน `config.js` แล้ว):
```
https://docs.google.com/spreadsheets/d/1Gi1A-6YHoVOyvaDy_jk3eARSlmTWqRrDrOXVamm4O_Y/gviz/tq?sheet=Garmin&tqx=out:csv
```

---

## สิ่งที่ยังไม่ได้ทำ / Limitations

| รายการ | เหตุผล |
|--------|--------|
| Auto location tracking รายวัน | Data Portability API ต้อง Google Verification (หลายสัปดาห์) |
| Commute auto-fill จาก GPS | ยังไม่มีระบบ — manual entry ใน dashboard |

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
├── index.html          # Dashboard หลัก (all-in-one)
├── manifest.json       # PWA manifest
├── sw.js               # Service Worker
├── icon-192.png        # PWA icon
├── icon-512.png        # PWA icon
├── config.js           # Local config (gitignored) — PROXY_URL, keys
├── log_garmin.py       # GitHub Action: ดึง Garmin → Google Sheets ทุก 1 ชม.
├── requirements.txt    # Python deps (garminconnect, gspread, python-dotenv)
├── garmin_server.py    # Flask local server ดึง Garmin
├── garmin_export.py    # CLI export Garmin data
├── location_fetch.py   # Data Portability API (ใช้ไม่ได้ — scope restricted)
├── location_parse.py   # Parse Google Takeout → commute.json
├── .env                # Garmin credentials (gitignored)
├── .github/workflows/
│   └── log-garmin.yml  # GitHub Action: cron ทุก 1 ชม.
├── cf-worker/
│   ├── src/index.js    # Cloudflare Worker code
│   └── wrangler.toml   # Worker config
└── data/
    ├── commute.json    # output จาก location_parse.py
    └── semantic/       # Google Takeout JSON files (gitignored)
```

---

## Last updated: 2026-04-08
