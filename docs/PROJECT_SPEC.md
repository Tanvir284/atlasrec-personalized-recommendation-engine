# AtlasRec — End-to-End Build Master Prompt

You are the lead engineer responsible for implementing AtlasRec, a complete full-stack product recommendation platform. Work directly in the available repository: write the software, run it, inspect its behavior, fix failures, and leave a reproducible project. This is an implementation request, not a request for a proposal or code snippets.

The owner wants a substantial machine learning engineering portfolio project that they can operate, study, demonstrate, and explain in interviews. Build for that goal: rigorous ML experiments, a useful React/Next.js product, maintainable Python services, and honest evidence of what works. Do not promise hiring outcomes or claim production experience the project does not have.

## 1. Working contract

- Inspect the existing repository, applicable AGENTS.md instructions, available tools, runtime versions, hardware, and existing changes before choosing the implementation details. Preserve unrelated work.
- If the workspace is empty, initialize a monorepo. If there is existing project code, extend it coherently instead of replacing it unnecessarily.
- Treat this document as the project specification. Save it as `docs/PROJECT_SPEC.md` if it is not already available in the repository. Maintain `PLAN.md` with milestones and acceptance checks, and `STATUS.md` with completed work, evidence, blockers, and the next executable step.
- Briefly state your assumptions and plan, then start implementation. Make routine decisions independently using the defaults below. Ask only when missing information creates a material blocker, an incompatible requirement, a destructive operation, or an unapproved cost.
- Use current official documentation for version-sensitive APIs and select compatible stable releases. Pin the actual resolved versions and commit lockfiles; do not invent package versions or rely on floating versions in reproducible builds.
- Work in small vertical slices. For each milestone: implement, run relevant checks, inspect the result, fix meaningful failures, then update status and proceed. Do not stop after scaffolding, a plan, one model, or a visually complete frontend.
- Respect actual tool access and environment limits. Never claim to have run a command, downloaded data, trained a model, measured a result, or deployed a service unless you did so.
- At an unavoidable session limit, checkpoint files and record exact remaining work. Resume from those files in the next session without rebuilding completed components. A checkpoint is not project completion.
- Continue through all required milestones within the available session. Keep explanations concise during implementation and put durable technical reasoning in the repository.

## 2. Product scope and resource defaults

AtlasRec helps users discover products based on their preferences and past interactions. It also gives an authenticated administrator an ML workbench for examining data, comparing experiments, promoting models, and observing system behavior.

Build two clearly identified operating profiles:

1. **Demo:** deterministic, generated product and interaction data with realistic sparsity, timestamps, repeated users, cold-start cases, and nontrivial preference patterns. This profile must work without external datasets, pretrained downloads, paid APIs, or a GPU after dependencies and containers are installed. Models must actually train; synthetic results demonstrate software behavior only.
2. **Research:** a configurable category/subset of Amazon Reviews 2023 with a real ingestion pipeline, temporal evaluation, experiment records, and dataset provenance. A missing network connection must not silently substitute synthetic results in this profile.

Use CPU-first settings suitable for a personal computer. Start with approximately 200 products, 100 synthetic users, and 3,000 timestamped interactions for the demo, ensuring each evaluation window contains meaningful examples. For research, begin with a deterministic user-based subset capped around 100,000 interactions, then scale by configuration. Document how the sampling procedure affects the population represented.

Make data size, epochs, embedding dimension, thread count, negative sample count, memory budget, and training time budget configurable. Set conservative smoke-training defaults, such as a five-minute cap per model, and record actual completion or timeout. Do not start an unbounded full-dataset download or expensive training job. Verify expected download size first; support user-provided local files and bounded streaming where available.

The required deliverable is a locally runnable, containerized portfolio application with a deployment runbook. Prepare deployment configuration, but do not purchase resources, publish to an external account, push commits, or expose an unauthenticated admin interface without authorization. Payment processing, checkout, shipment management, mobile apps, conversational agents, Kubernetes, Kafka, and large foundation-model training are outside this build.

