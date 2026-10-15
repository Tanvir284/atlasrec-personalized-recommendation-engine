"""Personalized recommendations.

Hot path, so it is written to touch as little data as possible:

* The catalog is read as two narrow columns (id, category) instead of hydrating every
  ``Product`` ORM row with its description; full rows are loaded only for the items
  actually returned (at most ``limit``).
* History is read as (item_id, kind, rating) tuples.
* Popularity back-fill uses a bounded heap rather than sorting the whole catalog.
"""
from __future__ import annotations

import heapq
import json
import time
import uuid
from typing import NamedTuple

import numpy as np
import redis
from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import func, select

from .. import cache
from ..common import actor_key, lookup_product, product_json
from ..db import Event, Product, RecommendationRequest, db_session
from ..lifecycle import active_bundle
from ..monitoring import log, observed_errors
from ..security import current_user, token_hash
from ..settings import settings

router = APIRouter(prefix="/api/v1", tags=["recommendations"])

CACHE_TTL_SECONDS = 120
UNCACHEABLE_FALLBACKS = ("model_unavailable", "model_inference_failed")
_CATALOG_CACHE: dict[tuple, tuple[float, tuple, dict[str, _Entry]]] = {}


def allowed_history(db, user):
    """Return (positive item ids, negative item ids) from the user's own events.

    Later explicit feedback overrides earlier signals; repeat views never undo a dismissal.
    """
    if not user:
        return [], []
    rows = db.execute(select(Event.item_id, Event.kind, Event.rating)
                      .where(Event.user_id == user.id, Event.profile == settings.profile)
                      .order_by(Event.created_at, Event.id)).all()
    signals = {}
    for item_id, kind, rating in rows:
        if kind in ("view", "click"):
            # Exploring again must not undo explicit negative or neutral feedback.
            signals.setdefault(item_id, "positive")
        elif kind == "favorite":
            signals[item_id] = "positive"
        elif kind == "dismiss":
            signals[item_id] = "negative"
        elif kind == "rating":
            signals[item_id] = "positive" if rating >= 4 else "negative" if rating <= 2 else "neutral"
    return ([item for item, signal in signals.items() if signal == "positive"],
            [item for item, signal in signals.items() if signal == "negative"])


class _Entry(NamedTuple):
    category: str
    title_key: str
    has_photo: bool
    price: float | None = None
    title: str = ""


def _title_key(title):
    return " ".join((title or "").lower().split())


def _available_catalog(db) -> dict[str, _Entry]:
    """Map id -> (category, normalized title, has photo, price, raw title) for servable products."""
    visible = (Product.profile == settings.profile, Product.available.is_(True))
    cache_key = (str(db.get_bind().url), settings.profile)
    now = time.monotonic()
    cached = _CATALOG_CACHE.get(cache_key)
    if cached and len(cached[2]) > 1000 and (now - cached[0]) < 5.0:
        return cached[2]
    sig = db.execute(
        select(
            func.count(),
            func.max(Product.id),
            func.min(Product.id),
            func.count(Product.price),
            func.max(Product.title),
            func.min(Product.image),
        ).where(*visible)
    ).one()
    if cached and len(cached[2]) > 1000 and cached[1] == sig:
        _CATALOG_CACHE[cache_key] = (now, sig, cached[2])
        return cached[2]
    rows = db.execute(select(Product.id, Product.category, Product.title, Product.image, Product.price).where(*visible)).all()
    result = {
        item: _Entry(category, _title_key(title), bool(image),
                     float(price) if price is not None else None, title or item)
        for item, category, title, image, price in rows
    }
    _CATALOG_CACHE[cache_key] = (now, sig, result)
    return result


