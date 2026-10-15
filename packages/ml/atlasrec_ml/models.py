from __future__ import annotations

import copy
import time

import faiss
import lightgbm as lgb
import numpy as np
import torch
from scipy.sparse import diags
from torch import nn

from .features import Features, chronological_examples, contrastive_mask, valid_negatives


class Towers(nn.Module):
    def __init__(self, n_items, content_dim, dimension, use_content=True):
        super().__init__()
        self.items = nn.Embedding(n_items, dimension)
        self.item_content = nn.Linear(content_dim, dimension, bias=False)
        self.user_net = nn.Sequential(nn.Linear(dimension, dimension), nn.Tanh(),
                                      nn.Linear(dimension, dimension))
        self.use_content = use_content
        self.register_buffer("id_mask", torch.ones(n_items, 1))

    def item_vectors(self, content):
        ids = self.items.weight * self.id_mask
        return nn.functional.normalize(ids + (self.item_content(content) if self.use_content else 0), dim=1)

    def user_vector(self, history_vectors):
        return nn.functional.normalize(self.user_net(history_vectors), dim=1)


class Recommender:
    def __init__(self, name="popularity", config=None):
        if name not in ("popularity", "item_cf", "bpr", "two_tower", "two_tower_id", "ranker"):
            raise ValueError("Unknown recommendation model")
        self.name = name
        self.config = config or {}
        self.fit_status = "not_started"
        self.best_epoch = 0
        self.ranker = None
        self.index = None
        self.excluded_rank_groups = 0

    def fit(self, products, train, validation=None, progress=None):
        start = time.monotonic()
        c = self.config
        seed = c.get("seed", 42)
        np.random.seed(seed)
        torch.manual_seed(seed)
        torch.set_num_threads(c.get("threads", 2))
        self.f = Features(products, train, c.get("dimension", 24), seed,
                          c.get("positive_threshold", 4))
        n = len(self.f.ids)
        est_bytes = (
            (self.f.matrix.nnz * 64 + n * 128)
            if self.name == "item_cf"
            else n * max(n, c.get("dimension", 24)) * 4
        )
        if est_bytes > c.get("memory_budget_mb", 1024) * 1024**2:
            # Dense catalog score batches are fine; do not allocate quadratic similarities.
            if self.name == "item_cf":
                raise MemoryError("Item-CF exceeds configured memory estimate; reduce research subset.")
        self.fit_status = "completed"
        self.item_vectors = self.f.content.copy()
        self.user_vectors = None
        if self.name == "item_cf":
            counts = np.asarray(self.f.matrix.sum(axis=0)).ravel()
            co = (self.f.matrix.T @ self.f.matrix).tocsr()
            co.setdiag(0)
            co.eliminate_zeros()
            co.data *= co.data / (co.data + c.get("shrinkage", 10))
            inv = diags(1 / np.sqrt(np.maximum(counts, 1)))
            self.similarity = (inv @ co @ inv).tocsr()
            # Keep strongest 50 neighbors per item and bound serving work.
            for row in range(n):
                a, b = self.similarity.indptr[row:row + 2]
                values = self.similarity.data[a:b]
                if len(values) > 50:
                    values[np.argsort(values)[:-50]] = 0
            self.similarity.eliminate_zeros()
        elif self.name == "bpr":
            self._fit_bpr(train, validation, start, progress)
        elif self.name in ("two_tower", "two_tower_id", "ranker"):
            self._fit_tower(train, validation, start, progress)
            if self.name == "ranker":
                self._fit_ranker(products, train, start)
        self.index = faiss.IndexFlatIP(self.item_vectors.shape[1])
        self.index.add(np.ascontiguousarray(self.item_vectors, dtype=np.float32))
        self.training_seconds = time.monotonic() - start
        return self

    def _validation(self, events):
        if not events:
            return 0
        from .evaluate import evaluate
        return evaluate(self, events, bootstrap=False)["ndcg@10"]

    def _fit_bpr(self, train, validation, start, progress):
        c, f = self.config, self.f
        dimension = c.get("dimension", 24)
        u = nn.Embedding(len(f.users), dimension)
        i = nn.Embedding(len(f.ids), dimension)
        nn.init.normal_(u.weight, std=0.05)
        nn.init.normal_(i.weight, std=0.05)
        optimizer = torch.optim.Adam(list(u.parameters()) + list(i.parameters()), lr=0.015)
        rng = np.random.default_rng(c.get("seed", 42))
        examples = list(chronological_examples(train, f))
        best, stale, snapshot = -1, 0, None
        for epoch in range(c.get("epochs", 12)):
            batches = []
            for user, target, hist, ts in examples:
                candidates = valid_negatives(f, hist, target, ts)
                if not len(candidates):
                    continue
                for neg in rng.choice(candidates, c.get("negative_samples", 4), replace=True):
                    batches.append((user, target, int(neg)))
            rng.shuffle(batches)
            for offset in range(0, len(batches), 256):
                b = torch.tensor(batches[offset:offset + 256], dtype=torch.long)
                uv, pv, nv = u(b[:, 0]), i(b[:, 1]), i(b[:, 2])
                loss = -nn.functional.logsigmoid((uv * (pv - nv)).sum(dim=1)).mean()
                loss += 1e-4 * (uv.square().mean() + pv.square().mean() + nv.square().mean())
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
            self.item_vectors = i.weight.detach().numpy().copy()
            self.user_vectors = u.weight.detach().numpy().copy()
            value = self._validation(validation)
            if not validation or value > best:
                best, stale = value, 0
                snapshot = (self.item_vectors.copy(), self.user_vectors.copy())
                self.best_epoch = epoch + 1
            else:
                stale += 1
            if progress:
                progress((epoch + 1) / c.get("epochs", 12))
            if time.monotonic() - start >= c.get("time_budget", 300):
                self.fit_status = "timeout"
                break
            if validation and stale >= 3:
                break
        if snapshot:
            self.item_vectors, self.user_vectors = snapshot

    def _fit_tower(self, train, validation, start, progress):
        c, f = self.config, self.f
        self.towers = Towers(len(f.ids), f.content.shape[1], c.get("dimension", 24),
                             use_content=self.name != "two_tower_id")
        for item in c.get("content_only_ids", []):
            if item in f.item_map:
                self.towers.id_mask[f.item_map[item]] = 0
        content = torch.tensor(f.content)
        optimizer = torch.optim.Adam(self.towers.parameters(), lr=0.01, weight_decay=1e-4)
        examples = [(u, t, h, ts) for u, t, h, ts in chronological_examples(train, f) if h]
        rng = np.random.default_rng(c.get("seed", 42))
        best, stale, snapshot = -1, 0, None
        for epoch in range(c.get("epochs", 12)):
            self.towers.train()
            order = rng.permutation(len(examples))
            for offset in range(0, len(order), 64):
                batch = [examples[j] for j in order[offset:offset + 64]]
                if len(batch) < 2:
                    continue
                v = self.towers.item_vectors(content)
                h = torch.stack([v[list(e[2])].mean(dim=0) for e in batch])
                query = self.towers.user_vector(h)
                targets = [e[1] for e in batch]
                logits = query @ v[targets].T / 0.15
                allowed = contrastive_mask(targets, [e[2] for e in batch])
                # Candidate first observation must precede each context.
                for r, e in enumerate(batch):
                    for col, target in enumerate(targets):
                        if col != r and f.first_seen[target] >= e[3]:
                            allowed[r, col] = False
                logits = logits.masked_fill(~torch.tensor(allowed), -1e9)
                loss = nn.functional.cross_entropy(logits, torch.arange(len(batch)))
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
            self.towers.eval()
            with torch.no_grad():
                self.item_vectors = self.towers.item_vectors(content).numpy().copy()
            value = self._validation(validation)
            if not validation or value > best:
                best, stale = value, 0
                snapshot = copy.deepcopy(self.towers.state_dict())
                self.best_epoch = epoch + 1
            else:
                stale += 1
            if progress:
                progress((epoch + 1) / c.get("epochs", 12))
            if time.monotonic() - start >= c.get("time_budget", 300):
                self.fit_status = "timeout"
                break
            if validation and stale >= 3:
                break
        if snapshot:
            self.towers.load_state_dict(snapshot)
            with torch.no_grad():
                self.item_vectors = self.towers.item_vectors(content).numpy().copy()

    def _fit_ranker(self, products, train, start):
        times = [e["timestamp"] for e in train]
        cutoffs = np.quantile(times, [0.4 / 0.7, 0.55 / 0.7, 1.0])
        features, labels, groups = [], [], []
        for a, b in zip(cutoffs[:-1], cutoffs[1:]):
            if time.monotonic() - start > self.config.get("time_budget", 300):
                self.fit_status = "timeout"
                break
            earlier = [e for e in train if e["timestamp"] < a]
            later = [e for e in train if a <= e["timestamp"] < b]
            retrieval = Recommender("two_tower", {**self.config, "epochs": 4})
            retrieval.fit(products, earlier)
            f = retrieval.f
            for user in sorted({e["user"] for e in later}):
                hist = list(dict.fromkeys(f.histories.get(user, [])))
                scores = retrieval.scores(user, [f.ids[i] for i in hist])
                candidates = retrieval.order(scores, hist)[:self.config.get("candidate_k", 50)]
                positives = {e["item"] for e in later if e["user"] == user
                             and e["rating"] >= f.threshold}
                y = [int(f.ids[i] in positives) for i in candidates]
                if len(set(y)) < 2:
                    self.excluded_rank_groups += 1
                    continue
                features.extend(f.rank_features(hist, candidates, scores))
                labels.extend(y)
                groups.append(len(candidates))
        if not groups:
            raise ValueError("No ranker groups with relevance variation; retrieval remains unchanged.")
        self.ranker = lgb.LGBMRanker(objective="lambdarank", n_estimators=40, num_leaves=7,
                                    min_child_samples=5, random_state=self.config.get("seed", 42),
                                    n_jobs=self.config.get("threads", 2), verbosity=-1)
        self.ranker.fit(np.array(features), labels, group=groups)
        self.rank_groups = len(groups)

    def query_vector(self, user, history):
        hist = self.f.indices(history)
        if self.name == "bpr" and user in self.f.user_map:
            return self.user_vectors[self.f.user_map[user]]
        if not hist:
            return np.zeros(self.item_vectors.shape[1], dtype=np.float32)
        mean = self.item_vectors[hist].mean(axis=0)
        if self.name in ("two_tower", "two_tower_id", "ranker"):
            with torch.no_grad():
                return self.towers.user_vector(torch.tensor(mean[None])).numpy()[0]
        return mean

    def scores(self, user=None, history=(), preferences=()):
        hist = self.f.indices(history)
        if self.name == "popularity" or not hist:
            score = np.log1p(self.f.popularity).copy()
        elif self.name == "item_cf":
            score = np.asarray(self.similarity[hist].sum(axis=0)).ravel()
        else:
            query = self.query_vector(user, history).astype(np.float32)
            if self.index is not None:
                distances, positions = self.index.search(query[None], len(self.f.ids))
                score = np.empty(len(self.f.ids), dtype=np.float32)
                score[positions[0]] = distances[0]
            else:
                score = self.item_vectors @ query
        if preferences:
            pref_set = set(preferences)
            score = score + np.array([0.15 if p["category"] in pref_set else 0 for p in self.f.products])
        return np.asarray(score)

    def order(self, scores, excluded=(), limit=None):
        mask = np.ones(len(scores), dtype=bool)
        mask[list(excluded)] = False
        eligible = np.flatnonzero(mask)
        if limit is not None and 0 < limit < len(eligible) // 2:
            neg = -scores[eligible]
            thresh = np.partition(neg, limit - 1)[limit - 1]
            strict = np.flatnonzero(neg < thresh)
            ties = np.flatnonzero(neg == thresh)[: limit - len(strict)]
            sub = np.concatenate([strict, ties])
            el_sub = eligible[sub]
            return el_sub[np.lexsort((el_sub, neg[sub]))].tolist()
        return eligible[np.lexsort((eligible, -scores[eligible]))].tolist()

    def recommend(self, user=None, history=(), preferences=(), excluded=(), k=10, diversity=0):
        hist = self.f.indices(history)
        scores = self.scores(user, history, preferences)
        limit = max(k, self.config.get("candidate_k", 50))
        candidates = self.order(scores, set(hist) | set(self.f.indices(excluded)), limit=limit)
        candidates = candidates[:limit]
        retrieval = candidates.copy()
        if self.ranker is not None and candidates:
            ranked = self.ranker.predict(self.f.rank_features(hist, candidates, scores))
            if preferences:
                ranked = ranked + np.array(
                    [0.15 if self.f.products[i]["category"] in preferences else 0.0 for i in candidates]
                )
            scores = scores.copy()
            scores[candidates] = ranked
            candidates = [candidates[i] for i in np.argsort(-ranked, kind="stable")]
        if diversity:
            result, counts = [], {}
            while candidates and len(result) < k:
                i = max(candidates, key=lambda j: scores[j] - diversity * counts.get(self.f.products[j]["category"], 0))
                result.append(i)
                candidates.remove(i)
                category = self.f.products[i]["category"]
                counts[category] = counts.get(category, 0) + 1
            candidates = result
        return [self.f.ids[i] for i in candidates[:k]], [self.f.ids[i] for i in retrieval]

    def embed_product(self, product):
        if product["id"] in self.f.item_map:
            return self.item_vectors[self.f.item_map[product["id"]]]
        v = self.f.unknown_content(product)
        if self.name in ("two_tower", "ranker"):
            with torch.no_grad():
                result = self.towers.item_content(torch.tensor(v[None])).numpy()[0]
            return result / max(float(np.linalg.norm(result)), 1e-8)
        return v
