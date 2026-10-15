"""Verify repaired behavior against the running PostgreSQL/Redis API."""
import json
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from http.cookiejar import CookieJar
from pathlib import Path

from atlasrec_api.db import Event, Favorite, RecommendationRequest, SessionLocal, User, engine
from sqlalchemy import func, inspect, select

BASE = "http://127.0.0.1:8000/api/v1"
jar = CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
csrf = None


def call(path, method="GET", body=None):
    headers = {"origin": "http://localhost:3000"}
    if method != "GET":
        headers.update({"x-csrf-token": csrf or "", "content-type": "application/json"})
    request = urllib.request.Request(BASE + path, method=method, headers=headers,
                                    data=json.dumps(body).encode() if body is not None else None)
    with opener.open(request, timeout=45) as response:
        return json.load(response)


csrf = call("/auth/csrf")["csrf_token"]
email = "bug-audit-" + uuid.uuid4().hex[:12] + "@example.com"
registered = call("/auth/register", "POST", {"email": email, "name": "Bug Audit", "password": "AuditOwner!2026"})
csrf = registered["csrf_token"]
user_id = registered["user"]["id"]
cookie_header = "; ".join(cookie.name + "=" + cookie.value for cookie in jar)


def save(item):
    request = urllib.request.Request(BASE + "/favorites/" + item, method="PUT",
        headers={"origin": "http://localhost:3000", "x-csrf-token": csrf, "cookie": cookie_header})
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.status


with ThreadPoolExecutor(max_workers=8) as pool:
    statuses = list(pool.map(save, ["demo-0000"] * 4 + ["demo-0001"] * 2 + ["demo-0002"] * 2))
assert statuses == [200] * 8
with SessionLocal() as db:
    favorites = db.scalar(select(func.count()).select_from(Favorite).where(Favorite.user_id == user_id))
    favorite_events = db.scalar(select(func.count()).select_from(Event).where(Event.user_id == user_id, Event.kind == "favorite"))
    revision = db.get(User, user_id).history_revision
assert favorites == favorite_events == revision == 3

rec = call("/recommendations")
item = rec["items"][0]["id"]
rating_results = []
for rating in (1, 5, 3):
    rating_results.append(call("/events", "POST", {"id": str(uuid.uuid4()), "item_id": item, "kind": "rating",
        "rating": rating, "surface": "bug-audit", "request_id": rec["request_id"], "position": 0}))
assert all(not result["duplicate"] for result in rating_results)
before = call("/me")["user"]["history_revision"]
call("/events", "POST", {"id": str(uuid.uuid4()), "item_id": item, "kind": "view", "surface": "bug-audit"})
assert call("/me")["user"]["history_revision"] == before + 1

for cookie in list(jar):
    if cookie.name == "atlas_csrf":
        jar.clear(cookie.domain, cookie.path, cookie.name)
csrf = call("/auth/csrf")["csrf_token"]
call("/me/preferences", "PUT", {"categories": ["Audio"]})
assert call("/me")["user"]["id"] == user_id
call("/recommendations")
cached = call("/recommendations")
with SessionLocal() as db:
    stored = db.get(RecommendationRequest, cached["request_id"])
    cache_hit = stored.cache_hit
    served_match = stored.item_ids == [product["id"] for product in cached["items"]]
    ratings = db.scalar(select(func.count()).select_from(Event).where(Event.user_id == user_id, Event.kind == "rating"))
assert cache_hit and served_match and ratings == 3
index = next(index for index in inspect(engine).get_indexes("interaction_events") if index["name"] == "event_exposure_unique")
predicate = str(index["dialect_options"]["postgresql_where"])
assert index["unique"] and all(kind in predicate for kind in ("view", "impression", "click"))
assert "rating" not in predicate
result = {"status": "passed", "user_id": user_id, "concurrent_save_statuses": statuses,
          "favorites": favorites, "favorite_events": favorite_events, "favorite_revision": revision,
          "revised_ratings_persisted": ratings, "view_invalidates_cache": True, "csrf_cookie_recovery": True,
          "cache_hit": cache_hit, "served_ids_match_record": served_match, "exposure_index_predicate": predicate}
path = Path("/app/docs/evidence/bug-audit-live.json")
path.write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result, indent=2))
