# BACKLOG — Health Dashboard (roadmap แหล่งความจริงเดียวของ `/health-dev-loop`)

> `/health-dev-loop` อ่านไฟล์นี้ที่ step 1 (PLAN) และเขียนกลับที่ step 7 (LOOP) ทุกรอบ
> สถานะ: `queued` (รอทำ) · `in-progress` (กำลังทำ) · `✅ done <hash>` · `blocked` (ติด — ดูเหตุ)
> เลือกงาน: ตัวบนสุดที่ `queued` และ `depends-on` เสร็จแล้ว · ว่างหมด → `LOOP_DONE`

## Active queue

| # | งาน | สถานะ | depends-on | ไฟล์หลักที่จะแตะ | หมายเหตุ |
|---|-----|------|-----------|----------------|---------|
| B1 | `/done` เซฟ raw ก่อนเรียก Gemini (กัน Gemini พังแล้วการบ้านหาย+เงียบ) | queued | — | `cf-worker/src/index.js` | เจอในเซสชัน 2026-06-22 · ลำดับ: `STATS.put(hw)` raw → เรียก Gemini ใน try/catch → ตอบ error ถ้า comment ล้ม |
| B2 | Adherence: streak นับวันต่อเนื่อง (ต้อง KV) | queued | — | `morning_digest.py`, `cf-worker/src/index.js` | KV `streak:*` · โชว์ใน digest + `/week` |
| B3 | Adherence: check-back ✅/❌ รายวัน (เทียบแผน vs `/done`) | queued | B2 | `morning_digest.py`, `cf-worker/src/index.js` | ดึง `hw:<date>` มาเทียบ planFor → ✅/❌ ใน digest 7 วัน |
| B4 | Adherence: session-specific accountability (จับทำของง่ายข้ามของจำเป็น) | queued | B3 | `morning_digest.py` | ①⑤ ในงานวิจัย adherence |
| B5 | เปิดบันทึก meal data ถาวร (เลิกโหมดทดสอบ) → ฿/วัน + แคล/วัน เข้า digest/`/health` | queued | — | `cf-worker/src/index.js`, `morning_digest.py` | ตอนนี้ draft 6 ชม. · ต้อง KV `meal:<date>` · ระวัง outward-facing (เก็บข้อมูลจริง) → SCOPE ตรวจก่อน |

## Discovered backlog (งานที่ loop เจอระหว่างทำ — เติมที่ step 5 LEARN)

| # | งาน | สถานะ | จาก | หมายเหตุ |
|---|-----|------|-----|---------|
| D1 | worker `/today` parity: โชว์ deep/REM flag เหมือน digest | queued | B6 | ตอนนี้ digest-only (สอดคล้อง asymmetry เดิมที่ worker ไม่มี stress) · ทำเมื่ออยากให้ /today ครบ |
| D2 | ตัวแปรเหตุเพิ่ม: alcohol flag, late eating, HRV-dip กลางดึก | queued | B6 | ต้องหา data source ก่อน (Oura ไม่มีตรง ๆ) |
| D3 | คาลิเบรต DEEP_MIN/REM_MIN ตาม baseline นักกีฬา (ตอนนี้ fix 0.9/1.0h) | queued | B6 | อาจใช้ค่าเฉลี่ย 14 วันแทน absolute |

## Done (ล่าสุดอยู่บน)

| # | งาน | hash | วันที่ |
|---|-----|------|-------|
| B6 | flag deep/REM สั้น + หาเหตุ (stress/readiness) ใน digest | 05aac22 | 2026-06-22 |
| K0 | kaizen: KV `--remote` hook (poka-yoke) + GTM docs + รับ dev loop | 2026-06-22 | 2026-06-22 |
