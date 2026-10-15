# AtlasRec storefront redesign

Updated 2026-10-05, Asia/Dhaka.

The storefront now uses an Amazon-inspired retail layout with AtlasRec branding:
a sticky navy shopping header, prominent search, orange search controls, yellow
save buttons, department navigation, white product panels and compact price typography.

## Shopping experience

- Home: a product-led hero, four department panels with working product links,
  horizontal recommendation shelves, five department tiles and an interests banner.
- Search: submit a product name and department from the header on any page.
- Catalog: department counts, sidebar filters, minimum/maximum prices, active filter
  chips, sorting and pagination. Filters collapse behind a button on phones.
- Product detail: a larger image gallery, image zoom, description and status, a
  separate save panel, personal star ratings and related products.
- Account: saved-item counts, login return paths, persisted favorites and interests.
- Navigation: a keyboard-accessible department drawer, Escape to close, a skip
  link, visible focus states and a functional back-to-top control.
- Artwork: 20 original SVG illustrations represent the actual demo product types,
  replacing the repeated generic department pictures. Research images remain intact.
- The protected ML workbench keeps its existing routes, data and controls with
  typography, tables and panels matched to the new storefront.

Product prices, counts, availability, saved state and recommendations come from
the existing API. Stars represent the signed-in shopper's personal rating.
The app remains a discovery and recommendation platform; it has no checkout or
shipping system.

## Correctness fixes found during the redesign

The personal rating lookup now filters history by product and rating before its
100-row limit. A rating remains visible after many newer browsing events and
cannot leak between shoppers. The UI derives the rating from that product's
persisted query, so navigating to another product does not carry a previous rating.

Screen-reader price text is positioned inside each price element. This prevents
hidden text in offscreen shelf cards from widening the page on phones while
keeping the complete price available to assistive technology. Catalog price inputs
also sit below their fieldset heading rather than being squeezed beside a float.

The response client now rejects incomplete JSON instead of treating it as an
empty successful response. The transport proxy finishes reading the upstream body
inside its timeout/error boundary before forwarding a successful status. A failed
read shows a retryable error rather than crashing the experiment table.

A delayed home-page script reproduced a hydration mismatch when shared category
data arrived before a nested Suspense boundary hydrated. The unnecessary home
boundary was removed. A browser regression now delays that script and checks for
runtime errors and the fully rendered storefront.

The experiment list now omits per-user rows from its three metric sections by
default. Aggregate metrics, uncertainty intervals, provenance and stored records
remain intact. Administrators can request the detailed rows with
`/api/v1/admin/experiments?include_user_rows=true`. The earlier default response
contained roughly 3 MB of detailed rows and could hit the transport timeout.
An API regression checks response size, preserved metrics, full-detail access,
record preservation and admin authorization.

Product tracking retries a temporary service failure or lost response once,
reusing the original event ID. This preserves idempotency when the first request
committed but its response was delayed. A browser regression injects a temporary
view failure and checks that both attempts use the same ID and the view succeeds.

## Verification

Production web build and healthy Compose startup passed. Desktop and phone browser checks: **18 passed**, zero failures or flaky cases, in 179.86 seconds. The controlled delayed-script and incomplete-response cases both passed on each screen size.
Targeted API and feedback tests: **7 passed** in 110.74 seconds, including a
110-event history regression, cross-account isolation and compact experiment summaries. Python and frontend
lint passed.

Final evidence:

- evidence/storefront-checks.json: verification summary and source hashes.
- evidence/storefront-browser.json: actual desktop and phone browser journeys.
- evidence/storefront-visual.json: viewport widths, image checks and runtime errors.
- evidence/storefront-home-desktop-viewport.png: desktop home preview.
- evidence/storefront-home-phone-viewport.png: phone home preview.
- evidence/storefront-catalog-desktop.png and storefront-catalog-phone.png.
- evidence/storefront-product-desktop.png and storefront-product-phone.png.

The initial browser pass (11 passed, one failed) and the initial visual check are retained as storefront-initial-browser.json and storefront-initial-visual.json. Those failures led to the transport and hydration fixes above.

The previous correctness audit and performance measurements remain documented in
BUG_AUDIT.md and BUILD_REPORT.md. This redesign does not make a new latency or
real-world model-quality claim.

Exact requested Desktop source/evidence copy: SHA256 verified for all 190 files.
