# AtlasRec execution plan
The pasted PROJECT_SPEC is authoritative. CPU-first, local-only.

## Real retail follow-up (in progress)

1. Import official real product metadata/photos and historical customer ratings with source checksums.
2. Build a train-period-only cohort and evaluate chronological holdouts; refit serving models on observed history.
3. Install the real catalog, activate a compatible trained model, and enable queued retraining from actual app feedback.
4. Replace synthetic storefront artwork with source product photography and honest price/source labels.
5. Verify predictions, shopper actions, actual worker completion, desktop/phone layout, and sync the Desktop project.

| Gate | Acceptance | Result |
|---|---|---|
| 0 Foundation | Locked dependencies, environment, health and web | Passed; WSL repair and real Docker startup verified |
| 1 Vertical slice | PostgreSQL migrations, seed, trained popularity | Passed against fresh project volumes; bootstrap reuse verified |
| 2 Product | Sessions, CSRF, interests, favorites, event ownership | API and production desktop/phone journeys passed |
| 3 Research | Provenance importer, temporal evaluation, CF/BPR | Real bounded data and three seeds executed; sparse-sample limits reported |
| 4 Advanced | Towers/content, FAISS, chronological ranker, ablations | Six models, reload checks and corrected cold-content experiment executed |
| 5 Operations | Worker, experiments, registry, monitoring | Real failure/retry and promotion/rollback passed |
| 6 Release | Browser, build, benchmark, audit, Desktop copy | Local functional checks and bug audit passed; HTTP performance gate remains open |

CI and external deployment are provided/documented paths with no execution claim.
Performance measurements and research limitations are retained, not substituted with
invented successes. See STATUS.md and docs/BUILD_REPORT.md.
