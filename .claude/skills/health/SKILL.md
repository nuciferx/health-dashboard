---
name: health
description: "วิเคราะห์สุขภาพ+การซ้อม CM6 i2 เชิงลึก on-demand. Trigger (TH): \"/health\", \"เช็คสุขภาพ\", \"วิเคราะห์สุขภาพ\", \"ดูข้อมูลซ้อม\", \"สรุปสัปดาห์\", \"ควรซ้อมไหม\", \"readiness วันนี้\". Trigger (EN): \"/health\", \"health check\", \"analyze training\", \"should I train\". ดึง Oura(หลายวัน)+Strava(activity)+Garmin(local best-effort) → เทียบแผน 7 สัปดาห์ → ธงเตือน + คำแนะนำ + ปรับตาราง. ใช้สำหรับวิเคราะห์ลึก ไม่ใช่ digest รายวัน (อันนั้นคือ morning_digest.py อัตโนมัติ)"
---

# /health — วิเคราะห์สุขภาพ + การซ้อม CM6 i2 เชิงลึก (on-demand)

นี่คือส่วน "AI brain" ของระบบ — ใช้ตอนผู้ใช้อยากเจาะลึก/ตัดสินใจ/ปรับแผน
(digest รายเช้าอัตโนมัติเป็น rule-based แยกต่างหากที่ `morning_digest.py` — **อย่าทำซ้ำ**)

ตอบภาษาไทยเสมอ · บริบทนักกีฬา/แผนอยู่ใน memory `cm6-i2-training` + ไฟล์ `CM6_i2_*.md`

## ขั้นตอน

1. **ดึงข้อมูล** (เรียก subagent `health-analyst` ให้ทำ หรือทำเองถ้าเร็วกว่า):
   - **Oura:** `python health_pull.py 14` → readiness/sleep/HRV/RHR ย้อนหลัง (default 14 วัน; ขอมากกว่าได้)
   - **Strava (activity จริง):** ใช้ `mcp__claude_ai_Strava__list_activities` ดู session ล่าสุด แล้ว `get_activity_streams`/`get_activity_performance` เจาะ HR/elevation/pace ของ session ที่น่าสนใจ (เช่น long run, vertical)
   - **Garmin (optional):** `python morning_digest.py` ดึง activity ล่าสุดได้ถ้ารัน local (cloud จะ n/a) — ใช้ Strava เป็นหลัก

2. **อ่านแผน:** `CM6_i2_ตารางซ้อม.md` (แผนรายวัน) + memory เพื่อรู้สัปดาห์ปัจจุบัน/เป้า/จุดอ่อน

3. **วิเคราะห์ 4 ด้าน** เทียบเป้า:
   - 😴 **นอน/ฟื้นตัว:** trend นอน(เป้า 7ชม.) · HRV/RHR แนวโน้ม · readiness · temp_dev (ป่วย?)
   - 🏃 **โซนซ้อม:** session จริงคุม HR ≤150 ไหม (จุดอ่อนเรื้อรัง: pacing error avgHR สูง) · vertical speed (เป้า 550-650 ม/ชม @HR≤150, เดิม ~220)
   - ⚖️ **น้ำหนัก/โหลด:** trend ถ้ามีข้อมูล · training load สมดุลไหม
   - 📋 **เทียบแผน:** ทำตามตารางสัปดาห์นี้แค่ไหน · เหลือกี่วันถึงแข่ง

4. **สรุปแบบ actionable:**
   - สถานะรวม + ธงแดง/เขียวต่อด้าน (อ้างตัวเลขจริง)
   - **คำแนะนำที่ตัดสินใจได้** (เช่น "readiness 48 + วันนี้แผน interval → สลับเป็น Z2 เบา") — ไม่ใช่คำแนะนำกว้าง ๆ
   - ถ้าควรปรับตาราง → เสนอแก้ `CM6_i2_ตารางซ้อม.md` (และเตือนว่าต้องแก้ dict ใน `morning_digest.py` ด้วยถ้ากระทบ "แผนวันนี้")

## กฎ
- **อ้างตัวเลขจริงเสมอ** ห้ามแนะนำลอย ๆ — ดึงข้อมูลก่อนค่อยสรุป
- เคารพกฎ 5 ข้อของนักกีฬา (HR≤150 / น้ำ / เกลือแร่ / กิน / นอน — ดู CLAUDE.md)
- ถ้าเจอข้อมูลใหม่ที่ควรจำข้ามเซสชัน → อัปเดต memory `cm6-i2-training`
- ห้ามแก้ secret / push อัตโนมัติ — ถามก่อน

## คืนค่า
สรุปวิเคราะห์ 4 ด้าน + ธงเตือน + คำแนะนำตัดสินใจได้ (+ ข้อเสนอปรับตารางถ้ามี)
