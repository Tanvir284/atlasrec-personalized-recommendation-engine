# Data card

Current installed catalog (2026-10-06): Amazon Reviews 2018 Luxury Beauty,
dataset `079976012a366152`. The bounded full ratings download and source product
metadata produce a training-period-selected cohort of 52,249 reviews, 9,947
pseudonymous reviewers and 6,692 products; 5,886 have source photographs.
Details, exact checksums, provenance and limitations are in REAL_DATA.md and
evidence/retail-source-downloads.json. This is a separate additional source;
the earlier Amazon Reviews 2023 Digital Music configuration remains reproducible.

Historical reviewers are not current app customers. New app activity remains
separate, server-timestamped and opt-in to administrator-triggered serving refits.
The source metadata omits photos for 806 selected products; the UI shows a
missing-photo state and excludes such departments from homepage merchandising.

## Earlier data profiles

Demo: seed 42, 200 generated products, 100 pseudonymous synthetic users, 3,000
chronologically spaced review-like events. Category affinities, overlap, repeated
items, popularity skew and low ratings produce sparse preference patterns.
Images are original local SVG drawings. USD values are explicitly generated examples.
Synthetic traffic and model results retain the demo namespace.

Research source: McAuley Lab Amazon Reviews 2023:
https://amazon-reviews-2023.github.io/ (consulted 2026-10-05).
Digital Music is a comparatively small category with content metadata: approximately
130.4K ratings, 101K users, 70.5K items according to the official category table.
This is sparse; repeated-user evaluation coverage must be measured, not assumed.

Join metadata by parent_asin, never variant asin. Normalize millisecond timestamps,
ratings and IDs; pseudonymize reviewer IDs and retain no review text or login identity.
Ignore crawl-time average_rating/rating_number. Titles/descriptions are snapshot content
with uncertain historical availability. Price is USD at crawl time; missing price stays null.

The sampler hashes users with a seeded fraction while scanning a bounded file prefix.
A scan/interaction cap may truncate a selected user's later rows, and file ordering can
bias this population. There is no full-dataset future activity filter. Report scanned,
rejected, duplicates, missing metadata, checksums, parser version and chronological bounds.
First-observed interaction is an item availability proxy, not launch date evidence.

Use scripts/fetch_research.py only after declared byte sizes pass the configured total
cap. It has a wall-clock limit and writes a retrieval manifest. Local JSONL(.gz) files
are supported. Missing research files stop the research profile; no demo substitution.

Review ratings >=4 represent positive preference, not complete purchases or exposures.
Unobserved products are not confirmed dislikes. Selection and popularity bias limit
generalization. Do not calculate CTR/business lift from these records. Review identities
remain separate from application users; new app users use their own history.

The source home page does not provide a clear dataset license grant. The manifest
retains the official source/terms reference; confirm applicable source conditions for
your use. No full source files, reviews or credentials are shipped in images/source copies.