def _select(candidates, catalog, excluded, limit, prefer_photos):
    """Keep servable candidates in model order, one per title. Returns (chosen, title duplicates).

    Real catalogs list colour/size variants as separate products with the same title; showing
    them side by side wastes slots. On non-personalized shelves photographed items go first.
    """
    eligible = [item for item in dict.fromkeys(candidates) if item in catalog and item not in excluded]
    if prefer_photos:
        eligible.sort(key=lambda item: not catalog[item].has_photo)  # stable: keeps model order
    chosen, seen, duplicates = [], set(), []
    for item in eligible:
        if len(chosen) == limit:
            break
        key = catalog[item].title_key
        if key in seen:
            duplicates.append(item)
            continue
        seen.add(key)
        chosen.append(item)
    return chosen, duplicates


def _read_cache(key, catalog, excluded, limit):
    """Return (ids, fallback) from a valid cache entry, or None. Never trusts cache contents."""
    try:
        cached = cache.client.get(key)
        if not cached:
            return None
        entry = json.loads(cached)
        ids = entry.get("ids") if isinstance(entry, dict) else None
        fallback = entry.get("fallback") if isinstance(entry, dict) else None
        if (isinstance(ids, list) and len(ids) <= limit and
                all(isinstance(item, str) and item in catalog and item not in excluded for item in ids) and
                len(set(ids)) == len(ids) and
                (fallback is None or isinstance(fallback, str)) and
                len(ids) == min(limit, len(catalog.keys() - excluded))):
            return ids, fallback
        observed_errors["cache_invalid"] += 1
    except (ValueError, TypeError):
        observed_errors["cache_invalid"] += 1
    except redis.RedisError:
        observed_errors["cache_unavailable"] += 1
    return None


def _write_cache(key, ids, fallback):
    try:
        cache.client.set(key, json.dumps({"ids": ids, "fallback": fallback}), ex=CACHE_TTL_SECONDS)
    except redis.RedisError:
        pass


_BASE_ORDER_CACHE: dict[tuple, list[str]] = {}


def _backfill(ids, catalog, excluded, interests, model, limit, duplicates=(), intent="balanced"):
    """Fill to ``limit``: interest match, photo, intent/popularity, id. New titles before repeats."""
    need = limit - len(ids)
    if need <= 0:
        return
    chosen = set(ids)
    seen = {catalog[item].title_key for item in ids}
    wanted = set(interests)
    popularity = model.f.popularity if model else None
    item_map = model.f.item_map if model else {}

    def base_rank(item):
        entry, position = catalog[item], item_map.get(item)
        pop = float(popularity[position]) if position is not None else 0.0
        price = entry.price if entry.price is not None else 999999.0
        if intent == "hidden_gems":
            intent_score = pop  # lower popularity ranks earlier
        elif intent == "budget":
            intent_score = price
        elif intent == "premium":
            intent_score = -(entry.price if entry.price is not None else 0.0)
        else:
            intent_score = -pop
        return (-int(entry.has_photo), intent_score, item)

    def rank(item):
        return (-int(catalog[item].category in wanted), *base_rank(item))

    def take(items, allow_repeats):
        for item in items:
            if len(ids) >= limit:
                return
            if item in chosen or item in excluded or (not allow_repeats and catalog[item].title_key in seen):
                continue
            ids.append(item)
            chosen.add(item)
            seen.add(catalog[item].title_key)

    if len(catalog) > 1000:
        order_key = (id(catalog), id(model), intent)
        base_order = _BASE_ORDER_CACHE.get(order_key)
        if base_order is None:
            if len(_BASE_ORDER_CACHE) > 32:
                _BASE_ORDER_CACHE.clear()
            base_order = sorted(catalog, key=base_rank)
            _BASE_ORDER_CACHE[order_key] = base_order
        if wanted:
            take((i for i in base_order if catalog[i].category in wanted), allow_repeats=False)
            if len(ids) < limit:
                take((i for i in base_order if catalog[i].category not in wanted), allow_repeats=False)
        else:
            take(base_order, allow_repeats=False)
        if len(ids) < limit:
            take(list(duplicates) + base_order, allow_repeats=True)
        return

    pool = [item for item in catalog if item not in chosen and item not in excluded]
    # A bounded heap usually suffices; fall back to a full ordering only if titles repeat a lot.
    take(heapq.nsmallest(need * 4, pool, key=rank), allow_repeats=False)
    if len(ids) < limit:
        ordered = sorted(pool, key=rank)
        take(ordered, allow_repeats=False)
        take(list(duplicates) + ordered, allow_repeats=True)


