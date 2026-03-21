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
  - `OURA_TOKEN` = XKJ5LXPVFSD62Z3SNNM43ZW2E7C4FJ5A
  - `GEMINI_KEY` = AIzaSyAzy0svHVW8lxLNAxTK0pvVKJEXAB7H9Tw

### 3. PWA (Progressive Web App)
- `manifest.json` — ชื่อ, icon, theme color
- `sw.js` — Service Worker: cache assets, network-first สำหรับ API
- สามารถ "Add to Home Screen" ได้บนมือถือ

### 4. Garmin Local Server (`garmin_server.py`)
- Flask server รัน `http://localhost:5001/garmin`
- ดึง: body_battery, steps, HRV last night, last_activity
- Cache 5 นาที
- รัน: `py -3 garmin_server.py`
- Credentials: `nuciferx@gmail.com` / `R@inbow40` (เก็บใน `.env`)

### 5. Location Parser (`location_parse.py`)
- รัน: `py -3 location_parse.py`
- Input: `data/semantic/*.json` (จาก Google Takeout)
- Output: `data/commute.json` — วันที่, ออกบ้าน, ถึงงาน, ออกงาน, ถึงบ้าน, commute_min

---

## สิ่งที่ยังไม่ได้ทำ / Limitations

| รายการ | เหตุผล |
|--------|--------|
| Auto location tracking รายวัน | Data Portability API ต้อง Google Verification (หลายสัปดาห์) |
| Garmin ทำงานอัตโนมัติบนเว็บ | garmin_server.py ต้องรันในเครื่อง (localhost) |
| Commute auto-fill จาก GPS | ยังไม่มีระบบ — manual entry ใน dashboard |

---

## วิธี Deploy อัพเดต

```bash
# แก้ไฟล์ใดก็ได้ แล้ว:
cd F:/ai/health-dashboard
git add <ไฟล์>
git commit -m "..."
git push
# GitHub Pages อัพเดตใน ~30 วิ
```

## อัพเดต Cloudflare Worker

```bash
cd F:/ai/health-dashboard/cf-worker
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
├── garmin_server.py    # Flask local server ดึง Garmin
├── garmin_export.py    # CLI export Garmin data
├── location_fetch.py   # Data Portability API (ใช้ไม่ได้ — scope restricted)
├── location_parse.py   # Parse Google Takeout → commute.json
├── .env                # Garmin credentials (gitignored)
├── cf-worker/
│   ├── src/index.js    # Cloudflare Worker code
│   └── wrangler.toml   # Worker config
└── data/
    ├── commute.json    # output จาก location_parse.py
    └── semantic/       # Google Takeout JSON files (gitignored)
```

---

## Last updated: 2026-03-22
