---
name: health-dev-loop
description: |
  One iteration of the Health-Dashboard Autonomous Dev Loop — pick the next queued item from BACKLOG.md, scope it, build it, test it (digest dry-run + node --check), learn from findings, ship (sync docs + commit master), update the roadmap. Designed to run continuously via `/loop /health-dev-loop` until BACKLOG is exhausted or a stop-condition halts it. Full-auto: commits to master without per-item review (no push, no deploy, no secret changes).

  Trigger phrases (Thai): "dev loop", "รันลูปพัฒนา", "ทำ backlog ต่อ", "วิ่ง loop", "พัฒนาต่อเอง", "ลุย backlog"
  Trigger phrases (English): "health dev loop", "run the dev loop", "autonomous loop", "keep building the backlog"

  Do NOT use for: a single targeted change (do it directly via GTM discipline), data analysis (use /health), or when the user wants to review each item before the next.
---

# /health-dev-loop — Autonomous Dev Loop (one iteration)

Goal: drive Health-Dashboard development item-by-item with no per-item human review, until `BACKLOG.md` is done or a stop-condition fires. **One invocation = one backlog item = one commit.** Run `/loop /health-dev-loop` for continuous operation.

ตอบไทยเสมอ · เดินตาม **GTM Infinite Loop** (CLAUDE.md → "Dev Operating Loop") เป็นวินัยเบื้องหลังทุกสเต็ป
Roadmap source of truth: `BACKLOG.md`. อ่านที่ step 1, เขียนที่ step 7 — ทุกรอบ

## The 8 steps (one iteration)

1. **PLAN** — อ่าน `BACKLOG.md`. เลือก item บนสุดใน Active queue ที่ `queued` และ `depends-on` เสร็จแล้ว. ถ้าไม่มี (queue + Discovered ว่าง) → emit `LOOP_DONE` แล้วหยุด. mark item เป็น `in-progress`.

2. **SCOPE** — ระบุไฟล์ที่จะแตะ + เช็ก 3 ด่าน:
   - **กระทบ "แผนวันนี้" หรือ Oura logic?** → ต้อง sync **2 ที่** (`morning_digest.py` dict ↔ `cf-worker/src/index.js` `/plan`,`/today`,`/week`). จดไว้ว่าต้องแก้คู่
   - **ต้องตั้ง/แก้ secret** (`gh secret set` / `wrangler secret put`)? → **STOP** → `LOOP_STOP_SECRET` (ห้ามแตะ secret อัตโนมัติ)
   - **คลุมเครือเชิงดีไซน์** (มีหลายทาง ต้องให้คนเลือก) → **STOP** → `LOOP_STOP_DESIGN`
   - ชัดเจน → ไปต่อ

3. **BUILD** — implement **item เดียว** ให้แคบสุด. รักษา behavior เดิมที่ไม่เกี่ยว. ถ้าเรียก Gemini ใหม่ = ต้องมี `usageLine` (กฎเสียเงินต้องโชว์ราคา). ถ้าจำเป็นต้องข้าม pre-release gate (deploy/secret) เพื่อให้งานเดิน → **STOP** → `LOOP_STOP_GATE`.

4. **TEST** — รัน gate จริงของโปรเจกต์:
   - `python morning_digest.py` → ต้อง **print dry-run ไม่ error** (ไม่ส่งจริง)
   - แตะ worker → `node --check cf-worker/src/index.js` ต้องผ่าน
   - แตะแผน → ยืนยันแก้ครบ **ทั้ง dict + worker** (อ่านซ้ำ 2 ที่ว่าตรงกัน)
   - fail → แก้ surgical **1 ครั้ง** · ยังไม่ผ่าน → **STOP** → `LOOP_STOP_TEST`

5. **LEARN** — ปัญหา/งานใหม่ที่เจอระหว่างทำ → เขียนลง `BACKLOG.md` → "Discovered backlog". มันจะกลายเป็นรอบถัดไปของ loop (นี่คือกลไก "เรียนรู้ → พัฒนาต่อ")

6. **SHIP** — lock condition แล้ว commit:
   - update `PROJECT_LOG.md` (section ตามวันที่: เปลี่ยนอะไร/ทำไม/test ผ่านอะไร/gap)
   - update `CLAUDE.md` ถ้าเปลี่ยนสถาปัตยกรรม/secret/ไฟล์ · update memory (`cm6-i2-training`/`morning-digest`) ถ้าเกี่ยว
   - **full-auto commit master** (`feat:`/`fix:` + co-author trailer). **ห้าม push · ห้าม `wrangler deploy` · ห้ามแตะ secret** — สิ่ง outward-facing เหล่านี้สรุปเป็น handoff ใน report ให้ผู้ใช้ทำเอง

7. **LOOP** — update `BACKLOG.md`: ย้าย item ไป Done พร้อม `<hash>`, รีเฟรช queue. emit `LOOP_ITERATION_DONE` (≤3 บรรทัด: ทำอะไรเสร็จ / test ผล / item ถัดไป + handoff ถ้ามี deploy/secret ค้าง). `/loop` จะเรียกรอบถัดไปเอง

## Stop conditions (หยุด · รายงาน · รอผู้ใช้)

| # | เงื่อนไข | Emit |
|---|---------|------|
| 1 | ต้องตั้ง/แก้ secret | `LOOP_STOP_SECRET` |
| 2 | คลุมเครือเชิงดีไซน์ ต้องให้คนเลือก | `LOOP_STOP_DESIGN` |
| 3 | ต้องข้าม pre-release gate (deploy/outward) งานถึงจะเดิน | `LOOP_STOP_GATE` |
| 4 | test (digest dry-run / node --check) แดงหลัง retry 1 ครั้ง | `LOOP_STOP_TEST` |
| 5 | BACKLOG queue + Discovered ว่างทั้งคู่ | `LOOP_DONE` |

ทุกครั้งที่หยุด: เขียนเหตุ + สถานะปัจจุบันลง report, **อย่าทำต่อ**. ผู้ใช้แก้แล้วรีสตาร์ต `/loop /health-dev-loop` เอง

## Rules

- 1 รอบ = 1 item = 1 commit. **ห้ามรวมหลาย item**
- full-auto commit master — แต่ทุก commit ต้องผ่าน gate (step 4) ก่อนเสมอ. build แดง = ไม่ commit
- **ห้าม** auto-push · auto-`wrangler deploy` · แตะ secret — เป็น outward-facing → handoff/STOP
- แตะแผน/Oura → sync 2 ที่เสมอ (dict + worker) ไม่งั้นถือว่า test ไม่ผ่าน
- เรียก Gemini ใหม่ = ต้องมี `usageLine` (กฎโชว์ราคา)
- `BACKLOG.md` คือแหล่งความจริงเดียว — อ่าน step 1, เขียน step 7 ทุกรอบ
- report ต่อรอบ ≤25 บรรทัด — loop รันหลายรอบ รายงานสั้นอ่านง่าย