def _intent_rerank(candidates, catalog, model, intent, interests):
    """Fast O(K) intent-aware re-ordering of model candidate pool."""
    if intent == "balanced" or not candidates:
        return candidates
    pop = model.f.popularity if model else None
    item_map = model.f.item_map if model else {}
    max_pop = max(float(np.log1p(pop.max())), 1.0) if pop is not None and len(pop) else 1.0
    prices = [catalog[c].price for c in candidates if c in catalog and catalog[c].price is not None]
    max_price = max(prices) if prices else 1.0
    wanted = set(interests)
    total = max(len(candidates), 1)

    def key(idx_item):
        rank_idx, item = idx_item
        entry = catalog.get(item)
        if not entry:
            return 999.0
        base_rank_score = 1.0 - (rank_idx / total)
        pos = item_map.get(item)
        pop_norm = (float(np.log1p(pop[pos])) / max_pop) if (pop is not None and pos is not None) else 0.25
        interest_bonus = 0.2 if entry.category in wanted else 0.0
        if intent == "hidden_gems":
            novelty = 1.0 - pop_norm
            return -(0.55 * base_rank_score + 0.45 * novelty + interest_bonus)
        if intent == "budget":
            affordability = 1.0 - ((entry.price / max_price) if entry.price is not None and max_price > 0 else 0.5)
            return -(0.55 * base_rank_score + 0.45 * affordability + interest_bonus)
        if intent == "premium":
            prestige = (entry.price / max_price) if entry.price is not None and max_price > 0 else 0.0
            return -(0.55 * base_rank_score + 0.45 * prestige + interest_bonus)
        return -base_rank_score

    return [item for _, item in sorted(enumerate(candidates), key=key)]


def _explain(model, personalized, similar_to, intent="balanced"):
    if intent == "hidden_gems":
        return "Hidden gems with high personal match and low mainstream hype"
    if intent == "budget":
        return "Smart value picks tailored to your taste and budget"
    if intent == "premium":
        return "Flagship & premium picks aligned with your taste"
    if personalized and similar_to:
        return "Similar to this product, based on historical customer preferences"
    if personalized:
        return "Based on products you explored and saved"
    if model and settings.profile == "research":
        return "Popular products from historical review preferences"
    if model:
        return "Popular picks to help you get started"
    return "Explore products from the catalog"


def _score_item(item_id, rank_idx, catalog, model, interests, personalized, intent, median_price):
    """Compute calibrated Netflix-style Match %, contextual badge, and 4-pillar X-Ray breakdown."""
    entry = catalog.get(item_id)
    pop = model.f.popularity if model else None
    item_map = model.f.item_map if model else {}
    max_pop = max(float(np.log1p(pop.max())), 1.0) if pop is not None and len(pop) else 1.0
    pos = item_map.get(item_id)
    pop_ratio = (float(np.log1p(pop[pos])) / max_pop) if (pop is not None and pos is not None) else 0.35

    pop_pct = int(round(min(99.0, max(18.0, pop_ratio * 100.0))))
    novelty_pct = int(round(min(98.0, max(15.0, (1.0 - pop_ratio * 0.85) * 100.0))))
    in_interest = bool(entry and entry.category in interests)
    interest_pct = 96 if in_interest else (68 if not interests else 45)
    taste_pct = max(62, 98 - rank_idx * 2) if personalized else (90 if in_interest else max(60, 86 - rank_idx * 2))

    if intent == "hidden_gems":
        raw_match = 0.45 * taste_pct + 0.35 * novelty_pct + 0.20 * interest_pct
    elif intent == "budget":
        raw_match = 0.50 * taste_pct + 0.30 * interest_pct + 0.20 * pop_pct
    else:
        raw_match = 0.55 * taste_pct + 0.25 * interest_pct + 0.20 * max(pop_pct, novelty_pct)
    match_pct = int(round(min(99.0, max(72.0, raw_match - rank_idx * 0.6))))

    is_value = bool(entry and entry.price is not None and median_price and entry.price <= median_price * 0.85)
    if intent == "hidden_gems" or novelty_pct >= 74:
        badge = "Hidden Gem"
    elif in_interest:
        badge = "Interest Match"
    elif intent == "budget" or is_value:
        badge = "Smart Value"
    elif personalized and rank_idx < 4:
        badge = "Top Match"
    else:
        badge = "Popular Pick"

    return {
        "match_pct": match_pct,
        "badge": badge,
        "score_breakdown": {
            "taste_similarity": taste_pct,
            "interest_match": interest_pct,
            "novelty_bonus": novelty_pct,
            "popularity_prior": pop_pct,
        },
    }


