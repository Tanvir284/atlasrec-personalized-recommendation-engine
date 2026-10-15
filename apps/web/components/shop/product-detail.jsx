"use client";
// Product page: photo zoom, rating, save/dismiss and similar items.
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  Sparkles,
  Heart,
  Ban,
  ArrowLeft,
  CheckCircle2,
  Star,
  ChevronRight,
  X,
} from "lucide-react";
import { api, sendEvent } from "../../lib/api";
import { Price, ProductGrid, ProductPhoto, State, SectionTitle, useMe, useNotice } from "../ui";

export function ProductDetail({ id }) {
  const product = useQuery({ queryKey: ["product", id], queryFn: () => api("/products/" + id) });
  const similar = useQuery({
    queryKey: ["similar", id],
    queryFn: () => api("/recommendations?limit=6&include_bundle=true&similar_to=" + id),
  });
  const client = useQueryClient(),
    notify = useNotice(),
    me = useMe(),
    router = useRouter(),
    zoom = useRef(null);
  const [pending, setPending] = useState(false);
  const favorites = useQuery({
    queryKey: ["favorites"],
    queryFn: () => api("/favorites"),
    enabled: !!me.data?.user,
  });
  const history = useQuery({
    queryKey: ["history", "rating", id],
    queryFn: () => api("/me/history?ratings_only=true&item_id=" + encodeURIComponent(id)),
    enabled: !!me.data?.user,
  });
  const saved = favorites.data?.items.some(p => p.id === id);
  const currentRating = history.data?.[0]?.rating ?? 0;
  const trackedViews = useRef(new Set()),
    loadedId = product.data?.id;
  useEffect(() => {
    if (!loadedId || trackedViews.current.has(loadedId)) return;
    trackedViews.current.add(loadedId);
    sendEvent(loadedId, "view", "product-detail")
      .then(() => {
        client.invalidateQueries({ queryKey: ["recommendations"] });
        client.invalidateQueries({ queryKey: ["history"] });
      })
      .catch(() => trackedViews.current.delete(loadedId));
  }, [loadedId, client]);
  async function action(path, method, body, message) {
    if (!me.data?.user) {
      router.push("/login?next=" + encodeURIComponent("/products/" + id));
      return false;
    }
    setPending(true);
    try {
      await api(path, { method, ...(body ? { body: JSON.stringify(body) } : {}) });
      await client.invalidateQueries();
      notify(message);
      return true;
    } catch (error) {
      notify(error.message);
      return false;
    } finally {
      setPending(false);
    }
  }
  async function rate(value) {
    await action(
      "/events",
      "POST",
      {
        id: crypto.randomUUID(),
        item_id: id,
        kind: "rating",
        surface: "product-detail",
        rating: value,
      },
      "Your rating is saved",
    );
  }
  const p = product.data;
  if (product.error?.status === 404)
    return (
      <div className="state">
        <h1>Product not found</h1>
        <Link href="/catalog" className="button">
          Explore the catalog
        </Link>
      </div>
    );
  return (
    <div className="container product-page">
      <div className="breadcrumbs">
        <Link href="/catalog">
          <ArrowLeft size={13} />
          Back to results
        </Link>
        {p && (
          <>
            <ChevronRight size={13} />
            <Link href={"/catalog?category=" + encodeURIComponent(p.category)}>{p.category}</Link>
            <ChevronRight size={13} />
            <span>{p.title}</span>
          </>
        )}
      </div>
      <State query={product}>
        {p && (
          <>
            <section className="product-detail-grid">
              <div className="product-gallery">
                <button
                  className="enlarge-image"
                  onClick={() => zoom.current.showModal()}
                  aria-label="Enlarge product image"
                >
                  <ProductPhoto product={p} width={600} height={510} loading="eager" />
                </button>
                <span>
                  {p.id?.startsWith("demo-")
                    ? "Click the image for a closer look"
                    : "Source catalog photograph · Click for a closer look"}
                </span>
              </div>
              <div className="product-information">
                <Link
                  className="shop-link"
                  href={"/catalog?category=" + encodeURIComponent(p.category)}
                >
                  Explore the {p.category.toLowerCase()} collection
                </Link>
                <h1>{p.title}</h1>
                <span className="detail-collection">
                  <Sparkles size={15} />
                  Find a little more of what you love
                </span>
                <hr />
                <Price product={p} className="detail-price" />
                <p className="price-caption">
                  {p.id?.startsWith("demo-")
                    ? "USD example price · Synthetic demo product"
                    : p.price == null
                      ? "The source catalog has no listed price"
                      : "Historical source price · Current merchant price may differ"}
                </p>
                <p className="product-description">
                  {p.description || "No description is available in the source catalog."}
                </p>
                <div className="product-specs">
                  <div>
                    <strong>Department</strong>
                    <Link href={"/catalog?category=" + encodeURIComponent(p.category)}>
                      {p.category}
                    </Link>
                  </div>
                  <div>
                    <strong>Catalog status</strong>
                    <span>{p.available ? "Available to explore" : "Currently unavailable"}</span>
                  </div>
                </div>
                <div className="detail-recommendation-note">
                  <Sparkles size={19} />
                  <div>
                    <strong>A choice that shapes your next discovery</strong>
                    <p>
                      Save what you like, rate it, or let us know when it isn't for you. We'll use
                      your choices to refine your picks.
                    </p>
                  </div>
                </div>
              </div>
              <aside className="save-panel">
                <Price product={p} />
                <span className={"availability " + (!p.available ? "unavailable" : "")}>
                  <CheckCircle2 size={16} />
                  {p.available ? "Available in the catalog" : "Currently unavailable"}
                </span>
                <p>Add it to your collection and find it again whenever you're ready.</p>
                <button
                  className="button"
                  disabled={pending || me.isPending || (!!me.data?.user && favorites.isPending)}
                  onClick={() =>
                    action(
                      "/favorites/" + id,
                      saved ? "DELETE" : "PUT",
                      null,
                      saved ? "Removed from saved" : "Saved to your collection",
                    )
                  }
                >
                  <Heart size={16} fill={saved ? "currentColor" : "none"} />
                  {saved ? "Remove from saved" : "Save for later"}
                </button>
                <button
                  className="button secondary"
                  disabled={pending || me.isPending}
                  onClick={() =>
                    action(
                      "/events",
                      "POST",
                      { id: crypto.randomUUID(), item_id: id, kind: "dismiss", surface: "detail" },
                      "We'll leave this product out of your next recommendations",
                    )
                  }
                >
                  <Ban size={16} />
                  Not for me
                </button>
                <hr />
                <Link href="/saved">
                  View your saved collection
                  <ChevronRight size={14} />
                </Link>
                <div className="save-panel-note">
                  <CheckCircle2 size={15} />
                  {me.data?.user
                    ? "Saved securely to your account"
                    : "Sign in to keep your favorites"}
                </div>
              </aside>
            </section>
            <nav className="detail-tabs" aria-label="Product sections">
              <a href="#product-details">Product overview</a>
              <a href="#your-feedback">Your feedback</a>
              <a href="#related-products">Related products</a>
            </nav>
            <section id="product-details" className="product-overview">
              <h2>About this product</h2>
              <p>{p.description || "No description is available in the source catalog."}</p>
              <Link
                href={"/catalog?category=" + encodeURIComponent(p.category)}
                className="shop-link"
              >
                Discover more in {p.category}
                <ArrowRight size={15} />
              </Link>
            </section>
            <section id="your-feedback" className="rating-panel">
              <div>
                <h2>Make your recommendations better</h2>
                <p>
                  Your rating helps us understand your preferences. Low ratings tell us to leave
                  this product out; higher ratings help us find similar picks.
                </p>
              </div>
              {me.data?.user ? (
                <div className="your-rating">
                  <span>Your rating</span>
                  <div>
                    {[1, 2, 3, 4, 5].map(value => (
                      <button
                        key={value}
                        disabled={pending || history.isPending}
                        aria-label={"Rate " + value + " out of 5"}
                        aria-pressed={currentRating === value}
                        onClick={() => rate(value)}
                      >
                        <Star size={27} fill={value <= currentRating ? "currentColor" : "none"} />
                      </button>
                    ))}
                  </div>
                  <small>
                    {currentRating
                      ? currentRating + " out of 5 · Saved to your account"
                      : "Choose 1–5 stars"}
                  </small>
                </div>
              ) : (
                <Link
                  className="button secondary"
                  href={"/login?next=" + encodeURIComponent("/products/" + id)}
                >
                  Sign in to rate this product
                </Link>
              )}
            </section>
            <dialog
              ref={zoom}
              className="product-zoom"
              aria-label="Expanded product image"
              onClick={e => {
                if (e.target === zoom.current) zoom.current.close();
              }}
            >
              <button
                className="zoom-close"
                aria-label="Close expanded image"
                onClick={() => zoom.current.close()}
              >
                <X size={23} />
              </button>
              <ProductPhoto product={p} width={800} height={680} />
            </dialog>
          </>
        )}
      </State>
      {similar.data?.bundle?.items?.length >= 2 && (
        <section className="bundle-box" aria-label="Frequently paired together">
          <div className="bundle-copy">
            <span className="eyebrow">
              {similar.data.bundle.synergy_pct}% Cross-Category Compatibility
            </span>
            <h2>Frequently paired together</h2>
            <p>{similar.data.bundle.subtitle}</p>
            <div className="bundle-meta">
              <span>
                Combined bundle price:{" "}
                <strong>${similar.data.bundle.total_price.toFixed(2)}</strong>
              </span>
              <button
                type="button"
                className="button"
                disabled={pending}
                onClick={async () => {
                  if (!me.data?.user) {
                    router.push("/login?next=" + encodeURIComponent("/products/" + id));
                    return;
                  }
                  setPending(true);
                  try {
                    await Promise.all(
                      similar.data.bundle.items.map(item =>
                        api("/favorites/" + item.id, { method: "PUT" }),
                      ),
                    );
                    await client.invalidateQueries();
                    notify("Saved entire bundle to your collection");
                  } catch (err) {
                    notify(err.message);
                  } finally {
                    setPending(false);
                  }
                }}
              >
                <Heart size={15} />
                Save full bundle ({similar.data.bundle.items.length} items)
              </button>
            </div>
          </div>
          <div className="bundle-items">
            {similar.data.bundle.items.map((item, idx) => (
              <Link key={item.id} href={"/products/" + item.id} className="bundle-card">
                <span className="bundle-role">{idx === 0 ? "This Item" : "Companion"}</span>
                <ProductPhoto product={item} width={150} height={130} />
                <strong>{item.title}</strong>
                <small>{item.category}</small>
                <Price product={item} />
              </Link>
            ))}
          </div>
        </section>
      )}
      <section id="related-products" className="retail-section">
        <SectionTitle
          title="You might also like"
          subtitle="More products to discover in your collection."
        />
        <State query={similar} count={similar.data?.items.length}>
          <ProductGrid
            items={similar.data?.items}
            requestId={similar.data?.request_id}
            layout="rail"
          />
        </State>
      </section>
    </div>
  );
}
