from __future__ import annotations

from collections import defaultdict

import numpy as np
from scipy.sparse import csr_matrix
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize


def text(product):
    return " ".join(str(product.get(k) or "") for k in ("title", "description", "category"))


class Features:
    def __init__(self, products, events, dimension=24, seed=42, threshold=4):
        self.threshold = threshold
        observed = {e["item"] for e in events}
        self.products = sorted((p for p in products if p["id"] in observed), key=lambda p: p["id"])
        self.ids = [p["id"] for p in self.products]
        if len(self.ids) < 2:
            raise ValueError("Need at least two train-observed products")
        self.item_map = {v: i for i, v in enumerate(self.ids)}
        self.users = sorted({e["user"] for e in events})
        self.user_map = {v: i for i, v in enumerate(self.users)}
        self.histories = defaultdict(list)
        self.first_seen = np.full(len(self.ids), np.inf)
        self.popularity = np.zeros(len(self.ids), dtype=np.float32)
        rows, cols = [], []
        for e in sorted(events, key=lambda e: e["timestamp"]):
            i = self.item_map[e["item"]]
            self.first_seen[i] = min(self.first_seen[i], e["timestamp"])
            if e["rating"] >= threshold:
                self.histories[e["user"]].append(i)
                self.popularity[i] += 1
                rows.append(self.user_map[e["user"]])
                cols.append(i)
        self.matrix = csr_matrix((np.ones(len(rows)), (rows, cols)),
                                 shape=(len(self.users), len(self.ids)), dtype=np.float32)
        self.matrix.data[:] = 1
        documents = [text(product).strip() or "unknown" for product in self.products]
        self.vectorizer = TfidfVectorizer(max_features=4096, stop_words="english")
        try:
            x = self.vectorizer.fit_transform(documents)
        except ValueError as exc:
            if "empty vocabulary" not in str(exc):
                raise
            self.vectorizer = TfidfVectorizer(max_features=4096, token_pattern=r"(?u)\b\w+\b")
            x = self.vectorizer.fit_transform(documents)
        self.svd = None
        if x.shape[1] > 1:
            n = min(dimension, x.shape[1] - 1, x.shape[0] - 1)
            self.svd = TruncatedSVD(n_components=max(1, n), random_state=seed)
        content = self.svd.fit_transform(x) if self.svd is not None else x.toarray()
        self.content = normalize(content).astype(np.float32)

    def indices(self, history):
        return list(dict.fromkeys(self.item_map[x] for x in history if x in self.item_map))

    def unknown_content(self, product):
        x = self.vectorizer.transform([text(product)])
        content = self.svd.transform(x) if self.svd is not None else x.toarray()
        return normalize(content).astype(np.float32)[0]

    def rank_features(self, history, candidates, retrieval_scores):
        if history:
            h = self.content[history].mean(axis=0)
            categories = [self.products[i]["category"] for i in history]
        else:
            h = np.zeros(self.content.shape[1])
            categories = []
        return np.array([
            [float(retrieval_scores[i]), float(self.content[i] @ h),
             float(np.log1p(self.popularity[i])),
             categories.count(self.products[i]["category"]) / max(1, len(categories))]
            for i in candidates
        ], dtype=np.float32)


def chronological_examples(events, f: Features):
    past = defaultdict(set)
    for e in sorted(events, key=lambda e: (e["timestamp"], e["id"])):
        if e["rating"] < f.threshold:
            continue
        i = f.item_map[e["item"]]
        # Capture history BEFORE the event, then update it.
        yield f.user_map[e["user"]], i, tuple(sorted(past[e["user"]])), e["timestamp"]
        past[e["user"]].add(i)


def valid_negatives(f: Features, history, target, timestamp):
    mask = f.first_seen < timestamp
    mask[list(history) + [target]] = False
    return np.flatnonzero(mask)


def contrastive_mask(targets, histories):
    # Duplicate positives and known-history items cannot act as negative labels.
    mask = np.ones((len(targets), len(targets)), dtype=bool)
    for row, target in enumerate(targets):
        for col, other in enumerate(targets):
            if col != row and (other == target or other in histories[row]):
                mask[row, col] = False
    return mask