## 3. Technology and service boundaries

Use this stack unless an actual compatibility problem requires a documented, minimal substitution:

| Area | Required choice |
| --- | --- |
| Web application | React with Next.js App Router; JavaScript `.js` / `.jsx`, not TypeScript source |
| Web styling | Tailwind CSS, accessible reusable components, Lucide icons, Recharts for actual metrics |
| Client data access | A centralized API client and TanStack Query where client caching is useful |
| API and business logic | Python, FastAPI, Pydantic, SQLAlchemy, Alembic migrations |
| Persistent application data | PostgreSQL |
| Cache and background queue | Redis and Celery, with training concurrency limited by configuration |
| ML implementation | NumPy, SciPy, pandas or Polars, scikit-learn, PyTorch, LightGBM |
| Candidate index | FAISS CPU with an exact-search reference implementation |
| Experiment tracking | MLflow; a local tracking database/artifact directory or private service profile |
| Tooling | npm workspaces and lockfile; uv and Python lockfile; ESLint, Ruff, pytest, Playwright |
| Packaging and automation | Dockerfiles, Docker Compose, GitHub Actions workflow files |

JavaScript is an explicit frontend requirement. Configure the Next.js scaffolder accordingly. Use JSDoc and runtime validation where helpful; do not quietly switch the project to TypeScript. Python code should have useful type hints.

Keep training and inference in Python. FastAPI owns business rules, authentication, authorization, database writes, and recommendation orchestration. Next.js handles UI and a narrow same-origin proxy/server integration; do not duplicate the backend inside Next.js route handlers.

Long training and evaluation jobs run in the Celery worker, never inside a web request or the API's lightweight background-task mechanism. Return a job ID promptly, persist job state, expose progress, handle failure/timeouts, and make retries idempotent. A failed run must not replace the active model.

Use one shared Python feature/transformation package for training and inference. A separate feature-store product is unnecessary. Store immutable model bundles in a local mounted artifact directory for the default installation; use an interface that could later support object storage.

A reasonable repository layout is `apps/web`, `services/api`, `packages/ml/atlasrec_ml`, `configs`, `scripts`, `tests`, `docs`, and `.github/workflows`. Keep one installable Python workspace/package configuration where practical. The worker may share the API image with a separate command. Create directories when they have a real purpose, not as empty scaffolding.

## 4. User experience and visual direction

Build a polished, responsive product with two connected areas: a shopping-discovery experience and an ML workbench. Use a consistent light theme with warm neutral backgrounds, dark readable text, restrained teal accents, generous spacing, and clear typography. Build a compact responsive navigation system and deliberate product cards. Avoid decorative dashboards with invented business numbers.

Required routes and behavior:

- `/`: discover feed with personalized recommendations, popular products, and category exploration.
- `/catalog`: searchable product catalog, category and available-price filters, sorting, pagination, URL-preserved filters, and useful empty results.
- `/products/[id]`: product information, similar items, favorite/not-interested actions, and a concise recommendation explanation when applicable.
- `/for-you`: recommendations based on the authenticated user's available history and onboarding preferences.
- `/saved`: persisted favorites with add/remove behavior.
- `/profile`: preference editing, interaction-history controls, and an explanation of what influences recommendations.
- `/login` and `/register`: working authentication and validation.
- `/admin`: protected system overview with real status and links into datasets, experiments, model versions, jobs, and monitoring.
- `/admin/experiments`: comparisons of compatible runs with dataset profile, split, metrics, seed, runtime, and model version visible.
- `/admin/models`: active version, validation evidence, explicit promotion, rollback, and a history of changes.
- `/admin/jobs`: queued/running/completed/failed jobs with progress and actionable failures.
- `/admin/monitoring`: observed latency, errors, cache/fallback behavior, data quality, and drift summaries.

