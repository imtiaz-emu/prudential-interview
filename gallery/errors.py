"""
Internal error hierarchy for the gallery application.

All upstream and operational failures are mapped to one of these typed
exceptions before leaving the service layer.  Views and the cache service
catch these — raw ``requests`` exceptions must never propagate to templates.
"""

from __future__ import annotations


class GalleryError(Exception):
    """Base class for all gallery application errors."""


class UpstreamError(GalleryError):
    """Upstream provider returned a non-success HTTP response.

    Attributes:
        status_code: HTTP status code from the upstream response, if available.
        image_id:    Identifier of the image that triggered the error.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        image_id: int | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.image_id = image_id


class UpstreamTimeoutError(UpstreamError):
    """Upstream request did not complete within the configured timeout."""


class UpstreamUnavailableError(UpstreamError):
    """Upstream unreachable or failing after all retry attempts are exhausted."""


class NoFallbackError(GalleryError):
    """A cached fallback was needed but none was available.

    Attributes:
        image_id: Identifier of the image with no available fallback.
    """

    def __init__(self, message: str, *, image_id: int | None = None) -> None:
        super().__init__(message)
        self.image_id = image_id
