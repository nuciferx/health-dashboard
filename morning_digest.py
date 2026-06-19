"""
morning_digest.py — สรุปสุขภาพเช้า CM6 i2 → ส่ง Telegram (rule-based ล้วน, ไม่มี AI)

ออกแบบ:
  - Oura เป็นหลัก (นอน/HRV/Readiness) — เสถียร ดึงได้เสมอ
  - Garmin best-effort (activity เมื่อวาน) — ถ้า login ไม่ผ่าน/โดนบล็อก ก็ขึ้น n/a ไม่พังทั้งใบ
  - "แผนวันนี้" map จากตารางซ้อม CM6 i2 ด้วยชื่อวันจริง (ไม่เชื่อ label ใน .md ที่เลื่อน)

Env vars:
  OURA_TOKEN          — Oura personal access token (จำเป็น)
  GARMIN_EMAIL/PASSWORD — Garmin Connect (optional, best-effort)
  TELEGRAM_BOT_TOKEN  — ถ้าไม่มี → dry-run (print แทนส่ง)
  TELEGRAM_CHAT_ID    — chat ปลายทาง

รัน:  python morning_digest.py
"""

import os
import sys
import io
from datetime import datetime, timedelta, timezone

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ICT = timezone(timedelta(hours=7))
RACE_DATE = datetime(2026, 8, 8, tzinfo=ICT).date()

# โซน HR (max 186) จากตารางซ้อม
ZONES = [(130, 148, "Z2"), (149, 160, "Z3"), (161, 172, "Z4")]
EASY_HR_CAP = 150  # กฎข้อ 1: ขึ้น HR ≤150

# ── ตารางซ้อม: map ด้วยชื่อวันจริงในสัปดาห์ (Mon=0 .. Sun=6) ───────────────
# W2-W6 = บล็อก 7 วัน เริ่มวันอังคาร (anchor) → key ด้วยวันที่อังคารที่เริ่ม
S = lambda name, detail, hr: {"session": name, "detail": detail, "hr": hr}

W1_BY_DATE = {
    "2026-06-18": S("Vertical baseline (ลู่)", "เริ่ม 8-10% หา speed ที่ HR 130-145 · จดชัน/speed/m-hr", "≤150"),
    "2026-06-19": S("เวท + core", "squat, step-down eccentric, calf, core", "—"),
    "2026-06-20": S("Long Vertical 2.5-3 ชม. (ลู่)", "สะสม +900 ม. สลับเดินราบ · กฎครบ 5 ข้อ · เป้า: ไม่หมดที่ 3 ชม.", "ขึ้น ≤150"),
    "2026-06-21": S("วิ่ง/เดินราบ 6-8 กม. (ฟื้น)", "time-on-feet เบา", "Z2"),
}

