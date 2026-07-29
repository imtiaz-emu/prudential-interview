"""
Cache service: read-through wrapper with stale fallback path.

Strategy
--------
1. **Primary hit** — return immediately, log ``cache.hit``.
2. **Primary miss** — call *fetch_fn* (the upstream provider):
   - **Success** — write to primary (TTL from settings) and fallback
     (no expiry), return item, log ``cache.miss``.
   - **Upstream failure** — read fallback key (no-TTL copy written on
     the last successful fetch):
     - **Fallback hit** — return stale item, log ``cache.fallback_hit``.
     - **Fallback miss** — raise ``NoFallbackError``, log
       ``cache.no_fallback``.

Cache invalidation philosophy
------------------------------
This application uses Django's ``LocMemCache`` (in-process, no shared
state).  Cache entries expire after ``CACHE_TTL`` seconds (default 300).
The cache is fully invalidated on process restart.  There is no active
invalidation mechanism because image URLs are deterministic and the
upstream data does not change between process lifetimes.  The fallback
key is stored without a TTL so it survives primary expiry and guards
against transient upstream outages.
"""

from __future__ import annotations

import logging
from typing import Callable

from django.core.cache import cache

from gallery.cache.keys import make_fallback_key, make_image_key
from gallery.domain.transformations import ImageTransform
from gallery.errors import GalleryError, NoFallbackError, UpstreamError
from gallery.logging.events import (
    log_cache_fallback_hit,
    log_cache_hit,
    log_cache_miss,
    log_cache_no_fallback,
    log_cache_stored,
)
from gallery.types import ImageItem

logger = logging.getLogger(__name__)


class CacheService:
    """Read-through cache with stale fallback for upstream failures.

    All cache interactions go through ``get_or_fetch`` — nothing else in
    the application reads or writes the cache directly.
    """

    def get_or_fetch(
        self,
        image_id: int,
        transform: ImageTransform,
        fetch_fn: Callable[[], ImageItem],
    ) -> ImageItem:
        """Return a cached ``ImageItem`` or fetch it from upstream.

        Args:
            image_id:  Numeric image identifier.
            transform: Active transform; included in the cache key.
            fetch_fn:  Zero-argument callable that fetches the item from
                       the upstream provider.  Called only on cache miss.

        Returns:
            ``ImageItem`` — either from cache or freshly fetched.

        Raises:
            ``NoFallbackError``: Upstream failed and no fallback is cached.
        """
        primary_key = make_image_key(image_id, transform)

        # 1. Primary cache hit
        cached: ImageItem | None = cache.get(primary_key)
        if cached is not None:
            log_cache_hit(logger, primary_key, image_id)
            return cached

        log_cache_miss(logger, primary_key, image_id)

        # 2. Cache miss — call upstream
        try:
            item = fetch_fn()
        except UpstreamError as exc:
            return self._serve_fallback(image_id, transform, primary_key, exc)

        # 3. Success — populate primary (with TTL) and fallback (no TTL)
        fallback_key = make_fallback_key(image_id, transform)
        cache.set(primary_key, item)          # uses default CACHE_TTL from settings
        cache.set(fallback_key, item, timeout=None)  # persists for process lifetime
        log_cache_stored(logger, primary_key, image_id)
        return item

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _serve_fallback(
        self,
        image_id: int,
        transform: ImageTransform,
        primary_key: str,
        upstream_exc: UpstreamError,
    ) -> ImageItem:
        """Attempt to serve a stale fallback after an upstream failure.

        Raises:
            ``NoFallbackError``: No stale fallback is available.
        """
        fallback_key = make_fallback_key(image_id, transform)
        fallback: ImageItem | None = cache.get(fallback_key)

        if fallback is not None:
            log_cache_fallback_hit(logger, fallback_key, image_id, str(upstream_exc))
            return fallback

        log_cache_no_fallback(logger, primary_key, image_id)
        raise NoFallbackError(
            f"No cached fallback available for image {image_id}.",
            image_id=image_id,
        ) from upstream_exc
