# Evaluation protocol (version 1)

Written before model optimization. Demo exports are persistently labeled synthetic.
Amazon review labels are preference proxies, not purchases, exposure, CTR or lift.

Globally split timestamps at the 70th and 85th percentiles into train, validation,
test. Boundaries are exclusive on the earlier side. Fit IDs/content vocabulary,
counts and embeddings on train only. Validation selects epochs; test selects nothing.
Evaluate fixed-cutoff histories against the full catalog first observed before train
cutoff. Positive labels are ratings >=4, unseen in history and eligible at the cutoff.
Queries with no eligible positives are counted and excluded from averages explicitly.

Recall@k = unique hits / number of relevant items. NDCG@k = sum of binary hit/log2(rank+1)
divided by ideal DCG for min(k, relevant count). MRR@k = reciprocal rank of first hit,
or zero. Retrieval recall uses k=50; end-to-end uses k=10. A retrieval miss remains
zero in end-to-end metrics. Coverage is unique recommended items / eligible catalog.
Concentration is fraction of recommendations in the top popularity decile.
Diversity is mean distinct categories / returned items. Warm means >=5 history items.
History strata are 0-4, 5-14, >=15 unique past items. Popularity strata use train counts.

Ranker groups come from chronological earlier windows (40%-55%, 55%-70%).
Each retrieval fit and feature transform sees only its earlier window. Candidates
are retrieved without positive injection; exclude groups with all-equal labels and
report the count. Compare ranker and retrieval on equivalent final candidates.

User bootstrap CIs use fixed seed, 200 resamples; paired differences require matching
protocol/dataset/split. Multi-seed research runs are bounded by config.
Cold-item stress withholds interactions for a seeded selection of already-eligible
items while retaining their snapshot content. Retrain; evaluate only held-out item
positives. This is artificial withholding, not newly launched-product evidence.
Snapshot content historical availability is uncertain; include ID-only tower control.

Record duration, artifact bytes, memory where measurable, dependency/source hashes,
hardware, sample counts and benchmark workload. Timeout is a status, not convergence.
Observed app events and synthetic training metrics use distinct namespaces.
Actual executed results are exported under docs/evidence and referenced in BUILD_REPORT.

## Executed bounded research benchmark

Digital Music: 6,402 events from a deterministic 5% user sample, 5,580 metadata products,
3,981 train-observed eligible items. Three seeds (42/43/44), six models each, completed.
All test NDCG@10 values were zero on only 26 eligible queries; 820 users had no eligible
held-out positive after availability/seen filtering. There were no warm test users.
Popularity/CF/BPR/tower validation NDCG was 0.03790; ranker validation was lower and variable.
This sparse temporal subset does not support a superiority claim. Preserve misses and
exclusions, rather than inject positives or substitute synthetic evidence.

Reports retain original training source hashes and separate evaluation source hashes
when additional strata diagnostics are computed over immutable trained bundles.
Item-popularity strata and conditional ranking metrics are separate from end-to-end metrics.

The corrected demo cold-content stress test masks withheld ID embeddings to zero and
retains only permitted content. NDCG@10 was 0.2494 on 30 eligible queries with 20 eligible
withheld items. This is artificial withholding, not evidence for newly launched products.

In-process model benchmarks used 200 requests, 20 warmup requests and 10 clients.
No errors were observed. This excludes HTTP, database and cache costs. The separate native
SQLite HTTP run missed the 300ms target (p95 2502.8ms) while Redis was unavailable and builds
contended for memory. Do not report that run as a PostgreSQL/Redis production measurement.


## Actual Compose HTTP measurement

The repeated guest workload included 200 requests after 20 warmup, ten concurrent
clients, 200 products, the trained popularity-cde25f148369 bundle, HTTP/Next proxy,
FastAPI, PostgreSQL writes and Redis. Using 127.0.0.1:3000, p50 was 462.88ms, p95
4384.05ms, throughput 8.59 requests/second, with zero errors. PostgreSQL records confirmed
200 cache hits for the exact measured request IDs. The 300ms target was missed.
The host had about 232MB free RAM at measurement start; this is one resource-constrained
local cached guest workload, not uncached personalized latency or production capacity.

The initial localhost run retained p95 6805.84ms and ten 503 responses. A socket probe
measured about 2.03s for localhost (IPv6 then IPv4) versus 0.8-18ms for explicit IPv4.
The verified rerun's recorded precommit API p95 was 689.84ms; that measurement excludes
commit/response transfer. These results suggest substantial non-model overhead in the
network/proxy/persistence boundary under memory pressure; the remaining overhead was
not isolated to one component. See compose-http-benchmark.json, its retained initial
measurement, and latency-diagnostics.json. Do not replace the initial failure with a
claim that every performance run passed.
