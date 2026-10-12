"""Read public RSS transport inside the deployed runtime; no DB or notification writes."""
import json
from time import monotonic
from urllib.parse import urlparse
from app.services import us_market

original_get = us_market.requests.get
probes = []

def observed_get(url, **kwargs):
    started = monotonic()
    try:
        response = original_get(url, **kwargs)
        probes.append({"host":urlparse(url).hostname, "language":(kwargs.get("params") or {}).get("hl"),
                       "status":response.status_code, "bytes":len(response.content),
                       "content_type":response.headers.get("content-type"),
                       "elapsed_seconds":round(monotonic()-started, 2)})
        return response
    except Exception as exc:
        probes.append({"host":urlparse(url).hostname, "error_type":type(exc).__name__,
                       "elapsed_seconds":round(monotonic()-started,2)})
        raise

us_market.requests.get = observed_get
payload = us_market.build_us_trends(days=7)
print(json.dumps({"status":payload["status"], "count":len(payload["timeline"]), "probes":probes}))
