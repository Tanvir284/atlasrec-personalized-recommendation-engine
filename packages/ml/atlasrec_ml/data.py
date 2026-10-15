from __future__ import annotations

import csv
import gzip
import hashlib
import html
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import numpy as np

PARSER_VERSION = "amazon-real-v3"
CATEGORIES = ["Audio", "Workspace", "Home", "Outdoors", "Wellness"]
NAMES = [
    ["Studio headphones", "Pocket speaker", "Wireless earbuds", "Record player"],
    ["Task lamp", "Mechanical keyboard", "Canvas organizer", "Desk clock"],
    ["Pour-over kettle", "Ceramic mug", "Linen throw", "Oak shelf"],
    ["Trail backpack", "Steel water bottle", "Camping lantern", "Picnic blanket"],
    ["Yoga mat", "Travel diffuser", "Sleep mask", "Fitness band"],
]


@dataclass
class Dataset:
    products: list[dict]
    events: list[dict]
    manifest: dict

    def save(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.__dict__, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path):
        return cls(**json.loads(path.read_text(encoding="utf-8")))


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def demo(seed=42, products=200, users=100, interactions=3000) -> Dataset:
    if products < len(CATEGORIES) or users < 1 or interactions < 1:
        raise ValueError("Demo data requires at least five products, one user and one interaction")
    rng = np.random.default_rng(seed)
    items = []
    for i in range(products):
        c = i % len(CATEGORIES)
        items.append({
            "id": f"demo-{i:04d}", "title": NAMES[c][(i // 5) % 4] + f" · {i // 20 + 1}",
            "category": CATEGORIES[c], "description": (
                f"A thoughtfully designed {NAMES[c][(i // 5) % 4].lower()} for everyday "
                f"{CATEGORIES[c].lower()}. Durable materials, considered details."
            ), "price": round(float(rng.uniform(15, 190)), 2), "currency": "USD",
            "image": f"/products/{c}.svg", "available": True,
        })
    pref = rng.dirichlet([0.22] * 5, users)
    events = []
    for n in range(interactions):
        u = int(rng.integers(users))
        c = int(rng.choice(5, p=pref[u]))
        pool = np.arange(c, products, 5)
        # Skew plus repeated users and overlapping category-specific preferences.
        p = 1 / np.power(np.arange(len(pool)) + 2, 0.45)
        i = int(rng.choice(pool, p=p / p.sum()))
        positive = rng.random() < 0.88
        events.append({
            "id": f"synthetic-{seed}-{n}", "user": f"synthetic-{u:04d}",
            "item": items[i]["id"], "rating": int(rng.integers(4, 6) if positive else 2),
            "timestamp": 1704067200 + n * 1800, "kind": "synthetic_review",
        })
    manifest = {
        "profile": "demo", "synthetic": True, "seed": seed, "user_count": users, "parser": "demo-v2",
        "source": "deterministic generator", "row_count": len(events),
        "product_count": len(items), "rejected": 0,
        "timestamp_range": [events[0]["timestamp"], events[-1]["timestamp"]],
    }
    manifest["dataset_id"] = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()[:16]
    return Dataset(items, events, manifest)


def jsonl(path: Path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as f:
        for line in f:
            try:
                yield json.loads(line)
            except (ValueError, TypeError):
                yield None


def review_rows(path: Path, source_format: str):
    if source_format != "amazon2018_ratings":
        yield from jsonl(path)
        return
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as stream:
        for row in csv.reader(stream):
            if len(row) != 4:
                yield None
                continue
            item, user, rating, timestamp = row
            yield {"asin": item, "reviewerID": user, "overall": rating,
                   "unixReviewTime": timestamp}


def clean_text(value, limit=20000):
    if isinstance(value, list):
        value = " ".join(clean_text(part, limit) for part in value)
    if not isinstance(value, str):
        return ""
    value = html.unescape(value)
    value = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", value,
                   flags=re.IGNORECASE | re.DOTALL)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()[:limit]


def product_image(row):
    """Use only source product photography; do not substitute drawn demo products."""
    images = row.get("images", [])
    candidates = []
    if isinstance(images, list):
        main_first = sorted((x for x in images if isinstance(x, dict)),
                            key=lambda x: x.get("variant") != "MAIN")
        for entry in main_first:
            candidates.extend(entry.get(key) for key in ("hi_res", "large", "thumb"))
    for key in ("imageURLHighRes", "imageURL", "imUrl"):
        values = row.get(key, [])
        candidates.extend(values if isinstance(values, list) else [values])
    allowed = {"m.media-amazon.com", "images-na.ssl-images-amazon.com",
               "images-eu.ssl-images-amazon.com", "ecx.images-amazon.com"}
    for value in candidates:
        if not isinstance(value, str) or len(value) > 500:
            continue
        parsed = urlparse(value.strip())
        if parsed.scheme in ("http", "https") and parsed.hostname in allowed and not parsed.username:
            return parsed._replace(scheme="https").geturl()
    return ""


def product_category(row, default):
    categories = row.get("category") or row.get("categories")
    if isinstance(categories, list) and categories:
        if isinstance(categories[0], list):
            categories = categories[0]
        # Retain a shopper-useful category below the source domain when available.
        for category in categories[1:] or categories:
            text = clean_text(category, 100)
            if text and text.lower() not in {"beauty & personal care", "luxury beauty", "all beauty"}:
                return text
    return clean_text(row.get("main_category"), 100) or default.replace("_", " ")[:100]


def research(config: dict) -> Dataset:
    review = Path(config["reviews_path"])
    metadata = Path(config["metadata_path"])
    if not review.is_file() or not metadata.is_file():
        raise FileNotFoundError("Research requires official local review AND metadata files; see DATA_CARD.")
    seed = config.get("seed", 42)
    source_format = config.get("source_format", "amazon2023")
    if source_format not in ("amazon2023", "amazon2018", "amazon2018_ratings"):
        raise ValueError("Unsupported research source_format")
    legacy = source_format.startswith("amazon2018")
    complete = config.get("require_complete_histories", False)
    min_history = int(config.get("min_train_user_positives", 0))
    if min_history and not complete:
        raise ValueError("Training-history cohort selection requires complete source scanning")
    fraction = config.get("user_sample_fraction", 0.2)
    if not 0 < fraction <= 1:
        raise ValueError("user_sample_fraction must be in (0, 1]")
    events, seen, ids = [], set(), set()
    rejected = scanned = duplicates = 0
    for scanned, row in enumerate(review_rows(review, source_format), 1):
        if scanned > config.get("max_scan_rows", 200000):
            if complete:
                raise ValueError("Source exceeds max_scan_rows; no incomplete user histories accepted")
            scanned -= 1
            break
        try:
            if legacy and isinstance(row, dict):
                row = {"user_id": row.get("reviewerID"), "parent_asin": row.get("asin"),
                       "timestamp": float(row.get("unixReviewTime", 0)) * 1000,
                       "rating": row.get("overall")}
            if (not isinstance(row, dict) or
                    not isinstance(row.get("user_id"), str) or not row["user_id"].strip() or
                    not isinstance(row.get("parent_asin"), str) or not row["parent_asin"].strip()):
                raise ValueError("missing or invalid ID")
            raw_user = row["user_id"]
            selected = int(hashlib.sha256(f"{seed}:{raw_user}".encode()).hexdigest()[:8], 16) / 2**32
            # A train-only cohort needs boundaries from the complete source first.
            if not min_history and selected >= fraction:
                continue
            user = hashlib.sha256(raw_user.encode()).hexdigest()[:24]
            item = str(row["parent_asin"])
            ts = int(row["timestamp"]) / 1000
            rating = float(row["rating"])
            if not 1 <= rating <= 5 or not 820454400 <= ts <= 4102444800:
                raise ValueError("invalid timestamp/rating")
            key = (user, item, ts)
            if key in seen:
                duplicates += 1
                continue
            seen.add(key)
            events.append({"id": hashlib.sha256(str(key).encode()).hexdigest(), "user": user,
                           "item": item, "timestamp": ts, "rating": rating, "kind": "imported_review"})
            ids.add(item)
        except (ValueError, TypeError, KeyError):
            rejected += 1
        if not complete and len(events) >= config.get("max_interactions", 100000):
            break
    source_rows = len(events)
    boundaries = None
    source_users = len({e["user"] for e in events})
    if min_history:
        if len(events) < 100:
            raise ValueError("Insufficient source events for training-only cohort selection")
        boundaries = np.quantile([e["timestamp"] for e in events], [0.7, 0.85]).tolist()
        train_histories = defaultdict(set)
        threshold = config.get("positive_threshold", 4)
        for event in events:
            if event["timestamp"] < boundaries[0] and event["rating"] >= threshold:
                train_histories[event["user"]].add(event["item"])
        cohort = {user for user, history in train_histories.items() if len(history) >= min_history}
        # Hash pseudonymous IDs consistently; never use validation/test activity to select users.
        cohort = {user for user in cohort if
                  int(hashlib.sha256(f"{seed}:{user}".encode()).hexdigest()[:8], 16) / 2**32 < fraction}
        events = [event for event in events if event["user"] in cohort]
        ids = {event["item"] for event in events}
    if complete and len(events) > config.get("max_interactions", 100000):
        raise ValueError("Complete selected histories exceed max_interactions; lower user_sample_fraction")
    products = {}
    meta_rejected = 0
    # Stream the metadata file, retaining only selected parent IDs.
    for row in jsonl(metadata):
        if not isinstance(row, dict):
            meta_rejected += 1
            continue
        item = row.get("asin") if legacy else row.get("parent_asin")
        if not isinstance(item, str):
            meta_rejected += 1
            continue
        if item not in ids:
            continue
        price = row.get("price")
        try:
            if isinstance(price, str):
                # Ranges and non-USD text remain missing; do not invent an endpoint price.
                price = price.strip().removeprefix("$").replace(",", "")
            price = float(price) if price is not None else None
        except (ValueError, TypeError):
            price = None
        if price is not None and (not np.isfinite(price) or price < 0):
            price = None
        description = clean_text([row.get("description", ""), row.get("feature", row.get("features", []))])
        title = clean_text(row.get("title"), 500)
        products[item] = {"id": item, "title": title or item,
                          "description": description, "category": product_category(row, config["category"]),
                          "price": price, "currency": "USD" if price is not None else None,
                          "image": product_image(row), "available": True}
    missing = len(ids - products.keys())
    for item in ids - products.keys():
        products[item] = {"id": item, "title": item, "category": "Unknown",
                          "description": "", "price": None, "currency": None,
                          "image": "", "available": True}
    events.sort(key=lambda e: (e["timestamp"], e["id"]))
    if len(events) < 100:
        raise ValueError("Insufficient accepted data for a meaningful chronological benchmark.")
    manifest = {
        "profile": "research", "synthetic": False, "category": config["category"],
        "source_dataset": "Amazon Reviews 2018" if legacy else "Amazon Reviews 2023",
        "source_format": source_format,
        "source": config["source_url"], "terms": config["terms_url"],
         "retrieved_at": config.get("retrieved_at"), "imported_at": datetime.now(timezone.utc).isoformat(), "parser": PARSER_VERSION,
        "files": {str(p): digest(p) for p in (review, metadata)},
        "sampling": {"method": "training-history cohort then complete hashed-user histories" if min_history else
                     ("complete hashed-user histories" if complete else "hash user within bounded file prefix"),
                     "fraction": fraction, "seed": seed, "scan_cap": config.get("max_scan_rows", 200000),
                     "complete_histories": complete, "min_train_user_positives": min_history,
                     "source_accepted_rows": source_rows, "source_users": source_users,
                     "selection_bias": "Established reviewers with sufficient positive training history; not all shoppers"
                     if min_history else "Hash user sampling; bounded prefixes may bias/truncate histories"},
        "row_count": len(events), "scanned": scanned, "rejected": rejected,
        "duplicates": duplicates, "missing_metadata": missing, "meta_rejected": meta_rejected,
        "product_count": len(products),
        "user_count": len({e["user"] for e in events}),
        "products_with_source_photo": sum(bool(p["image"]) for p in products.values()),
        "price_semantics": "USD at source crawl time; archived price, not a current offer",
        "interaction_semantics": "Real historical reviewer ratings; not purchases, exposures or app customer accounts",
        "timestamp_range": [events[0]["timestamp"], events[-1]["timestamp"]],
    }
    if boundaries:
        manifest["temporal_boundaries"] = boundaries
        manifest["boundary_population"] = "Full accepted source before training-only user cohort selection"
    download_manifest = review.parent / "downloads.json"
    if download_manifest.exists():
        manifest["retrieved_at"] = json.loads(download_manifest.read_text())["retrieved_at"]
    identity = {k: v for k, v in manifest.items() if k not in ("retrieved_at", "imported_at")}
    manifest["dataset_id"] = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:16]
    return Dataset(list(products.values()), events, manifest)


def temporal_split(data: Dataset, threshold=4):
    times = [e["timestamp"] for e in data.events]
    a, b = data.manifest.get("temporal_boundaries", np.quantile(times, [0.7, 0.85]))
    return {
        "train": [e for e in data.events if e["timestamp"] < a],
        "validation": [e for e in data.events if a <= e["timestamp"] < b],
        "test": [e for e in data.events if e["timestamp"] >= b],
        "boundaries": [float(a), float(b)], "positive_threshold": threshold,
        "split_id": hashlib.sha256(f"{data.manifest['dataset_id']}:{a}:{b}:{threshold}".encode()).hexdigest()[:16],
    }


def history_before(events, timestamp, user, threshold=4):
    return list(dict.fromkeys(e["item"] for e in events if e["user"] == user
                             and e["timestamp"] < timestamp and e["rating"] >= threshold))