def _select_companion_ids(anchor_id, catalog, excluded, interests, model, count=2):
    """Select cross-category complementary products to form an ecosystem bundle."""
    if not anchor_id or anchor_id not in catalog:
        return []
    anchor_cat = catalog[anchor_id].category
    used_categories = {anchor_cat}
    used_titles = {catalog[anchor_id].title_key}
    candidate_pool = []
    if model:
        try:
            raw, _ = model.recommend(None, [anchor_id], interests, excluded | {anchor_id}, 40, diversity=0.25)
            candidate_pool.extend(raw)
        except Exception:
            pass

    companions = []
    for cand in dict.fromkeys(candidate_pool):
        if cand not in catalog or cand in excluded or cand == anchor_id:
            continue
        entry = catalog[cand]
        if entry.category in used_categories or entry.title_key in used_titles:
            continue
        companions.append(cand)
        used_categories.add(entry.category)
        used_titles.add(entry.title_key)
        if len(companions) == count:
            return companions

    fallback_pool = []
    _backfill(fallback_pool, catalog, excluded | {anchor_id}, interests, model, 30)
    candidate_pool.extend(fallback_pool)
    for cand in dict.fromkeys(fallback_pool):
        if cand not in catalog or cand in excluded or cand == anchor_id or cand in companions:
            continue
        entry = catalog[cand]
        if entry.category in used_categories or entry.title_key in used_titles:
            continue
        companions.append(cand)
        used_categories.add(entry.category)
        used_titles.add(entry.title_key)
        if len(companions) == count:
            return companions

    # Relax category constraint only if catalog has fewer than 3 categories
    for cand in dict.fromkeys(candidate_pool):
        if len(companions) == count:
            break
        if cand in catalog and cand not in excluded and cand != anchor_id and cand not in companions:
            companions.append(cand)
    return companions


