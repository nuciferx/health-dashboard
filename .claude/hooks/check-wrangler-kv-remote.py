#!/usr/bin/env python3
"""PreToolUse(Bash) hook — kaizen 2026-06-22: KV --remote gotcha.

`wrangler kv key get/list/put ...` defaults to the LOCAL miniflare store, which
holds stale/test data different from the production KV the live worker uses.
Reading without --remote once caused a wrong conclusion ("user didn't submit /done")
when the records existed in production all along.

This hook BLOCKS any `wrangler kv` command that doesn't explicitly choose a store
(--remote / --local / --preview), forcing a conscious decision every time.
Escape hatch: add --local if you really mean the local store.
"""
import sys
import json
import re

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)  # unparseable input -> don't interfere

cmd = (data.get("tool_input") or {}).get("command", "") or ""

# Only gate wrangler kv commands
if re.search(r"wrangler\s+kv", cmd):
    if not re.search(r"--(remote|local|preview)\b", cmd):
        reason = (
            "wrangler kv อ่าน/เขียน LOCAL store เป็นค่าเริ่มต้น (ไม่ใช่โปรดักชันที่ worker ใช้จริง). "
            "เติม --remote เพื่อแตะข้อมูลจริง หรือ --local ถ้าตั้งใจใช้ local. "
            "[เกณฑ์ kaizen 2026-06-22: KV --remote gotcha]"
        )
        out = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }
        print(json.dumps(out, ensure_ascii=False))
        sys.exit(0)

sys.exit(0)
