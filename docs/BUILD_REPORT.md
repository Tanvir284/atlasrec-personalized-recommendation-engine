# Build report - local verification

Verified on 2026-10-05, Asia/Dhaka. This is a local portfolio application with no
production traffic, proven sales lift, or external deployment.

## Delivered and executed

Next.js JavaScript discovery/catalog/detail, account onboarding, interests, saved
products, dismissals and personalized/similar recommendations connect to FastAPI.
PostgreSQL persists users, sessions, preferences, ownership-bound events, exposure
requests, datasets, runs, jobs, model versions and promotion history. Redis caches
recommendations; a real Celery worker runs bounded CPU experiments. The protected
workbench displays persisted experiments, jobs, registry changes and observations.

The original Desktop folder was empty because work ran in Codex's separate worktree.
Source and evidence are synchronized to the exact requested Desktop folder.
Dependencies, raw data, local secrets and native artifacts are excluded from that copy.
The named Compose volumes retain the running application's data and models.

## Environment and WSL repair

Windows 11 build 26300, approximately 8GB RAM, eight logical CPU threads.
System Python 3.14.3 launches Docker; the ML runtime uses Python 3.12.13 and CPU
PyTorch 2.14.1+cpu. Node 24.11.0, Next 16.3.8 and React 19.3.0 are pinned in locks.
The broken PATH npm shim is bypassed through Node's bundled npm CLI.

The official Microsoft-signed WSL 3.0.1 installer exited successfully. WSL reports
3.0.1 and Docker server 29.8.1 responds. Installer SHA256:
28b1a0d013640a2ac95898ea705fa186e5b4ff767a1c1b49257161bc106599c6.
No Windows reboot was issued. Docker image digests are pinned.
Windows long paths and Unicode FAISS file IO were repaired. Next build concurrency
is limited to two following observed memory pressure during concurrent builds.

## Acceptance evidence

| Check | Actual outcome |
|---|---|
| Ruff and frontend ESLint | Passed; commands retained in evidence/checks.json |
| Python correctness | Original full suite: 17 passed; dedicated cold-ID mask check passed; latest API/feedback/settings regression: 6 passed in 121.55s |
| Production build | Next standalone image built with every required route |
| PostgreSQL migrations and bootstrap | Executed against fresh project volumes; subsequent bootstrap reused the active model and data |
| Persisted shopper / ownership | Real HTTP acceptance and production browser journeys passed |
| Concurrent event IDs | Five simultaneous copies created one event |
| Queue failure/retry | Real Redis/Celery job failed, then completed on attempt 2; active version preserved |
| Promotion / rollback | Real candidate activation followed by restoration of the previous validated bundle |
| Desktop and phone browser | 2 passed, 0 failed; actual queue completion and screenshots |
| Visual inspection | Actual screenshots inspected; no document overflow, broken images, or corrupted visible text |
| CI | Workflow provided; GitHub execution not claimed |

Browser checks use the actual container API, PostgreSQL, Redis and trained models.
No request interception supplies mock recommendation results. An earlier isolated
SQLite fixture is separate from this acceptance environment. Failed build/browser
attempts are not counted as passes. The Starlette httpx adapter deprecation remains
documented. Session-bound CSRF, Origin validation, role checks and public demo
credential rejection in production have been exercised.

## Measured synthetic models

200 products, 100 generated users, 3,000 timestamped events; one chronological split
and 96 eligible test users. These results demonstrate software behavior.

| Model | Test NDCG@10 | Train seconds | Bundle bytes |
|---|---:|---:|---:|
| popularity | 0.08616 | 0.19 | 52,967 |
| item_cf | 0.20970 | 0.08 | 80,069 |
| bpr | 0.19339 | 19.67 | 94,480 |
| two_tower | 0.18650 | 50.92 | 111,564 |
| two_tower_id | 0.17768 | 62.11 | 111,518 |
| ranker | 0.17675 | 51.36 | 129,442 |

Item-CF improved NDCG@10 over popularity by 0.12354, paired user bootstrap 95% interval
[0.08761, 0.16000]. It beat the advanced models in point estimates on this synthetic
sample. Content tower scored 0.18650 versus ID-only 0.17768. The ranker used 123
usable historical groups and excluded 76 constant-label groups. Missed candidates
remain misses; no relevant test items were injected.

Corrected cold-content stress masked withheld collaborative ID embeddings to zero:
20 eligible items withheld, 30 queries, NDCG@10 0.24941. This is artificial withholding,
not evidence for newly launched item performance.

Six real offline demo bundles were copied, compatibility-checked and registered as
candidates in PostgreSQL. Their original run/source provenance remains in records.
They were tracked in the native MLflow store; container worker runs use the private
persistent container MLflow store. Importing reports does not automatically promote.

