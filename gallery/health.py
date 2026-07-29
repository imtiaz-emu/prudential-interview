"""
Health check endpoint.

``GET /health`` always returns HTTP 200 while the Django process is alive.
It also performs an optional upstream ping to picsum and reports the result
in the JSON body — useful for diagnosing degraded states without breaking
container orchestration (which relies on the 200 status).

Response body::

    {
        "status": "ok" | "degraded",
        "timestamp": "2024-01-01T12:00:00.000Z",
        "checks": {
            "cache": "ok",
            "upstream": "ok" | "<error class>: <message>"
        }
    }
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from django.core.cache import cache
from django.http import JsonResponse

from gallery.domain.transformations import ImageTransform
from gallery.errors import GalleryError
from gallery.services.image_provider import PicsumImageProvider
from gallery.services.url_builder import PicsumUrlBuilder

logger = logging.getLogger(__name__)

# Tiny image used for the upstream ping — minimal data transfer.
_PING_IMAGE_ID = 1
_PING_TRANSFORM = ImageTransform('small')  # 200x200


def health(request):
    """Return application health as a JSON object."""
    timestamp = (
        datetime.now(tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.') +
        f'{datetime.now(tz=timezone.utc).microsecond // 1000:03d}Z'
    )

    checks: dict[str, str] = {}

    # --- cache check ---
    try:
        cache.set('health:ping', 'pong', timeout=5)
        result = cache.get('health:ping')
        checks['cache'] = 'ok' if result == 'pong' else 'error: unexpected value'
    except Exception as exc:
        checks['cache'] = f'{type(exc).__name__}: {exc}'

    # --- upstream check ---
    builder = PicsumUrlBuilder()
    provider = PicsumImageProvider(url_builder=builder)
    ping_url = builder.image_url(_PING_IMAGE_ID, _PING_TRANSFORM)
    try:
        provider._verify_url(ping_url, image_id=_PING_IMAGE_ID)
        checks['upstream'] = 'ok'
    except GalleryError as exc:
        checks['upstream'] = f'{type(exc).__name__}: {exc}'
    except Exception as exc:
        checks['upstream'] = f'{type(exc).__name__}: {exc}'

    overall = 'ok' if all(v == 'ok' for v in checks.values()) else 'degraded'

    logger.info(
        'health.check',
        extra={'status': overall, 'checks': checks},
    )

    return JsonResponse({
        'status': overall,
        'timestamp': timestamp,
        'checks': checks,
    })
