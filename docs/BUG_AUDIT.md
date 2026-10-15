# Bug audit - 2026-10-05

This audit covers the local application, feedback and cache logic, sessions, model
lifecycle, and small or malformed ML inputs. It does not claim that every possible
bug has been eliminated.

Nine new regression tests failed before their corresponding fixes. The final
Python suite has 29 passing cases, including ten added audit cases. Both Python
and frontend lint pass. Production and browser verification are recorded below.

| Problem | Corrected behavior |
|---|---|
| Old low ratings permanently excluded an item; later ratings on the same request were discarded | The latest explicit feedback determines the signal. Ratings 1-2 exclude, 3 clears the explicit signal, and 4-5 supply positive history. Exploring again does not undo a dismissal. Revised ratings persist even on one served request. |
| Duplicate saves raced into errors; concurrent updates could lose history revisions | Favorite creation uses a database upsert. Only a new save creates a favorite event and advances the revision. Revisions increment atomically in the database. |
| Event IDs and served requests accepted inconsistent attribution | Unknown supplied request IDs and unbound positions are rejected. Reusing an event ID with a changed position, surface, timestamp, rating, or request conflicts. Exposure retries remain idempotent. |
| A lost CSRF cookie left a valid session unable to mutate | The CSRF endpoint repairs the session protection token without revoking the session. The client reads the current cookie, including changes from another tab, and retries only explicit CSRF rejections once. |
| Damaged or stale cache entries produced errors, missing items, or inaccurate request records | Cache entries have a profile-aware namespace and validated structure, availability, exclusions and cardinality. Invalid entries are rebuilt; logged served IDs exactly match the response. Fallback reasons survive valid cache hits. |
| Inference exceptions bypassed the intended fallback | A failed model call supplies valid catalog/category/popularity fallback and records the failure. Transient model failures are not cached. Database failure still returns a service error. |
| Product-title and arrow clicks were not tracked; direct views did not influence picks | All card product links track clicks. Successful detail loads track views, which advance history. Missing product pages do not emit views. Failed visible impressions get bounded retries. |
| Empty trimmed names and malformed email addresses were accepted | Registration validates normalized names and supported email syntax. A concurrent duplicate email receives a conflict response. |
| Literal backslashes broke search; invalid price ranges silently returned no results | Search escapes backslashes, percent signs and underscores. Reversed ranges and nonfinite limits are rejected. Category counts match the available catalog. |
| Promoting the active version created misleading rollback history; rollback could select another profile | Promotion of the active version is idempotent. Audit entries include the profile; registry history and rollback targets are constrained to valid versions in that profile. |
| Training crashed with stop-word-only or one-term product text | The text pipeline supports a fallback vocabulary and a single feature without requiring SVD. Unknown product transforms use the same fitted pipeline. |
| Non-object JSON rows crashed ingestion; metadata strings and nonfinite prices were mishandled | Invalid review/metadata rows are counted. String descriptions remain intact. Invalid or negative prices are represented as unavailable. The parser version changes to identify the corrected behavior. |
| Different synthetic user populations shared a dataset ID | The generator identity includes user count and a new parser version. Invalid generator sizes raise an explicit validation error. |

The database migration to revision 0003 preserves existing events and replaces the
broad event uniqueness constraint with an index for views, impressions and clicks.
Event IDs remain unique for all interaction types. Earlier model artifacts and
benchmark reports retain the versions and measurements recorded when they ran.

## Verification

- Before fixes: seven audit cases failed; two additional lifecycle/import cases also failed.
- After fixes: full Python suite **29 passed** in 74.49 seconds.
- Python Ruff and frontend ESLint: passed.
- Production image build, migration to 0003, healthy Compose startup and bootstrap reuse: passed.
- Live PostgreSQL/Redis audit: eight concurrent saves, three distinct favorites/events/revisions, three revised ratings on one served request, view invalidation, session-preserving CSRF recovery and a verified cache hit passed.
- Desktop and phone browser checks: **6 passed**, zero failures or flaky cases, in 99.83 seconds. Both layouts include actual worker completion. Tracking checks cover title clicks, loaded views, missing products, a failed impression retry, missing CSRF cookies and same-account session rotation in another tab.
- Machine-readable evidence: evidence/bug-audit-checks.json, evidence/bug-audit-live.json and evidence/bug-audit-browser.json.
- Exact Desktop source copy: SHA256 verified for all 140 source/evidence files.

The earlier HTTP p95 measurement of 4384.05ms still misses the 300ms target.
This audit is a correctness pass, with no new latency or real-world model-quality
claim. GitHub CI, external deployment, backup/restore rehearsal and hard-kill
recovery remain unverified.
