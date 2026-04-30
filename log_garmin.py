"""
log_garmin.py — ดึงข้อมูล Garmin Connect ทุก 15 นาที → เก็บ Google Sheets

Smart logic:
  - ถ้าไม่มีข้อมูล有意义 (body_battery, steps, hrv = null ทั้งหมด) → ข้าม ไม่เขียน sheet
  - Dedup: ถ้าข้อมูลหลักเหมือนแถวสุดท้าย → ข้าม (ป้องกันเขียนซ้ำ)
  - เมื่อใส่ Garmin แล้วมีข้อมูลใหม่ → จะถูกบันทึกทันทีในรอบถัดไป

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

# คอลัมน์ที่ใช้เช็ค meaningful data (ต้องมีอย่างน้อย 1 ตัวที่ไม่ใช่ null)
MEANINGFUL_KEYS = ["body_battery", "steps", "hrv_last_night"]

# คอลัมน์ที่ใช้เช็ค dedup (ถ้าเหมือนกันทั้งหมด → ข้าม)
DEDUP_KEYS = ["body_battery", "steps", "hrv_last_night", "resting_hr"]


def emit_github_error(message: str) -> None:
    print(f"::error::{message}", file=sys.stderr)


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def get_garmin_credentials() -> tuple[str, str]:
    return require_env("GARMIN_EMAIL"), require_env("GARMIN_PASSWORD")


def load_sheet_config() -> tuple[dict, str]:
    sa_key_raw = os.environ.get("GCP_SA_KEY")
    sheet_id = os.environ.get("SHEET_ID")

    if sa_key_raw:
        try:
            sa_key = json.loads(sa_key_raw)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"GCP_SA_KEY is not valid JSON: {e}") from e
    else:
        creds_path = os.path.join(os.path.dirname(__file__), "creds.json")
        try:
            with open(creds_path, encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError as e:
            raise RuntimeError(
                "Missing GCP_SA_KEY GitHub secret or local creds.json file."
            ) from e
        sa_key = data.get("gcp_sa_key")
        sheet_id = sheet_id or data.get("sheet_id")

    if not sa_key:
        raise RuntimeError("Missing Google service account JSON in GCP_SA_KEY or creds.json.")
    if not sheet_id:
        raise RuntimeError("Missing required environment variable: SHEET_ID")

    return sa_key, sheet_id


def get_garmin_client(email: str, password: str) -> Garmin:
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


def has_meaningful_data(data: dict) -> bool:
    """เช็คว่ามีข้อมูล meaningful อย่างน้อย 1 ตัว (ไม่ใส่นาฬิกา = null ทั้งหมด)"""
    for key in MEANINGFUL_KEYS:
        if data.get(key) is not None:
            return True
    return False


def is_duplicate(ws, new_data: dict) -> bool:
    """เช็คว่าข้อมูลใหม่เหมือนกับแถวสุดท้ายใน sheet หรือไม่ (dedup)"""
    try:
        all_rows = ws.get_all_values()
        if len(all_rows) < 2:
            return False  # ยังไม่มีข้อมูล → ไม่ซ้ำ

        last_row = all_rows[-1]  # แถวสุดท้าย
        header_row = all_rows[0]

        # สร้าง dict จากแถวสุดท้าย
        last_data = {}
        for i, key in enumerate(header_row):
            if key in DEDUP_KEYS:
                val = last_row[i] if i < len(last_row) else None
                # แปลง string → number ถ้าเป็นไปได้
                if val is not None and val != "":
                    try:
                        val = float(val) if "." in str(val) else int(val)
                    except (ValueError, TypeError):
                        pass
                last_data[key] = val

        # เปรียบเทียบทุก key
        for key in DEDUP_KEYS:
            new_val = new_data.get(key)
            old_val = last_data.get(key)
            # แปลง type ให้เหมือนกันก่อนเทียบ
            if new_val is None and (old_val is None or old_val == "" or old_val == "null"):
                continue
            if new_val is not None and old_val is not None:
                try:
                    if float(new_val) == float(old_val):
                        continue
                except (ValueError, TypeError):
                    if str(new_val) == str(old_val):
                        continue
            # ถ้าไม่ตรงกัน → ไม่ใช่ duplicate
            return False

        return True  # ทุก key ตรงกัน → duplicate

    except Exception as e:
        log.warning("dedup check failed: %s", e)
        return False  # ถ้าเช็คไม่ได้ → เขียนไปเลย (ปลอดภัยกว่า)


def get_sheet(sa_key: dict, sheet_id: str):
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
    email, password = get_garmin_credentials()
    sa_key, sheet_id = load_sheet_config()
    ws = get_sheet(sa_key, sheet_id)
    client = get_garmin_client(email, password)

    log.info("กำลังดึงข้อมูล Garmin วันนี้ ...")
    data = fetch_today(client)

    # ── Check 1: มีข้อมูล meaningful หรือไม่ ──
    if not has_meaningful_data(data):
        log.info("No meaningful data (body_battery, steps, hrv = null) — ข้าม ไม่เขียน sheet")
        log.info("ยังไม่ใส่ Garmin หรือยังไม่มีข้อมูลวันนี้ — จะลองใหม่ในรอบถัดไป (15 นาที)")
        return

    # ── Check 2: Dedup — ข้อมูลซ้ำกับแถวสุดท้ายหรือไม่ ──
    if is_duplicate(ws, data):
        log.info("ข้อมูลเหมือนกับแถวสุดท้าย — ข้าม (dedup)")
        return

    # ── เขียนข้อมูลใหม่ ──
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    row = [ts] + [data.get(k) for k in HEADERS[1:]]

    log.info("Row: %s", row)
    ws.append_row(row, value_input_option="USER_ENTERED")
    log.info("เขียน Google Sheets สำเร็จ — body_battery=%s, steps=%s, hrv=%s",
             data.get("body_battery"), data.get("steps"), data.get("hrv_last_night"))


if __name__ == "__main__":
    try:
        main()
    except GarminConnectAuthenticationError as e:
        message = f"Garmin authentication failed: {e}"
        log.error(message)
        emit_github_error(message)
        sys.exit(1)
    except Exception as e:
        log.error("%s", e)
        emit_github_error(str(e))
        sys.exit(1)