Search can use PostgreSQL full-text search initially; it does not need to be a second ML research project. Keep recommendation evaluation separate from search relevance.

Support guest browsing and a signed-in personalized experience. New users choose a few interests or favorite products. For users without enough signals, apply a documented popularity/content fallback and describe the reason plainly. The demo may offer clearly labeled synthetic personas; never let this become arbitrary account impersonation in research or production configuration.

Make every visible control functional. Include loading, empty, error, retry, not-found, and access-denied states. Use semantic markup, keyboard navigation, visible focus, accessible form labels, meaningful alt text, and reduced-motion support. Verify phone and desktop layouts. Use licensed or generated local demo assets and reliable fallbacks; avoid mandatory remote fonts or images for demo startup.

Do not invent local prices or silently relabel USD as BDT. Preserve source currency where available and show missing values honestly. Keep technical details in the ML workbench and documentation; shopper-facing pages should remain understandable.

## 5. API, identity, and data model

Design versioned REST endpoints under `/api/v1` and publish the actual OpenAPI schema. Implement coherent endpoints for authentication/session lifecycle, current user/preferences, catalog/detail/search, favorites, feedback/events, personalized/similar recommendations, and protected dataset/run/job/model/monitoring operations. Every required UI screen must connect to persisted backend data.

Use PostgreSQL migrations and appropriate indexes/constraints for users, sessions, preferences, products, favorites, interaction events, recommendation requests/exposures, dataset versions, experiment runs, model versions, jobs, and admin audit records. Use explicit UTC timestamps and dataset/profile namespaces. Keep research reviewer identities pseudonymous and separate from application login identities; offline research users are not customer accounts.

For local authentication, use a maintained password-hashing library with Argon2 and opaque expiring server-side sessions. Store session-token hashes, rotate sessions on authentication, implement logout/revocation, and use HttpOnly cookies with environment-appropriate Secure and SameSite settings. Validate Origin and use CSRF protection for cookie-authenticated state changes. Do not store credentials or session tokens in browser localStorage. Enforce ownership and admin permissions in FastAPI, not just by hiding buttons.

Default to same-origin browser API calls through the application proxy. Document host URLs, container-internal URLs, cookie forwarding, allowed origins, and the separate server/client environment variables. Keep PostgreSQL, Redis, and MLflow private in deployment configuration. Include request size limits, bounded pagination, input validation, basic authentication rate limiting, and safe error responses.

Interaction records must distinguish views, visible impressions, clicks, favorites, dismissals, ratings, and imported review events. Use an idempotency/event ID, server timestamp, optional validated client timestamp, session/request ID, item ID, surface, position, and served model version. Derive the actor from the session; do not trust a client-supplied user ID.

Record impressions when recommendations become visible, not merely when the server generates candidates. Prevent duplicate impressions from rendering retries. Keep demonstration traffic labeled and separate from real-user metrics. Do not claim CTR, conversion, or business lift from Amazon review records.

## 6. Dataset and feature pipeline

Implement reproducible CLI commands for generating demo data, ingesting research files, validating schemas, cleaning/deduplicating, creating temporal splits, building features, training, evaluating, and exporting a serving bundle. These must share code with worker jobs.

Use the official Amazon Reviews 2023 project as the initial research source. Choose a category after inspecting size, metadata coverage, and repeated-user density. Normalize source fields explicitly, including rating, review timestamp, reviewer ID, and parent product ID. Join product metadata by the documented parent ID, not by accidentally mixing product variants. Record rejected/malformed rows and missing metadata.

Create a dataset manifest containing source URL/reference, retrieval date, applicable terms/license reference, files/checksums, category, parser version, filtering/sampling configuration, row counts, timestamp range, and split boundaries. Do not redistribute a full third-party dataset by default. Provide reproducible download/import instructions and respect the source's usage conditions.

Define the first research task precisely: recommend previously unseen products that a user will positively rate in a future evaluation window. Use a configurable positive threshold, initially rating >= 4. Imported reviews are a preference proxy, not a complete purchase or exposure log. Unobserved items are not confirmed dislikes; document this limitation and selection bias.