## Bounded research result

Official Amazon Reviews 2023 Digital Music files totaled 39,886,470 bytes, with retained
checksums and provenance. Deterministic 5% user sampling retained 6,402 events and
5,580 metadata products; 3,981 train-observed candidates were eligible.
Eighteen completed experiments cover all six models and seeds 42/43/44.
Every test NDCG@10 was zero on only 26 eligible queries; 820 users were excluded and
no warm test users remained. Cold research stress had five queries and zero NDCG.
This sample supports execution/provenance evidence and does not support a useful
superiority claim. A degenerate zero bootstrap interval is not population certainty.
No synthetic research results were substituted. Raw data is not redistributed.

## HTTP and model performance

Actual Compose HTTP benchmark: 200 requests after 20
warmup, 10 concurrent clients, 200 products,
one stable guest actor, active versions popularity-cde25f148369.
The boundary includes localhost HTTP, Next proxy, FastAPI, PostgreSQL writes and Redis.
P50 462.88ms; p95 4384.05ms;
throughput 8.59 requests/second; 0 errors.
Per-request PostgreSQL records confirm 200 cache hits out
of 200 requests. The 300ms warm target was
missed. This repeated guest/cache workload does
not establish uncached personalized latency or production capacity.

The initial localhost benchmark is retained in compose-http-benchmark-initial.json:
p95 6805.84ms and ten service errors. A direct socket probe found localhost resolved
to IPv6 and IPv4, taking about 2.03s to connect versus 0.8-18ms with explicit IPv4.
The verified zero-error rerun used 127.0.0.1 and observed only about 232MB free host RAM.
Recorded precommit API p95 was 689.84ms, compared with full HTTP p95 4384.05ms.
These measurements suggest substantial overhead in networking, proxy and persistence
under resource pressure; they do not isolate the remaining overhead to one component.
Model-only speed must not be presented as end-to-end application latency.

In-process inference over existing bundles used 200 requests, 20 warmup and ten
clients with zero errors; p95 ranged from 4.83ms popularity to 148.08ms ranker,
excluding HTTP/DB/cache. The earlier native SQLite/no-Redis HTTP run measured p95
2502.8ms under memory/build contention and missed the target; it is retained separately.
Earlier Windows training peaks were marked unavailable. The current sampler measures
process RSS every 100ms using Windows counters or Linux /proc, excluding child processes.
No unmeasured historical peaks were backfilled.

## Remaining limitations and unverified paths

There are no open local build/browser/container acceptance blockers.
External deployment, GitHub CI execution, backup/restore rehearsal and hard-kill
exactly-once recovery have not been exercised. Explicit stale-job retry exists after
the configured cap plus a grace period. Registry activation is atomic within the
single API process used here; multi-process deployment needs coordinated activation.
Review bias, uncertain historical content availability, sparse research users and
false negatives limit model interpretation. Inspect licenses/terms before reuse.
The local demo credentials are public and rejected by production settings.
Deliberately failed smoke jobs remain visible as real diagnostic history.

## Evidence and commands

- evidence/checks.json: executed command outcomes and visual inspection.
- evidence/container-check.json: real persisted state, event IDs and promotion/rollback.
- evidence/queue-recovery.json: actual failure, retry and active-version preservation.
- evidence/browser-check.json and home/admin/experiments desktop/phone PNGs: production browser results.
- evidence/demo-benchmark.json, research-benchmark.json and summaries: measured ML records.
- evidence/compose-http-benchmark.json: measured HTTP requests and verified cache state.
- evidence/model-serving-benchmark.json: in-process workload and results.
- evidence/http-benchmark.json: earlier isolated native workload.

From the project directory:
python scripts/manage.py doctor
python scripts/manage.py demo
Shop http://localhost:3000; workbench http://localhost:3000/admin.
Demo access is documented in DEMO.md. stop preserves volumes.

A measured portfolio description: implemented six CPU recommendation models and a
persisted full-stack discovery application; verified chronological evaluation, bundle
compatibility, real worker recovery and two browser layouts; executed an 18-run
Amazon research benchmark with explicitly reported sparse-sample limitations.

## Subsequent correctness audit

The 2026-10-05 audit corrected feedback, concurrent saves, CSRF recovery, cache and inference fallback, tracking, validation, lifecycle and ML input issues. The current full Python suite passed 29 cases and desktop/phone browser checks passed six cases. The rebuilt local stack and PostgreSQL/Redis audit passed. See [BUG_AUDIT.md](BUG_AUDIT.md) and evidence/bug-audit-checks.json. Earlier benchmark measurements above remain historical evidence; this audit makes no new latency or real-world quality claim.
