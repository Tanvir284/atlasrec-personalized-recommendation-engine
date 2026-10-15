import csv
import json

import numpy as np
import pytest
from atlasrec_ml.bundle import load_bundle
from atlasrec_ml.data import clean_text, demo, product_image, research, temporal_split
from atlasrec_ml.models import Recommender
from atlasrec_ml.pipeline import run


def source_fixture(tmp_path):
    rows = []
    for user in range(60):
        for item in range(3):
            rows.append([f"product-{item}", f"established-{user}", 5, 1000000000 + len(rows)])
    for user in range(420):
        rows.append(["product-0", f"single-{user}", 5, 1000000000 + len(rows)])
    for user in range(60):
        rows.append(["product-3", f"established-{user}", 5, 1000000000 + len(rows)])
    for item in range(100):
        rows.append([f"future-{item}", "future-only", 5, 1000000000 + len(rows)])
    reviews = tmp_path / "ratings.csv"
    with reviews.open("w", newline="", encoding="utf-8") as stream:
        csv.writer(stream).writerows(rows)
    metadata = tmp_path / "metadata.jsonl"
    metadata.write_text("\n".join(json.dumps({
        "asin": f"product-{i}", "title": "<b>Real &amp; archived</b>",
        "description": ["<p>Actual description.</p>", "<script>bad()</script>"],
        "feature": ["Details &amp; materials"], "price": "$12.50" if i else "$5 - $20",
        "category": ["Beauty & Personal Care", "Hair Care", "Shampoo"],
        "imageURLHighRes": [f"http://images-na.ssl-images-amazon.com/images/I/photo-{i}.jpg"],
    }) for i in range(4)), encoding="utf-8")
    config = {"source_format": "amazon2018_ratings", "reviews_path": str(reviews),
              "metadata_path": str(metadata), "category": "Luxury_Beauty", "source_url": "fixture",
              "terms_url": "fixture", "require_complete_histories": True,
              "min_train_user_positives": 3, "user_sample_fraction": 1,
              "max_scan_rows": 1000, "max_interactions": 1000}
    return config, rows


def test_real_csv_train_only_cohort_preserves_full_source_cutoffs_and_photos(tmp_path):
    config, rows = source_fixture(tmp_path)
    data = research(config)
    assert data.manifest["source_dataset"] == "Amazon Reviews 2018"
    assert data.manifest["synthetic"] is False
    assert data.manifest["user_count"] == 60
    assert len(data.events) == 240
    assert not any(event["item"].startswith("future-") for event in data.events)
    expected = np.quantile([row[3] for row in rows], [0.7, 0.85]).tolist()
    assert data.manifest["temporal_boundaries"] == expected
    assert temporal_split(data)["boundaries"] == expected
    assert max(e["timestamp"] for e in temporal_split(data)["train"]) < expected[0]
    assert data.manifest["products_with_source_photo"] == 4
    assert all(p["image"].startswith("https://images-na.ssl-images-amazon.com/") for p in data.products)
    product = next(p for p in data.products if p["id"] == "product-1")
    assert product["title"] == "Real & archived"
    assert product["category"] == "Hair Care"
    assert product["price"] == 12.5 and product["currency"] == "USD"
    assert product["description"] == "Actual description. Details & materials"
    assert next(p for p in data.products if p["id"] == "product-0")["price"] is None
    assert data.manifest["sampling"]["source_accepted_rows"] == 760


def test_complete_history_limits_fail_instead_of_silent_truncation(tmp_path):
    config, _ = source_fixture(tmp_path)
    with pytest.raises(ValueError, match="max_interactions"):
        research({**config, "max_interactions": 100})
    with pytest.raises(ValueError, match="max_scan_rows"):
        research({**config, "max_scan_rows": 50})


def test_source_photo_validation_and_main_variant():
    assert product_image({"imageURLHighRes": ["javascript:alert(1)", "https://127.0.0.1/private"]}) == ""
    assert product_image({"imageURL": ["https://evil.com@images-na.ssl-images-amazon.com/test.jpg"]}) == ""
    assert product_image({"images": [
        {"large": "https://m.media-amazon.com/images/I/other.jpg", "variant": "PT01"},
        {"hi_res": "https://m.media-amazon.com/images/I/main.jpg", "variant": "MAIN"},
    ]}) == "https://m.media-amazon.com/images/I/main.jpg"
    assert clean_text("<style>.fake{}</style><p>Source &amp; text</p>") == "Source & text"


@pytest.mark.parametrize("model_name", ["bpr", "two_tower"])
def test_serving_fit_without_validation_keeps_final_epoch(model_name):
    data = demo(products=20, users=10, interactions=180)
    model = Recommender(model_name, {"epochs": 2, "dimension": 8, "time_budget": 120}).fit(
        data.products, data.events)
    assert model.best_epoch == 2


def test_deployment_refit_includes_new_app_feedback_after_honest_evaluation(tmp_path, monkeypatch):
    data = demo(products=20, users=10, interactions=180)
    data.events.append({"id": "new-real-feedback", "user": "app:new-customer", "item": "demo-0001",
                        "rating": 5, "timestamp": 1900000000, "kind": "rating"})
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("ARTIFACT_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "sqlite:///" + str(tmp_path / "mlflow.db").replace("\\", "/"))
    report = run({"profile": "demo", "models": ["popularity"], "dimension": 8,
                  "refit_for_serving": True, "evidence_name": "retail-test"}, data)
    record = report["runs"][0]
    assert record["status"] == "completed", record.get("error")
    model, manifest = load_bundle(record["bundle"])
    assert "app:new-customer" in model.f.users
    assert record["serving_refit"]["evaluation_before_refit"]
    assert record["serving_refit"]["event_count"] == 181
    assert manifest["serving_refit"]["event_count"] == 181
    assert (tmp_path / "docs/evidence/retail-test-benchmark.json").is_file()
    assert not (tmp_path / "docs/evidence/demo-benchmark.json").exists()