Leakage controls are mandatory:

- Use global chronological train/validation/test boundaries. Fit vocabularies, scalers, text transforms, sampling statistics, and other learned preprocessing only on the applicable training history.
- Construct every example's user history and aggregate features from information available before its prediction timestamp. Exclude the target interaction from its own history. Do not build historical features from current application state.
- Compute popularity and rating aggregates using training-time events. Do not use the dataset's crawl-time `average_rating`, `rating_number`, or similar future-derived metadata as historical features.
- Treat product title, description, and price from a crawl snapshot as having uncertain historical availability. Report this assumption for content experiments, exclude unsuitable time-varying fields from strict historical claims, and retain an ID-only comparison.
- Define item eligibility at the prediction cutoff. First-observed interaction may serve as a documented availability proxy, not proof of catalog launch date. Exclude future-only items from the strict time-respecting candidate universe.
- Define repeat-item handling, duplicate handling, unknown-ID handling, empty histories, and users with no eligible test positives. Report excluded counts and their effect on coverage.
- Do not choose thresholds, checkpoints, feature sets, or hyperparameters on the held-out test set. Do not apply full-dataset activity filters that reveal future user behavior.

## 7. Required recommender models

Implement a consistent interface for fit, candidate retrieval, scoring, save/load, and metadata, with adapters where algorithms differ. Train and evaluate these required models on the demo and on a bounded real subset when accessible:

1. **Popularity baseline:** training-only counts or configurable time decay, with a category-aware cold-user fallback.
2. **Item-item collaborative filtering:** sparse similarity with documented normalization, shrinkage/minimum support, seen-item filtering, and memory limits.
3. **Matrix factorization:** implement BPR implicit-feedback training in PyTorch with negative sampling, L2 regularization, validation-based early stopping, and deterministic seeds. Include the objective and sampling assumptions in documentation.
4. **Two-tower retrieval:** a user tower that can encode past item history/preferences and an item tower with learned item representations and text/category features. Use an explicit sampled-softmax or contrastive objective, including a mathematical definition and implementation notes. Handle repeated positives and mask invalid in-batch negatives. Treat negative samples as training assumptions rather than verified negative feedback.
5. **Learning-to-rank stage:** LightGBM LambdaMART/LGBMRanker over retrieved candidates, using retrieval score, history-item similarity, training-time popularity, and category affinity where available. Group examples correctly by user/prediction context and document the label construction.

For the content pathway, start with training-fitted TF-IDF and optional truncated SVD over product title/description/category. This keeps the entire pipeline reproducible on CPU without a model download. The item content pathway must handle an unknown item ID; avoid collapsing all new items into an identical OOV vector. A pretrained text encoder can be a later controlled extension, not a requirement for booting the app.

Train the ranker on candidates generated from earlier historical windows or chronological out-of-fold retrieval predictions. Retrieval models, feature transformations, and aggregate statistics used for each such window must be fitted only on its earlier history. Do not train the ranker on final test candidates or use a target event in its features. If positives are injected into ranker training candidates, label and document that intervention; never inject them into the end-to-end evaluation results.

Ensure training groups contain usable relevance variation; record groups excluded from ranker training and preserve all eligible queries in end-to-end evaluation. Keep review-based relevance labels and application-event weighting explicit and versioned rather than merging event types indiscriminately.

Online recommendation flow: derive allowed history/preferences, retrieve candidates, score/rank, filter seen/dismissed/unavailable items as configured, and apply a small configurable diversity reranker. Return unique valid items and evidence-based reason codes. A score is a relevance score, not a calibrated purchase probability.

Cache item representations and load models once per serving process. On CPU, start with exact inner-product search through FAISS and retain a NumPy/brute-force reference for correctness. Add approximate indexing only if measured scale justifies it, then measure recall relative to exact retrieval. Do not claim an approximate-search implementation when the active index is exact.

