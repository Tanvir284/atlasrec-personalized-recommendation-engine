import json

import numpy as np
import pytest
from atlasrec_ml.bundle import load_bundle, save_bundle
from atlasrec_ml.data import demo, history_before, research, temporal_split
from atlasrec_ml.evaluate import metrics
from atlasrec_ml.features import Features, chronological_examples, contrastive_mask, valid_negatives
from atlasrec_ml.models import Recommender


def fixture():
    return demo(products=40, users=10, interactions=400)


def test_temporal_sentinel_and_target_separation():
    data = fixture()
    split = temporal_split(data)
    assert max(e["timestamp"] for e in split["train"]) < split["boundaries"][0]
    f = Features(data.products, split["train"])
    earlier = f.popularity.copy()
    future = {**data.events[0], "id": "future", "timestamp": 9999999999, "rating": 5}
    cutoff = split["boundaries"][0]
    assert history_before(data.events + [future], cutoff, future["user"]) == history_before(data.events, cutoff, future["user"])
    filtered = [e for e in split["train"] + [future] if e["timestamp"] < cutoff]
    assert np.array_equal(earlier, Features(data.products, filtered).popularity)
    for _, target, hist, timestamp in chronological_examples(split["train"], f):
        candidates = valid_negatives(f, hist, target, timestamp)
        assert target not in candidates and not (set(hist) & set(candidates))
        assert all(f.first_seen[i] < timestamp for i in candidates)


def test_hand_metrics_multiple_positives_and_missed_retrieval():
    result = metrics(["x", "a", "b"], {"a", "b", "c"})
    assert result["recall@10"] == pytest.approx(2 / 3)
    assert result["mrr@10"] == 0.5
    assert result["ndcg@10"] == pytest.approx((1 / np.log2(3) + 0.5) / (1 + 1 / np.log2(3) + 0.5))
    assert metrics([], {"a"})["ndcg@10"] == 0
    assert metrics(["a", "a"], {"a", "b"})["recall@10"] == 0.5


def test_duplicate_and_history_negative_masks():
    mask = contrastive_mask([2, 2, 4], [(4,), (), (2,)])
    assert not mask[0, 1] and not mask[0, 2] and not mask[2, 0]
    assert np.all(np.diag(mask))


@pytest.mark.parametrize("name", ["popularity", "item_cf", "bpr", "two_tower", "two_tower_id", "ranker"])
def test_model_train_reload_filter_and_exact_index(name, tmp_path):
    data = fixture()
    split = temporal_split(data)
    model = Recommender(name, {"epochs": 2, "dimension": 8, "time_budget": 120}).fit(data.products, split["train"])
    user = model.f.users[0]
    history = [model.f.ids[i] for i in model.f.histories[user]]
    result, _ = model.recommend(user, history, excluded=[model.f.ids[-1]], k=10)
    assert len(result) == len(set(result))
    assert not set(result) & set(history)
    assert model.f.ids[-1] not in result
    assert set(result) <= set(model.f.ids)
    path = tmp_path / name
    save_bundle(model, path, {"version": "test", "profile": "demo"})
    loaded, _ = load_bundle(path)
    assert model.recommend(user, history) == loaded.recommend(user, history)
    query = model.item_vectors[0]
    distances, positions = model.index.search(query[None].astype(np.float32), len(model.f.ids))
    assert np.allclose(distances[0], (model.item_vectors @ query)[positions[0]], atol=1e-5)


def test_artifact_corruption_and_dependency_rejection(tmp_path):
    data = fixture()
    model = Recommender().fit(data.products, data.events[:280])
    path = tmp_path / "model"
    save_bundle(model, path, {"version": "test", "profile": "demo"})
    manifest = json.loads((path / "manifest.json").read_text())
    manifest["dimension"] += 1
    (path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        load_bundle(path)
    manifest["dimension"] -= 1
    manifest["dependencies"]["torch"] = "incompatible"
    (path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        load_bundle(path)


def test_seeded_bpr_and_unknown_content():
    data = fixture()
    a = Recommender("bpr", {"epochs": 2, "dimension": 8}).fit(data.products, data.events[:280])
    b = Recommender("bpr", {"epochs": 2, "dimension": 8}).fit(data.products, data.events[:280])
    assert np.allclose(a.item_vectors, b.item_vectors, atol=1e-6)
    model = Recommender("two_tower", {"epochs": 2, "dimension": 8}).fit(data.products, data.events[:280])
    x = model.embed_product({"id": "new-a", "title": "Studio headphones", "category": "Audio"})
    y = model.embed_product({"id": "new-b", "title": "Ceramic mug", "category": "Home"})
    assert not np.allclose(x, y)


def test_parent_metadata_join_missing_and_rejected_rows(tmp_path):
    reviews = tmp_path / "reviews.jsonl"
    rows = [{"user_id": "reviewer", "parent_asin": "parent", "asin": "variant",
             "timestamp": (1700000000 + i) * 1000, "rating": 4} for i in range(120)]
    reviews.write_text("\n".join(json.dumps(r) for r in rows) + "\nmalformed\n")
    meta = tmp_path / "meta.jsonl"
    meta.write_text(json.dumps({"parent_asin": "parent", "title": "Correct parent",
                               "average_rating": 5, "rating_number": 999, "price": None}) + "\n")
    data = research({"reviews_path": str(reviews), "metadata_path": str(meta), "category": "test",
                     "source_url": "official-test-fixture", "terms_url": "fixture",
                     "user_sample_fraction": 1, "max_interactions": 1000})
    assert data.products[0]["title"] == "Correct parent"
    assert "average_rating" not in data.products[0]
    assert data.manifest["rejected"] == 1
    assert data.events[0]["user"] != "reviewer"
