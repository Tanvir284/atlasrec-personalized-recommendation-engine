# ML design

Task: retrieve unseen, train-cutoff-eligible items a user positively rates in a future
window. Global chronological boundaries, train-only preprocessing, immutable IDs,
and target-before-history separation are implemented in data.py/features.py.

Popularity uses train positive counts (log1p when scoring). Cold history receives
popularity plus category preference boosts. Item-CF uses binary user-item cosine,
cooccurrence shrinkage c/(c+10), diagonal removal and strongest 50 neighbors per item.
A memory estimate rejects too-large item-CF configurations.

BPR learns user/item embeddings with objective
-L mean log sigmoid(u dot (i_positive-i_negative)) + lambda L2.
Negatives come from items first seen before the example time, excluding current target
and past known positives. Later positives can still be false negatives. Adam, seeded
sampling and validation NDCG early stopping select the checkpoint. Application users
are never assigned a research reviewer's user embedding; unknown-user BPR uses item
history aggregation.

Two towers project item IDs plus train-fitted TF-IDF/SVD content, and encode mean past
item vectors through a user MLP. The contrastive loss is
-log exp(dot(q,v_positive)/tau) / sum_allowed exp(dot(q,v)/tau), tau=0.15.
Duplicate in-batch target IDs, known past positives and future-only candidate negatives
are masked. Histories exclude the current target event. Empty-history examples have
no supervised tower history and are skipped. ID-only tower is a controlled ablation.
Unknown product IDs can be projected from content; distinct texts do not collapse to
one shared OOV vector. Snapshot historical availability is explicitly uncertain.

LightGBM LambdaMART trains query groups in earlier chronological windows. Each window
rebuilds retrieval/features/counts on earlier history. Features are retrieval score,
history/content similarity, log train popularity and past category affinity.
No positives are injected. Groups without label variation are counted and excluded
from training; end-to-end evaluation preserves all eligible queries. Failing training
does not change the active serving model.

FAISS IndexFlatIP is an exact index. Bundles also retain vectors for a NumPy reference.
No approximate-search claim is made. index/weight dimensions and exact vectors are
verified on load. Python byte serialization avoids FAISS's Windows Unicode path issue.
Bundle joblib files are trusted locally trained artifacts; arbitrary uploaded pickle
is not supported.

Diversity penalizes previously selected category counts by a configurable 0.1 score
offset. These scores are not purchase probabilities. Cache version/history keys and
one-process atomic promotion protect model/index consistency. Cross-replica promotion
consistency is not implemented. No production experience or commercial lift is claimed.
