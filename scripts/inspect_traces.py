import json
import zipfile
from pathlib import Path

for trace in Path("test-results").rglob("trace.zip"):
    print(str(trace.parent))
    with zipfile.ZipFile(trace) as z:
        for name in z.namelist():
            if name.endswith(".network"):
                events=[json.loads(line).get("snapshot",{}) for line in z.read(name).decode().splitlines()]
                rows=[(e.get("request",{}).get("method"),e.get("request",{}).get("url"),e.get("response",{}).get("status"),e.get("time")) for e in events if "/api/" in e.get("request",{}).get("url","")]
                print(rows[-18:])
