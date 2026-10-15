import time
import urllib.error
import urllib.request

for _ in range(120):
    try:
        urllib.request.urlopen("http://localhost:8000/health/ready", timeout=2)
        urllib.request.urlopen("http://localhost:3000", timeout=2)
        break
    except (OSError, urllib.error.URLError):
        time.sleep(1)
else:
    raise SystemExit("API/web readiness timed out")
