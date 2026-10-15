"use client";
import Link from "next/link";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, Database, Play, RotateCcw, Download, ShieldCheck } from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { api } from "../lib/api";
import { PageHeading, State, useNotice } from "./ui";
function Stat({ label, value }) {
  return (
    <div className="stat">
      <div>
        <span>{label}</span>
        <Activity size={17} />
      </div>
      <strong>{value ?? "—"}</strong>
    </div>
  );
}
function Label({ value }) {
  return <span className={"status-badge status-" + value}>{value}</span>;
}
export function Admin({ section = "overview" }) {
  const client = useQueryClient(),
    notify = useNotice(),
    [pending, setPending] = useState(false),
    [model, setModel] = useState("popularity"),
    [epochs, setEpochs] = useState(6),
    [seed, setSeed] = useState(42),
    [includeFeedback, setIncludeFeedback] = useState(false),
    [split, setSplit] = useState(""),
    [userSearch, setUserSearch] = useState(""),
    [roleFilter, setRoleFilter] = useState("all"),
    [newUserName, setNewUserName] = useState(""),
    [newUserEmail, setNewUserEmail] = useState(""),
    [newUserPassword, setNewUserPassword] = useState(""),
    [newUserAdmin, setNewUserAdmin] = useState(false),
    [editingUser, setEditingUser] = useState(null),
    [editUserName, setEditUserName] = useState(""),
    [editUserEmail, setEditUserEmail] = useState(""),
    [editUserPassword, setEditUserPassword] = useState(""),
    [editUserAdmin, setEditUserAdmin] = useState(false),
    [editUserPrefs, setEditUserPrefs] = useState("");
  const query = useQuery({
      queryKey: ["admin", section],
      queryFn: () => api("/admin/" + section),
      refetchInterval: section === "jobs" ? 3000 : false,
    }),
    data = query.data;
  async function mutate(path, body, method = "POST") {
    setPending(true);
    try {
      const result = await api(path, {
        method,
        ...(body ? { body: JSON.stringify(body) } : {}),
      });
      await client.invalidateQueries({ queryKey: ["admin"] });
      await client.invalidateQueries({ queryKey: ["me"] });
      notify(
        result?.status === "failed"
          ? "Could not queue training. Check the job error and retry."
          : result?.status === "queued"
            ? "Training queued"
            : "Request completed",
      );
      return result;
    } catch (e) {
      notify(e.message);
      return null;
    } finally {
      setPending(false);
    }
  }
  const headings = {
    overview: "Your recommendation system",
    users: "User management console",
    experiments: "Experiment notebook",
    models: "Model registry",
    jobs: "Training jobs",
    monitoring: "System observations",
    datasets: "Dataset registry",
  };
  const complete =
      section === "experiments" ? data?.filter(r => r.status === "completed") || [] : [],
    selected = split || complete[0]?.split_id,
    comparable = complete.filter(r => r.split_id === selected);
  function download() {
    const rows = [
      ["model", "profile", "dataset", "split", "seed", "recall@10", "ndcg@10", "runtime"],
      ...comparable.map(r => [
        r.model,
        r.profile,
        r.dataset_id,
        r.split_id,
        r.seed,
        r.metrics?.["recall@10"] ?? "",
        r.metrics?.["ndcg@10"] ?? "",
        r.training_seconds,
      ]),
    ];
    const url = URL.createObjectURL(
      new Blob([rows.map(r => r.join(",")).join("\n")], { type: "text/csv" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = "atlasrec-" + (comparable[0]?.profile || "empty") + "-experiments.csv";
    a.click();
    URL.revokeObjectURL(url);
  }
  return (
    <div className="container">
      <PageHeading
        eyebrow="AtlasRec / ML & Admin workbench"
        title={headings[section]}
        description="Actual persisted runs, versioned models, user directory, and observed system behavior."
      >
        <span className="workbench-label">
          <ShieldCheck size={15} />
          Protected workspace
        </span>
      </PageHeading>
      <State query={query}>
        {section === "overview" && data && (
          <>
            <div className="info-strip">
              <Database size={17} />
              {data.synthetic
                ? "Synthetic demo profile — software behavior, not real-world quality."
                : "Research profile — review preferences are proxies, not sales."}
            </div>
            <div className="stats">
              {["products", "users", "runs", "jobs"].map(label => (
                <Stat key={label} label={label} value={data[label]} />
              ))}
            </div>
            <div className="admin-grid">
              <section className="panel">
                <h2>Serving status</h2>
                <dl className="key-values">
                  <dt>Database</dt>
                  <dd>{data.health.database}</dd>
                  <dt>Model</dt>
                  <dd>{data.health.model}</dd>
                  <dt>Active version</dt>
                  <dd className="mono">{data.health.model_version || "Fallback"}</dd>
                  <dt>Pending jobs</dt>
                  <dd>{data.pending_jobs}</dd>
                </dl>
              </section>
              <section className="panel">
                <h2>Explore the pipeline</h2>
                {["users", "datasets", "experiments", "models", "jobs", "monitoring"].map(s => (
                  <Link className="admin-link" key={s} href={"/admin/" + s}>
                    {headings[s]} →
                  </Link>
                ))}
              </section>
            </div>
          </>
        )}
        {section === "users" && data && (
          <>
            <div className="stats">
              <Stat label="Total users" value={data.summary?.total ?? 0} />
              <Stat label="Administrators" value={data.summary?.admins ?? 0} />
              <Stat label="Users with preferences" value={data.summary?.with_preferences ?? 0} />
              <Stat label="Active sessions" value={data.summary?.active_sessions ?? 0} />
            </div>
            {editingUser && (
              <section
                className="panel"
                style={{
                  border: "2px solid #007185",
                  background: "linear-gradient(125deg, #f3faf9 0%, #ffffff 100%)",
                  marginBottom: "1.25rem",
                }}
              >
                <h2>Edit user account: {editingUser.name}</h2>
                <p className="muted">
                  Update name, email, role, interest categories, or set a new password for{" "}
                  <strong>{editingUser.email}</strong>.
                </p>
                <form
                  className="profile-form"
                  onSubmit={async e => {
                    e.preventDefault();
                    const payload = {
                      name: editUserName,
                      email: editUserEmail,
                      admin: editUserAdmin,
                      preferences: editUserPrefs
                        .split(",")
                        .map(s => s.trim())
                        .filter(Boolean)
                        .slice(0, 10),
                    };
                    if (editUserPassword.trim()) {
                      payload.password = editUserPassword.trim();
                    }
                    const res = await mutate(
                      "/admin/users/" + editingUser.id,
                      payload,
                      "PATCH",
                    );
                    if (res?.user) {
                      notify("Updated user " + res.user.email);
                      setEditingUser(null);
                      setEditUserPassword("");
                    }
                  }}
                >
                  <div className="profile-management-grid" style={{ marginBottom: 0 }}>
                    <label>
                      Full name
                      <input
                        type="text"
                        value={editUserName}
                        onChange={e => setEditUserName(e.target.value)}
                        required
                        maxLength="80"
                      />
                    </label>
                    <label>
                      Email address
                      <input
                        type="email"
                        value={editUserEmail}
                        onChange={e => setEditUserEmail(e.target.value)}
                        required
                      />
                    </label>
                    <label>
                      New password (optional, min 10 chars)
                      <input
                        type="password"
                        minLength="10"
                        maxLength="128"
                        value={editUserPassword}
                        onChange={e => setEditUserPassword(e.target.value)}
                        placeholder="Leave blank to keep existing password"
                      />
                    </label>
                    <label>
                      Interest categories (comma-separated, up to 10)
                      <input
                        type="text"
                        value={editUserPrefs}
                        onChange={e => setEditUserPrefs(e.target.value)}
                        placeholder="e.g. Headphones, Monitors, Keyboards"
                      />
                    </label>
                  </div>
                  <label className="checkbox-row">
                    <input
                      type="checkbox"
                      checked={editUserAdmin}
                      onChange={e => setEditUserAdmin(e.target.checked)}
                    />
                    Administrator & ML workbench access
                  </label>
                  <div style={{ display: "flex", gap: "0.6rem", flexWrap: "wrap" }}>
                    <button className="button" disabled={pending}>
                      {pending ? "Saving…" : "Save user changes"}
                    </button>
                    <button
                      type="button"
                      className="button secondary"
                      onClick={() => setEditingUser(null)}
                    >
                      Cancel
                    </button>
                  </div>
                </form>
              </section>
            )}
            <div className="admin-grid">
              <section className="panel">
                <h2>Create a new user account</h2>
                <p className="muted">
                  Provision a shopper or administrator account directly from the workbench.
                </p>
                <form
                  className="profile-form"
                  onSubmit={async e => {
                    e.preventDefault();
                    const res = await mutate("/admin/users", {
                      name: newUserName,
                      email: newUserEmail,
                      password: newUserPassword,
                      admin: newUserAdmin,
                    });
                    if (res?.user) {
                      setNewUserName("");
                      setNewUserEmail("");
                      setNewUserPassword("");
                      setNewUserAdmin(false);
                      notify("Created user " + res.user.email);
                    }
                  }}
                >
                  <label>
                    Full name
                    <input
                      type="text"
                      value={newUserName}
                      onChange={e => setNewUserName(e.target.value)}
                      required
                      maxLength="80"
                      placeholder="e.g. Tanvir Islam"
                    />
                  </label>
                  <label>
                    Email address
                    <input
                      type="email"
                      value={newUserEmail}
                      onChange={e => setNewUserEmail(e.target.value)}
                      required
                      placeholder="user@atlasrec.local"
                    />
                  </label>
                  <label>
                    Initial password (min 10 chars)
                    <input
                      type="password"
                      minLength="10"
                      maxLength="128"
                      value={newUserPassword}
                      onChange={e => setNewUserPassword(e.target.value)}
                      required
                      placeholder="At least 10 characters"
                    />
                  </label>
                  <label className="checkbox-row">
                    <input
                      type="checkbox"
                      checked={newUserAdmin}
                      onChange={e => setNewUserAdmin(e.target.checked)}
                    />
                    Grant administrator & ML workbench access
                  </label>
                  <button className="button" disabled={pending}>
                    {pending ? "Creating…" : "Create user account"}
                  </button>
                </form>
              </section>
              <section className="panel">
                <h2>Directory filters</h2>
                <p className="muted">Search by name or email, or filter by workspace role.</p>
                <div className="profile-form">
                  <label>
                    Search users
                    <input
                      type="search"
                      placeholder="Filter by name or email…"
                      value={userSearch}
                      onChange={e => setUserSearch(e.target.value)}
                    />
                  </label>
                  <label>
                    Role filter
                    <select value={roleFilter} onChange={e => setRoleFilter(e.target.value)}>
                      <option value="all">All users ({data.items?.length || 0})</option>
                      <option value="admin">Administrators only</option>
                      <option value="shopper">Shoppers only</option>
                    </select>
                  </label>
                </div>
              </section>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>User / Email</th>
                    <th>Role</th>
                    <th>Interests</th>
                    <th>Saved / Events / Ratings</th>
                    <th>Sessions</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {(data.items || [])
                    .filter(u => {
                      if (roleFilter === "admin" && !u.admin) return false;
                      if (roleFilter === "shopper" && u.admin) return false;
                      if (!userSearch.trim()) return true;
                      const q = userSearch.toLowerCase();
                      return (
                        (u.name || "").toLowerCase().includes(q) ||
                        (u.email || "").toLowerCase().includes(q)
                      );
                    })
                    .map(u => (
                      <tr key={u.id}>
                        <td>
                          <strong>{u.name}</strong>
                          <small className="mono">{u.email}</small>
                        </td>
                        <td>
                          <span className={"role-pill " + (u.admin ? "role-admin" : "role-user")}>
                            {u.admin ? "Admin" : "Shopper"}
                          </span>
                        </td>
                        <td>
                          {u.preferences?.length ? (
                            <span>{u.preferences.slice(0, 3).join(", ")}</span>
                          ) : (
                            <span className="muted">None</span>
                          )}
                        </td>
                        <td>
                          {u.favorites_count} saved · {u.events_count} events · {u.ratings_count}{" "}
                          ratings
                        </td>
                        <td>{u.sessions_count} active</td>
                        <td>
                          <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
                            <button
                              type="button"
                              className="button"
                              disabled={pending}
                              onClick={() => {
                                setEditingUser(u);
                                setEditUserName(u.name || "");
                                setEditUserEmail(u.email || "");
                                setEditUserPassword("");
                                setEditUserAdmin(Boolean(u.admin));
                                setEditUserPrefs((u.preferences || []).join(", "));
                                window.scrollTo({ top: 0, behavior: "smooth" });
                              }}
                            >
                              Edit Info
                            </button>
                            <button
                              type="button"
                              className="button secondary"
                              disabled={pending}
                              onClick={() =>
                                mutate("/admin/users/" + u.id, { admin: !u.admin }, "PATCH")
                              }
                            >
                              {u.admin ? "Demote" : "Make Admin"}
                            </button>
                            <button
                              type="button"
                              className="button secondary"
                              disabled={pending}
                              onClick={() => {
                                if (
                                  window.confirm(
                                    `Clear interaction history and saved products for ${u.email}?`,
                                  )
                                ) {
                                  mutate("/admin/users/" + u.id + "/history", null, "DELETE");
                                }
                              }}
                            >
                              Reset History
                            </button>
                            <button
                              type="button"
                              className="danger-button"
                              disabled={pending}
                              onClick={() => {
                                if (window.confirm(`Delete user ${u.email} permanently?`)) {
                                  mutate("/admin/users/" + u.id, null, "DELETE");
                                }
                              }}
                            >
                              Delete
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </>
        )}
        {section === "experiments" && (
          <>
            <div className="table-controls">
              <label>
                Comparable split
                <select value={selected || ""} onChange={e => setSplit(e.target.value)}>
                  {[...new Set(complete.map(r => r.split_id))].map(s => (
                    <option key={s}>{s}</option>
                  ))}
                </select>
              </label>
              <button className="button secondary" disabled={!comparable.length} onClick={download}>
                <Download size={16} />
                Export results
              </button>
            </div>
            {!data?.length ? (
              <div className="state">
                <h2>No experiments recorded yet.</h2>
                <Link href="/admin/jobs" className="button">
                  Train a model
                </Link>
              </div>
            ) : (
              <>
                <div className="panel">
                  <h2>End-to-end quality at 10</h2>
                  <p className="muted">
                    {comparable[0]?.profile} · full eligible catalog · split {selected}
                  </p>
                  {comparable.length ? (
                    <ResponsiveContainer width="100%" height={300}>
                      <BarChart
                        data={comparable.map(r => ({
                          name: r.model + " · " + r.seed,
                          Recall: r.metrics["recall@10"],
                          NDCG: r.metrics["ndcg@10"],
                          MRR: r.metrics["mrr@10"],
                        }))}
                      >
                        <CartesianGrid strokeDasharray="3 3" vertical={false} />
                        <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                        <YAxis domain={[0, 1]} />
                        <Tooltip />
                        <Legend />
                        <Bar isAnimationActive={false} dataKey="Recall" fill="#15776c" />
                        <Bar isAnimationActive={false} dataKey="NDCG" fill="#97b9af" />
                        <Bar isAnimationActive={false} dataKey="MRR" fill="#d3a779" />
                      </BarChart>
                    </ResponsiveContainer>
                  ) : (
                    <p>No completed runs in this split.</p>
                  )}
                </div>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Model / version</th>
                        <th>Profile / split</th>
                        <th>Seed</th>
                        <th>Recall@10</th>
                        <th>NDCG@10</th>
                        <th>Runtime</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data?.map(r => (
                        <tr key={r.id}>
                          <td>
                            <strong>{r.model}</strong>
                            <small className="mono">{r.id}</small>
                          </td>
                          <td>
                            {r.profile}
                            <small className="mono">{r.split_id}</small>
                          </td>
                          <td>{r.seed}</td>
                          <td>{r.metrics?.["recall@10"]?.toFixed(4) ?? "—"}</td>
                          <td>{r.metrics?.["ndcg@10"]?.toFixed(4) ?? "—"}</td>
                          <td>{r.training_seconds?.toFixed(2) ?? r.total_seconds?.toFixed(2)} s</td>
                          <td>
                            <Label value={r.status} />
                            {r.error && <small>{r.error}</small>}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </>
        )}
        {section === "models" && data && (
          <>
            <section className="panel active-model">
              <span className="eyebrow">Active serving bundle</span>
              <h2 className="mono">
                {data.items.find(v => v.active)?.id || "Popularity/content fallback"}
              </h2>
              <p>Validated bundles swap atomically in this single API process.</p>
              <button
                className="button secondary"
                disabled={pending}
                onClick={() => mutate("/admin/models/rollback")}
              >
                <RotateCcw size={15} />
                Roll back
              </button>
            </section>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Version</th>
                    <th>Validation</th>
                    <th>Serving</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map(v => (
                    <tr key={v.id}>
                      <td className="mono">{v.id}</td>
                      <td>
                        {v.validated ? "Checksums, dimensions & IDs verified" : "Unvalidated"}
                      </td>
                      <td>
                        <Label value={v.active ? "active" : "candidate"} />
                      </td>
                      <td>
                        <button
                          disabled={pending || v.active || !v.validated}
                          onClick={() => mutate("/admin/models/" + v.id + "/promote")}
                        >
                          Promote
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <section className="panel">
              <h2>Change history</h2>
              {data.history.length ? (
                data.history.map((h, i) => (
                  <p key={i}>
                    <Label value={h.action} /> {h.details.next} <small>{h.at}</small>
                  </p>
                ))
              ) : (
                <p>No promotions yet.</p>
              )}
            </section>
          </>
        )}
        {section === "jobs" && (
          <>
            <section className="panel">
              <h2>Start a bounded experiment</h2>
              <form
                className="job-form"
                onSubmit={e => {
                  e.preventDefault();
                  mutate("/admin/jobs", {
                    model,
                    epochs: Number(epochs),
                    seed: Number(seed),
                    include_application_feedback: includeFeedback,
                  });
                }}
              >
                <label>
                  Model
                  <select value={model} onChange={e => setModel(e.target.value)}>
                    {["popularity", "item_cf", "bpr", "two_tower", "two_tower_id", "ranker"].map(
                      m => (
                        <option key={m}>{m}</option>
                      ),
                    )}
                  </select>
                </label>
                <label>
                  Epoch budget
                  <input
                    type="number"
                    min="1"
                    max="30"
                    value={epochs}
                    onChange={e => setEpochs(e.target.value)}
                    required
                  />
                </label>
                <label>
                  Seed
                  <input
                    type="number"
                    min="0"
                    max="100000"
                    value={seed}
                    onChange={e => setSeed(e.target.value)}
                    required
                  />
                </label>
                <label>
                  <input
                    type="checkbox"
                    checked={includeFeedback}
                    onChange={e => setIncludeFeedback(e.target.checked)}
                  />{" "}
                  Include live feedback
                </label>
                <button className="button" disabled={pending}>
                  <Play size={15} />
                  Queue training
                </button>
              </form>
              <p className="muted">
                CPU only · one worker · configured time cap · explicit promotion required.
              </p>
            </section>
            {!data?.length ? (
              <div className="state">
                <h2>No jobs yet.</h2>
              </div>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Job / model</th>
                      <th>Status</th>
                      <th>Progress</th>
                      <th>Result</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.map(j => (
                      <tr key={j.id}>
                        <td>
                          <strong>{j.config.models.join(", ")}</strong>
                          <small className="mono">{j.id}</small>
                        </td>
                        <td>
                          <Label value={j.status} />
                        </td>
                        <td>
                          <progress max="1" value={j.progress} />
                          <small>
                            {Math.round(j.progress * 100)}% · attempt {j.attempts}
                          </small>
                        </td>
                        <td>{j.error || j.result?.runs?.join(", ") || "—"}</td>
                        <td>
                          {j.retryable && (
                            <button
                              disabled={pending}
                              onClick={() => mutate("/admin/jobs/" + j.id + "/retry")}
                            >
                              Retry
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
        {section === "monitoring" && data && (
          <>
            <div className="stats">
              <Stat label="Requests" value={data.requests} />
              <Stat
                label="P50 latency"
                value={data.p50_ms == null ? null : data.p50_ms.toFixed(1) + " ms"}
              />
              <Stat
                label="P95 latency"
                value={data.p95_ms == null ? null : data.p95_ms.toFixed(1) + " ms"}
              />
              <Stat
                label="Cache hit rate"
                value={
                  data.cache_hit_rate == null ? null : (data.cache_hit_rate * 100).toFixed(1) + "%"
                }
              />
              <Stat
                label="Fallback rate"
                value={
                  data.fallback_rate == null ? null : (data.fallback_rate * 100).toFixed(1) + "%"
                }
              />
            </div>
            <div className="admin-grid">
              <section className="panel">
                <h2>Data drift diagnostics</h2>
                <p>
                  {data.drift.reference} vs {data.drift.current}
                </p>
                <dl className="key-values">
                  <dt>Samples: reference / current</dt>
                  <dd>
                    {data.drift.reference_n} / {data.drift.current_n}
                  </dd>
                  <dt>Category total variation</dt>
                  <dd>
                    {data.drift.category_total_variation?.toFixed(4) ?? "Insufficient nonoverlap"} (
                    {data.drift.category_warning ? "warning" : "normal"})
                  </dd>
                  <dt>Threshold</dt>
                  <dd>{data.drift.threshold}</dd>
                  <dt>Standardized position shift</dt>
                  <dd>
                    {data.drift.position_standardized_mean_shift?.toFixed(4) ?? "Insufficient data"}{" "}
                    ({data.drift.numeric_warning ? "warning" : "normal"})
                  </dd>
                  <dt>Missing product price</dt>
                  <dd>{(data.feature_missingness * 100).toFixed(1)}%</dd>
                </dl>
                <p className="muted">Diagnostics do not automatically replace a model.</p>
              </section>
              <section className="panel">
                <h2>Fallbacks & errors</h2>
                <p>
                  {data.window} · {data.profile}
                </p>
                <pre>
                  {JSON.stringify(
                    { fallbacks: data.fallback_reasons, errors: data.errors_since_process_start },
                    null,
                    2,
                  )}
                </pre>
              </section>
            </div>
          </>
        )}
        {section === "datasets" && (
          <div>
            {data?.length ? (
              data.map(d => (
                <section className="panel" key={d.id}>
                  <span className="eyebrow">{d.profile}</span>
                  <h2 className="mono">{d.id}</h2>
                  <pre>{JSON.stringify(d.manifest, null, 2)}</pre>
                </section>
              ))
            ) : (
              <div className="state">
                <h2>No dataset manifests recorded.</h2>
              </div>
            )}
          </div>
        )}
      </State>
    </div>
  );
}