# weekday -> session (Mon=0..Sun=6)
WEEKS = {
    "2026-06-23": {  # W2 เติมงานหนัก (ลู่ล้วน)
        0: S("พัก", "—", "—"),
        1: S("ลู่ชัน intervals 6×4 นาที", "ขึ้นหนัก-เดินฟื้น (ดัน m/hr)", "Z4 ช่วงดัน"),
        2: S("เวท + core", "+ step-down eccentric", "—"),
        3: S("ราบ Z2 8 กม.", "—", "≤148"),
        4: S("เวทเบา / พัก", "—", "—"),
        5: S("Long Vertical 3-3.5 ชม. (ลู่)", "สะสม +1,200 ม. + ราบ", "ขึ้น ≤150"),
        6: S("ราบยาว 10 กม. (ขาล้า)", "time-on-feet", "Z2"),
    },
    "2026-06-30": {  # W3 ทริปเขา #1
        0: S("พัก", "—", "—"),
        1: S("ลู่ชัน climb-sim (~600 ม.)", "ใส่เป้ถ่วงเริ่มชินน้ำหนัก", "Z4"),
        2: S("เวท + core", "—", "—"),
        3: S("ราบ Z2 10 กม. (+ลู่ชัน tempo)", "—", "Z2-Z3"),
        4: S("เวทเบา / พัก", "—", "—"),
        5: S("🏔️ เขาจริง: LR 26 กม. / +1,500", "ใส่เป้+อุปกรณ์จริง · ซ้อมกินครบ · โฟกัสขาลง", "ขึ้น ≤150"),
        6: S("B2B เขา/ราบ 12 กม.", "ขาล้า (ถ้ายังอยู่เขา)", "Z2"),
    },
    "2026-07-07": {  # W4 ฟื้น (ลดโหลด ~50%)
        0: S("พัก", "—", "—"),
        1: S("ลู่ชันเบา 4 เที่ยว", "ไม่ดันหนัก", "≤Z3"),
        2: S("เวทเบา", "—", "—"),
        3: S("ราบ Z2 8 กม.", "—", "≤148"),
        4: S("พัก", "—", "—"),
        5: S("Vertical เบา ~2 ชม. (+700 ม. ลู่)", "เก็บความสด", "ขึ้น ≤150"),
        6: S("พัก / เดินเบา", "—", "—"),
    },
    "2026-07-14": {  # W5 PEAK — RACE SIM
        0: S("พัก", "—", "—"),
        1: S("ลู่ชัน 6×5 นาที", "คมความเร็วไต่", "Z4"),
        2: S("เวท + core", "—", "—"),
        3: S("ราบ Z2 8 กม.", "—", "≤148"),
        4: S("พัก (เตรียม sim)", "นอนเต็มที่", "—"),
        5: S("🏔️ RACE SIM เขาจริง 30-33 กม. / +2,000", "เสมือนแข่งครบ · เป้า 7-8 ชม.", "ขึ้น ≤150"),
        6: S("เดินฟื้น 5 กม.", "—", "—"),
    },
    "2026-07-21": {  # W6 ทริปเขา #3
        0: S("พัก", "—", "—"),
        1: S("ลู่ชัน 5×3 นาที เร็วสุด", "ดัน m/hr", "Z4"),
        2: S("เวท + core", "—", "—"),
        3: S("ราบ Z2 8 กม.", "—", "≤148"),
        4: S("เวทเบา / พัก", "—", "—"),
        5: S("🏔️ เขาจริง: LR 20 กม. / +1,000", "คงฟิต + ขาลงครั้งสุดท้ายก่อนเทเปอร์", "ขึ้น ≤150"),
        6: S("เดินเบา", "—", "—"),
    },
}

W7_BY_DATE = {  # เทเปอร์ + แข่ง
    "2026-07-28": S("พัก", "—", "—"),
    "2026-07-29": S("กระตุ้นเบา (ลู่ชัน 3 เที่ยวสั้น)", "—", "—"),
    "2026-07-30": S("เวทเบามาก / พัก", "—", "—"),
    "2026-07-31": S("ราบสั้น 5 กม. สบาย", "—", "—"),
    "2026-08-01": S("Vertical เบา ~1.5 ชม. (+400 ม. ลู่)", "ซ้อมระบบกิน/น้ำครั้งสุดท้าย", "—"),
    "2026-08-08": S("🏁 RACE — CM6 i2", "ออก 05:30 · กฎ 5 ข้อ · pacing ตามแผน", "ขึ้น ≤150"),
}


def plan_for(d):
    """d = datetime.date → คืน session dict หรือ None"""
    iso = d.isoformat()
    if iso in W1_BY_DATE:
        return W1_BY_DATE[iso]
    if iso in W7_BY_DATE:
        return W7_BY_DATE[iso]
    if datetime(2026, 8, 2).date() <= d <= datetime(2026, 8, 7).date():
        return S("พักให้สด / เดินเบา", "นอนเยอะ · เพิ่มคาร์บ 2-3 วันสุดท้าย · เช็กอุปกรณ์บังคับ", "—")
    for tue_iso, week in WEEKS.items():
        tue = datetime.fromisoformat(tue_iso).date()
        if tue <= d <= tue + timedelta(days=6):
            return week.get(d.weekday())
    return None


