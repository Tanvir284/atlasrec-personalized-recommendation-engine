# Status - real catalog installed; final visual check in progress
Updated 2026-10-06, Asia/Dhaka. docs/PROJECT_SPEC.md remains authoritative.

The running installation now uses the real Luxury Beauty research catalog:
6,692 products, 52,249 historical reviews, 9,947 pseudonymous reviewers and
5,886 source photo URLs. Dataset `079976012a366152`; active model
`item_cf-7f011e780482`. Existing demo data remains isolated and preserved.

Current checks: 41 Python tests passed, Python/frontend lint passed, production
images built, six desktop/phone browser checks passed, and an actual real-data
worker job completed in 118.65 seconds. Different observed histories produce
different recommendations, and seen/dismissed products are excluded. Final
homepage photo selection, screenshots and Desktop synchronization are in progress.

On 655 chronological test queries, NDCG@10 was 0.025176 for item-CF,
0.013602 for two-tower and 0.001820 for popularity. Selection used validation;
serving bundles were then refit on all source history. These are historical
recommendation metrics, not purchase accuracy or demonstrated business lift.
See docs/REAL_DATA.md and docs/evidence/retail-checks.json.

## Earlier verified baseline

The local application and bounded research deliverable pass their functional
checks. The HTTP performance acceptance target remains open. The app runs at http://localhost:3000 with a protected workbench at /admin.
Sources and evidence are copied into the exact requested Desktop project directory.

Verified:
- WSL 3.0.1 repaired; Docker 29.8.1 responds; final Compose startup and idempotent bootstrap pass.
- Next.js/FastAPI/PostgreSQL/Redis/Celery serve an actual trained popularity bundle.
- Six real demo models trained, evaluated, serialized and registered as candidates.
- Research importer and 18 real Digital Music runs over seeds 42/43/44 completed.
- Previous full bug audit Python suite: 29 passed, including ten bug audit cases. Nine new cases failed before their fixes.
- Python/frontend lint and production image build pass. Targeted API/feedback checks: seven passed.
- Amazon-inspired storefront and 20 product illustrations verified at 1440px, 390px and 320px; no overflow, broken images or runtime errors in the final captures.
- Eighteen current desktop/phone browser checks pass, including search/filter/pagination, department drawer, login return, wishlist counts, rating persistence, image zoom, delayed-script hydration, incomplete-response recovery, persisted shopper state, actual worker completion, title/view tracking, impression retry and CSRF cookie recovery/rotation.
- Concurrent event IDs, real worker failure/retry, active-model preservation and promotion/rollback pass.
- Actual shop, monitoring and experiment screenshots were inspected after data and chart rendering settled.
- Warm IPv4 HTTP workload: 200 requests, ten clients, zero errors, 200 verified Redis cache hits.

Material limitations:
- HTTP p95 was 4384.05ms and missed the 300ms goal on this resource-constrained host.
  The initial localhost run had p95 6805.84ms and ten errors; both results are retained.
- All research test NDCG values were zero on only 26 eligible queries with no warm users.
  This provides reproducibility evidence, not a real-world superiority claim.
- GitHub CI, external deployment, backup/restore rehearsal and hard-kill exactly-once
  recovery remain unverified. Activation is coordinated within the single API process.

See docs/BUILD_REPORT.md for measurements and docs/BUG_AUDIT.md for earlier fixes and docs/UI_REDESIGN.md for the current storefront verification.
