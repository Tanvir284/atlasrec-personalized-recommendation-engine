"use client";
// Personal collections: For You recommendations (with Taste Studio, Bundle Builder, AI Compare, and Multi-Lanes) and saved products.
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  Sparkles,
  Heart,
  SlidersHorizontal,
  Layers,
  Eye,
  RotateCcw,
  X,
} from "lucide-react";
import { api } from "../../lib/api";
import {
  PageHeading,
  Price,
  ProductGrid,
  ProductPhoto,
  SectionTitle,
  State,
  useMe,
  useNotice,
} from "../ui";

const INTENTS = [
  ["balanced", "All-Rounder", "Balanced personal affinity & popularity"],
  ["hidden_gems", "Hidden Gems", "High personal match, low mainstream hype"],
  ["budget", "Smart Value", "High affinity prioritized for affordability"],
  ["premium", "Flagship Pro", "Top-tier flagship & high-spec picks"],
];

export function ForYou() {
  const me = useMe(),
    client = useQueryClient(),
    notify = useNotice(),
    router = useRouter();
  const [intent, setIntent] = useState("balanced"),
    [diversity, setDiversity] = useState(0.1),
    [maxPriceInput, setMaxPriceInput] = useState(""),
    [appliedMaxPrice, setAppliedMaxPrice] = useState(""),
    [ignoredIds, setIgnoredIds] = useState([]),
    [showBreakdown, setShowBreakdown] = useState(false),
    [compared, setCompared] = useState([]),
    [savingBundle, setSavingBundle] = useState(false);

  const queryParams = new URLSearchParams({
    limit: "20",
    intent,
    diversity: String(diversity),
    include_bundle: "true",
    include_lanes: "true",
  });
  if (appliedMaxPrice) queryParams.set("max_price", appliedMaxPrice);
  if (ignoredIds.length) queryParams.set("ignore_items", ignoredIds.join(","));

  const recs = useQuery({
    queryKey: ["recommendations", "for-you", intent, diversity, appliedMaxPrice, ignoredIds],
    queryFn: () => api("/recommendations?" + queryParams.toString()),
  });

  function toggleSeed(id) {
    setIgnoredIds(prev => (prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]));
  }

  function toggleCompare(product) {
    setCompared(prev => {
      if (prev.some(p => p.id === product.id)) return prev.filter(p => p.id !== product.id);
      if (prev.length >= 3) {
        notify("You can compare up to 3 products side by side");
        return prev;
      }
      return [...prev, product];
    });
  }

  async function saveBundle(bundleItems) {
    if (!me.data?.user) {
      router.push("/login?next=/for-you");
      return;
    }
    setSavingBundle(true);
    try {
      await Promise.all(bundleItems.map(item => api("/favorites/" + item.id, { method: "PUT" })));
      await client.invalidateQueries();
      notify(`Saved all ${bundleItems.length} bundle items to your collection`);
    } catch (err) {
      notify(err.message);
    } finally {
      setSavingBundle(false);
    }
  }

  const studio = recs.data?.studio,
    seeds = recs.data?.active_seeds || [],
    bundle = recs.data?.bundle,
    lanes = recs.data?.lanes || [];

  return (
    <div className="container collection-page">
      <PageHeading
        eyebrow="Recommended for you"
        title={
          me.data?.user
            ? me.data.user.name.split(" ")[0] + ", meet your next favorites."
            : "Discover your next favorite."
        }
        description="Your saved products, explored items, and interests guide these picks."
      >
        <div className="heading-actions">
          <button
            type="button"
            className={"button secondary " + (showBreakdown ? "active-toggle" : "")}
            onClick={() => setShowBreakdown(!showBreakdown)}
          >
            <Eye size={16} />
            {showBreakdown ? "Hide Match DNA" : "Inspect Match DNA"}
          </button>
          <Link href="/profile" className="button secondary">
            <SlidersHorizontal size={16} />
            Edit interests
          </Link>
        </div>
      </PageHeading>
      {!me.data?.user && (
        <div className="info-strip">
          <Sparkles size={19} />
          <span>
            Start with popular picks.{" "}
            <Link href="/register">Create an account for recommendations that fit you.</Link>
          </span>
        </div>
      )}

      <section className="taste-studio" aria-label="Interactive Taste Studio">
        <div className="taste-studio-header">
          <div>
            <span className="eyebrow">AtlasRec Taste Studio · Real-Time Counterfactual Engine</span>
            <h2>Shape your live algorithm</h2>
            <p>
              Switch discovery intent, dial serendipity, set an instant budget ceiling, or mute past
              interactions to see how your shelf responds in real time.
            </p>
          </div>
          {studio && (
            <div className="studio-telemetry">
              <span>
                Engine latency: <strong>{studio.latency_ms} ms</strong>
              </span>
              <span>
                Mode: <strong>{recs.data?.model_type || "catalog"}</strong>
              </span>
              {(intent !== "balanced" ||
                diversity !== 0.1 ||
                appliedMaxPrice ||
                ignoredIds.length > 0) && (
                <button
                  type="button"
                  className="studio-reset"
                  onClick={() => {
                    setIntent("balanced");
                    setDiversity(0.1);
                    setMaxPriceInput("");
                    setAppliedMaxPrice("");
                    setIgnoredIds([]);
                  }}
                >
                  <RotateCcw size={13} />
                  Reset studio
                </button>
              )}
            </div>
          )}
        </div>

        <div className="intent-pills" role="group" aria-label="Discovery intent mode">
          {INTENTS.map(([key, label, hint]) => (
            <button
              key={key}
              type="button"
              aria-pressed={intent === key}
              className={"intent-pill " + (intent === key ? "active" : "")}
              onClick={() => setIntent(key)}
            >
              <strong>{label}</strong>
              <small>{hint}</small>
            </button>
          ))}
        </div>

        <div className="studio-controls">
          <label className="studio-slider">
            <span>
              Serendipity & category diversity: <strong>{Math.round(diversity * 200)}%</strong>
            </span>
            <input
              type="range"
              min="0"
              max="0.5"
              step="0.05"
              value={diversity}
              onChange={e => setDiversity(Number(e.target.value))}
            />
          </label>
          <form
            className="studio-budget"
            onSubmit={e => {
              e.preventDefault();
              setAppliedMaxPrice(maxPriceInput.trim());
            }}
          >
            <label>
              Max budget (USD)
              <input
                type="number"
                min="1"
                step="1"
                placeholder={
                  studio?.median_price ? `e.g. $${Math.round(studio.median_price)}` : "No cap"
                }
                value={maxPriceInput}
                onChange={e => setMaxPriceInput(e.target.value)}
              />
            </label>
            <button type="submit" className="button secondary">
              Apply cap
            </button>
          </form>
        </div>

        {seeds.length > 0 && (
          <div className="counterfactual-seeds">
            <div>
              <strong>What-If Counterfactual History Sandbox:</strong>{" "}
              <span>
                Click any past item below to temporarily mute its influence without deleting it from
                your history.
              </span>
            </div>
            <div className="seed-chips">
              {seeds.map(seed => (
                <button
                  key={seed.id}
                  type="button"
                  aria-pressed={!seed.muted}
                  className={"seed-chip " + (seed.muted ? "muted-seed" : "")}
                  onClick={() => toggleSeed(seed.id)}
                >
                  <span>{seed.title}</span>
                  <small>{seed.muted ? "Muted (What-If)" : seed.category}</small>
                </button>
              ))}
            </div>
          </div>
        )}
      </section>

      {compared.length > 0 && (
        <section className="compare-matrix" aria-label="Side-by-side product comparison">
          <div className="compare-header">
            <div>
              <span className="eyebrow">AI Side-by-Side Comparison</span>
              <h2>Comparing {compared.length} recommended picks</h2>
            </div>
            <button type="button" className="button secondary" onClick={() => setCompared([])}>
              <X size={15} />
              Clear comparison
            </button>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Attribute</th>
                  {compared.map(item => (
                    <th key={item.id}>
                      <Link href={"/products/" + item.id}>{item.title}</Link>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Match Score</td>
                  {compared.map(item => (
                    <td key={item.id}>
                      <strong>{item.match_pct ?? 90}% Match</strong> ({item.badge || "Pick"})
                    </td>
                  ))}
                </tr>
                <tr>
                  <td>Price</td>
                  {compared.map(item => (
                    <td key={item.id}>
                      <Price product={item} />
                    </td>
                  ))}
                </tr>
                <tr>
                  <td>Department</td>
                  {compared.map(item => (
                    <td key={item.id}>{item.category}</td>
                  ))}
                </tr>
                <tr>
                  <td>Taste Similarity</td>
                  {compared.map(item => (
                    <td key={item.id}>{item.score_breakdown?.taste_similarity ?? "—"}%</td>
                  ))}
                </tr>
                <tr>
                  <td>Interest Alignment</td>
                  {compared.map(item => (
                    <td key={item.id}>{item.score_breakdown?.interest_match ?? "—"}%</td>
                  ))}
                </tr>
                <tr>
                  <td>Novelty / Gem Score</td>
                  {compared.map(item => (
                    <td key={item.id}>{item.score_breakdown?.novelty_bonus ?? "—"}%</td>
                  ))}
                </tr>
                <tr>
                  <td>Why it fits you</td>
                  {compared.map(item => (
                    <td key={item.id}>{item.reason}</td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      )}

      <State query={recs} count={recs.data?.items.length}>
        <div className="collection-summary">
          <Sparkles size={16} />
          {recs.data?.reason}
          <span>{recs.data?.items.length} products to explore</span>
        </div>
        <ProductGrid
          items={recs.data?.items}
          requestId={recs.data?.request_id}
          showBreakdown={showBreakdown}
          onCompare={toggleCompare}
          comparedIds={compared.map(p => p.id)}
        />

        {bundle && bundle.items?.length >= 2 && (
          <section className="bundle-box" aria-label="Smart ecosystem bundle">
            <div className="bundle-copy">
              <span className="eyebrow">
                <Layers size={14} /> {bundle.synergy_pct}% Ecosystem Synergy
              </span>
              <h2>{bundle.headline}</h2>
              <p>{bundle.subtitle}</p>
              <div className="bundle-meta">
                <span>
                  Combined bundle value: <strong>${bundle.total_price.toFixed(2)}</strong>
                </span>
                <button
                  type="button"
                  className="button"
                  disabled={savingBundle}
                  onClick={() => saveBundle(bundle.items)}
                >
                  <Heart size={15} />
                  {savingBundle ? "Saving bundle..." : "Save all to collection"}
                </button>
              </div>
            </div>
            <div className="bundle-items">
              {bundle.items.map((item, idx) => (
                <Link key={item.id} href={"/products/" + item.id} className="bundle-card">
                  <span className="bundle-role">{idx === 0 ? "Anchor Pick" : "Companion"}</span>
                  <ProductPhoto product={item} width={160} height={140} />
                  <strong>{item.title}</strong>
                  <small>{item.category}</small>
                  <Price product={item} />
                </Link>
              ))}
            </div>
          </section>
        )}

        {lanes.map(lane => (
          <section key={lane.id} className="retail-section lane-section">
            <SectionTitle
              title={lane.title}
              subtitle={lane.subtitle}
              link="/catalog"
              label="Explore catalog"
            />
            <ProductGrid
              items={lane.items}
              requestId={recs.data?.request_id}
              layout="rail"
              showBreakdown={showBreakdown}
            />
          </section>
        ))}
      </State>
    </div>
  );
}
export function Saved() {
  const me = useMe(),
    items = useQuery({ queryKey: ["favorites"], queryFn: () => api("/favorites") });
  return (
    <div className="container collection-page">
      <PageHeading
        eyebrow="Your wishlist"
        title="Your saved collection"
        description="Keep the products you love together. Find them whenever inspiration strikes."
      >
        <Link href="/catalog" className="button secondary">
          Continue exploring
          <ArrowRight size={16} />
        </Link>
      </PageHeading>
      <State query={items} count={items.data?.items.length} empty="Your next favorite is waiting">
        {me.data?.user && (
          <div className="collection-summary">
            <Heart size={17} />
            {items.data?.items.length} saved products<span>Saved to your account</span>
          </div>
        )}
        <ProductGrid items={items.data?.items} saved />
      </State>
    </div>
  );
}