New application users will not exist in research user-ID tables. Use their own app history to construct history/content representations over the same product-ID space, with a documented source mismatch. Do not assign them a research user's embedding. Feedback can update the request's history immediately; updating model weights requires an explicit training job.

## 8. Evaluation and research evidence

Write the evaluation protocol before optimizing models. Make the offline evaluator independent of the web interface and callable from both CLI and worker jobs.

Report:

- Retrieval Recall@K for explicitly stated candidate cutoffs.
- End-to-end Recall@10, NDCG@10, and MRR@10, with exact metric definitions and treatment of multiple relevant items.
- Catalog coverage, recommendation popularity concentration, and diversity with stated definitions.
- Warm-user performance and results stratified by available history and item popularity.
- A separate cold-item/content stress test with stated item availability assumptions. Do not mislabel future-only products as eligible historical candidates.
- Training time, peak memory where measurable, serving latency, throughput, and artifact size, including hardware and workload details.

For a reproducible simulated cold-item test, choose products eligible at the training cutoff, hide their collaborative training interactions, retain only the permitted content, and retrain the affected models. Report this as artificial interaction withholding; it does not prove performance on genuinely newly launched products.

Evaluate against the full eligible catalog for the small demo and bounded research benchmark where feasible. If catalog scoring must be batched, preserve the same ranking semantics. If sampled evaluation is necessary, record the sampler and candidate counts, reuse a fixed protocol across models, and visibly distinguish sampled metrics from full-catalog metrics. Preserve the same data split, test queries, eligible catalog, and label definition in comparable runs.

Separate retrieval quality, conditional ranking quality, and end-to-end quality. If retrieval misses a relevant item, its contribution to end-to-end recall/NDCG must remain a miss. Do not evaluate a ranker only on conveniently selected successful retrievals and label that number end-to-end performance.

Report evaluation user counts and use user-level bootstrap confidence intervals for comparable metric differences when sample size permits. Run a bounded multi-seed comparison for stochastic models on the research subset; record seed count and variability. Synthetic metrics must have a persistent synthetic/demo label in exports and charts.

Required controlled experiments, using validation for decisions:

1. Popularity vs item-item CF vs BPR vs two-tower retrieval.
2. Two-tower with and without content features.
3. Retrieval-only ordering vs the learned ranker over equivalent candidate sets.
4. Relevance/coverage changes with and without diversity reranking.

Add a short failure analysis with representative examples, candidate misses, sparse users, and popular-item bias. Keep experiments tied to hypotheses. Do not run a large sweep just to fill a chart. A simpler model winning is an acceptable result; keep the advanced implementation and explain the evidence.

Persist run configuration, dependency/code version or source hash, dataset and split IDs, model/feature versions, seed, metrics, timing, artifact checksums, and completion status. Log actual experiments to MLflow and expose persisted summaries to the application. The UI must not depend on fabricated static metrics or require public access to the tracking server.

Keep synthetic data, public research data, replayed events, and real application traffic distinct in metrics. Observational clicks alone do not prove causal improvement. Document a future randomized A/B experiment design, but do not claim a live A/B test or sales lift without real assignment, exposure, outcome, and statistical evidence.

## 9. Model lifecycle, consistency, and failure handling

A serving bundle must contain model weights, preprocessing state, ID mappings, feature schema, vector index, configuration, dataset version, dependency compatibility metadata, and checksums. Tie the index and embeddings to the same model version. Reject mismatched dimensions, ID maps, corrupted files, and incompatible bundles before activation.

Support a candidate/staging state, validation, explicit admin promotion, and rollback to the previous validated bundle. Promotion must be atomic from a request's perspective: one request cannot mix old item vectors with a new model. Cache keys must include the active model version, user/history revision, and relevant filters. Invalidate stale personalized results on feedback or preferences changes.

