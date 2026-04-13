"""
garmin_export.py — ดึงข้อมูลสุขภาพจาก Garmin Connect

ติดตั้ง: pip install garminconnect
รัน:     python garmin_export.py your@email.com yourpassword
Output:  JSON ออก stdout → copy แล้ว paste ใน dashboard
"""
import sys
import json
import datetime

try:
    from garminconnect import Garmin, GarminConnectAuthenticationError
except ImportError:
    print("กรุณาติดตั้ง dependency: pip install garminconnect", file=sys.stderr)
    sys.exit(1)


def get_garmin_data(email: str, password: str) -> dict:
    # Login
    try:
        client = Garmin(email, password)
        client.login()
    except GarminConnectAuthenticationError as e:
        print(f"Login ล้มเหลว: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"เชื่อมต่อ Garmin ไม่ได้: {e}", file=sys.stderr)
        sys.exit(1)

    today = datetime.date.today().isoformat()

    result = {
        "date":            today,
        "body_battery":    None,
        "steps":           None,
        "hrv_last_night":  None,
        "last_activity": {
            "type":         None,
            "distance_km":  None,
            "duration_min": None,
            "avg_hr":       None,
        },
    }

    # Body Battery — format: [[timestamp, value], ...]
    try:
        bb_data = client.get_body_battery(today)
        if bb_data and isinstance(bb_data, list) and bb_data[0]:
            values = bb_data[0].get("bodyBatteryValuesArray", [])
            vals = [v[1] for v in values if isinstance(v, list) and len(v) > 1 and v[1] is not None]
            result["body_battery"] = vals[-1] if vals else None
    except Exception as e:
        print(f"[warn] body_battery: {e}", file=sys.stderr)

    # Steps
    try:
        steps_data = client.get_steps_data(today)
        if isinstance(steps_data, list):
            result["steps"] = sum(
                s.get("steps", 0) for s in steps_data if isinstance(s, dict)
            )
        elif isinstance(steps_data, dict):
            result["steps"] = steps_data.get("totalSteps") or steps_data.get("steps")
    except Exception as e:
        print(f"[warn] steps: {e}", file=sys.stderr)

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
        print(f"[warn] hrv: {e}", file=sys.stderr)

    # Last Activity
    try:
        activities = client.get_activities(0, 1)
        if activities and isinstance(activities, list):
            act = activities[0]
            dist_m = act.get("distance") or 0
            dur_s  = act.get("duration") or act.get("movingDuration") or 0
            result["last_activity"] = {
                "type":         act.get("activityType", {}).get("typeKey", "unknown"),
                "distance_km":  round(dist_m / 1000, 2) if dist_m else None,
                "duration_min": round(dur_s  / 60) if dur_s  else None,
                "avg_hr":       act.get("averageHR"),
            }
    except Exception as e:
        print(f"[warn] activities: {e}", file=sys.stderr)

    return result


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python garmin_export.py <email> <password>", file=sys.stderr)
        sys.exit(1)

    data = get_garmin_data(sys.argv[1], sys.argv[2])
    print(json.dumps(data, ensure_ascii=False, indent=2))
