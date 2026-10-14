"""Read-only smoke test of a running server plus an unsaved synthetic job."""
import json
import sys
import time
from urllib.request import Request, urlopen

base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8001"
for path in ("/health", "/", "/app.js", "/live.js", "/style.css", "/api/catalog"):
    with urlopen(base + path, timeout=10) as response:
        assert response.status == 200, path
    print(f"OK {path}")
request = Request(base + "/api/jobs", data=json.dumps(dict(source="demo", start="2025-01-01", end="2025-01-31", strategy="buyhold")).encode(), headers={"Content-Type": "application/json"})
with urlopen(request, timeout=10) as response:
    identifier = json.load(response)["id"]
for _ in range(100):
    with urlopen(base + "/api/jobs/" + identifier, timeout=10) as response:
        job = json.load(response)
    if job["state"] not in {"queued", "running"}:
        break
    time.sleep(0.1)
assert job["state"] == "complete", job
assert job["result"]["demo"] and "experiment_id" not in job["result"]
print("OK unsaved synthetic research job")
