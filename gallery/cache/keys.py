"""
Cache key construction for the gallery application.

Keys must be stable (same inputs → same key always) and unique
(different inputs → different key).  All output-affecting inputs
are included so cached values are never incorrectly reused.

Key format
----------
Primary:   gallery:img:{image_id}:{transform_segment}
Fallback:  gallery:img:fallback:{image_id}:{transform_segment}

The transform segment comes from ``ImageTransform.cache_key_segment()``
which encodes size, grayscale, and blur in canonical order, for example::

    size:medium,grayscale:1,blur:5

Note: ``PICSUM_BASE_URL`` is not included because changing the provider
base URL is an operational change that restarts the process (clearing the
in-process cache), so stale cross-provider hits cannot occur.
"""

from __future__ import annotations

from gallery.domain.transformations import ImageTransform

# Namespace prefix — makes gallery keys easy to identify in logs.
_NS = "gallery:img"


def make_image_key(image_id: int, transform: ImageTransform) -> str:
    """Return the primary cache key for *image_id* + *transform*.

    Examples::

        make_image_key(42, ImageTransform('medium'))
        # → 'gallery:img:42:size:medium'

        make_image_key(1, ImageTransform('small', grayscale=True, blur=3))
        # → 'gallery:img:1:size:small,grayscale:1,blur:3'
    """
    return f"{_NS}:{image_id}:{transform.cache_key_segment()}"


def make_fallback_key(image_id: int, transform: ImageTransform) -> str:
    """Return the long-lived fallback key for *image_id* + *transform*.

    Stored without expiry so it survives past the primary TTL and can be
    served when upstream is unavailable.
    """
    return f"{_NS}:fallback:{image_id}:{transform.cache_key_segment()}"
