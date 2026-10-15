# Operations

The current local installation runs the real retail research profile. Restart it
with `python scripts/manage.py start`; this preserves its catalog/model profile.
Use REAL_DATA.md to reproduce import, train and activation. The synthetic demo
launcher now refuses a configured research installation instead of attempting to
seed it. The real-data activation script validates compatible copied bundles,
sets copied dataset ownership for the worker, and changes the profile only after
installation succeeds. Current active version: `item_cf-7f011e780482`.

Queued research jobs pin an immutable dataset path/checksum within DATA_DIR.
Explicit signed-in feedback can enter a separate snapshot and serving refit.
Review the resulting candidate in the workbench before promotion. Clearing live
history does not rewrite previously saved immutable model artifacts; retrain and
retire obsolete snapshots/bundles according to an actual deployment's retention policy.

The reused administrator and database credentials remain local development
credentials. This local data upgrade is not an external production deployment.

Start from README. Docker Compose is the supported demo installation. WSL repair,
PostgreSQL migrations and actual application startup were verified on this Windows host.
python scripts/manage.py doctor reports actual tool/daemon/port failures.
python scripts/manage.py demo copies .env.example if absent, starts healthy services,
migrates PostgreSQL, seeds only missing demo records, reuses a compatible active bundle,
or trains/registers/promotes the initial demo popularity model.

Demo accounts exist only under the explicit demo profile. Production settings reject
demo profile, default DB password, documented demo admin identity and insecure cookies. Set HTTPS allowed origins and
COOKIE_SECURE=true. Argon2 passwords, opaque hashed expiring sessions, session rotation,
revocation, Origin validation and session-bound CSRF operate in FastAPI.

Only web localhost:3000 is published. API_INTERNAL_URL=http://api:8000 is container
internal; local native API defaults to localhost:8000. Browser cookies reach Python
through the transport proxy. No NEXT_PUBLIC API token/URL is necessary. SQL/Redis/MLflow
should stay private behind deployment networking and a reverse proxy with TLS/body limits.

Training concurrency defaults to one; job queue uses Redis/Celery. Inspect /admin/jobs,
repair the cause before retry, then inspect /admin/experiments and /admin/models. Promotion
loads/validates before activating; rollback has an audit trail. Hard-killed worker jobs
can remain running: the API marks them retryable after the configured training cap plus
180 seconds without a heartbeat. Retry is explicit; exactly-once crash recovery is not claimed.

Database backup: private pg_dump into encrypted storage; restore to a disposable
database first and run migrations/ownership/model checks. Back up artifact/data volumes
with matching DB model references. Model bundles are immutable after creation.
Test restoration before external deployment; backups/restores are not yet exercised.

stop preserves volumes. reset requires --yes-reset-demo and an explicit demo .env profile,
and targets only the atlasrec Compose project. Do not run reset against owner data.
Base images and services are pinned by digest. Clean-start integration, bootstrap
reuse, real worker failure/retry and promotion/rollback passed. CI configuration is provided; it has not been executed on GitHub. Nothing was published.

Monitoring uses last 1000 recommendation requests, process-local error counters,
fallback/cache rates, price missingness and nonoverlapping earliest/latest 500 event
windows. Category total variation threshold defaults to 0.2 and is configurable. Numeric sample
counts and minimum sample size are explicit. Numeric drift is position mean shift
scaled by max(reference standard deviation,1). Drift is diagnostic, never auto-promotion.


Trusted offline reports can be registered without promotion using scripts/register_report.py.
Copy each referenced immutable bundle into the installation artifact root first, then
provide the real report path. The script validates profile and bundle compatibility and
preserves original run/source provenance. Never load untrusted joblib artifacts.
Native MLflow runs keep their native tracking store; importing an application summary
is not a migration of that tracking database. Avoid replacing a live MLflow SQLite store.

Browser acceptance uses the actual Compose stack. Run npm ci, install the pinned
Playwright Chromium browser, and run the test suite with EXPECT_QUEUE=1. Local screenshots
wait for persisted data; metric chart entrance animations are disabled for stable resizing.
A separate capture command is node scripts/capture_experiments.js.

Performance command: python scripts/http_benchmark.py uses published IPv4 to avoid the
observed Windows localhost IPv6 connection delay. It does not change the application URL
or configured authentication Origin (http://localhost:3000). Verify its request IDs and
cache hits with scripts/verify_http_benchmark.py inside the API container, using --output
to write into /app/docs/evidence rather than a root-owned copied input file.
