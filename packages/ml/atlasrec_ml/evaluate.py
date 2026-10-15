from __future__ import annotations

from collections import defaultdict

import numpy as np


def metrics(ranked, relevant, k=10):
    relevant = set(relevant)
    ranked = list(dict.fromkeys(ranked))[:k]
    hits = [int(item in relevant) for item in ranked]
    recall = sum(hits) / max(1, len(relevant))
    dcg = sum(hit / np.log2(i + 2) for i, hit in enumerate(hits))
    ideal = sum(1 / np.log2(i + 2) for i in range(min(k, len(relevant))))
    mrr = next((1 / (i + 1) for i, hit in enumerate(hits) if hit), 0)
    return {"recall@10": recall, "ndcg@10": dcg / ideal if ideal else 0, "mrr@10": mrr}


def confidence(values, seed=42):
    if len(values) < 2:
        return None
    rng = np.random.default_rng(seed)
    samples = [np.mean(rng.choice(values, len(values), replace=True)) for _ in range(200)]
    return np.quantile(samples, [0.025, 0.975]).tolist()


def evaluate(model, events, bootstrap=True, diversity=0, positives_only=None):
    by_user = defaultdict(set)
    for e in events:
        if e["rating"] >= model.f.threshold:
            by_user[e["user"]].add(e["item"])
    rows, all_items, diversities = [], [], []
    excluded = 0
    eligible = set(model.f.ids)
    for user in sorted({e["user"] for e in events}):
        hist = list(dict.fromkeys(model.f.histories.get(user, [])))
        seen = {model.f.ids[i] for i in hist}
        relevant = (by_user[user] & eligible) - seen
        if positives_only is not None:
            relevant &= set(positives_only)
        if not relevant:
            excluded += 1
            continue
        history = [model.f.ids[i] for i in hist]
        ranked, retrieved = model.recommend(user, history, k=10, diversity=diversity)
        m = metrics(ranked, relevant)
        m["retrieval_recall@50"] = len(set(retrieved) & relevant) / len(relevant)
        m["user"] = user
        m["history_size"] = len(hist)
        m["relevant_items"] = sorted(relevant)
        m["ranked_items"] = ranked
        m["retrieval_misses"] = sorted(relevant - set(retrieved))
        rows.append(m)
        all_items.extend(ranked)
        cats = {model.f.products[model.f.item_map[i]]["category"] for i in ranked}
        diversities.append(len(cats) / max(1, len(ranked)))
    keys = ["recall@10", "ndcg@10", "mrr@10", "retrieval_recall@50"]
    result = {k: float(np.mean([r[k] for r in rows])) if rows else 0 for k in keys}
    result.update({"queries": len(rows), "excluded_no_eligible_positive": excluded,
                   "eligible_catalog": len(eligible), "full_catalog": True,
                   "catalog_coverage": len(set(all_items)) / max(1, len(eligible)),
                   "category_diversity": float(np.mean(diversities)) if rows else 0,
                   "user_rows": rows})
    popular = {model.f.ids[i] for i in np.argsort(-model.f.popularity)[:max(1, len(eligible) // 10)]}
    result["item_popularity_strata"] = {}
    for label, subset_ids in [("training_top_decile", popular), ("training_remaining", eligible - popular)]:
        subset = [metrics(r["ranked_items"], set(r["relevant_items"]) & subset_ids) for r in rows if set(r["relevant_items"]) & subset_ids]
        result["item_popularity_strata"][label] = {"queries": len(subset), **{k: float(np.mean([r[k] for r in subset])) if subset else None for k in keys[:3]}}
    conditional = [metrics(r["ranked_items"], set(r["relevant_items"]) - set(r["retrieval_misses"])) for r in rows if set(r["relevant_items"]) - set(r["retrieval_misses"])]
    result["conditional_ranking"] = {"definition": "only relevant items retrieved in top 50; separate from end-to-end metrics", "queries": len(conditional), **{k: float(np.mean([r[k] for r in conditional])) if conditional else None for k in keys[:3]}}
    result["top_decile_concentration"] = sum(i in popular for i in all_items) / max(1, len(all_items))
    result["strata"] = {}
    for label, a, b in [("0-4", 0, 5), ("5-14", 5, 15), ("15+", 15, np.inf)]:
        subset = [r for r in rows if a <= r["history_size"] < b]
        result["strata"][label] = {"queries": len(subset), **{
            k: float(np.mean([r[k] for r in subset])) if subset else None for k in keys}}
    warm = [r for r in rows if r["history_size"] >= 5]
    result["cold_user_queries"] = sum(r["history_size"] == 0 for r in rows)
    result["known_history_queries"] = sum(r["history_size"] > 0 for r in rows)
    result["warm_user_queries"] = len(warm)
    result["warm_ndcg@10"] = float(np.mean([r["ndcg@10"] for r in warm])) if warm else None
    if bootstrap:
        result["ci95"] = {k: confidence([r[k] for r in rows]) for k in keys}
    return result


def paired_difference(a, b, key="ndcg@10"):
    av = {r["user"]: r[key] for r in a["user_rows"]}
    bv = {r["user"]: r[key] for r in b["user_rows"]}
    users = sorted(av.keys() & bv.keys())
    diff = [bv[u] - av[u] for u in users]
    return {"metric": key, "users": len(users),
            "mean_difference": float(np.mean(diff)) if diff else None, "ci95": confidence(diff)}
