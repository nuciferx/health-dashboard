"""
log_garmin.py — ดึงข้อมูล Garmin Connect ทุกชั่วโมง → เก็บ Google Sheets

Env vars required:
  GARMIN_EMAIL     — Garmin account email
  GARMIN_PASSWORD  — Garmin account password
  GCP_SA_KEY       — Google Service Account JSON string
  SHEET_ID         — Google Sheets spreadsheet ID

ติดตั้ง: pip install garminconnect gspread python-dotenv
รัน:     python log_garmin.py
"""

import json
import logging
import os
import sys
import io
from datetime import datetime, timezone

from dotenv import load_dotenv

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

try:
    from garminconnect import Garmin, GarminConnectAuthenticationError
except ImportError:
    log.error("กรุณาติดตั้ง: pip install garminconnect")
    sys.exit(1)

try:
    import gspread
except ImportError:
    log.error("กรุณาติดตั้ง: pip install gspread")
    sys.exit(1)

load_dotenv()

# ── Google Sheets header ──────────────────────────────────────────────
HEADERS = [
    "timestamp",
    "body_battery",
    "steps",
    "hrv_last_night",
    "resting_hr",
    "spo2",
    "stress_high_min",
    "recovery_high_min",
    "activity_type",
    "activity_distance_km",
    "activity_duration_min",
    "activity_avg_hr",
]


def get_garmin_client() -> Garmin:
    email = os.environ.get("GARMIN_EMAIL")
    password = os.environ.get("GARMIN_PASSWORD")
    if not email or not password:
        raise ValueError("ไม่พบ GARMIN_EMAIL หรือ GARMIN_PASSWORD")
    log.info("กำลัง login Garmin (%s) ...", email)
    client = Garmin(email, password)
    client.login()
    log.info("Login สำเร็จ")
    return client


def fetch_today(client: Garmin) -> dict:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    result = {k: None for k in HEADERS[1:]}  # skip timestamp

    # Body Battery
    try:
        bb = client.get_body_battery(today)
        if bb and isinstance(bb, list) and bb[0]:
            values = bb[0].get("bodyBatteryValuesArray", [])
            vals = [v[1] for v in values if isinstance(v, list) and len(v) > 1 and v[1] is not None]
            if vals:
                result["body_battery"] = vals[-1]
                # Also capture start/end for range
                result["body_battery_start"] = vals[0]
    except Exception as e:
        log.warning("body_battery: %s", e)

    # Steps
    try:
        steps = client.get_steps_data(today)
        if isinstance(steps, list):
            result["steps"] = sum(s.get("steps", 0) for s in steps if isinstance(s, dict))
        elif isinstance(steps, dict):
            result["steps"] = steps.get("totalSteps") or steps.get("steps")
    except Exception as e:
        log.warning("steps: %s", e)

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
        log.warning("hrv: %s", e)

    # Resting HR (from daily summary)
    try:
        daily = client.get_daily_stats(today)
        if daily:
            result["resting_hr"] = daily.get("restingHeartRate")
    except Exception as e:
        log.warning("daily_stats (resting_hr): %s", e)

    # SpO2
    try:
        spo2 = client.get_spo2_data(today)
        if spo2 and isinstance(spo2, dict):
            avg = spo2.get("averageSpO2") or spo2.get("latestSpO2")
            if avg is not None:
                result["spo2"] = round(float(avg), 1)
    except Exception as e:
        log.warning("spo2: %s", e)

    # Stress
    try:
        stress = client.get_stress_data(today)
        if stress and isinstance(stress, dict):
            values = stress.get("stressValuesArray", [])
            if values:
                # values = [[timestamp, stress_value], ...]
                high = max((v[1] for v in values if v[1] is not None), default=None)
                result["stress_high_min"] = high
    except Exception as e:
        log.warning("stress: %s", e)

    # Last Activity
    try:
        acts = client.get_activities(0, 1)
        if acts and isinstance(acts, list) and acts[0]:
            a = acts[0]
            dist = a.get("distance") or 0
            dur = a.get("duration") or a.get("movingDuration") or 0
            result["activity_type"] = a.get("activityType", {}).get("typeKey")
            result["activity_distance_km"] = round(dist / 1000, 2) if dist else None
            result["activity_duration_min"] = round(dur / 60) if dur else None
            result["activity_avg_hr"] = a.get("averageHR")
    except Exception as e:
        log.warning("activities: %s", e)

    return result


def get_sheet():
    sa_key_raw = os.environ.get("GCP_SA_KEY")
    sheet_id = os.environ.get("SHEET_ID")

    if sa_key_raw:
        sa_key = json.loads(sa_key_raw)
    else:
        creds_path = os.path.join(os.path.dirname(__file__), "creds.json")
        with open(creds_path) as f:
            data = json.load(f)
        sa_key = data.get("gcp_sa_key")
        sheet_id = sheet_id or data.get("sheet_id")

    if not sheet_id:
        raise RuntimeError("SHEET_ID not set.")

    gc = gspread.service_account_from_dict(sa_key)
    ss = gc.open_by_key(sheet_id)

    # Use "Garmin" worksheet (create if not exists)
    try:
        ws = ss.worksheet("Garmin")
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title="Garmin", rows=2000, cols=20)
        ws.append_row(HEADERS, value_input_option="USER_ENTERED")
        log.info("สร้าง worksheet 'Garmin' แล้ว")

    if not ws.row_values(1):
        ws.append_row(HEADERS, value_input_option="USER_ENTERED")
        log.info("สร้าง header row แล้ว")

    return ws


def main():
    client = get_garmin_client()
    ws = get_sheet()

    log.info("กำลังดึงข้อมูล Garmin วันนี้ ...")
    data = fetch_today(client)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    row = [ts] + [data.get(k) for k in HEADERS[1:]]

    log.info("Row: %s", row)
    ws.append_row(row, value_input_option="USER_ENTERED")
    log.info("เขียน Google Sheets สำเร็จ — body_battery=%s, steps=%s, hrv=%s",
             data.get("body_battery"), data.get("steps"), data.get("hrv_last_night"))


if __name__ == "__main__":
    main()
