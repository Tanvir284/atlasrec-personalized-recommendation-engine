"""Public catalog browsing: categories, search/filter, product detail."""
import time
from collections import defaultdict
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select

from ..common import lookup_product, product_json
from ..db import Product, db_session
from ..research import catalog_information
from ..settings import settings

router = APIRouter(prefix="/api/v1", tags=["catalog"])
_CATEGORIES_CACHE: dict[tuple, tuple[float, tuple, list[dict]]] = {}


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("/categories")
def categories(db=Depends(db_session)):
    visible = (Product.profile == settings.profile, Product.available.is_(True))
    cache_key = (str(db.get_bind().url), settings.profile)
    now = time.monotonic()
    cached = _CATEGORIES_CACHE.get(cache_key)
    if cached and len(cached[2]) > 50 and (now - cached[0]) < 5.0:
        return cached[2]
    sig = db.execute(
        select(
            func.count(),
            func.max(Product.id),
            func.min(Product.id),
            func.max(Product.image),
            func.min(Product.image),
        ).where(*visible)
    ).one()
    if cached and cached[1] == sig:
        _CATEGORIES_CACHE[cache_key] = (now, sig, cached[2])
        return cached[2]
    rows = db.execute(select(Product.category, func.count()).where(*visible).group_by(Product.category)).all()
    ranked = select(Product.id, func.row_number().over(
        partition_by=Product.category,
        order_by=(Product.image == "", Product.title, Product.id)).label("position")).where(*visible).subquery()
    previews = defaultdict(list)
    for product in db.scalars(select(Product).join(ranked, ranked.c.id == Product.id).where(ranked.c.position <= 4)).all():
        previews[product.category].append(product_json(product))
    result = [{"name": c, "count": n, "preview_items": previews[c]} for c, n in rows]
    if settings.profile == "research":
        result.sort(key=lambda x: (-x["count"], x["name"]))
    _CATEGORIES_CACHE[cache_key] = (now, sig, result)
    return result


@router.get("/catalog/info")
def catalog_info(db=Depends(db_session)):
    return catalog_information(db)


@router.get("/products")
def products(q: str = Query("", max_length=200), category: str | None = None,
             min_price: float | None = Query(None, ge=0, allow_inf_nan=False),
             max_price: float | None = Query(None, ge=0, allow_inf_nan=False),
             sort: Literal["title", "price_asc", "price_desc"] = "title",
             page: int = Query(1, ge=1, le=10000), limit: int = Query(20, ge=1, le=60),
             db=Depends(db_session)):
    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(422, "Minimum price cannot exceed maximum price")
    query = select(Product).where(Product.profile == settings.profile, Product.available.is_(True))
    if q:
        query = query.where(Product.title.ilike("%" + _escape_like(q) + "%", escape="\\"))
    if category:
        query = query.where(Product.category == category)
    if min_price is not None:
        query = query.where(Product.price >= min_price)
    if max_price is not None:
        query = query.where(Product.price <= max_price)
    count = db.scalar(select(func.count()).select_from(query.subquery()))
    order = {"title": Product.title.asc(), "price_asc": Product.price.asc().nullslast(),
             "price_desc": Product.price.desc().nullslast()}[sort]
    rows = db.scalars(query.order_by(order, Product.id).offset((page - 1) * limit).limit(limit)).all()
    return {"items": [product_json(p) for p in rows], "total": count, "page": page,
            "pages": max(1, (count + limit - 1) // limit)}


@router.get("/products/{item_id}")
def product(item_id: str, db=Depends(db_session)):
    return product_json(lookup_product(db, item_id))
