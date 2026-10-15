"""Process-local observability shared by the middleware and routers."""
import logging
from collections import Counter

log = logging.getLogger("atlasrec")

# Error counters since process start; surfaced on the admin monitoring page.
observed_errors = Counter()
