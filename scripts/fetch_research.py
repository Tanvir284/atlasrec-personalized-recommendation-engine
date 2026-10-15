"""Bounded official source downloader; no pretrained assets or synthetic substitution."""
import argparse
import hashlib
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SOURCES = {
    "Digital_Music.jsonl.gz": "https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/raw/review_categories/Digital_Music.jsonl.gz",
    "meta_Digital_Music.jsonl.gz": "https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/raw/meta_categories/meta_Digital_Music.jsonl.gz",
}
RETAIL_SOURCES = {
    "Luxury_Beauty.csv": "https://mcauleylab.ucsd.edu/public_datasets/data/amazon_v2/categoryFilesSmall/Luxury_Beauty.csv",
    "meta_Luxury_Beauty.json.gz": "https://mcauleylab.ucsd.edu/public_datasets/data/amazon_v2/metaFiles2/meta_Luxury_Beauty.json.gz",
}


def checksum(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--max-total-mb", type=int, default=100)
    p.add_argument("--timeout-seconds", type=int, default=180)
    p.add_argument("--dataset", choices=["digital-music-2023", "luxury-beauty-2018"], default="digital-music-2023")
    p.add_argument("--legacy-mirror", action="store_true", help="Use the author's public HTTP archive if the current HTTPS host is unavailable")
    args = p.parse_args()
    if args.max_total_mb < 1 or args.timeout_seconds < 1:
        p.error("Download size and time limits must be positive")
    sources = RETAIL_SOURCES if args.dataset == "luxury-beauty-2018" else SOURCES
    if args.legacy_mirror:
        if args.dataset != "luxury-beauty-2018":
            p.error("The legacy archive is available only for the 2018 dataset")
        sources = {name: url.replace("https://mcauleylab.ucsd.edu/public_datasets/", "http://jmcauley.ucsd.edu/")
                   for name, url in sources.items()}
    cap = args.max_total_mb * 1024**2
    headers = {"User-Agent": "AtlasRecResearch/0.1"}
    sizes = {}
    for name, url in sources.items():
        req = urllib.request.Request(url, headers=headers, method="HEAD")
        with urllib.request.urlopen(req, timeout=20) as response:
            length = response.headers.get("Content-Length")
            if not length:
                raise RuntimeError("Unknown download size; provide local files instead")
            sizes[name] = int(length)
    if sum(sizes.values()) > cap:
        raise RuntimeError(f"Expected {sum(sizes.values())} bytes exceeds configured total byte cap {cap}")
    print("Verified expected sizes:", sizes, flush=True)
    root = Path("data/research") / ("luxury-beauty-2018" if args.dataset == "luxury-beauty-2018" else "")
    root.mkdir(parents=True, exist_ok=True)
    provenance = {"retrieved_at": datetime.now(timezone.utc).isoformat(), "dataset": args.dataset, "files": {}}
    manifest_path = root / "downloads.json"
    previous = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    deadline = time.monotonic() + args.timeout_seconds
    for name, url in sources.items():
        path = root / name
        previous_file = previous.get("files", {}).get(name, {})
        reusable = (path.exists() and path.stat().st_size == sizes[name] and previous_file.get("url") == url
                    and checksum(path) == previous_file.get("sha256"))
        if reusable:
            print("Reuse local file", name, flush=True)
        else:
            partial = path.with_suffix(path.suffix + ".partial")
            offset = partial.stat().st_size if partial.exists() and partial.stat().st_size < sizes[name] else 0
            req = urllib.request.Request(url, headers={**headers, **({"Range": f"bytes={offset}-"} if offset else {})})
            total = offset
            with urllib.request.urlopen(req, timeout=min(60, args.timeout_seconds)) as response:
                if offset and (response.status != 206 or not response.headers.get("Content-Range", "").startswith(f"bytes {offset}-")):
                    raise RuntimeError("Source did not honor the requested resume range")
                with partial.open("ab" if offset else "wb") as f:
                    while chunk := response.read1(64 * 1024):
                        total += len(chunk)
                        if total > sizes[name] or total > cap or time.monotonic() > deadline:
                            raise RuntimeError("Download exceeded declared size, byte cap or time budget; incomplete file is not importable")
                        f.write(chunk)
                        if total // (1024 * 1024) != (total - len(chunk)) // (1024 * 1024):
                            print(name, total, "/", sizes[name], "bytes", flush=True)
            if total != sizes[name]:
                raise RuntimeError("Download length mismatch")
            partial.replace(path)
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        provenance["files"][name] = {"url": url, "bytes": sizes[name], "sha256": h.hexdigest()}
        print(name, sizes[name], h.hexdigest(), flush=True)
        manifest_path.write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    manifest_path.write_text(json.dumps(provenance, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