# ── Oura ────────────────────────────────────────────────────────────────
def oura_get(token, path, start, end):
    r = requests.get(
        f"https://api.ouraring.com/v2/usercollection/{path}",
        headers={"Authorization": f"Bearer {token}"},
        params={"start_date": start, "end_date": end},
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("data", [])


def fetch_oura(token, today):
    start = (today - timedelta(days=8)).isoformat()
    end = today.isoformat()
    out = {"readiness": None, "sleep_score": None, "sleep_h": None,
           "hrv": None, "hrv_avg7": None, "rhr": None, "rhr_avg7": None}

    # Readiness (วันนี้)
    rd = oura_get(token, "daily_readiness", start, end)
    for x in rd:
        if x.get("day") == today.isoformat():
            out["readiness"] = x.get("score")

    # Sleep score (วันนี้)
    ds = oura_get(token, "daily_sleep", start, end)
    for x in ds:
        if x.get("day") == today.isoformat():
            out["sleep_score"] = x.get("score")

    # Sleep sessions (duration, HRV, RHR) — เลือก long_sleep ต่อวัน
    sl = oura_get(token, "sleep", start, end)
    by_day = {}
    for s in sl:
        if s.get("type") not in ("long_sleep", "sleep"):
            continue
        day = s.get("day")
        # เลือก session ที่นอนนานสุดของวันนั้น
        if day not in by_day or (s.get("total_sleep_duration") or 0) > (by_day[day].get("total_sleep_duration") or 0):
            by_day[day] = s

    today_s = by_day.get(today.isoformat())
    if today_s:
        dur = today_s.get("total_sleep_duration")
        out["sleep_h"] = round(dur / 3600, 1) if dur else None
        out["hrv"] = today_s.get("average_hrv")
        out["rhr"] = today_s.get("lowest_heart_rate")

    # ค่าเฉลี่ย 7 วันก่อนหน้า (ไม่รวมวันนี้) สำหรับ trend
    prev = [v for k, v in by_day.items() if k != today.isoformat()]
    hrvs = [s.get("average_hrv") for s in prev if s.get("average_hrv")]
    rhrs = [s.get("lowest_heart_rate") for s in prev if s.get("lowest_heart_rate")]
    if hrvs:
        out["hrv_avg7"] = round(sum(hrvs) / len(hrvs))
    if rhrs:
        out["rhr_avg7"] = round(sum(rhrs) / len(rhrs))
    return out


# ── Garmin ──────────────────────────────────────────────────────────────
# Garmin บล็อก login-ด้วยรหัส จาก cloud (429/403) แต่ login-ด้วย token ผ่านได้
# → GARMIN_TOKENS (จาก client.dumps() ที่ดึง local) ทำงานทั้ง local + cloud
def garmin_login():
    from garminconnect import Garmin
    tokens = os.environ.get("GARMIN_TOKENS")
    if tokens:
        g = Garmin()
        g.login(tokens)            # token-only (ใช้ได้บน cloud)
        return g
    email, password = os.environ.get("GARMIN_EMAIL"), os.environ.get("GARMIN_PASSWORD")
    if email and password:
        g = Garmin(email, password)
        g.login()                  # password (local เท่านั้น)
        return g
    return None


def fetch_garmin_wellness():
    """ดึง stress (เมื่อวาน) + body battery (เช้านี้) + RHR กลางวัน. คืน dict หรือ {'error':...}"""
    try:
        g = garmin_login()
        if not g:
            return {"error": "no-credentials"}
        today = datetime.now(ICT).date()
        yday = (today - timedelta(days=1)).isoformat()
        tstr = today.isoformat()
        out = {}
        # stress เมื่อวาน (เต็มวัน)
        try:
            st = g.get_stress_data(yday)
            avg = st.get("avgStressLevel")
            out["stress_avg"] = avg if (avg is not None and avg >= 0) else None
        except Exception:
            pass
        # body battery เช้านี้ (ค่าล่าสุด = ชาร์จหลังนอน)
        try:
            bb = g.get_body_battery(tstr)
            if bb and isinstance(bb, list) and bb[0]:
                vals = [v[1] for v in bb[0].get("bodyBatteryValuesArray", []) if isinstance(v, list) and len(v) > 1 and v[1] is not None]
                if vals:
                    out["body_battery"] = vals[-1]
        except Exception:
            pass
        # RHR กลางวัน (Garmin)
        try:
            hr = g.get_heart_rates(tstr)
            out["rhr_day"] = hr.get("restingHeartRate")
        except Exception:
            pass
        return out if out else {"error": "no-data"}
    except Exception as e:
        return {"error": str(e)[:80]}


def fetch_garmin():
    """คืน dict activity ล่าสุด หรือ {'error': ...} (fallback เมื่อ Strava ไม่พร้อม)"""
    try:
        c = garmin_login()
        if not c:
            return {"error": "no-credentials"}
        acts = c.get_activities(0, 1)
        if not acts:
            return {"error": "no-activity"}
        a = acts[0]
        dist = a.get("distance") or 0
        dur = a.get("duration") or a.get("movingDuration") or 0
        return {
            "type": (a.get("activityType") or {}).get("typeKey"),
            "name": a.get("activityName"),
            "date": (a.get("startTimeLocal") or "")[:10],
            "km": round(dist / 1000, 1) if dist else None,
            "min": round(dur / 60) if dur else None,
            "avg_hr": a.get("averageHR"),
            "gain_m": round(a.get("elevationGain")) if a.get("elevationGain") else None,
        }
    except Exception as e:
        return {"error": str(e)[:80]}


# ── Strava (activity จาก cloud — Garmin sync เข้า Strava อยู่แล้ว) ─────────
def fetch_strava():
    """ดึง activity ล่าสุดจาก Strava API. คืน dict หรือ {'error': ...}
    ต้องมี env: STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, STRAVA_REFRESH_TOKEN"""
    cid = os.environ.get("STRAVA_CLIENT_ID")
    secret = os.environ.get("STRAVA_CLIENT_SECRET")
    refresh = os.environ.get("STRAVA_REFRESH_TOKEN")
    if not (cid and secret and refresh):
        return {"error": "no-credentials"}
    try:
        tok = requests.post("https://www.strava.com/oauth/token", data={
            "client_id": cid, "client_secret": secret,
            "refresh_token": refresh, "grant_type": "refresh_token",
        }, timeout=30)
        tok.raise_for_status()
        access = tok.json()["access_token"]
        r = requests.get("https://www.strava.com/api/v3/athlete/activities",
                         headers={"Authorization": f"Bearer {access}"},
                         params={"per_page": 1}, timeout=30)
        r.raise_for_status()
        acts = r.json()
        if not acts:
            return {"error": "no-activity"}
        a = acts[0]
        dur = a.get("moving_time") or a.get("elapsed_time") or 0
        gain = a.get("total_elevation_gain") or 0
        return {
            "name": a.get("name"),
            "type": a.get("sport_type") or a.get("type"),
            "date": (a.get("start_date_local") or "")[:10],
            "km": round((a.get("distance") or 0) / 1000, 1) or None,
            "min": round(dur / 60) if dur else None,
            "gain_m": round(gain) if gain else None,
            "avg_hr": round(a["average_heartrate"]) if a.get("average_heartrate") else None,
            "vert": round(gain / (dur / 3600)) if (gain and dur) else None,  # ม/ชม
        }
    except Exception as e:
        return {"error": str(e)[:80]}


def pick_activity(strava, garmin):
    """เลือกแหล่ง activity: Strava ก่อน (cloud-friendly) → Garmin (local) → None"""
    if strava and "error" not in strava:
        return {**strava, "source": "Strava"}
    if garmin and "error" not in garmin:
        return {**garmin, "source": "Garmin"}
    return None


# ── Format ──────────────────────────────────────────────────────────────
def arrow(now, avg):
    if now is None or avg is None:
        return ""
    if now > avg * 1.03:
        return " ↑"
    if now < avg * 0.97:
        return " ↓"
    return " →"


def zone_of(hr):
    for lo, hi, name in ZONES:
        if lo <= hr <= hi:
            return name
    if hr < ZONES[0][0]:
        return "Z1"
    return "Z4+"


THAI_DOW = ["จ", "อ", "พ", "พฤ", "ศ", "ส", "อา"]
THAI_MON = ["", "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
            "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]


def build_message(today, oura, activity, plan, gwell=None):
    days_left = (RACE_DATE - today).days
    L = []
    L.append(f"🌅 {THAI_DOW[today.weekday()]} {today.day} {THAI_MON[today.month]} — เหลือ {days_left} วัน CM6 i2")
    L.append("")

    # 😴 นอน/ฟื้นตัว
    flags = []
    if oura["sleep_h"] is not None:
        warn = " 🔴" if oura["sleep_h"] < 7 else " ✅"
        L.append(f"😴 นอน {oura['sleep_h']} ชม.{warn}  (เป้า 7)")
        if oura["sleep_h"] < 7:
            flags.append("นอนน้อย")
    else:
        L.append("😴 นอน: n/a")

    if oura["hrv"] is not None:
        L.append(f"💗 HRV {oura['hrv']}{arrow(oura['hrv'], oura['hrv_avg7'])}  (avg7 {oura['hrv_avg7'] or '–'})")
    if oura["rhr"] is not None:
        L.append(f"❤️ RHR {oura['rhr']}{arrow(oura['rhr'], oura['rhr_avg7'])}  (avg7 {oura['rhr_avg7'] or '–'})")

    if oura["readiness"] is not None:
        if oura["readiness"] < 55:
            rflag = " 🔴 พัก/เดินเบา"
            flags.append("readiness ต่ำ")
        elif oura["readiness"] < 70:
            rflag = " 🟡"
        else:
            rflag = " ✅"
        L.append(f"💚 Readiness {oura['readiness']}{rflag}")
    if oura["sleep_score"] is not None:
        L.append(f"🛌 Sleep score {oura['sleep_score']}")

    # 🔋 Garmin wellness (token-based — ใช้ได้บน cloud)
    if gwell and "error" not in gwell:
        parts = []
        bb = gwell.get("body_battery")
        if bb is not None:
            bmark = " 🔴" if bb < 30 else (" 🟡" if bb < 50 else " ✅")
            parts.append(f"🔋 Body Battery {bb}{bmark}")
        sv = gwell.get("stress_avg")
        if sv is not None:
            smark = " 🔴" if sv > 60 else (" 🟡" if sv > 50 else " ✅")
            parts.append(f"😰 Stress(เมื่อวาน) {sv}{smark}")
            if sv > 60:
                flags.append("stress สูง")
        if parts:
            L.append("  ·  ".join(parts))
        if bb is not None and bb < 30:
            flags.append("body battery ต่ำ")

    L.append("")

    # 🏃 activity ล่าสุด (Strava ก่อน → Garmin local)
    if not activity:
        L.append("🏃 activity: n/a — (ดูเต็ม → /health กับ Claude)")
    else:
        parts = []
        if activity.get("km"):
            parts.append(f"{activity['km']} กม.")
        if activity.get("min"):
            parts.append(f"{activity['min']} นาที")
        if activity.get("gain_m"):
            parts.append(f"+{activity['gain_m']} ม.")
        desc = " · ".join(parts) if parts else (activity.get("type") or "กิจกรรม")
        L.append(f"🏃 ล่าสุด ({activity.get('date') or '?'}): {desc}")
        hr = activity.get("avg_hr")
        if hr:
            z = zone_of(hr)
            mark = " ✅ คุมโซนดี" if hr <= EASY_HR_CAP else " ⚠️ HR สูง — ระวัง pacing"
            L.append(f"   avgHR {hr} ({z}){mark}")
            if hr > EASY_HR_CAP:
                flags.append("HR ซ้อมสูง")
        if activity.get("vert"):
            vmark = " ✅" if activity["vert"] >= 550 else (" 🟡" if activity["vert"] >= 400 else " 🔴 (เป้า 550-650)")
            L.append(f"   ไต่ {activity['vert']} ม/ชม{vmark}")

    L.append("")

    # 📋 แผนวันนี้
    if plan:
        L.append(f"📋 แผนวันนี้: {plan['session']}")
        if plan.get("detail") and plan["detail"] != "—":
            L.append(f"   {plan['detail']}")
        if plan.get("hr") and plan["hr"] != "—":
            L.append(f"   เป้า HR: {plan['hr']}")
    else:
        L.append("📋 แผนวันนี้: (นอกช่วงตารางซ้อม)")

    # สรุปเส้นแดง
    if flags:
        L.append("")
        L.append("⚠️ ธงเตือน: " + " · ".join(flags))

    return "\n".join(L)


def send_telegram(token, chat_id, text):
    r = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def main():
    token = os.environ.get("OURA_TOKEN")
    if not token:
        print("::error::Missing OURA_TOKEN", file=sys.stderr)
        sys.exit(1)

    today = datetime.now(ICT).date()
    oura = fetch_oura(token, today)
    strava = fetch_strava()
    garmin = fetch_garmin() if "error" in strava else None  # fallback เฉพาะตอน Strava ไม่พร้อม
    activity = pick_activity(strava, garmin)
    gwell = fetch_garmin_wellness()                         # stress + body battery (token-based)
    plan = plan_for(today)
    msg = build_message(today, oura, activity, plan, gwell)

    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    tg_chat = os.environ.get("TELEGRAM_CHAT_ID")
    if tg_token and tg_chat:
        send_telegram(tg_token, tg_chat, msg)
        print("✅ ส่ง Telegram แล้ว\n")
        print(msg)
    else:
        print("── DRY-RUN (ไม่มี TELEGRAM_BOT_TOKEN/CHAT_ID — แสดงผลแทนการส่ง) ──\n")
        print(msg)


if __name__ == "__main__":
    main()
