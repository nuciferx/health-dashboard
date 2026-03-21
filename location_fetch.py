"""
location_fetch.py — ดึง Google Maps Timeline ผ่าน Data Portability API
ติดตั้ง: pip install google-auth-oauthlib google-api-python-client
รัน:     python location_fetch.py
"""
import os
import sys
import io
import json
import time
import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
except ImportError:
    print("กรุณาติดตั้ง: pip install google-auth-oauthlib google-api-python-client")
    sys.exit(1)

# ── Config ──────────────────────────────────────────────────────
SCOPES = [
    "https://www.googleapis.com/auth/dataportability.maps.timeline",
]
CLIENT_SECRETS = "client_secrets.json"
TOKEN_FILE     = "location_token.json"
OUTPUT_FILE    = "data/location_history.json"


# ── Auth ────────────────────────────────────────────────────────
def get_credentials() -> Credentials:
    creds = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
        print("บันทึก token แล้ว")

    return creds


# ── Request Archive ─────────────────────────────────────────────
def request_location_archive(service) -> str:
    print("กำลังส่ง request ดึง Location History ...")
    body = {
        "resources": [
            "myactivity.maps",
            "maps.commute_routes",
            "maps.ev_profile",
            "maps.offering_contributions",
            "maps.photos_videos",
            "maps.questions_answers",
            "maps.reviews",
            "maps.starred_places",
            "maps.timeline",
        ]
    }
    try:
        response = service.portabilityArchive().initiate(body=body).execute()
        job_id = response.get("archiveJobId")
        print(f"Job ID: {job_id}")
        return job_id
    except Exception as e:
        print(f"Error initiating archive: {e}")
        # ลอง minimal request
        try:
            body = {"resources": ["maps.timeline"]}
            response = service.portabilityArchive().initiate(body=body).execute()
            job_id = response.get("archiveJobId")
            print(f"Job ID (minimal): {job_id}")
            return job_id
        except Exception as e2:
            print(f"Error (minimal): {e2}")
            return None


# ── Poll Status ─────────────────────────────────────────────────
def wait_for_archive(service, job_id: str, timeout: int = 300) -> list:
    print("รอ archive สร้างเสร็จ ...")
    start = time.time()

    while time.time() - start < timeout:
        try:
            state = service.archiveJobs().getPortabilityArchiveState(
                name=f"archiveJobs/{job_id}"
            ).execute()

            status = state.get("state", "UNKNOWN")
            print(f"  Status: {status}")

            if status == "COMPLETE":
                urls = state.get("urls", [])
                print(f"  ได้ {len(urls)} ไฟล์")
                return urls
            elif status in ("FAILED", "CANCELLED"):
                print(f"  Archive {status}")
                return []

        except Exception as e:
            print(f"  Error polling: {e}")

        time.sleep(10)

    print("Timeout รอนานเกิน")
    return []


# ── Download & Parse ────────────────────────────────────────────
def download_and_parse(urls: list) -> list:
    import urllib.request
    import zipfile
    import tempfile

    all_visits = []

    for url in urls:
        print(f"กำลังดาวน์โหลด ...")
        try:
            with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
                urllib.request.urlretrieve(url, tmp.name)
                tmp_path = tmp.name

            with zipfile.ZipFile(tmp_path, "r") as z:
                for name in z.namelist():
                    if "Timeline" in name and name.endswith(".json"):
                        print(f"  อ่านไฟล์: {name}")
                        with z.open(name) as f:
                            data = json.load(f)
                            visits = parse_timeline(data)
                            all_visits.extend(visits)

            os.unlink(tmp_path)
        except Exception as e:
            print(f"  Error: {e}")

    return all_visits


def parse_timeline(data: dict) -> list:
    """แปลง Timeline JSON เป็น list of place visits"""
    visits = []
    objects = data.get("timelineObjects", [])

    for obj in objects:
        if "placeVisit" in obj:
            pv   = obj["placeVisit"]
            loc  = pv.get("location", {})
            dur  = pv.get("duration", {})

            start = dur.get("startTimestamp", "")
            end   = dur.get("endTimestamp", "")

            if start and end:
                start_dt = datetime.datetime.fromisoformat(start.replace("Z", "+00:00"))
                end_dt   = datetime.datetime.fromisoformat(end.replace("Z", "+00:00"))
                # แปลงเป็น Bangkok time (UTC+7)
                bkk = datetime.timezone(datetime.timedelta(hours=7))
                start_bkk = start_dt.astimezone(bkk)
                end_bkk   = end_dt.astimezone(bkk)

                visits.append({
                    "type":      "place",
                    "date":      start_bkk.strftime("%Y-%m-%d"),
                    "name":      loc.get("name", "Unknown"),
                    "address":   loc.get("address", ""),
                    "arrive":    start_bkk.strftime("%H:%M"),
                    "leave":     end_bkk.strftime("%H:%M"),
                    "duration_min": round((end_dt - start_dt).total_seconds() / 60),
                    "lat":       loc.get("latitudeE7", 0) / 1e7,
                    "lng":       loc.get("longitudeE7", 0) / 1e7,
                })

        elif "activitySegment" in obj:
            seg = obj["activitySegment"]
            dur = seg.get("duration", {})
            start = dur.get("startTimestamp", "")
            end   = dur.get("endTimestamp", "")

            if start and end:
                start_dt = datetime.datetime.fromisoformat(start.replace("Z", "+00:00"))
                end_dt   = datetime.datetime.fromisoformat(end.replace("Z", "+00:00"))
                bkk      = datetime.timezone(datetime.timedelta(hours=7))

                visits.append({
                    "type":         "transit",
                    "date":         start_dt.astimezone(bkk).strftime("%Y-%m-%d"),
                    "activity":     seg.get("activityType", "UNKNOWN"),
                    "depart":       start_dt.astimezone(bkk).strftime("%H:%M"),
                    "arrive":       end_dt.astimezone(bkk).strftime("%H:%M"),
                    "duration_min": round((end_dt - start_dt).total_seconds() / 60),
                    "distance_m":   seg.get("distance", 0),
                })

    return visits


# ── Main ────────────────────────────────────────────────────────
def main():
    print("=" * 55)
    print("  Google Maps Timeline Fetcher")
    print("=" * 55)

    creds   = get_credentials()
    service = build("dataportability", "v1", credentials=creds)

    job_id = request_location_archive(service)
    if not job_id:
        print("ไม่สามารถสร้าง archive ได้")
        sys.exit(1)

    urls = wait_for_archive(service, job_id)
    if not urls:
        print("ไม่ได้รับไฟล์")
        sys.exit(1)

    visits = download_and_parse(urls)

    os.makedirs("data", exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(visits, f, ensure_ascii=False, indent=2)

    print(f"\nเสร็จ! บันทึก {len(visits)} รายการ → {OUTPUT_FILE}")

    # สรุปเบื้องต้น
    places   = [v for v in visits if v["type"] == "place"]
    transits = [v for v in visits if v["type"] == "transit"]
    print(f"  สถานที่: {len(places)} แห่ง")
    print(f"  การเดินทาง: {len(transits)} ช่วง")

    if places:
        print("\n5 สถานที่ล่าสุด:")
        for p in sorted(places, key=lambda x: x["date"], reverse=True)[:5]:
            print(f"  {p['date']} {p['arrive']}-{p['leave']} | {p['name']}")


if __name__ == "__main__":
    main()
