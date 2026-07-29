"""
Provider boundary: abstract contract + picsum implementation.

The ``ImageProvider`` Protocol defines the interface that the rest of the
application depends on.  ``PicsumImageProvider`` is the concrete adapter
for picsum.photos, with built-in timeout enforcement, bounded exponential
backoff retry, and typed error classification.

Swapping providers means supplying a different class that satisfies the
same Protocol — views and services never need changing.
"""

from __future__ import annotations

import logging
import time
from typing import Callable, Protocol, runtime_checkable

import requests
from django.conf import settings

from gallery.domain.transformations import ImageTransform
from gallery.errors import (
    UpstreamError,
    UpstreamTimeoutError,
    UpstreamUnavailableError,
)
from gallery.services.url_builder import PicsumUrlBuilder
from gallery.types import ImageItem

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Provider contract
# ---------------------------------------------------------------------------


@runtime_checkable
class ImageProvider(Protocol):
    """Structural interface for image providers."""

    def fetch_image(self, image_id: int, transform: ImageTransform) -> ImageItem:
        """Fetch a single image item.

        Raises:
            UpstreamTimeoutError: Request timed out.
            UpstreamError:        Non-success HTTP response.
            UpstreamUnavailableError: All retries exhausted.
        """
        ...

    def fetch_images(
        self, image_ids: list[int], transform: ImageTransform
    ) -> list[ImageItem]:
        """Fetch a batch of image items in the given order."""
        ...


# ---------------------------------------------------------------------------
# Picsum adapter
# ---------------------------------------------------------------------------


class PicsumImageProvider:
    """Concrete ``ImageProvider`` backed by picsum.photos.

    Resilience behaviour is driven entirely by settings:

    - ``UPSTREAM_TIMEOUT_SECONDS`` — per-request socket timeout.
    - ``UPSTREAM_RETRY_COUNT``     — max retries after a transient failure.
    - ``UPSTREAM_BACKOFF_SECONDS`` — base backoff; doubles each attempt.

    A shared ``requests.Session`` is used for connection reuse within a
    single provider instance (one per view invocation).

    ``_sleep`` is injectable for tests to avoid real delays.
    """

    def __init__(
        self,
        url_builder: PicsumUrlBuilder | None = None,
        _sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._url_builder = url_builder or PicsumUrlBuilder()
        self.session: requests.Session = requests.Session()
        self._timeout: float = getattr(settings, 'UPSTREAM_TIMEOUT_SECONDS', 5.0)
        self._retry_count: int = getattr(settings, 'UPSTREAM_RETRY_COUNT', 3)
        self._backoff: float = getattr(settings, 'UPSTREAM_BACKOFF_SECONDS', 0.5)
        self._sleep = _sleep

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_image(self, image_id: int, transform: ImageTransform) -> ImageItem:
        """Build and return an ``ImageItem`` for *image_id*.

        The URL is constructed by the URL builder and returned directly.
        The browser fetches the actual image bytes from picsum — the server
        is a URL provider, not an image proxy.

        ``_verify_url`` is available for explicit health checks (e.g. the
        ``/health`` endpoint) but is intentionally not called per-image to
        avoid unnecessary server-side round-trips.

        Raises:
            UpstreamTimeoutError:     (when called via ``_verify_url``)
            UpstreamError:            (when called via ``_verify_url``)
            UpstreamUnavailableError: (when called via ``_verify_url``)
        """
        url = self._url_builder.image_url(image_id, transform)
        size = transform.pixel_size()
        return ImageItem(
            image_id=image_id,
            url=url,
            width=size,
            height=size,
            transform=transform,
        )

    def fetch_images(
        self, image_ids: list[int], transform: ImageTransform
    ) -> list[ImageItem]:
        """Return an ``ImageItem`` for every ID in *image_ids*."""
        return [self.fetch_image(image_id, transform) for image_id in image_ids]

    # ------------------------------------------------------------------
    # Resilience internals
    # ------------------------------------------------------------------

    def _verify_url(self, url: str, *, image_id: int | None = None) -> None:
        """Issue a HEAD request to *url* with timeout and retry policy.

        - Retries on: timeout, connection error, 5xx responses.
        - Does NOT retry on: 4xx responses (client errors are not transient).
        - Backoff doubles each attempt: base, base*2, base*4, …

        Args:
            url:      Fully qualified upstream URL to verify.
            image_id: For error attribution in logs and exceptions.

        Raises:
            UpstreamTimeoutError:     All attempts timed out.
            UpstreamError:            Non-retriable HTTP error (4xx).
            UpstreamUnavailableError: Retriable error persisted through all retries.
        """
        last_exc: UpstreamError | None = None

        for attempt in range(self._retry_count + 1):
            if attempt > 0:
                backoff = self._backoff * (2 ** (attempt - 1))
                logger.debug(
                    "upstream.retry",
                    extra={
                        "url": url,
                        "attempt": attempt,
                        "backoff_seconds": backoff,
                        "image_id": image_id,
                    },
                )
                self._sleep(backoff)

            try:
                logger.debug(
                    "upstream.request",
                    extra={"url": url, "attempt": attempt, "image_id": image_id},
                )
                response = self.session.get(
                    url, timeout=self._timeout, allow_redirects=True, stream=True
                )
                response.raise_for_status()
                response.close()
                logger.debug(
                    "upstream.response",
                    extra={
                        "url": url,
                        "status": response.status_code,
                        "image_id": image_id,
                    },
                )
                return  # success

            except requests.Timeout:
                logger.warning(
                    "upstream.timeout",
                    extra={"url": url, "attempt": attempt, "image_id": image_id},
                )
                last_exc = UpstreamTimeoutError(
                    f"Request to {url} timed out (attempt {attempt + 1}).",
                    image_id=image_id,
                )

            except requests.ConnectionError as exc:
                logger.warning(
                    "upstream.connection_error",
                    extra={"url": url, "attempt": attempt, "image_id": image_id, "detail": str(exc)},
                )
                last_exc = UpstreamUnavailableError(
                    f"Connection error for {url} (attempt {attempt + 1}): {exc}",
                    image_id=image_id,
                )

            except requests.HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else None
                logger.warning(
                    "upstream.http_error",
                    extra={
                        "url": url,
                        "status": status,
                        "attempt": attempt,
                        "image_id": image_id,
                    },
                )
                if status is not None and status < 500:
                    # 4xx — not transient, do not retry
                    raise UpstreamError(
                        f"Upstream returned {status} for {url}.",
                        status_code=status,
                        image_id=image_id,
                    )
                last_exc = UpstreamError(
                    f"Upstream returned {status} for {url} (attempt {attempt + 1}).",
                    status_code=status,
                    image_id=image_id,
                )

        # All attempts exhausted
        if isinstance(last_exc, UpstreamTimeoutError):
            raise UpstreamTimeoutError(
                f"All {self._retry_count + 1} attempts timed out for {url}.",
                image_id=image_id,
            )
        raise UpstreamUnavailableError(
            f"Upstream unavailable after {self._retry_count + 1} attempts for {url}.",
            image_id=image_id,
        )
