# Model card

## Current real retail installation (2026-10-06)

Active model: `item_cf-7f011e780482`, real dataset `079976012a366152`.
Three models completed the same chronological evaluation on 655 eligible test
queries. Item-CF test NDCG@10 was 0.025176 and Recall@10 0.037674, compared with
popularity NDCG@10 0.001820 and two-tower 0.013602. Item-CF was selected using
validation warm-user NDCG, then refit on all 52,249 accepted historical reviews.
The serving refit's training data includes the old evaluation windows; reported
metrics describe the preceding held-out evaluation, not an independent test of
the refitted artifact. One seed and one established-reviewer cohort do not
establish general performance superiority.

New application feedback changes the online context immediately and can enter
queued serving refits. Historical reviewer IDs never identify app accounts.
Live inference checks confirmed different observed histories yield different
recommendations and seen items are excluded. Details: REAL_DATA.md.

## Earlier baseline and common guarantees

Intended use: local discovery and reproducible recommendation experiments.
The initial demo launcher trains and promotes a popularity bundle; advanced experiments
produce validated candidates requiring explicit administrator promotion.

Active version is installation-specific and displayed by /admin/models. Do not infer
a globally active model from an offline experiment export. Demo comparative results
are in docs/evidence/demo-benchmark.json. The item-CF baseline beat the advanced models
on the first synthetic seed; validation governs promotion, not held-out test scores.

Artifacts retain version, dataset/split IDs, source hash, dependency versions, feature
schema, ID map, vectors/index and checksums. Load/parity checks and corrupted bundle
tests protect consistency. Failed/timeout runs cannot be promoted.

Fallback is valid available category/popularity items when history is empty, weights
are missing/invalid or candidate retrieval is insufficient. Database failure is a
service error. App users' preference signals differ from imported offline review users.
Synthetic performance establishes software behavior only.

Replacement requires completed training, compatible bundle validation, comparable
validation protocol and explicit admin promotion; rollback uses previous audit entries.
Review bias, sparse users, uncertain snapshot content and false-negative training samples
remain limitations. Latency measurements depend on hardware, database/cache and workload.


Verified serving version on this host, 2026-10-05: popularity-cde25f148369, synthetic
demo profile, 200 products. Its displayed test NDCG@10 is 0.0862. Worker jobs produce
candidates and preserve this active version; real promotion/rollback checks restored it.
The six offline benchmark bundles are registered as candidates, not automatically active.
Actual application HTTP p95 was 4384.05ms in the documented cached guest workload;
model-only benchmarks exclude this networking/persistence overhead. The current machine
missed the latency goal, and no production capacity claim is supported.
