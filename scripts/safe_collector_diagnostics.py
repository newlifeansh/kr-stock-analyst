"""Redact infrastructure logs before writing diagnostic CI evidence."""
import json
import re
import sys

for line in sys.stdin:
    try:
        record = json.loads(line)
    except ValueError:
        continue
    message = str(record.get("message") or "")
    if re.search(r"secret|password|authorization|bearer|appkey|app_key|apikey|api_key|endpoint=|share_id|p256dh|vapid|access_token", message, re.I):
        continue
    message = re.sub(r"https?://\S+", "[URL]", message)
    message = re.sub(r"postgres(?:ql)?://\S+", "[DATABASE_URL]", message)
    print(json.dumps({"timestamp": record.get("timestamp"), "message": message[:1500]}, ensure_ascii=False))
