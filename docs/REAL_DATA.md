# Real retail catalog and recommendations

The retail configuration uses the official Amazon Reviews 2018 Luxury Beauty
ratings and product metadata published by the dataset authors:
https://cseweb.ucsd.edu/~jmcauley/datasets/amazon_v2/ .
This is historical retail data, not a current merchant inventory feed.

Dataset citation: Jianmo Ni, Jiacheng Li and Julian McAuley (EMNLP 2019),
"Justifying recommendations using distantly-labeled reviews and fine-grained aspects."

The source has 574,628 rating rows. After removing 36,972 duplicate
user/product/timestamp rows, training-period cohort selection retains 52,249
reviews by 9,947 pseudonymous reviewers and 6,692 products. Source metadata
provides photographs for 5,886 products. Missing or unreachable photos show an
honest unavailable state, never a generated substitute. Prices retain USD and
the source's historical meaning; neither live prices nor merchant stock are claimed.

The importer fixes 70%/85% chronological boundaries from the complete accepted
source first. It selects reviewers with at least three distinct positive products
before the first boundary, then retains their complete histories. It never uses
validation/test activity to choose the cohort. Results represent established
reviewers, not all shoppers. Source metadata is an archived snapshot with uncertain
historical availability; that limitation remains in content-based experiments.

## Training and live personalization

Popularity, item-based collaborative filtering and a two-tower model are evaluated
on the same chronological holdouts. Deployment selection uses validation results
among completed personalized models; test outcomes do not choose the winner.
A separate serving refit uses all accepted source history. Metrics remain those
measured before refitting, not measurements made on the serving model's own history.

AtlasRec accounts are separate from historical reviewers. Views and clicks change
online recommendation context. Saves, ratings and dismissals persist per account,
and dismissed products are excluded. Administrator training jobs pin an immutable,
checksum-verified dataset and may add the latest explicit feedback from signed-in
non-admin accounts. Impressions/views are not fabricated as rating labels.
Application feedback is included in serving refits while offline evaluation remains
restricted to historical source reviews. A completed job creates a candidate;
promotion validates dataset/profile/catalog compatibility before changing serving.

No public-review identities become login accounts. Automated browser QA accounts
and their feedback are removed before the live worker verification. Historical
review counts and AtlasRec account activity remain separate in the UI.

## Reproduce on Windows

Run from the project folder after the documented Python/Node/Docker setup:

```powershell
python scripts/fetch_research.py --dataset luxury-beauty-2018 --max-total-mb 40 --timeout-seconds 600
.venv\Scripts\python.exe -m atlasrec_ml.cli train --config configs/retail.yaml
powershell -File scripts/activate-retail.ps1
```

If the current HTTPS dataset host is unavailable, the downloader supports the
author's public legacy archive with `--legacy-mirror`. The successful retrieval
used that HTTP archive; actual URLs, byte counts and SHA256 hashes are recorded in
`data/research/luxury-beauty-2018/downloads.json`. A checksum detects later changes
to the retrieved copy; it is not a publisher signature. Downloads have explicit
byte/time limits, validated resume ranges and atomic completion. Raw source files
are excluded from source distribution and images.

The activation script preserves the previous configured profile until catalog
installation succeeds, then sets `ATLASREC_PROFILE=research` and the installed
`RESEARCH_DATASET_ID`. Existing demo data and accounts remain intact. A failed
startup restores the previous environment configuration. On a clean install,
initialize the local administrator using the documented bootstrap first.

Review source conditions for your intended use. The public dataset page supplies
research citation instructions rather than a clear blanket commercial license.
External deployment, a connected live merchant feed, purchase/checkout processing,
and demonstrated production customer traffic are separate from this local build.

## Evidence

- `evidence/retail-benchmark.json`: real data manifest, split, measured model results.
- `evidence/retail-install.json`: selected model and installed catalog.
- `evidence/retail-browser.json`: actual desktop/phone storefront journeys.
- `evidence/retail-live-checks.json`: changing predictions and actual worker completion.
- `evidence/retail-checks.json`: final verification and Desktop synchronization.
