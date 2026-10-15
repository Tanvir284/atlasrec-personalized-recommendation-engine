"use client";
// Searchable, filterable, paginated catalog.
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Sparkles, SlidersHorizontal, ChevronRight, X } from "lucide-react";
import { api } from "../../lib/api";
import { ProductGrid, State, useMe } from "../ui";

export function Catalog() {
  const params = useSearchParams(),
    router = useRouter(),
    queryString = params.toString();
  const me = useMe();
  const [filtersOpen, setFiltersOpen] = useState(false),
    [priceError, setPriceError] = useState(""),
    [categoryFilter, setCategoryFilter] = useState("");
  const products = useQuery({
    queryKey: ["catalog", queryString],
    queryFn: () => api("/products?" + queryString),
  });
  const categories = useQuery({ queryKey: ["categories"], queryFn: () => api("/categories") });
  const visibleCategories = (categories.data || []).filter(
    c => me.data?.profile !== "research" || c.name !== "Unknown",
  );
  const filteredCategories = visibleCategories.filter(c =>
    c.name.toLowerCase().includes(categoryFilter.toLowerCase()),
  );
  function update(key, value) {
    const next = new URLSearchParams(queryString);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key !== "page") next.delete("page");
    router.push("/catalog" + (next.size ? "?" + next : ""));
  }
  function applyFilters(event) {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    const min = values.get("min_price"),
      max = values.get("max_price");
    if (min !== "" && max !== "" && Number(min) > Number(max)) {
      setPriceError("Minimum price must be less than maximum price.");
      return;
    }
    setPriceError("");
    const next = new URLSearchParams(queryString);
    for (const key of ["q", "min_price", "max_price"]) {
      const value = String(values.get(key) || "").trim();
      if (value) next.set(key, value);
      else next.delete(key);
    }
    next.delete("page");
    router.push("/catalog" + (next.size ? "?" + next : ""));
  }
  const selected = params.get("category"),
    term = params.get("q"),
    data = products.data,
    pageSize = Number(params.get("limit")) || 20;
  const chips = [
    ["category", selected],
    ["q", term],
    ["min_price", params.get("min_price") ? "From $" + params.get("min_price") : null],
    ["max_price", params.get("max_price") ? "Up to $" + params.get("max_price") : null],
  ].filter(([, value]) => value);
  return (
    <div className="catalog-page container">
      <div className="breadcrumbs">
        <Link href="/">Home</Link>
        <ChevronRight size={13} />
        <Link href="/catalog">Catalog</Link>
        {selected && (
          <>
            <ChevronRight size={13} />
            <span>{selected}</span>
          </>
        )}
      </div>
      <div className="catalog-heading">
        <div>
          <h1>{term ? 'Results for "' + term + '"' : selected || "The catalog"}</h1>
          <p>
            {term
              ? "Find the right fit for what you're looking for."
              : "Find your next everyday favorite."}
          </p>
        </div>
        <Link href="/for-you" className="shop-link">
          <Sparkles size={15} />
          Your recommendations
        </Link>
      </div>
      {me.data?.profile === "research" && (
        <p className="source-catalog-note">
          Original product photos and descriptions from the source dataset. Listed prices are
          historical; missing prices are shown as unavailable.
        </p>
      )}
      <div className="catalog-toolbar">
        <span>
          {data
            ? (data.total
                ? (data.page - 1) * pageSize +
                  1 +
                  "–" +
                  Math.min(data.page * pageSize, data.total) +
                  " of "
                : "") +
              data.total +
              " results"
            : "Loading products..."}
        </span>
        <div>
          <button
            className="mobile-filter-toggle"
            aria-expanded={filtersOpen}
            aria-controls="catalog-filters"
            onClick={() => setFiltersOpen(!filtersOpen)}
          >
            <SlidersHorizontal size={16} />
            Filters
          </button>
          <label className="sort-control">
            Sort by
            <select
              aria-label="Sort products"
              value={params.get("sort") || "title"}
              onChange={e => update("sort", e.target.value)}
            >
              <option value="title">Name</option>
              <option value="price_asc">Price: low to high</option>
              <option value="price_desc">Price: high to low</option>
            </select>
          </label>
        </div>
      </div>
      <div className="catalog-layout">
        <aside id="catalog-filters" className={"catalog-sidebar " + (filtersOpen ? "is-open" : "")}>
          <div className="filter-heading">
            <h2>Filters</h2>
            {chips.length > 0 && <Link href="/catalog">Clear all</Link>}
          </div>
          <div className="department-filter">
            <h3>Department ({visibleCategories.length})</h3>
            <input
              type="text"
              placeholder="Search categories..."
              value={categoryFilter}
              onChange={e => setCategoryFilter(e.target.value)}
              className="category-search-input"
            />
            <div className="department-filter-list">
              <label>
                <input
                  type="radio"
                  name="department"
                  checked={!selected}
                  onChange={() => update("category", "")}
                />
                All departments
              </label>
              {filteredCategories.map(category => (
                <label key={category.name}>
                  <input
                    type="radio"
                    name="department"
                    checked={selected === category.name}
                    onChange={() => update("category", category.name)}
                  />
                  <span>{category.name}</span>
                  <small>{category.count}</small>
                </label>
              ))}
            </div>
          </div>
          <form key={queryString} onSubmit={applyFilters}>
            <fieldset>
              <legend>Search within results</legend>
              <input
                name="q"
                aria-label="Search products"
                placeholder="Product name"
                defaultValue={term || ""}
              />
            </fieldset>
            <fieldset>
              <legend>Price range (USD)</legend>
              <div className="price-inputs">
                <label>
                  Min
                  <input
                    type="number"
                    name="min_price"
                    aria-label="Minimum price"
                    min="0"
                    step="0.01"
                    placeholder="$ Min"
                    defaultValue={params.get("min_price") || ""}
                  />
                </label>
                <span>–</span>
                <label>
                  Max
                  <input
                    type="number"
                    name="max_price"
                    aria-label="Maximum price"
                    min="0"
                    step="0.01"
                    placeholder="$ Max"
                    defaultValue={params.get("max_price") || ""}
                  />
                </label>
              </div>
              {priceError && (
                <p role="alert" className="form-error">
                  {priceError}
                </p>
              )}
            </fieldset>
            <button className="button secondary" type="submit">
              Apply filters
            </button>
          </form>
          <div className="filter-tip">
            <Sparkles size={18} />
            <strong>A little more you.</strong>
            <p>Your interests help us find related products you'll want to explore.</p>
            <Link href="/profile">
              Choose your interests
              <ChevronRight size={13} />
            </Link>
          </div>
        </aside>
        <section className="catalog-results" aria-label="Product results">
          {chips.length > 0 && (
            <div className="filter-chips">
              {chips.map(([key, value]) => (
                <button
                  key={key}
                  onClick={() => update(key, "")}
                  aria-label={"Remove filter " + value}
                >
                  {value}
                  <X size={13} />
                </button>
              ))}
              <Link href="/catalog">Clear filters</Link>
            </div>
          )}
          <State query={products} count={data?.items.length} empty="No products match your search">
            <ProductGrid items={data?.items} />
            <div className="pagination">
              <button
                disabled={(data?.page || 1) <= 1}
                onClick={() => update("page", String(data.page - 1))}
              >
                Previous
              </button>
              <span>
                Page {data?.page} of {data?.pages}
              </span>
              <button
                disabled={data?.page >= data?.pages}
                onClick={() => update("page", String(data.page + 1))}
              >
                Next
              </button>
            </div>
          </State>
        </section>
      </div>
    </div>
  );
}
