"""
location_parse.py — parse Google Takeout Semantic Location History
วิธีใช้:
  1. ไปที่ https://takeout.google.com
  2. เลือกเฉพาะ "Location History (Timeline)" → Export once → Download ZIP
  3. แตก ZIP → copy โฟลเดอร์ Takeout/Location History/Semantic Location History/
     ไปไว้ที่ F:/ai/health-dashboard/data/semantic/
  4. รัน: py -3 location_parse.py

ผลลัพธ์: data/commute.json — รายวัน (ออกบ้านกี่โมง ถึงงานกี่โมง ฯลฯ)
"""
import os, sys, io, json, glob, datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BKK = datetime.timezone(datetime.timedelta(hours=7))

# ── กำหนดพิกัดบ้านและที่ทำงาน (แก้ให้ตรงกับของตัวเอง) ──
HOME_LAT   = 13.7563   # Bangkok default — แก้ด้วย
HOME_LNG   = 100.5018
WORK_LAT   = 13.7563
WORK_LNG   = 100.5018
RADIUS_KM  = 0.5       # รัศมี 500m ถือว่า "ถึงแล้ว"

INPUT_DIR  = "data/semantic"    # ไฟล์ .json จาก Takeout
OUTPUT     = "data/commute.json"


def dist_km(lat1, lng1, lat2, lng2):
    from math import radians, sin, cos, sqrt, atan2
    R = 6371
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1-a))


def is_home(lat, lng):
    return dist_km(lat, lng, HOME_LAT, HOME_LNG) <= RADIUS_KM


def is_work(lat, lng):
    return dist_km(lat, lng, WORK_LAT, WORK_LNG) <= RADIUS_KM


def parse_ts(ts: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(BKK)


def parse_file(path: str) -> list:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    events = []
    for obj in data.get("timelineObjects", []):
        if "placeVisit" in obj:
            pv  = obj["placeVisit"]
            loc = pv.get("location", {})
            dur = pv.get("duration", {})
            lat = loc.get("latitudeE7", 0) / 1e7
            lng = loc.get("longitudeE7", 0) / 1e7
            st  = dur.get("startTimestamp", "")
            et  = dur.get("endTimestamp", "")
            if not st or not et:
                continue

            start_dt = parse_ts(st)
            end_dt   = parse_ts(et)
            events.append({
                "type":    "place",
                "name":    loc.get("name", ""),
                "address": loc.get("address", ""),
                "lat": lat, "lng": lng,
                "arrive":  start_dt,
                "leave":   end_dt,
                "is_home": is_home(lat, lng),
                "is_work": is_work(lat, lng),
            })

        elif "activitySegment" in obj:
            seg = obj["activitySegment"]
            dur = seg.get("duration", {})
            st  = dur.get("startTimestamp", "")
            et  = dur.get("endTimestamp", "")
            if not st or not et:
                continue
            events.append({
                "type":       "transit",
                "activity":   seg.get("activityType", "UNKNOWN"),
                "depart":     parse_ts(st),
                "arrive":     parse_ts(et),
                "distance_m": seg.get("distance", 0),
            })

    return events


def build_commute(events: list) -> dict:
    """จากรายการ events → สรุปการเดินทางรายวัน"""
    by_day = {}
    for e in sorted(events, key=lambda x: x.get("arrive") or x.get("depart")):
        dt = (e.get("arrive") or e.get("depart"))
        if not dt:
            continue
        day = dt.strftime("%Y-%m-%d")
        by_day.setdefault(day, []).append(e)

    commute = {}
    for day, evs in by_day.items():
        rec = {"date": day}
        places = [e for e in evs if e["type"] == "place"]

        # หาเวลาออกบ้านครั้งแรก (leave home)
        home_leaves = [e["leave"] for e in places if e.get("is_home")]
        if home_leaves:
            rec["leave_home"] = min(home_leaves).strftime("%H:%M")

        # หาเวลาถึงงานครั้งแรก (arrive work)
        work_arrives = [e["arrive"] for e in places if e.get("is_work")]
        if work_arrives:
            rec["arrive_work"] = min(work_arrives).strftime("%H:%M")

        # หาเวลาออกงาน (leave work)
        work_leaves = [e["leave"] for e in places if e.get("is_work")]
        if work_leaves:
            rec["leave_work"] = max(work_leaves).strftime("%H:%M")

        # หาเวลาถึงบ้านครั้งสุดท้าย
        home_arrives = [e["arrive"] for e in places if e.get("is_home")]
        if home_arrives:
            rec["arrive_home"] = max(home_arrives).strftime("%H:%M")

        # commute time (นาที)
        if "leave_home" in rec and "arrive_work" in rec:
            lh = datetime.datetime.strptime(day + " " + rec["leave_home"], "%Y-%m-%d %H:%M")
            aw = datetime.datetime.strptime(day + " " + rec["arrive_work"], "%Y-%m-%d %H:%M")
            rec["commute_min"] = int((aw - lh).total_seconds() / 60)

        # สถานที่ที่ไปทั้งหมด (ไม่ใช่บ้านหรืองาน)
        others = [e["name"] for e in places if not e.get("is_home") and not e.get("is_work") and e.get("name")]
        if others:
            rec["places"] = list(dict.fromkeys(others))  # unique ตามลำดับ

        commute[day] = rec

    return commute


def main():
    # ค้นหาไฟล์ JSON ใน input dir
    pattern = os.path.join(INPUT_DIR, "**", "*.json")
    files = glob.glob(pattern, recursive=True)

    # ถ้าไม่มีโฟลเดอร์ semantic → ลองอ่านจาก data/ ตรงๆ
    if not files:
        files = glob.glob("data/semantic*.json") + \
                glob.glob("data/*Timeline*.json") + \
                glob.glob("data/2*.json")

    if not files:
        print(f"ไม่เจอไฟล์ JSON ใน {INPUT_DIR}/")
        print("วิธีดาวน์โหลด:")
        print("  1. ไปที่ https://takeout.google.com")
        print("  2. เลือก Location History (Timeline) → Export once")
        print("  3. แตก ZIP → วางโฟลเดอร์ Semantic Location History/ ไว้ที่ data/semantic/")
        return

    print(f"พบ {len(files)} ไฟล์")
    all_events = []
    for path in sorted(files):
        print(f"  อ่าน: {os.path.basename(path)}")
        try:
            all_events.extend(parse_file(path))
        except Exception as e:
            print(f"    Error: {e}")

    print(f"\nรวม events: {len(all_events)}")

    commute = build_commute(all_events)

    os.makedirs("data", exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(commute, f, ensure_ascii=False, indent=2)

    # สรุป
    days_with_work = [v for v in commute.values() if "arrive_work" in v]
    print(f"\nบันทึก {len(commute)} วัน → {OUTPUT}")
    print(f"วันที่มีข้อมูลไปทำงาน: {len(days_with_work)} วัน")

    if days_with_work:
        recent = sorted(days_with_work, key=lambda x: x["date"], reverse=True)[:7]
        print("\n7 วันล่าสุด:")
        for r in recent:
            ct = f"({r['commute_min']} นาที)" if "commute_min" in r else ""
            print(f"  {r['date']} | ออกบ้าน {r.get('leave_home','?')} → ถึงงาน {r.get('arrive_work','?')} {ct}")


if __name__ == "__main__":
    main()
