"use client";
// Home page: department cards, catalog provenance and recommendation shelves.
import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Sparkles, Heart, CheckCircle2, ChevronRight } from "lucide-react";
import { api } from "../../lib/api";
import { DEPARTMENTS, departmentProduct, productImage } from "../../lib/products";
import { ProductGrid, ProductPhoto, State, SectionTitle, useMe } from "../ui";

function DepartmentCard({ category, demo = false }) {
  const info = demo && DEPARTMENTS[category.name],
    items = category.preview_items?.slice(0, 4) || [];
  return (
    <article className="department-card">
      <h2>{info?.headline || "Explore " + category.name}</h2>
      {info ? (
        <div className="department-products">
          {info.items.map(([image, name]) => (
            <Link
              key={image}
              href={
                "/catalog?category=" +
                encodeURIComponent(category.name) +
                "&q=" +
                encodeURIComponent(name)
              }
            >
              <div>
                <ProductPhoto
                  product={{
                    id: "demo-" + image,
                    title: name,
                    image: "/products/store/" + image + ".svg",
                  }}
                />
              </div>
              <span>{name}</span>
            </Link>
          ))}
        </div>
      ) : items.length ? (
        <div className="department-products actual-products">
          {items.map(product => (
            <Link key={product.id} href={"/products/" + product.id} title={product.title}>
              <div>
                <ProductPhoto product={product} />
              </div>
              <span>{product.title}</span>
            </Link>
          ))}
        </div>
      ) : (
        <div className="single-department-image">
          <ProductPhoto product={departmentProduct(category, demo)} />
        </div>
      )}
      <Link className="shop-link" href={"/catalog?category=" + encodeURIComponent(category.name)}>
        Explore {category.name}
        <ArrowRight size={15} />
      </Link>
    </article>
  );
}
function CatalogProvenance({ query }) {
  const info = query.data;
  if (!info || info.synthetic) return null;
  const model = info.personalization,
    number = value => new Intl.NumberFormat("en-US").format(value || 0);
  const source =
    typeof info.source === "string" && info.source.startsWith("https://") ? info.source : null;
  return (
    <section className="catalog-provenance" aria-label="Catalog data source">
      <div>
        <span className="eyebrow">Real catalog. Transparent recommendations.</span>
        <h2>Built around products and recorded preferences</h2>
        <p>
          Product photos and descriptions come from the source catalog. Historical reviews help
          train recommendations; your own saves, ratings, and browsing guide your picks.
        </p>
        {source && (
          <a className="shop-link" href={source} target="_blank" rel="noreferrer">
            View the source dataset
            <ArrowRight size={14} />
          </a>
        )}
      </div>
      <dl>
        <div>
          <dt>Source products</dt>
          <dd>{number(info.product_count)}</dd>
        </div>
        <div>
          <dt>Historical reviews</dt>
          <dd>{number(info.historical_interactions)}</dd>
        </div>
        <div>
          <dt>Historical reviewers</dt>
          <dd>{number(info.historical_reviewers)}</dd>
        </div>
        <div>
          <dt>Recommendation model</dt>
          <dd className="model-name">
            {model?.status === "ready" ? model.model_type || "Trained model" : "Catalog fallback"}
          </dd>
        </div>
      </dl>
      <p className="provenance-note">
        Historical reviewers are anonymized source records, separate from AtlasRec accounts. Source
        prices are historical, not live merchant offers.
      </p>
    </section>
  );
}
export function Discover() {
  const me = useMe();
  const [showAllDepts, setShowAllDepts] = useState(false);
  const recommendations = useQuery({
    queryKey: ["recommendations"],
    queryFn: () => api("/recommendations?limit=12"),
  });
  const categories = useQuery({ queryKey: ["categories"], queryFn: () => api("/categories") });
  const popular = useQuery({ queryKey: ["popular"], queryFn: () => api("/products?limit=10") });
  const catalogInfo = useQuery({ queryKey: ["catalog-info"], queryFn: () => api("/catalog/info") });
  const demo = me.data?.profile === "demo";
  const ordered = [...(categories.data || [])]
    .filter(category => demo || category.preview_items?.some(product => productImage(product)))
    .sort((a, b) =>
      demo
        ? ["Workspace", "Home", "Audio", "Outdoors", "Wellness"].indexOf(a.name) -
          ["Workspace", "Home", "Audio", "Outdoors", "Wellness"].indexOf(b.name)
        : b.count - a.count || a.name.localeCompare(b.name),
    );
  const heroProducts = [...(recommendations.data?.items || []), ...(popular.data?.items || [])]
    .filter((p, i, all) => productImage(p) && all.findIndex(item => item.id === p.id) === i)
    .slice(0, 3);
  return (
    <div className={"marketplace-home " + (!demo ? "source-storefront" : "")}>
      <section className={"retail-hero " + (!demo ? "source-hero" : "")}>
        <div className="retail-hero-copy">
          <span className="hero-kicker">
            <Sparkles size={15} />
            {demo ? "A better way to discover" : "Find your next favorite"}
          </span>
          <h1>
            {demo ? (
              <>
                Everyday essentials.
                <br />
                <strong>Extraordinary finds.</strong>
              </>
            ) : (
              <>
                Real products.
                <br />
                <strong>Your next discovery.</strong>
              </>
            )}
          </h1>
          <p>
            {demo ? (
              <>
                From your desk to your next adventure.
                <br />
                Discover products that feel like you.
              </>
            ) : (
              <>
                Explore the collection. Save what speaks to you.
                <br />
                Find recommendations shaped by your taste.
              </>
            )}
          </p>
          <Link href="/catalog" className="button">
            Explore the catalog
            <ArrowRight size={18} />
          </Link>
        </div>
        {demo ? (
          <div className="retail-hero-art" aria-hidden="true">
            <div className="hero-ring" />
            <img
              className="hero-item hero-item-headphones"
              src="/products/store/headphones.svg"
              alt=""
              width="400"
              height="340"
            />
            <img
              className="hero-item hero-item-kettle"
              src="/products/store/kettle.svg"
              alt=""
              width="400"
              height="340"
            />
            <img
              className="hero-item hero-item-lamp"
              src="/products/store/lamp.svg"
              alt=""
              width="400"
              height="340"
            />
            <span className="hero-pill">
              <Sparkles size={15} />
              Good finds start here
            </span>
          </div>
        ) : (
          <div className="source-hero-products" aria-label="From the source catalog">
            {heroProducts.map((product, index) => (
              <Link
                href={"/products/" + product.id}
                className={"source-hero-product source-hero-product-" + index}
                key={product.id}
                title={product.title}
              >
                <ProductPhoto product={product} loading="eager" />
                <span>{product.title}</span>
              </Link>
            ))}
          </div>
        )}
      </section>
      <div className="home-content">
        <State query={categories}>
          <div className="department-panels">
            {ordered.slice(0, 4).map(category => (
              <DepartmentCard key={category.name} category={category} demo={demo} />
            ))}
          </div>
        </State>
        <div className="store-benefits">
          <span>
            <Sparkles size={19} />
            <strong>Picked for your interests</strong> Discover with a reason
          </span>
          <span>
            <Heart size={19} />
            <strong>Keep your favorites close</strong> Your collection, your way
          </span>
          <span>
            <CheckCircle2 size={19} />
            <strong>Explore at your own pace</strong> Easy to browse. Easy to save.
          </span>
        </div>
        <section className="retail-section">
          <SectionTitle
            title="A few picks to start with"
            subtitle={recommendations.data?.reason || "Discover your next favorite."}
            link="/for-you"
            label="See all your picks"
          />
          <State query={recommendations} count={recommendations.data?.items.length}>
            <ProductGrid
              items={recommendations.data?.items}
              requestId={recommendations.data?.request_id}
              layout="rail"
            />
          </State>
        </section>
        <section className="retail-section">
          <SectionTitle
            title="Shop by department"
            subtitle={
              ordered.length > 12
                ? `Explore ${ordered.length} specialized departments across the catalog.`
                : "Start with what you love. Find something new."
            }
            link="/catalog"
            label={`Browse all ${ordered.length || ""} departments`}
          />
          <State query={categories}>
            <div className="category-grid">
              {(showAllDepts ? ordered : ordered.slice(0, 12)).map(category => (
                <Link
                  className="category-tile"
                  href={"/catalog?category=" + encodeURIComponent(category.name)}
                  key={category.name}
                >
                  <div>
                    <ProductPhoto product={departmentProduct(category, demo)} />
                  </div>
                  <h3>{category.name}</h3>
                  <p>
                    {category.count} products
                    <ChevronRight size={13} />
                  </p>
                </Link>
              ))}
            </div>
            {ordered.length > 12 && (
              <div style={{ marginTop: "1rem", display: "flex", justifyContent: "center" }}>
                <button
                  type="button"
                  className="button secondary"
                  onClick={() => setShowAllDepts(v => !v)}
                >
                  {showAllDepts
                    ? "Show top 12 departments"
                    : `Show all ${ordered.length} departments`}
                </button>
              </div>
            )}
          </State>
        </section>
        <div className="personalization-banner">
          <div className="personalization-icon">
            <Sparkles size={34} />
          </div>
          <div>
            <span className="eyebrow">A collection that's yours</span>
            <h2>
              {me.data?.user ? "Make every discovery more you." : "Your next favorite is waiting."}
            </h2>
            <p>Choose your interests and save what you love. Your recommendations grow with you.</p>
          </div>
          <Link href={me.data?.user ? "/profile" : "/register"} className="button">
            {me.data?.user ? "Edit your interests" : "Make it personal"}
            <ArrowRight size={16} />
          </Link>
        </div>
        <section className="retail-section">
          <SectionTitle
            title="More to explore"
            subtitle="Browse the collection. Keep what catches your eye."
          />
          <State query={popular} count={popular.data?.items.length}>
            <ProductGrid items={popular.data?.items} layout="rail" />
          </State>
        </section>
        {!demo && <CatalogProvenance query={catalogInfo} />}
      </div>
    </div>
  );
}
