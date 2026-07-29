"""
Gallery service: orchestrates page assembly from cache and provider.

This is the single entry point for the gallery view.  It:

1. Converts validated ``GalleryParams`` into an ``ImageTransform``.
2. Computes the deterministic image-ID range for the requested page.
3. Fetches each item via ``CacheService`` (cache-first, provider on miss).
4. Handles partial failures gracefully — unavailable images are skipped
   and a human-readable error is recorded in ``GalleryPage.errors``.
5. Returns a ``GalleryPage`` with all data the template needs.

No HTTP logic lives here.  Swapping the provider or cache implementation
requires no changes to this service.
"""

from __future__ import annotations

import logging

from django.conf import settings

from gallery.cache.cache_service import CacheService
from gallery.domain.transformations import ImageTransform
from gallery.domain.validation import DetailParams, GalleryParams
from gallery.errors import NoFallbackError
from gallery.services.image_provider import PicsumImageProvider
from gallery.types import GalleryPage, ImageItem

logger = logging.getLogger(__name__)


class GalleryService:
    """Assembles a ``GalleryPage`` payload for a single gallery request.

    Args:
        provider:      ``ImageProvider`` implementation.  Defaults to
                       ``PicsumImageProvider``.
        cache_service: ``CacheService`` instance.  Defaults to a new
                       ``CacheService``.
    """

    def __init__(
        self,
        provider=None,
        cache_service: CacheService | None = None,
    ) -> None:
        self._provider = provider or PicsumImageProvider()
        self._cache = cache_service or CacheService()
        self._max_image_id: int = getattr(settings, 'PICSUM_MAX_IMAGE_ID', 1000)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_page(self, params: GalleryParams) -> GalleryPage:
        """Return a complete ``GalleryPage`` for *params*.

        Images that cannot be fetched (upstream down, no fallback cached)
        are omitted from ``GalleryPage.items`` and recorded in
        ``GalleryPage.errors`` so the view can surface a partial-failure
        message without crashing.

        Args:
            params: Validated, normalised gallery query parameters.

        Returns:
            ``GalleryPage`` with items, pagination metadata, and any errors.
        """
        transform = ImageTransform.from_gallery_params(params)
        image_ids = self._compute_image_ids(params.page, params.per_page)

        items: list[ImageItem] = []
        errors: list[str] = []

        for image_id in image_ids:
            try:
                item = self._cache.get_or_fetch(
                    image_id,
                    transform,
                    self._make_fetch_fn(image_id, transform),
                )
                items.append(item)
            except NoFallbackError:
                errors.append(f"Image {image_id} could not be loaded.")
                logger.error(
                    "gallery.image_unavailable",
                    extra={"image_id": image_id, "page": params.page},
                )

        last_id = image_ids[-1] if image_ids else 0

        return GalleryPage(
            items=items,
            page=params.page,
            per_page=params.per_page,
            has_previous=params.page > 1,
            has_next=last_id < self._max_image_id,
            params=params,
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_image_ids(self, page: int, per_page: int) -> list[int]:
        """Return the ordered image IDs for *page*.

        Page 1 → IDs 1 … per_page
        Page 2 → IDs per_page+1 … 2*per_page
        …

        The range is clamped to ``PICSUM_MAX_IMAGE_ID`` so we never
        request IDs that don't exist.

        Examples::

            _compute_image_ids(1, 10)  → [1, 2, …, 10]
            _compute_image_ids(2, 10)  → [11, 12, …, 20]
            _compute_image_ids(1, 5)   → [1, 2, 3, 4, 5]
        """
        start = (page - 1) * per_page + 1
        end = min(page * per_page, self._max_image_id)
        if start > self._max_image_id:
            return []
        return list(range(start, end + 1))

    def _make_fetch_fn(self, image_id: int, transform: ImageTransform):
        """Return a zero-argument callable that fetches *image_id*.

        Using a factory avoids the late-binding closure bug that would
        occur if a lambda referenced the loop variable directly.
        """
        def _fetch():
            return self._provider.fetch_image(image_id, transform)
        return _fetch

    def get_detail(self, params: DetailParams) -> ImageItem:
        """Return a single ``ImageItem`` for the detail view.

        Uses the same cache-first strategy as the gallery page so repeated
        detail requests do not trigger duplicate upstream calls.

        Args:
            params: Validated detail parameters (image_id, size, grayscale, blur).

        Returns:
            ``ImageItem`` ready for template rendering.

        Raises:
            ``NoFallbackError``: Upstream failed and nothing is cached.
        """
        transform = ImageTransform.from_detail_params(params)
        return self._cache.get_or_fetch(
            params.image_id,
            transform,
            self._make_fetch_fn(params.image_id, transform),
        )
