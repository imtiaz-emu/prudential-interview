"""
URL builder for the picsum provider.

Constructs picsum-compatible image URLs from an image ID and an
``ImageTransform``.  This is the *only* place that knows about
picsum URL conventions; nothing else in the codebase should
construct picsum URLs directly.
"""

from __future__ import annotations

from django.conf import settings

from gallery.domain.transformations import ImageTransform


class PicsumUrlBuilder:
    """Builds picsum image URLs from a transform and image ID.

    The base URL is read from ``settings.PICSUM_BASE_URL`` so it can be
    overridden in tests or swapped for a different provider endpoint.

    picsum URL format::

        {base}/id/{image_id}/{width}/{height}[?grayscale][&blur=N]

    Examples::

        builder = PicsumUrlBuilder()
        builder.image_url(42, ImageTransform('medium'))
        # → 'https://picsum.photos/id/42/400/400'

        builder.image_url(42, ImageTransform('small', grayscale=True, blur=3))
        # → 'https://picsum.photos/id/42/200/200?grayscale&blur=3'
    """

    def __init__(self, base_url: str | None = None) -> None:
        self._base_url = (
            base_url
            or getattr(settings, 'PICSUM_BASE_URL', 'https://picsum.photos')
        ).rstrip('/')

    def image_url(self, image_id: int, transform: ImageTransform) -> str:
        """Return the fully qualified picsum URL for *image_id* + *transform*.

        Args:
            image_id:  Numeric picsum image identifier.
            transform: Canonical transform describing size and filters.

        Returns:
            Absolute URL string ready for use in an ``<img src>`` attribute.
        """
        size = transform.pixel_size()
        url = f"{self._base_url}/id/{image_id}/{size}/{size}"

        query_parts: list[str] = []
        if transform.grayscale:
            query_parts.append('grayscale')
        if transform.blur > 0:
            query_parts.append(f'blur={transform.blur}')

        if query_parts:
            url += '?' + '&'.join(query_parts)

        return url

    def info_url(self, image_id: int) -> str:
        """Return the picsum info endpoint URL for *image_id*."""
        return f"{self._base_url}/id/{image_id}/info"
