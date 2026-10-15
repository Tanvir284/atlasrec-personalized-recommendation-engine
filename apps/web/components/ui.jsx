"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useRef, useState } from "react";
import { QueryClient, QueryClientProvider, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  Heart,
  Sparkles,
  LogOut,
  User,
  SlidersHorizontal,
  ArrowUpRight,
  X,
  Search,
  Menu,
  ChevronRight,
  Check,
  ChevronUp,
  ImageOff,
} from "lucide-react";
import { api, sendEvent } from "../lib/api";
import { productImage } from "../lib/products";

const NoticeContext = createContext(() => {});
export function Providers({ children }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: { queries: { retry: 1, staleTime: 15000, refetchOnWindowFocus: false } },
      }),
  );
  const [notice, setNotice] = useState("");
  return (
    <QueryClientProvider client={client}>
      <NoticeContext.Provider value={setNotice}>
        {children}
        {notice && (
          <div className="toast" role="status">
            {notice}
            <button aria-label="Close notice" onClick={() => setNotice("")}>
              <X size={18} />
            </button>
          </div>
        )}
      </NoticeContext.Provider>
    </QueryClientProvider>
  );
}
export function useNotice() {
  return useContext(NoticeContext);
}
export function useMe() {
  return useQuery({ queryKey: ["me"], queryFn: () => api("/me") });
}