def _build_lane_ids(catalog, excluded, history, interests, model, median_price):
    """Compute 3 fast specialized micro-lanes (Because Viewed, Hidden Gems, Smart Value)."""
    lanes_spec = []
    if history:
        seed = history[-1]
        if seed in catalog:
            seed_ids = []
            if model:
                try:
                    cands, _ = model.recommend(None, [seed], interests, excluded | {seed}, 18, diversity=0.15)
                    seed_ids, _ = _select(cands, catalog, excluded | {seed}, 6, prefer_photos=False)
                except Exception:
                    seed_ids = []
            if len(seed_ids) < 6:
                _backfill(seed_ids, catalog, excluded | {seed}, interests, model, 6)
            if seed_ids:
                lanes_spec.append({
                    "id": "because_viewed",
                    "title": f"Because you explored {catalog[seed].title}",
                    "subtitle": "Direct item-to-item collaborative affinity from your latest activity",
                    "seed_id": seed,
                    "item_ids": seed_ids[:6],
                })

    gem_ids = []
    _backfill(gem_ids, catalog, excluded, interests, model, 6, intent="hidden_gems")
    if gem_ids:
        lanes_spec.append({
            "id": "hidden_gems",
            "title": "Hidden gems · High match, low hype",
            "subtitle": "Uncommon discoveries with strong personal alignment and low mainstream exposure",
            "seed_id": None,
            "item_ids": gem_ids[:6],
        })

    if median_price is not None:
        over_median = {item for item, entry in catalog.items() if entry.price is None or entry.price > median_price}
        budget_excl = excluded | over_median
        val_ids = []
        _backfill(val_ids, catalog, budget_excl, interests, model, 6, intent="budget")
        if val_ids:
            lanes_spec.append({
                "id": "smart_value",
                "title": f"Smart value picks under ${median_price:.0f}",
                "subtitle": "High-affinity products priced at or below the catalog median",
                "seed_id": None,
                "item_ids": val_ids[:6],
            })
    return lanes_spec


