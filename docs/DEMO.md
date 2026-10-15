# Five-minute walkthrough

After Docker works:
python scripts/manage.py demo
Open http://localhost:3000. Workbench: http://localhost:3000/admin.

Local demo administrator:
email admin@atlasrec.local
password AtlasDemo!2026
These are public local-demo credentials, rejected for production use.

1. Browse Discover and Catalog; search, category, USD price, sorting and pagination.
2. Register your own account (password >=10 characters); pick interests in Profile.
3. Save a product, refresh Saved, open details, choose Not for me, inspect For you.
4. Explain why a new user gets popularity/category picks and how history changes results.
5. Sign out, sign in as the local demo admin. Inspect datasets, runs, active model.
6. Queue a six-epoch CPU job; watch actual progress/completion. Promote only a validated
   completed candidate, then demonstrate rollback and the audit trail.
7. Show observed monitoring values; insufficient drift data is an empty state.

For comparative evidence run python scripts/manage.py benchmark --config configs/benchmark.yaml.
Its offline runs do not automatically activate their test-best model. Use validation
and explicit promotion. Demo metrics remain labeled synthetic.

Screenshots must come from the real browser integration suite; generated artwork is
product illustration only. The isolated SQLite browser fixture is documented separately
from the required PostgreSQL/Redis/Celery container journey.
