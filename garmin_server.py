"""
garmin_server.py — Local Garmin data server สำหรับ Health Dashboard

ติดตั้ง: pip install flask flask-cors garminconnect python-dotenv
ตั้งค่า: ใส่ GARMIN_EMAIL และ GARMIN_PASSWORD ใน .env
รัน:     python garmin_server.py
Dashboard จะดึงข้อมูล Garmin อัตโนมัติจาก http://localhost:5001/garmin
"""
import os
import json
import datetime
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

try:
    from garminconnect import Garmin, GarminConnectAuthenticationError
except ImportError:
    print("กรุณาติดตั้ง: pip install garminconnect")
    sys.exit(1)

load_dotenv()

app = Flask(__name__)
CORS(app)  # อนุญาต dashboard ทุก origin (localhost, file://, github pages)

# ── State ─────────────────────────────────────────────────────────
_client = None
_cache  = {"data": None, "at": None}
CACHE_TTL = 300  # วินาที (5 นาที)


def get_client() -> Garmin:
    global _client
    email    = os.getenv("GARMIN_EMAIL")
    password = os.getenv("GARMIN_PASSWORD")

    if not email or not password:
        raise ValueError("ไม่พบ GARMIN_EMAIL หรือ GARMIN_PASSWORD ใน .env")

    if _client is None:
        print(f"  กำลัง login Garmin ({email}) ...")
        _client = Garmin(email, password)
        _client.login()
        print("  Login สำเร็จ")

    return _client


def fetch_garmin_data() -> dict:
    global _client

    today  = datetime.date.today().isoformat()
    result = {
        "date":           today,
        "body_battery":   None,
        "steps":          None,
        "hrv_last_night": None,
        "last_activity": {
            "type":         None,
            "distance_km":  None,
            "duration_min": None,
            "avg_hr":       None,
        },
    }

    client = get_client()

    # Body Battery
    try:
        bb = client.get_body_battery(today)
        if bb and isinstance(bb, list) and bb[0]:
            vals = [v.get("value") for v in bb[0].get("bodyBatteryValuesArray", [])
                    if v.get("value") is not None]
            result["body_battery"] = vals[-1] if vals else None
    except Exception as e:
        print(f"  [warn] body_battery: {e}")

    # Steps
    try:
        steps = client.get_steps_data(today)
        if isinstance(steps, list):
            result["steps"] = sum(s.get("steps", 0) for s in steps if isinstance(s, dict))
        elif isinstance(steps, dict):
            result["steps"] = steps.get("totalSteps") or steps.get("steps")
    except Exception as e:
        print(f"  [warn] steps: {e}")

    # HRV
    try:
        hrv = client.get_hrv_data(today)
        if hrv and isinstance(hrv, dict):
            summary = hrv.get("hrvSummary", {})
            result["hrv_last_night"] = (
                hrv.get("lastNight")
                or summary.get("lastNight")
                or summary.get("rmssd")
            )
    except Exception as e:
        print(f"  [warn] hrv: {e}")

    # Last Activity
    try:
        acts = client.get_activities(0, 1)
        if acts and isinstance(acts, list):
            a    = acts[0]
            dist = a.get("distance") or 0
            dur  = a.get("duration") or a.get("movingDuration") or 0
            result["last_activity"] = {
                "type":         a.get("activityType", {}).get("typeKey", "unknown"),
                "distance_km":  round(dist / 1000, 2) if dist else None,
                "duration_min": round(dur  / 60)      if dur  else None,
                "avg_hr":       a.get("averageHR"),
            }
    except Exception as e:
        print(f"  [warn] activities: {e}")

    return result


# ── Routes ────────────────────────────────────────────────────────
@app.route("/garmin")
def garmin():
    global _cache, _client
    now = datetime.datetime.now()

    # คืน cache ถ้ายังสด
    if _cache["data"] and _cache["at"]:
        age = (now - _cache["at"]).total_seconds()
        if age < CACHE_TTL:
            return jsonify({**_cache["data"], "_cached": True, "_age_sec": int(age)})

    print(f"\n[{now.strftime('%H:%M:%S')}] ดึงข้อมูล Garmin ...")
    try:
        data = fetch_garmin_data()
    except GarminConnectAuthenticationError:
        _client = None  # force re-login ครั้งต่อไป
        return jsonify({"error": "Garmin login ล้มเหลว — ตรวจสอบ email/password ใน .env"}), 401
    except Exception as e:
        _client = None
        return jsonify({"error": str(e)}), 500

    _cache = {"data": data, "at": now}
    print(f"  สำเร็จ: body_battery={data['body_battery']}, steps={data['steps']}")
    return jsonify(data)


@app.route("/health")
def health():
    return jsonify({"status": "ok", "time": datetime.datetime.now().isoformat()})


# ── Main ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    email = os.getenv("GARMIN_EMAIL", "")
    print("=" * 55)
    print("  Garmin Local Server")
    print(f"  http://localhost:5001/garmin")
    print(f"  Email: {email or '(ยังไม่ตั้งค่า — ใส่ใน .env)'}")
    print("  กด Ctrl+C เพื่อหยุด")
    print("=" * 55)
    app.run(host="127.0.0.1", port=5001, debug=False)