For a default single API process, a validated in-memory bundle swap is sufficient. Document the process-count assumption and how version changes would propagate before scaling to multiple API replicas; do not claim consistency guarantees you have not implemented.

Provide reliable fallback to valid category/popularity recommendations when a user is unknown, history is empty, a model is unavailable, or retrieval yields too few results. Track fallback reason/rate. If the database is unavailable, return an honest service error rather than inventing products. Distinguish API liveness, database readiness, and model readiness.

Log structured request IDs, model version, durations, and errors without passwords, tokens, raw personal data, or unnecessary review text. Track latency distributions, errors, recommendation volume, job health, cache behavior, fallback rate, and feature missingness. Show actual observed values and empty states when insufficient data exists.

Implement a lightweight drift report for at least category distributions and one numeric feature using a defined reference window and configurable threshold. Label the statistic and sample counts. A drift warning is a diagnostic signal; do not automatically replace a model because a threshold fired. Retraining should produce a candidate version that must pass validation and promotion checks.

## 10. Reproducible local operation

Provide tested Docker Compose services for web, API, worker, PostgreSQL, and Redis. Make the tracking service an optional private profile if it is not needed for basic operation. Persist database and model artifacts in documented volumes and avoid embedding secrets or training data in images.

Create `.env.example` with every required variable, useful comments, and no real credentials. A setup script may generate local secrets. Demo accounts/personas are allowed only with an explicit demo setting; any local demo admin credentials must be documented and rejected by a production configuration check.

Implement a cross-platform Python launcher with this coherent command surface; use working wrappers instead of documenting imaginary commands:

| Command | Expected behavior |
| --- | --- |
| `python scripts/manage.py doctor` | Check runtime/tool prerequisites, configuration, ports, and hardware; report useful fixes |
| `python scripts/manage.py demo` | Build/start the local stack, apply migrations, seed demo data idempotently, train/register a small model, and report URLs |
| `python scripts/manage.py verify` | Run the implemented fast correctness/build checks and report failures accurately |
| `python scripts/manage.py research --config configs/research.yaml` | Run bounded ingestion, training, evaluation, and reporting with explicit provenance |
| `python scripts/manage.py benchmark --config configs/benchmark.yaml` | Execute the selected comparable model experiments and serving benchmark |
| `python scripts/manage.py stop` | Stop services while preserving persistent data |

The exact CLI names may be adapted once with a documented reason, but README, CI, and implementation must agree. `doctor` should not require installing the entire ML stack just to inspect prerequisites. Document both `python` and `python3` invocation where relevant and Windows/WSL notes without assuming Unix-only Make commands.

Demo startup should be idempotent. Re-running it must preserve user changes, avoid duplicate records, reuse compatible artifacts, and not retrain everything on every web restart. Provide an explicit reset command restricted to project/demo resources and require confirmation before deleting persistent data. Use health checks and readiness conditions instead of arbitrary long sleeps.

Set modest performance goals after measuring the initial demo: for example, target warm recommendation p95 under 300 ms with 10 concurrent local clients, excluding first model load and network outside the local host. This is an engineering target, never a prefilled result. Record request count, warmup, concurrency, catalog size, cache state, hardware, p50/p95, errors, and throughput. If the target is missed, report the measurement and the main bottleneck.

## 11. Verification that proves the system works

Use focused tests that protect correctness and important behavior. Do not generate hundreds of trivial tests to achieve a coverage number. Required evidence includes:

**Data and ML correctness**

- Temporal ordering and a sentinel future interaction that cannot affect earlier features.
- Training-only preprocessing/aggregates and correct target/history separation.
- Stable product-ID mappings and metadata joins, including missing/unknown products.
- Negative sampling that masks known positives/history at the relevant cutoff and handles duplicate in-batch items; acknowledge remaining false negatives.
- Metric functions verified on tiny hand-calculated examples, including missed retrieval positives and multiple relevant items.
- Consistent filtering, unique valid recommendations, cold-start behavior, and reproducible seeded runs within stated tolerances.
- Train/save/load/infer parity and failure on incompatible artifact bundles.