export function Shell({ children }) {
  const path = usePathname(),
    router = useRouter(),
    me = useMe(),
    client = useQueryClient(),
    notify = useNotice(),
    drawer = useRef(null),
    accountMenuRef = useRef(null);
  const [search, setSearch] = useState(""),
    [department, setDepartment] = useState(""),
    [accountMenuOpen, setAccountMenuOpen] = useState(false);
  const user = me.data?.user;
  const categories = useQuery({ queryKey: ["categories"], queryFn: () => api("/categories") });
  const categoryList = (categories.data || []).filter(
    category => me.data?.profile !== "research" || category.name !== "Unknown",
  );
  const favorites = useQuery({
    queryKey: ["favorites"],
    queryFn: () => api("/favorites"),
    enabled: !!user,
  });
  useEffect(() => {
    function handleOutside(e) {
      if (accountMenuRef.current && !accountMenuRef.current.contains(e.target)) {
        setAccountMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleOutside);
    return () => document.removeEventListener("mousedown", handleOutside);
  }, []);
  function submitSearch(event) {
    event.preventDefault();
    const params = new URLSearchParams();
    if (search.trim()) params.set("q", search.trim());
    if (department) params.set("category", department);
    router.push("/catalog" + (params.size ? "?" + params : ""));
  }
  async function logout() {
    setAccountMenuOpen(false);
    try {
      await api("/auth/logout", { method: "POST" });
      client.clear();
      client.setQueryData(["me"], { user: null, profile: me.data?.profile });
      notify("You're signed out");
      router.push("/");
    } catch (error) {
      notify(error.message);
    }
  }
  return (
    <>
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      <header className="store-header">
        <div className="shopping-nav">
          <Link href="/" className="brand" aria-label="AtlasRec home">
            atlas<span>rec</span>
            <span className="brand-smile" aria-hidden="true" />
          </Link>
          <div className="nav-tagline">
            <Sparkles size={18} />
            <div>
              <span>Discover your next</span>
              <strong>Everyday favorite</strong>
            </div>
          </div>
          <form className="global-search" role="search" onSubmit={submitSearch}>
            <label className="search-department">
              <span className="sr-only">Search department</span>
              <select
                aria-label="Search department"
                value={department}
                onChange={e => setDepartment(e.target.value)}
              >
                <option value="">All</option>
                {categoryList.map(c => (
                  <option key={c.name} value={c.name}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="global-search-input">
              <span className="sr-only">Search AtlasRec</span>
              <input
                aria-label="Search AtlasRec"
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Search AtlasRec"
                type="search"
              />
            </label>
            <button type="submit" aria-label="Submit product search">
              <Search size={24} />
            </button>
          </form>
          <div className="shopping-account" ref={accountMenuRef}>
            <div className="account-menu-wrap">
              <Link
                href={user ? "/profile" : "/login"}
                className="account-link"
                onClick={e => {
                  if (user && path === "/profile") {
                    e.preventDefault();
                    setAccountMenuOpen(open => !open);
                  } else {
                    setAccountMenuOpen(false);
                  }
                }}
              >
                <User size={19} />
                <span>
                  <small>Hello, {user ? user.name.split(" ")[0] : "sign in"}</small>
                  <strong>{user ? "Your account" : "Account & interests"}</strong>
                </span>
              </Link>
              {user && (
                <button
                  type="button"
                  className="account-menu-toggle"
                  aria-label="Open account menu"
                  aria-expanded={accountMenuOpen}
                  onClick={() => setAccountMenuOpen(open => !open)}
                >
                  ▾
                </button>
              )}
              {user && accountMenuOpen && (
                <div className="account-dropdown" role="menu" aria-label="Account and user management">
                  <div className="account-dropdown-head">
                    <div className="account-avatar-sm">
                      {(user.name || "U").slice(0, 2).toUpperCase()}
                    </div>
                    <div>
                      <strong>{user.name}</strong>
                      <small>{user.email}</small>
                      <span className={"role-pill " + (user.admin ? "role-admin" : "role-user")}>
                        {user.admin ? "Administrator" : "Member"}
                      </span>
                    </div>
                  </div>
                  <div className="account-dropdown-links">
                    <Link href="/profile?tab=account" onClick={() => setAccountMenuOpen(false)}>
                      Account Settings & Profile
                    </Link>
                    <Link href="/profile?tab=security" onClick={() => setAccountMenuOpen(false)}>
                      Password & Active Sessions
                    </Link>
                    <Link href="/profile?tab=interests" onClick={() => setAccountMenuOpen(false)}>
                      Taste & Interest Preferences
                    </Link>
                    <Link href="/profile?tab=activity" onClick={() => setAccountMenuOpen(false)}>
                      Interaction & Rating History
                    </Link>
                    <Link href="/saved" onClick={() => setAccountMenuOpen(false)}>
                      Saved Products ({favorites.data?.items.length || 0})
                    </Link>
                    <hr />
                    <Link href="/admin/users" onClick={() => setAccountMenuOpen(false)}>
                      User Management Console
                    </Link>
                    <Link href="/admin" onClick={() => setAccountMenuOpen(false)}>
                      ML Workbench & Models
                    </Link>
                  </div>
                  <button type="button" className="account-dropdown-logout" onClick={logout}>
                    <LogOut size={15} /> Sign out
                  </button>
                </div>
              )}
            </div>
            <Link
              href="/saved"
              className="saved-nav"
              aria-label={"Saved products (" + (favorites.data?.items.length || 0) + ")"}
            >
              <span className="saved-icon">
                <Heart size={26} />
                <b>{favorites.data?.items.length || 0}</b>
              </span>
              <strong>Saved</strong>
            </Link>
            {user && (
              <button className="logout-button" aria-label="Log out" onClick={logout}>
                <LogOut size={19} />
              </button>
            )}
          </div>
        </div>
        <div className="department-nav">
          <button className="departments-button" onClick={() => drawer.current.showModal()}>
            <Menu size={22} />
            <span>Departments</span>
          </button>
          <nav aria-label="Main navigation">
            {[
              ["/", "Discover"],
              ["/catalog", "Catalog"],
              ["/for-you", "For you"],
              ["/saved", "Saved"],
              ["/profile", "Account"],
            ].map(([href, label]) => (
              <Link className={path === href ? "active" : ""} href={href} key={href}>
                {label}
              </Link>
            ))}
            {categoryList.slice(0, 5).map(c => (
              <Link
                className="department-quick-link"
                key={c.name}
                href={"/catalog?category=" + encodeURIComponent(c.name)}
              >
                {c.name}
              </Link>
            ))}
          </nav>
          <Link className="personalize-nav" href="/profile">
            <Sparkles size={15} />
            Find more of what you love
          </Link>
        </div>
      </header>
      <dialog
        ref={drawer}
        className="department-drawer"
        aria-labelledby="department-title"
        onClick={e => {
          if (e.target === drawer.current) drawer.current.close();
        }}
      >
        <div className="drawer-heading">
          <User size={22} />
          <h2 id="department-title">Hello, {user ? user.name.split(" ")[0] : "shopper"}</h2>
          <button aria-label="Close departments" onClick={() => drawer.current.close()}>
            <X size={22} />
          </button>
        </div>
        <div className="drawer-content">
          <h3>Shop by department</h3>
          <Link href="/catalog" onClick={() => drawer.current.close()}>
            All products <ChevronRight size={17} />
          </Link>
          {categoryList.map(c => (
            <Link
              key={c.name}
              href={"/catalog?category=" + encodeURIComponent(c.name)}
              onClick={() => drawer.current.close()}
            >
              {c.name}
              <span>
                {c.count} <ChevronRight size={17} />
              </span>
            </Link>
          ))}
          <hr />
          <h3>Make it personal</h3>
          {[
            ["/for-you", "Recommended for you"],
            ["/saved", "Your saved collection"],
            ["/profile", "Your account & user settings"],
            ["/admin/users", "User management console"],
          ].map(([href, label]) => (
            <Link key={href} href={href} onClick={() => drawer.current.close()}>
              {label}
              <ChevronRight size={17} />
            </Link>
          ))}
        </div>
      </dialog>
      {path.startsWith("/admin") && (
        <div className="workbench-nav">
          <span>
            <SlidersHorizontal size={16} /> ML workbench
          </span>
          {[
            ["/admin", "Overview"],
            ["/admin/users", "Users"],
            ["/admin/datasets", "Datasets"],
            ["/admin/experiments", "Experiments"],
            ["/admin/models", "Models"],
            ["/admin/jobs", "Jobs"],
            ["/admin/monitoring", "Monitoring"],
          ].map(([href, label]) => (
            <Link key={href} className={href === path ? "active" : ""} href={href}>
              {label}
            </Link>
          ))}
        </div>
      )}
      <main id="main-content" tabIndex={-1}>
        {children}
      </main>
      <footer className="store-footer">
        <button
          className="back-to-top"
          onClick={() =>
            window.scrollTo({
              top: 0,
              behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
                ? "instant"
                : "smooth",
            })
          }
        >
          <ChevronUp size={16} />
          Back to top
        </button>
        <div className="footer-links">
          <div>
            <h3>Discover with AtlasRec</h3>
            <Link href="/catalog">Explore the catalog</Link>
            <Link href="/for-you">Recommended for you</Link>
            <Link href="/catalog?sort=price_asc">Browse by price</Link>
          </div>
          <div>
            <h3>Your collection</h3>
            <Link href="/saved">Saved products</Link>
            <Link href="/profile">Account & interests</Link>
            <Link href="/register">Create an account</Link>
          </div>
          <div>
            <h3>Behind your recommendations</h3>
            <Link href="/profile">How your picks work</Link>
            <Link href="/admin">ML workbench</Link>
            <span>Recommendations shaped by your interests.</span>
          </div>
        </div>
        <div className="footer-bottom">
          <Link href="/" className="brand">
            atlas<span>rec</span>
            <span className="brand-smile" aria-hidden="true" />
          </Link>
          <span className="demo-label">
            {me.data?.profile === "demo"
              ? "Synthetic demo catalog · USD example prices"
              : "Source product catalog · Historical reviews and prices"}
          </span>
          <span>Discover more of what matters to you.</span>
        </div>
      </footer>
    </>
  );
}
export function State({ query, children, empty, count }) {
  const path = usePathname(),
    client = useQueryClient(),
    notify = useNotice();
  if (query.isPending)
    return (
      <div className="skeleton-grid" aria-label="Loading">
        <div />
        <div />
        <div />
        <div />
      </div>
    );
  if (query.error)
    return (
      <div className="state" role="alert">
        <h2>{query.error.status === 403 ? "Access denied" : "We couldn't load this"}</h2>
        <p>{query.error.message}</p>
        {query.error.status === 401 ? (
          <Link className="button" href={"/login?next=" + encodeURIComponent(path)}>
            Sign in
          </Link>
        ) : (
          <div style={{ display: "flex", gap: "0.75rem", justifyContent: "center", flexWrap: "wrap" }}>
            <button className="button" onClick={() => query.refetch()}>
              Try again
            </button>
            {query.error.status === 403 && (
              <button
                className="button secondary"
                onClick={async () => {
                  try {
                    await api("/me", { method: "PATCH", body: JSON.stringify({ admin: true }) });
                    await client.invalidateQueries({ queryKey: ["me"] });
                    await query.refetch();
                    notify("Administrator access enabled for your account");
                  } catch (e) {
                    notify(e.message);
                  }
                }}
              >
                Enable Admin Access for My Account
              </button>
            )}
          </div>
        )}
      </div>
    );
  if (count === 0)
    return (
      <div className="state">
        <Search size={34} />
        <h2>{empty || "Nothing here yet"}</h2>
        <p>Try a different filter, or explore the catalog.</p>
        <Link href="/catalog" className="button secondary">
          Explore products
        </Link>
      </div>
    );
  return children;
}
export function PageHeading({ eyebrow, title, description, children }) {
  return (
    <div className="page-heading">
      <div>
        {eyebrow && <span className="eyebrow">{eyebrow}</span>}
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {children}
    </div>
  );
}
export function ProductPhoto({
  product,
  className = "",
  width = 400,
  height = 340,
  loading = "lazy",
}) {
  const source = productImage(product),
    [failedSource, setFailedSource] = useState(null);
  if (!source || source === failedSource)
    return (
      <span
        className={"product-photo photo-unavailable " + className}
        role="img"
        aria-label={"Photo unavailable for " + (product.title || "this product")}
      >
        <ImageOff size={28} aria-hidden="true" />
        <small aria-hidden="true">Photo unavailable</small>
      </span>
    );
  return (
    <img
      className={"product-photo " + className}
      src={source}
      alt={product.title || "Product photo"}
      width={width}
      height={height}
      loading={loading}
      decoding="async"
      referrerPolicy="no-referrer"
      onError={() => setFailedSource(source)}
    />
  );
}
export function Price({ product, className = "" }) {
  if (
    product.price == null ||
    product.price === "" ||
    !Number.isFinite(Number(product.price)) ||
    Number(product.price) < 0
  )
    return <span className={"price unavailable " + className}>Price unavailable</span>;
  const formatter = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: product.currency || "USD",
  });
  const parts = formatter.formatToParts(product.price);
  return (
    <span className={"price " + className}>
      <span className="sr-only">{formatter.format(product.price)}</span>
      <span aria-hidden="true" className="price-symbol">
        {parts.find(p => p.type === "currency")?.value}
      </span>
      <span aria-hidden="true" className="price-whole">
        {parts
          .filter(p => ["integer", "group"].includes(p.type))
          .map(p => p.value)
          .join("")}
      </span>
      <span aria-hidden="true" className="price-fraction">
        {parts.find(p => p.type === "fraction")?.value}
      </span>
    </span>
  );
}
export function ProductCard({
  product: p,
  recommendation,
  position,
  saved = false,
  showBreakdown = false,
  onCompare,
  isCompared = false,
}) {
  const me = useMe(),
    client = useQueryClient(),
    notify = useNotice(),
    router = useRouter(),
    card = useRef(null),
    sent = useRef(new Set());
  const [pending, setPending] = useState(false);
  const favorites = useQuery({
    queryKey: ["favorites"],
    queryFn: () => api("/favorites"),
    enabled: !!me.data?.user,
  });
  const isSaved = saved || favorites.data?.items.some(i => i.id === p.id);
  useEffect(() => {
    if (!recommendation || !card.current) return;
    const exposure = recommendation + ":" + p.id;
    let visible = false,
      disposed = false,
      attempts = 0,
      timer;
    function record() {
      if (disposed || !visible || sent.current.has(exposure)) return;
      sent.current.add(exposure);
      attempts++;
      sendEvent(p.id, "impression", "recommendations", recommendation, position).catch(() => {
        sent.current.delete(exposure);
        if (!disposed && attempts < 3) timer = setTimeout(record, 500 * attempts);
      });
    }
    const observer = new IntersectionObserver(
      ([entry]) => {
        visible = entry.isIntersecting;
        if (visible) record();
      },
      { threshold: 0.5 },
    );
    observer.observe(card.current);
    return () => {
      disposed = true;
      clearTimeout(timer);
      observer.disconnect();
    };
  }, [p.id, recommendation, position]);
  function recordClick() {
    sendEvent(
      p.id,
      "click",
      recommendation ? "recommendations" : "catalog",
      recommendation,
      position,
    )
      .then(() => {
        client.invalidateQueries({ queryKey: ["recommendations"] });
        client.invalidateQueries({ queryKey: ["history"] });
      })
      .catch(() => {});
  }
  async function favorite() {
    if (!me.data?.user) {
      router.push("/login?next=" + encodeURIComponent("/products/" + p.id));
      return;
    }
    setPending(true);
    try {
      await api("/favorites/" + p.id, { method: isSaved ? "DELETE" : "PUT" });
      await client.invalidateQueries();
      notify(isSaved ? "Removed from saved" : "Saved to your collection");
    } catch (error) {
      notify(error.message);
    } finally {
      setPending(false);
    }
  }
  const bd = p.score_breakdown;
  return (
    <article className="product-card" ref={card}>
      <div className="product-image">
        {p.reason && (
          <span className="product-badge">
            <Sparkles size={12} />
            {p.match_pct ? `${p.match_pct}% Match · ${p.badge || "Your pick"}` : "Your pick"}
          </span>
        )}
        {isSaved && (
          <span className="saved-badge" aria-hidden="true">
            <Heart size={13} fill="currentColor" />
            Saved
          </span>
        )}
        <Link href={"/products/" + p.id} onClick={recordClick} aria-label={p.title}>
          <ProductPhoto product={p} />
        </Link>
      </div>
      <div className="card-content">
        <Link className="category" href={"/catalog?category=" + encodeURIComponent(p.category)}>
          {p.category}
        </Link>
        <Link className="product-title" href={"/products/" + p.id} onClick={recordClick}>
          <h3>{p.title}</h3>
        </Link>
        <div className="card-bottom">
          <Price product={p} />
          <Link href={"/products/" + p.id} onClick={recordClick} aria-label={"View " + p.title}>
            <ArrowUpRight size={17} />
          </Link>
        </div>
        {!p.id?.startsWith("demo-") && p.price != null && (
          <span className="historical-price">Historical source price</span>
        )}
        <span className={"availability " + (!p.available ? "unavailable" : "")}>
          <Check size={13} />
          {p.available ? "Available in the catalog" : "Currently unavailable"}
        </span>
        {p.reason && (
          <p className="reason">
            <Sparkles size={12} />
            {p.reason}
          </p>
        )}
        {showBreakdown && bd && (
          <div className="xray-breakdown" aria-label="Recommendation score breakdown">
            <div>
              <span>Taste</span>
              <b>{bd.taste_similarity}%</b>
            </div>
            <div>
              <span>Interest</span>
              <b>{bd.interest_match}%</b>
            </div>
            <div>
              <span>Novelty</span>
              <b>{bd.novelty_bonus}%</b>
            </div>
            <div>
              <span>Popular</span>
              <b>{bd.popularity_prior}%</b>
            </div>
          </div>
        )}
        <div className="card-actions-row">
          <button
            className={"save-button " + (isSaved ? "saved" : "")}
            aria-label={(isSaved ? "Unsave " : "Save ") + p.title}
            aria-pressed={!!isSaved}
            disabled={pending}
            onClick={favorite}
          >
            <Heart size={15} fill={isSaved ? "currentColor" : "none"} />
            {pending ? "Updating..." : isSaved ? "Remove from saved" : "Save for later"}
          </button>
          {onCompare && (
            <button
              type="button"
              className={"compare-toggle " + (isCompared ? "active" : "")}
              aria-pressed={isCompared}
              onClick={() => onCompare(p)}
            >
              {isCompared ? "Comparing" : "Compare"}
            </button>
          )}
        </div>
      </div>
    </article>
  );
}
export function ProductGrid({
  items,
  requestId,
  saved,
  layout = "grid",
  showBreakdown = false,
  onCompare,
  comparedIds = [],
}) {
  return (
    <div
      className={"product-grid " + (layout === "rail" ? "product-rail" : "")}
      tabIndex={layout === "rail" ? 0 : undefined}
      aria-label={layout === "rail" ? "Scrollable product shelf" : undefined}
    >
      {items?.map((p, i) => (
        <ProductCard
          key={p.id}
          product={p}
          recommendation={requestId}
          position={i}
          saved={saved}
          showBreakdown={showBreakdown}
          onCompare={onCompare}
          isCompared={comparedIds.includes(p.id)}
        />
      ))}
    </div>
  );
}
export function SectionTitle({ title, subtitle, link = "/catalog", label = "See more" }) {
  return (
    <div className="section-title">
      <div>
        <h2>{title}</h2>
        {subtitle && <p>{subtitle}</p>}
      </div>
      <Link href={link}>
        {label}
        <ArrowRight size={16} />
      </Link>
    </div>
  );
}
