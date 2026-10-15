"use client";
// Sign-in / registration form and shopper profile & user management center.
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  Check,
  KeyRound,
  MonitorSmartphone,
  ShieldCheck,
  Sparkles,
  Trash2,
  UserCheck,
  UserCog,
  Users,
} from "lucide-react";
import { api } from "../../lib/api";
import { productImage } from "../../lib/products";
import { PageHeading, ProductPhoto, useMe, useNotice } from "../ui";

export function Auth({ register = false }) {
  const router = useRouter(),
    client = useQueryClient(),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [returnPath, setReturnPath] = useState("");
  const me = useMe(),
    demo = me.data?.profile === "demo";
  const products = useQuery({
    queryKey: ["popular"],
    queryFn: () => api("/products?limit=10"),
    enabled: !demo,
  });
  const featured = demo
    ? { id: "demo-headphones", title: "Studio headphones", image: "/products/store/headphones.svg" }
    : products.data?.items.find(product => productImage(product));
  useEffect(() => {
    const next = new URLSearchParams(window.location.search).get("next");
    if (next?.startsWith("/") && !next.startsWith("//") && !next.includes("\\"))
      setReturnPath(next);
  }, []);
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const data = Object.fromEntries(new FormData(e.currentTarget));
    try {
      await api(register ? "/auth/register" : "/auth/login", {
        method: "POST",
        body: JSON.stringify(data),
      });
      client.clear();
      await client.fetchQuery({ queryKey: ["me"], queryFn: () => api("/me") });
      const next = new URLSearchParams(window.location.search).get("next");
      router.push(
        next?.startsWith("/") && !next.startsWith("//") && !next.includes("\\")
          ? next
          : register
            ? "/profile"
            : "/for-you",
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="auth-page">
      <div className="auth-story">
        <span className="eyebrow">Welcome to your next discovery</span>
        <h1>
          Good finds.
          <br />
          Great possibilities.
          <br />
          <em>Made for you.</em>
        </h1>
        <p>
          A few favorites. A few interests.
          <br />A little more of what you love.
        </p>
        {featured && <ProductPhoto product={featured} width={300} height={250} />}
      </div>
      <div className="auth-form">
        <span className="eyebrow">Welcome to AtlasRec</span>
        <h2>{register ? "Make yourself at home." : "Good to see you again."}</h2>
        <p>
          {register
            ? "Create your account and start discovering."
            : "Sign in to pick up where you left off."}
        </p>
        <form onSubmit={submit}>
          {register && (
            <label>
              Your name
              <input name="name" autoComplete="name" required maxLength="80" />
            </label>
          )}
          <label>
            Email address
            <input name="email" type="email" autoComplete="email" required />
          </label>
          <label>
            Password
            <input
              name="password"
              type="password"
              minLength="10"
              maxLength="128"
              autoComplete={register ? "new-password" : "current-password"}
              required
            />
          </label>
          <span className="muted">At least 10 characters.</span>
          {error && (
            <p role="alert" className="form-error">
              {error}
            </p>
          )}
          <button className="button" disabled={busy}>
            {busy ? "Please wait…" : register ? "Create account" : "Sign in"}
            <ArrowRight size={17} />
          </button>
        </form>
        <p>
          {register ? "Already have an account?" : "New here?"}{" "}
          <Link
            href={
              (register ? "/login" : "/register") +
              (returnPath ? "?next=" + encodeURIComponent(returnPath) : "")
            }
          >
            {register ? "Sign in" : "Create an account"}
          </Link>
        </p>
      </div>
    </div>
  );
}

export function Profile() {
  const me = useMe(),
    router = useRouter(),
    searchParams = useSearchParams(),
    cats = useQuery({ queryKey: ["categories"], queryFn: () => api("/categories") }),
    client = useQueryClient(),
    notify = useNotice();
  const user = me.data?.user;
  const history = useQuery({
    queryKey: ["history"],
    queryFn: () => api("/me/history"),
    enabled: !!user,
  });
  const sessions = useQuery({
    queryKey: ["sessions"],
    queryFn: () => api("/me/sessions"),
    enabled: !!user,
  });

  const tabParam = searchParams.get("tab") || "all";
  const [activeTab, setActiveTab] = useState(tabParam);
  useEffect(() => {
    setActiveTab(searchParams.get("tab") || "all");
  }, [searchParams]);

  const [draft, setDraft] = useState(null),
    [interestFilter, setInterestFilter] = useState(""),
    [showAllCategories, setShowAllCategories] = useState(false),
    [historyKindFilter, setHistoryKindFilter] = useState("all"),
    [profileName, setProfileName] = useState(""),
    [profileEmail, setProfileEmail] = useState(""),
    [profilePassword, setProfilePassword] = useState(""),
    [profileAdmin, setProfileAdmin] = useState(false),
    [savingProfile, setSavingProfile] = useState(false),
    [currentPassword, setCurrentPassword] = useState(""),
    [newPassword, setNewPassword] = useState(""),
    [savingPassword, setSavingPassword] = useState(false);

  useEffect(() => {
    if (user) {
      setProfileName(user.name || "");
      setProfileEmail(user.email || "");
      setProfileAdmin(Boolean(user.admin));
    }
  }, [user]);

  const chosen = draft ?? user?.preferences ?? [];
  const availableCategories = (cats.data || []).filter(
    c => me.data?.profile !== "research" || c.name !== "Unknown",
  );
  const filteredCategories = availableCategories.filter(c =>
    c.name.toLowerCase().includes(interestFilter.toLowerCase()),
  );
  const visibleCategories =
    interestFilter.trim() || showAllCategories
      ? filteredCategories
      : [
          ...filteredCategories.filter(c => chosen.includes(c.name)),
          ...filteredCategories.filter(c => !chosen.includes(c.name)).slice(0, 24),
        ];

  const meaningfulHistory = (history.data || []).filter(e => e.kind !== "impression");
  const filteredHistory =
    historyKindFilter === "all"
      ? meaningfulHistory
      : meaningfulHistory.filter(e => e.kind === historyKindFilter);

  function toggleInterest(name) {
    if (chosen.includes(name)) {
      setDraft(chosen.filter(x => x !== name));
      return;
    }
    if (chosen.length >= 10) {
      notify("You can choose up to 10 interest categories");
      return;
    }
    setDraft([...chosen, name]);
  }

  async function save() {
    try {
      await api("/me/preferences", { method: "PUT", body: JSON.stringify({ categories: chosen }) });
      await client.invalidateQueries();
      notify("Your interests are saved");
    } catch (e) {
      notify(e.message);
    }
  }

  async function saveProfile(e) {
    e.preventDefault();
    setSavingProfile(true);
    try {
      const payload = {
        name: profileName,
        email: profileEmail,
        admin: profileAdmin,
      };
      if (profilePassword.trim()) {
        payload.password = profilePassword.trim();
      }
      await api("/me", {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      setProfilePassword("");
      await client.invalidateQueries({ queryKey: ["me"] });
      await client.invalidateQueries({ queryKey: ["admin"] });
      notify("Profile information updated successfully");
    } catch (err) {
      notify(err.message);
    } finally {
      setSavingProfile(false);
    }
  }

  async function toggleAdminRole() {
    try {
      const nextAdmin = !user?.admin;
      await api("/me", { method: "PATCH", body: JSON.stringify({ admin: nextAdmin }) });
      await client.invalidateQueries({ queryKey: ["me"] });
      await client.invalidateQueries({ queryKey: ["admin"] });
      notify(nextAdmin ? "Administrator access enabled" : "Switched to standard shopper role");
    } catch (err) {
      notify(err.message);
    }
  }

  async function updatePassword(e) {
    e.preventDefault();
    setSavingPassword(true);
    try {
      await api("/me/password", {
        method: "POST",
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      });
      setCurrentPassword("");
      setNewPassword("");
      notify("Password updated successfully");
    } catch (err) {
      notify(err.message);
    } finally {
      setSavingPassword(false);
    }
  }

  async function removeHistoryItem(eventId) {
    try {
      await api("/me/history/" + eventId, { method: "DELETE" });
      await client.invalidateQueries({ queryKey: ["history"] });
      await client.invalidateQueries({ queryKey: ["me"] });
      notify("Activity item removed");
    } catch (err) {
      notify(err.message);
    }
  }

  async function revokeOtherSessions() {
    try {
      const res = await api("/me/sessions/others", { method: "DELETE" });
      await client.invalidateQueries({ queryKey: ["sessions"] });
      await client.invalidateQueries({ queryKey: ["me"] });
      notify(`Signed out ${res.removed || 0} other session(s)`);
    } catch (err) {
      notify(err.message);
    }
  }

  async function deleteAccount() {
    if (
      !window.confirm(
        "Are you sure you want to permanently delete your account, saved items, and activity history?",
      )
    )
      return;
    try {
      await api("/me", { method: "DELETE" });
      client.clear();
      client.setQueryData(["me"], { user: null, profile: me.data?.profile });
      notify("Your account has been deleted");
      router.push("/");
    } catch (err) {
      notify(err.message);
    }
  }

  if (me.isPending) {
    return (
      <div className="container">
        <div className="skeleton-grid" aria-label="Loading">
          <div />
          <div />
        </div>
      </div>
    );
  }

  if (!user)
    return (
      <div className="state">
        <h1>Your preferences, your picks.</h1>
        <p>Sign in to manage your account, security, interests, and recommendation history.</p>
        <div style={{ display: "flex", gap: "0.75rem", justifyContent: "center", flexWrap: "wrap" }}>
          <Link href="/login" className="button">
            Sign in
          </Link>
          <Link href="/register" className="button secondary">
            Create an account
          </Link>
        </div>
      </div>
    );

  const showSection = section => activeTab === "all" || activeTab === section;

  return (
    <div className="container">
      <PageHeading
        eyebrow="Account & User Management Center"
        title="Your profile"
        description={
          "Hello, " +
          (user.name || "there") +
          ". Manage your personal details, security, taste profile, and activity history."
        }
      >
        <div style={{ display: "flex", gap: "0.6rem", flexWrap: "wrap" }}>
          <Link href="/admin/users" className="button secondary">
            <Users size={16} /> User Management Console
          </Link>
          <Link href="/admin" className="button secondary">
            <ShieldCheck size={16} /> ML Workbench
          </Link>
        </div>
      </PageHeading>

      <div className="profile-hub-banner panel">
        <div className="profile-identity">
          <div className="profile-avatar-lg">{(user.name || "U").slice(0, 2).toUpperCase()}</div>
          <div className="profile-identity-meta">
            <div className="profile-name-row">
              <h2>{user.name}</h2>
              <span className={"role-pill " + (user.admin ? "role-admin" : "role-user")}>
                {user.admin ? "Administrator" : "Verified Member"}
              </span>
            </div>
            <p className="muted">{user.email}</p>
            <small className="mono">
              User ID: {user.id.slice(0, 8)}… · Taste Revision #{user.history_revision ?? 0}
              {user.created_at
                ? " · Joined " + new Date(user.created_at).toLocaleDateString()
                : ""}
            </small>
          </div>
        </div>
        <div className="profile-kpis">
          <div className="profile-kpi">
            <span>Saved items</span>
            <strong>{user.stats?.favorites_count ?? 0}</strong>
          </div>
          <div className="profile-kpi">
            <span>Ratings given</span>
            <strong>{user.stats?.ratings_count ?? 0}</strong>
          </div>
          <div className="profile-kpi">
            <span>Interactions</span>
            <strong>{user.stats?.events_count ?? meaningfulHistory.length}</strong>
          </div>
          <div className="profile-kpi">
            <span>Active sessions</span>
            <strong>{sessions.data?.items?.length ?? user.stats?.sessions_count ?? 1}</strong>
          </div>
        </div>
      </div>

      <div className="profile-tabs" role="tablist" aria-label="Account sections">
        {[
          ["all", "All Sections"],
          ["account", "Profile & Role"],
          ["security", "Password & Sessions"],
          ["interests", "Taste & Interests"],
          ["activity", "Activity History"],
        ].map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={activeTab === id}
            className={"profile-tab-btn" + (activeTab === id ? " active" : "")}
            onClick={() => setActiveTab(id)}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="profile-management-grid">
        {showSection("account") && (
          <section className="panel">
            <h2>
              <UserCog size={19} /> Account details & role management
            </h2>
            <p className="muted">
              Update your display name, email address, or workspace permissions.
            </p>
            <form onSubmit={saveProfile} className="profile-form">
              <label>
                Full name
                <input
                  type="text"
                  value={profileName}
                  onChange={e => setProfileName(e.target.value)}
                  required
                  maxLength="80"
                />
              </label>
              <label>
                Email address
                <input
                  type="email"
                  value={profileEmail}
                  onChange={e => setProfileEmail(e.target.value)}
                  required
                />
              </label>
              <label>
                New password (optional — leave blank to keep current)
                <input
                  type="password"
                  minLength="10"
                  maxLength="128"
                  value={profilePassword}
                  onChange={e => setProfilePassword(e.target.value)}
                  placeholder="Enter at least 10 characters to change password"
                  autoComplete="new-password"
                />
              </label>
              <label>
                Account role
                <select
                  value={profileAdmin ? "admin" : "shopper"}
                  onChange={e => setProfileAdmin(e.target.value === "admin")}
                >
                  <option value="shopper">Standard Shopper</option>
                  <option value="admin">Administrator (Full Access)</option>
                </select>
              </label>
              <button className="button" disabled={savingProfile}>
                {savingProfile ? "Saving…" : "Save profile changes"}
                <Check size={16} />
              </button>
            </form>
            <div className="role-management-box">
              <div>
                <strong>
                  <UserCheck size={16} /> Workspace Role:{" "}
                  {user.admin ? "Administrator (Full Access)" : "Standard Shopper"}
                </strong>
                <p className="muted">
                  Administrators can manage all registered users, edit any user’s info, inspect
                  model experiments, promote models, and monitor live recommendation drift.
                </p>
              </div>
              <div style={{ display: "flex", gap: "0.6rem", flexWrap: "wrap" }}>
                <button type="button" className="button secondary" onClick={toggleAdminRole}>
                  {user.admin ? "Switch to Shopper Role" : "Enable Administrator Role"}
                </button>
                {user.admin && (
                  <Link href="/admin/users" className="button">
                    Open All Users Directory <ArrowRight size={16} />
                  </Link>
                )}
              </div>
            </div>
          </section>
        )}

        {showSection("security") && (
          <section className="panel">
            <h2>
              <KeyRound size={19} /> Password & active sessions
            </h2>
            <p className="muted">
              Keep your account secure by updating your password or revoking other signed-in
              devices.
            </p>
            <form onSubmit={updatePassword} className="profile-form">
              <label>
                Current password (optional)
                <input
                  type="password"
                  value={currentPassword}
                  onChange={e => setCurrentPassword(e.target.value)}
                  placeholder="Optional verification"
                  autoComplete="current-password"
                />
              </label>
              <label>
                New password (at least 10 characters)
                <input
                  type="password"
                  minLength="10"
                  maxLength="128"
                  value={newPassword}
                  onChange={e => setNewPassword(e.target.value)}
                  required
                  autoComplete="new-password"
                />
              </label>
              <button className="button" disabled={savingPassword}>
                {savingPassword ? "Updating…" : "Update password"}
              </button>
            </form>

            <div className="sessions-box">
              <div className="sessions-head">
                <h3>
                  <MonitorSmartphone size={16} /> Active sessions (
                  {sessions.data?.items?.length || 1})
                </h3>
                {(sessions.data?.items?.length || 0) > 1 && (
                  <button
                    type="button"
                    className="button secondary"
                    onClick={revokeOtherSessions}
                  >
                    Sign out other sessions
                  </button>
                )}
              </div>
              <ul className="session-list">
                {(sessions.data?.items || []).map(s => (
                  <li key={s.id}>
                    <div>
                      <strong className="mono">Session #{s.id}</strong>
                      <small className="muted">
                        Expires {new Date(s.expires_at).toLocaleDateString()}
                      </small>
                    </div>
                    {s.current ? (
                      <span className="role-pill role-admin">Current session</span>
                    ) : (
                      <button
                        type="button"
                        className="danger-button"
                        onClick={async () => {
                          await api("/me/sessions/" + s.id, { method: "DELETE" });
                          await client.invalidateQueries({ queryKey: ["sessions"] });
                          notify("Session revoked");
                        }}
                      >
                        Revoke
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          </section>
        )}
      </div>

      {showSection("interests") && (
        <section className="panel">
          <h2>
            <Sparkles size={19} /> Your interests
          </h2>
          <p>
            Choose up to 10 categories to help us get to know your taste ({chosen.length}/10
            selected).
          </p>
          {availableCategories.length > 12 && (
            <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", alignItems: "center" }}>
              <input
                type="text"
                placeholder="Filter interest categories..."
                aria-label="Filter interest categories"
                value={interestFilter}
                onChange={e => setInterestFilter(e.target.value)}
                className="category-search-input"
                style={{ flex: "1 1 260px", marginBottom: 0 }}
              />
              {!interestFilter.trim() && filteredCategories.length > 24 && (
                <button
                  type="button"
                  className="button secondary"
                  onClick={() => setShowAllCategories(prev => !prev)}
                >
                  {showAllCategories
                    ? "Show top 24 categories"
                    : `Show all ${filteredCategories.length} categories`}
                </button>
              )}
            </div>
          )}
          <div className="interest-options" style={{ marginTop: "1rem" }}>
            {visibleCategories.map(c => (
              <button
                key={c.name}
                aria-pressed={chosen.includes(c.name)}
                className={chosen.includes(c.name) ? "chosen" : ""}
                onClick={() => toggleInterest(c.name)}
              >
                {c.name}
                {chosen.includes(c.name) && <Check size={16} />}
              </button>
            ))}
          </div>
          <button className="button" onClick={save}>
            Save interests <ArrowRight size={17} />
          </button>
        </section>
      )}

      {showSection("activity") && (
        <section className="panel">
          <h2>What shapes your recommendations?</h2>
          <p>
            Saved products and items you explore help us find related picks. Your interests add
            direction; dismissed products are excluded. When you’re new, we begin with popular
            products. Feedback changes your history immediately; model training happens separately.
          </p>
          <div className="activity-header-row">
            <h3>Your recent activity ({filteredHistory.length})</h3>
            <div className="activity-filters">
              {[
                ["all", "All"],
                ["rating", "Ratings"],
                ["favorite", "Saved"],
                ["click", "Clicks"],
                ["view", "Views"],
                ["dismiss", "Dismissed"],
              ].map(([kind, label]) => (
                <button
                  key={kind}
                  type="button"
                  className={"chip-btn" + (historyKindFilter === kind ? " active" : "")}
                  onClick={() => setHistoryKindFilter(kind)}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
          {filteredHistory.length ? (
            <ul className="history-list">
              {filteredHistory.slice(0, 20).map(e => (
                <li key={e.id}>
                  <div className="history-item-main">
                    <Link href={"/products/" + e.item_id}>{e.title || e.item_id}</Link>
                    {e.timestamp && (
                      <small className="muted">
                        {new Date(e.timestamp).toLocaleDateString()}
                      </small>
                    )}
                  </div>
                  <div className="history-item-actions">
                    <span className={"status-badge status-" + e.kind}>
                      {e.kind === "rating" && e.rating ? `rated ${e.rating}/5` : e.kind}
                    </span>
                    <button
                      type="button"
                      className="history-delete-btn"
                      aria-label={"Remove " + (e.title || e.item_id) + " from history"}
                      onClick={() => removeHistoryItem(e.id)}
                      title="Remove from history"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">No activity recorded yet.</p>
          )}
          <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", marginTop: "1rem" }}>
            <button
              className="danger-button"
              onClick={async () => {
                if (!window.confirm("Clear your interaction history and saved products?")) return;
                try {
                  await api("/me/history", { method: "DELETE" });
                  await client.invalidateQueries();
                  notify("History and saved products cleared");
                } catch (e) {
                  notify(e.message);
                }
              }}
            >
              Clear history and saved products
            </button>
            <button type="button" className="danger-button" onClick={deleteAccount}>
              Delete account permanently
            </button>
          </div>
        </section>
      )}
    </div>
  );
}

