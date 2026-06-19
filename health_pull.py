"""
health_pull.py — ดึงข้อมูล Oura หลายวันเป็น JSON สำหรับวิเคราะห์เชิงลึก (ใช้กับ /health)

รัน:   python health_pull.py [วันย้อนหลัง]   (default 14)
ออก:   JSON: {meta, days:[{date, readiness, sleep_score, sleep_h, hrv, rhr, temp_dev, ...}]}

Garmin ไม่รวมที่นี่ (ดึงจาก cloud ไม่ได้ + Strava ครอบคลุมกว่า) —
activity ใช้ Strava MCP ตอนวิเคราะห์
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ICT = timezone(timedelta(hours=7))
RACE = datetime(2026, 8, 8, tzinfo=ICT).date()


def oura(token, path, start, end):
    r = requests.get(
        f"https://api.ouraring.com/v2/usercollection/{path}",
        headers={"Authorization": f"Bearer {token}"},
        params={"start_date": start, "end_date": end},
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("data", [])


def main():
    token = os.environ.get("OURA_TOKEN")
    if not token:
        print(json.dumps({"error": "Missing OURA_TOKEN"}))
        sys.exit(1)

    days = int(sys.argv[1]) if len(sys.argv) > 1 else 14
    today = datetime.now(ICT).date()
    start = (today - timedelta(days=days)).isoformat()
    end = today.isoformat()

    rd = {x["day"]: x for x in oura(token, "daily_readiness", start, end)}
    ds = {x["day"]: x for x in oura(token, "daily_sleep", start, end)}
    stress = {x["day"]: x for x in oura(token, "daily_stress", start, end)}
    resil = {x["day"]: x for x in oura(token, "daily_resilience", start, end)}
    sl_raw = oura(token, "sleep", start, end)
    sl = {}
    for s in sl_raw:
        d = s.get("day")
        if d not in sl or (s.get("total_sleep_duration") or 0) > (sl[d].get("total_sleep_duration") or 0):
            sl[d] = s

    rows = []
    all_days = sorted(set(rd) | set(ds) | set(sl))
    for d in all_days:
        s = sl.get(d, {})
        dur = s.get("total_sleep_duration")
        rc = (rd.get(d) or {}).get("contributors") or {}
        sc = (ds.get(d) or {}).get("contributors") or {}
        rows.append({
            "date": d,
            "readiness": (rd.get(d) or {}).get("score"),
            "sleep_score": (ds.get(d) or {}).get("score"),
            "sleep_h": round(dur / 3600, 1) if dur else None,
            "hrv": s.get("average_hrv"),
            "rhr": s.get("lowest_heart_rate"),
            "resp": s.get("average_breath"),
            "efficiency": s.get("efficiency"),
            "temp_dev": (rd.get(d) or {}).get("temperature_deviation"),
            "stress": (stress.get(d) or {}).get("day_summary"),
            "resilience": (resil.get(d) or {}).get("level"),
            "rem_contrib": sc.get("rem_sleep"),
            "deep_contrib": sc.get("deep_sleep"),
            "recovery_idx": rc.get("recovery_index"),
            "hrv_balance": rc.get("hrv_balance"),
        })

    print(json.dumps({
        "meta": {
            "today": today.isoformat(),
            "days_to_race": (RACE - today).days,
            "race_date": RACE.isoformat(),
            "n_days": len(rows),
        },
        "days": rows,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