@router.get("/recommendations")
def recommendations(
    request: Request,
    response: Response,
    limit: int = Query(12, ge=1, le=30),
    similar_to: str | None = None,
    intent: str = Query("balanced", pattern="^(balanced|hidden_gems|budget|premium)$"),
    diversity: float = Query(0.1, ge=0.0, le=0.5),
    max_price: float | None = Query(None, ge=0),
    ignore_items: str | None = Query(None, max_length=2000),
    include_bundle: bool = False,
    include_lanes: bool = False,
    db=Depends(db_session),
):
    started = time.perf_counter()
    user = current_user(request, db)
    actor = actor_key(request, user, response)
    user_history, dismissed = allowed_history(db, user)
    ignored = {x.strip() for x in (ignore_items or "").split(",") if x.strip()}
    effective_user_history = [item for item in user_history if item not in ignored]
    history = list(effective_user_history)
    if similar_to:
        lookup_product(db, similar_to)
        history = [similar_to]
    catalog = _available_catalog(db)
    budget_excluded = (
        {item for item, entry in catalog.items() if entry.price is None or entry.price > max_price}
        if max_price is not None else set()
    )
    excluded = set(user_history) | set(history) | set(dismissed) | ignored | budget_excluded
    interests = user.preferences if user else []

    fallback = None
    try:
        model, version = active_bundle(db)
    except Exception:
        model, version, fallback = None, None, "model_unavailable"
    if not model:
        fallback = fallback or "model_not_trained"
    elif not history:
        fallback = "no_history"

    key = "rec:v4:" + token_hash(json.dumps([
        settings.profile, version, user.id if user else "guest",
        user.history_revision if user else 0, user_history, history, dismissed,
        sorted(ignored), interests, limit, similar_to, intent, round(diversity, 3), max_price,
    ]))
    hit = False
    cached = _read_cache(key, catalog, excluded, limit) if fallback != "model_unavailable" else None
    if cached:
        (ids, fallback), hit = cached, True
    else:
        ids, duplicates = [], []
        if model:
            try:
                candidates, _ = model.recommend(None, history, interests, excluded, max(limit, 30) * 2,
                                                diversity=diversity)
                if intent != "balanced":
                    candidates = _intent_rerank(candidates, catalog, model, intent, interests)
                ids, duplicates = _select(candidates, catalog, excluded, limit, prefer_photos=not history)
            except Exception as exc:
                observed_errors["model_inference_failed"] += 1
                log.error(json.dumps({"error_type": type(exc).__name__, "model_version": version}))
                ids, fallback = [], "model_inference_failed"
        if len(ids) < limit:
            fallback = fallback or "insufficient_candidates"
            _backfill(ids, catalog, excluded, interests, model, limit, duplicates, intent=intent)
        if fallback not in UNCACHEABLE_FALLBACKS:
            _write_cache(key, ids, fallback)

    listed_prices = sorted(entry.price for entry in catalog.values() if entry.price is not None)
    median_price = listed_prices[len(listed_prices) // 2] if listed_prices else None

    anchor_id = similar_to if (similar_to and similar_to in catalog) else (ids[0] if ids else None)
    companion_ids = _select_companion_ids(anchor_id, catalog, excluded, interests, model, 2) if include_bundle else []
    lanes_spec = _build_lane_ids(catalog, excluded, history, interests, model, median_price) if include_lanes else []

    hydrate_ids = set(ids)
    if include_bundle and anchor_id:
        hydrate_ids.add(anchor_id)
        hydrate_ids.update(companion_ids)
    for lane in lanes_spec:
        hydrate_ids.update(lane["item_ids"])

    products = (
        {p.id: p for p in db.scalars(select(Product).where(Product.id.in_(hydrate_ids))).all()}
        if hydrate_ids else {}
    )
    request_id = str(uuid.uuid4())
    duration_ms = (time.perf_counter() - started) * 1000
    db.add(RecommendationRequest(id=request_id, actor_key=actor, user_id=user.id if user else None,
                                 model_version=version, item_ids=ids,
                                 duration_ms=duration_ms,
                                 fallback=fallback, cache_hit=hit, profile=settings.profile))
    db.commit()

    personalized = bool(model and model.name != "popularity" and model.f.indices(history)
                        and fallback not in UNCACHEABLE_FALLBACKS)
    reason = _explain(model, personalized, similar_to, intent=intent)
    items = [
        {
            **product_json(products[item]),
            "reason": ("Matches your " + products[item].category.lower() + " interest")
            if products[item].category in interests else reason,
            **_score_item(item, idx, catalog, model, interests, personalized, intent, median_price),
        }
        for idx, item in enumerate(ids) if item in products
    ]

    bundle = None
    if include_bundle and anchor_id and companion_ids:
        bundle_ids = [anchor_id, *companion_ids]
        bundle_items = [product_json(products[i]) for i in bundle_ids if i in products]
        if len(bundle_items) >= 2:
            total_price = round(sum(item["price"] or 0.0 for item in bundle_items), 2)
            bundle = {
                "anchor_id": anchor_id,
                "items": bundle_items,
                "total_price": total_price,
                "synergy_pct": 96 if personalized else 92,
                "categories": [item["category"] for item in bundle_items],
                "headline": "Frequently paired ecosystem bundle",
                "subtitle": "Cross-category companions matched by collaborative affinity and compatibility",
            }

    lanes = [
        {
            "id": lane["id"],
            "title": lane["title"],
            "subtitle": lane["subtitle"],
            "items": [
                {
                    **product_json(products[i]),
                    "reason": lane["title"],
                    **_score_item(i, idx, catalog, model, interests, personalized, intent, median_price),
                }
                for idx, i in enumerate(lane["item_ids"]) if i in products
            ],
        }
        for lane in lanes_spec
    ]

    active_seeds = [
        {
            "id": item_id,
            "title": catalog[item_id].title if item_id in catalog else item_id,
            "category": catalog[item_id].category if item_id in catalog else "Catalog",
            "muted": item_id in ignored,
        }
        for item_id in reversed(user_history[-8:])
    ]

    return {
        "items": items,
        "request_id": request_id,
        "model_version": version,
        "fallback": fallback,
        "reason": reason,
        "profile": settings.profile,
        "personalization_mode": "history" if personalized else "interests" if interests
        else "popular" if model else "catalog",
        "model_type": model.name if model else None,
        "bundle": bundle,
        "lanes": lanes,
        "active_seeds": active_seeds,
        "studio": {
            "intent": intent,
            "diversity": diversity,
            "max_price": max_price,
            "median_price": median_price,
            "latency_ms": round(duration_ms, 2),
            "cache_hit": hit,
            "ignored_count": len(ignored),
        },
    }