**Backend and job behavior**

- Migrations against PostgreSQL, authentication/session lifecycle, ownership isolation, admin restrictions, and rejected forged user identity.
- CSRF handling, validation failures, pagination limits, and event idempotency.
- Queue success/failure/retry behavior, persisted job status, and preservation of the active model after a failed training run.
- Model promotion/rollback and cache invalidation after model or history changes.
- Real API integration tests using the actual demo model; boundary mocks are acceptable in unit tests, but not as the only recommendation evidence.

**Browser and integration behavior**

- Playwright journey: guest browses catalog, registers/logs in, completes onboarding, favorites/dismisses an item, refreshes, and observes persisted personalized state.
- User cannot open protected admin actions; admin can inspect a real run, start a bounded job, and observe the resulting status.
- Test the UI against the real backend; do not intercept every endpoint with canned responses.
- Inspect screenshots at phone and desktop sizes for overflow, broken images, unreadable charts, and incomplete loading/error states. Fix observed issues.
- Run frontend lint and production build, Python lint/tests, a container smoke test, and the documented startup flow in an isolated test/demo environment without wiping the user's data.

CI should run appropriate deterministic checks with bounded training on synthetic fixtures and disposable services. Full third-party dataset downloads and lengthy research sweeps must be explicit/manual jobs. Capture actual command outcomes; do not mark unexecuted checks as passed.

## 12. Implementation milestones and gates

| Milestone | Deliverable | Evidence needed before moving on |
| --- | --- | --- |
| 0 — Foundation | Repository inspection, dependency choices, environment templates, plan/status, minimal service wiring | Installed/validated environment or an accurately scoped blocker; health endpoint and web shell run where supported |
| 1 — First vertical slice | PostgreSQL migrations, deterministic demo seed, catalog API/UI, popularity recommendations | Browser displays persisted products and real backend recommendations |
| 2 — Personalized product | Sessions, onboarding, favorites, events, profile, personalized history, role controls | User journey persists across refresh; ownership/admin tests pass |
| 3 — Research pipeline and baselines | Data manifests, bounded Amazon importer, temporal splits, item-CF and BPR, metric harness | Leakage/metric tests pass; actual demo experiment records; real-data run if accessible |
| 4 — Advanced ML | Two-tower model, content/OOV behavior, candidate index, chronological ranker training, reranking | Required comparisons execute; artifact reload parity; end-to-end misses counted honestly |
| 5 — ML operations | Worker jobs, MLflow records, workbench, promotion/rollback, caching, monitoring/drift | UI reads real job/experiment data; failed training and rollback scenarios verified |
| 6 — Release candidate | Responsive polish, Docker/CI, browser verification, benchmark and documentation | Clean-start demo, integrated checks, screenshots, actual benchmark/report, requirement audit |

Do not treat a successful early milestone as permission to omit later required components. If an external dependency blocks a milestone, complete its independent work, keep the blocking check open, and continue with other executable milestones. Keep optional extensions separate from required completion.

Optional extensions only after the required system is working: pretrained multilingual product embeddings, a controlled Bangla/English search benchmark, multimodal item features, sequence-aware recommendation, approximate-search scaling, or a real-traffic experiment. Do not add these at the expense of evaluation, integration, or reliability.

## 13. Documentation and portfolio deliverables

Write documentation that reflects the built system, not an aspirational architecture. Include:

- `README.md`: project purpose, truthful status, prerequisites, quickstart, URLs, demo access, operating profiles, commands, screenshots, troubleshooting, and limitations.
- `docs/ARCHITECTURE.md`: a compact service/dataflow diagram, ownership boundaries, online inference flow, offline training flow, and key trade-offs.
- `docs/DATA_CARD.md`: provenance, licenses/terms reference, schema, sampling, assumptions, splits, sensitive fields, and known biases.
- `docs/ML_DESIGN.md`: problem formulation, objectives, feature availability, negative sampling, retrieval/ranking design, cold start, and serving consistency.
- `docs/EVALUATION.md`: protocol, exact definitions, candidate universe, actual comparable results, uncertainty, ablations, failure cases, and conclusions supported by evidence.
- `docs/MODEL_CARD.md`: active model version, intended use, training data, measured performance, limitations, fallback behavior, and conditions for replacement.
- `docs/OPERATIONS.md`: configuration, migration/backup/restore approach, jobs, model promotion/rollback, monitoring, deployment requirements, and recovery procedures.
- `docs/DEMO.md`: a five-minute demonstration walkthrough using the implemented screens and actual results.
- `docs/LEARNING_GUIDE.md`: how to trace a request and a training example through the code; explanations of BPR, two-tower loss, ranking groups, leakage, Recall/NDCG, and latency trade-offs; small exercises for the owner to complete.
- `docs/BUILD_REPORT.md`: acceptance checklist with evidence links, executed commands/results, environment details, remaining limitations, and measured achievements suitable for a portfolio description.

Maintain a concise dependency/source reference list with URLs and dates consulted. Link the final output to key files. Screenshots and benchmark exports must come from actual runs. Resume-style achievement suggestions must use measured quantities and accurately describe a portfolio project rather than commercial production experience.

## 14. Definition of done and honest stopping conditions

The required build is complete only when:

1. A fresh, documented environment can start the demo and reproduce its data/model preparation with the implemented commands.
2. Next.js JavaScript UI, Python API, PostgreSQL, worker, and real recommendation inference are integrated.
3. The shopper journey and protected admin workflow operate with persisted state.
4. Every required model has executable training, serialization, inference, and evaluation, with demo execution evidence.
5. The research importer and temporal evaluation are implemented and tested; a bounded real-data benchmark has run when data access permits.
6. The workbench shows actual runs, job progress, active model version, and observed monitoring values.
7. Authentication, ownership, feature leakage, metric correctness, model compatibility, and promotion/rollback checks have been exercised.
8. Relevant lint, production build, integration, and browser checks pass; visual defects found during inspection are fixed.
9. The report distinguishes demonstrated behavior, implemented but unverified paths, research results, and remaining external blockers.

Classify the outcome accurately as `complete`, `partially complete`, or `blocked`. A synthetic demo does not establish real-world model quality. If research data is inaccessible, label the research benchmark unverified and the overall research deliverable incomplete even when the application demo works. If Docker, browser tooling, package installation, or training cannot run, state exactly what was and was not verified and provide the smallest reproducible next step. Do not replace missing evidence with screenshots of invented results or claims of production readiness.

Your final implementation response should contain: the working features, exact startup commands and URLs, where demo access is documented, key files/artifacts, actual verification outcomes, measured ML findings, and remaining blockers/limitations. Do not dump the entire codebase into chat or finish with a request to begin work you were already instructed to do.

Begin now: inspect the workspace, establish the executable milestone plan, and implement the first vertical slice. Continue through the required milestones with recorded evidence.

---

## Reference starting points

These are documentation references, not instructions that override the project contract. Verify current APIs and package compatibility during implementation.

- OpenAI, long-running Codex work and durable project state: https://developers.openai.com/blog/run-long-horizon-tasks-with-codex
- Next.js installation and App Router setup: https://nextjs.org/docs/app/getting-started/installation
- FastAPI guidance on background work and heavy computation: https://fastapi.tiangolo.com/tutorial/background-tasks/
- Amazon Reviews 2023 source and schema: https://amazon-reviews-2023.github.io/
- Retrieval/ranking and two-tower overview; concepts may be implemented in PyTorch: https://www.tensorflow.org/recommenders/examples/basic_retrieval
- LightGBM ranking API and query groups: https://lightgbm.readthedocs.io/en/stable/pythonapi/lightgbm.LGBMRanker.html
