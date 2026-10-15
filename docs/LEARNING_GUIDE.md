# Trace and learn

Trace a shopper request from apps/web/lib/api.js, through app/api/[...path]/route.js,
into atlasrec_api/main.py recommendations, allowed_history, lifecycle.active_bundle,
and atlasrec_ml/models.py recommend. Compare model/history cache keys before and after
a favorite; follow the persisted request to its visible impression event.

Trace a training example in chronological_examples: history is captured before target
insertion. Inspect valid_negatives and contrastive_mask. Add a sentinel future event
and run test_temporal_sentinel_and_target_separation; earlier features must not change.
Read the BPR/contrastive objectives in ML_DESIGN and locate their actual torch losses.

Trace one ranker query group: earlier retrieval fit, later unseen positives, candidate
features and binary labels. Count groups excluded for no relevance variation. Explain
why injecting positives into evaluation would hide candidate misses.

Hand-calculate Recall/NDCG/MRR for [x,a,b] against {a,b,c}; compare test_hand_metrics.
Recall counts all relevant items, NDCG discounts positions, MRR uses the first hit.
Compare retrieval recall at 50 with end-to-end recall at 10; candidate misses stay misses.

Exercises: lower history density and report exclusion changes; vary shrinkage on
validation only; compare content and ID-only towers; inspect paired bootstrap intervals;
toggle diversity without changing candidates; measure warm HTTP latency under 10 clients.
Discuss snapshot metadata uncertainty, sparse-user selection bias, CPU index cost,
and why synthetic quality/observed clicks do not establish causal commercial lift.
