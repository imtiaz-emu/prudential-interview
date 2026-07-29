"""
Structured logging for the gallery application.

``StructuredFormatter`` emits one JSON object per log line, making logs
trivially parseable by log aggregators and readable from container stdout.

Usage — register via settings.LOGGING::

    LOGGING = {
        'formatters': {
            'structured': {'()': 'gallery.logging.events.StructuredFormatter'},
        },
        ...
    }

All application code uses standard ``logging.getLogger(__name__)`` and
passes context via ``extra={}``.  The formatter extracts every non-standard
field from the ``LogRecord`` automatically so no coupling exists between
this module and the callsites.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

# Standard LogRecord attributes we do NOT want to surface as extra fields.
_STANDARD_ATTRS = frozenset({
    'args', 'created', 'exc_info', 'exc_text', 'filename',
    'funcName', 'levelname', 'levelno', 'lineno', 'message',
    'module', 'msecs', 'msg', 'name', 'pathname', 'process',
    'processName', 'relativeCreated', 'stack_info', 'taskName',
    'thread', 'threadName',
})


class StructuredFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects.

    Every field passed via ``extra={}`` is included in the output so log
    events carry full diagnostic context without any coupling between the
    formatter and individual callsites.

    Example output::

        {"time": "2024-01-01T12:00:00.000Z", "level": "DEBUG",
         "logger": "gallery.cache.cache_service", "event": "cache.hit",
         "key": "gallery:img:1:size:medium", "image_id": 1}
    """

    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()

        payload: dict = {
            'time': datetime.fromtimestamp(record.created, tz=timezone.utc)
                    .strftime('%Y-%m-%dT%H:%M:%S.') +
                    f'{record.msecs:03.0f}Z',
            'level': record.levelname,
            'logger': record.name,
            'event': record.message,
        }

        # Append every extra field supplied by the callsite.
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS and not key.startswith('_'):
                payload[key] = value

        if record.exc_info:
            payload['exc'] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


# ---------------------------------------------------------------------------
# Typed event helpers
# ---------------------------------------------------------------------------
# These are thin wrappers so callsites stay readable and field names stay
# consistent.  All helpers accept a *logger* so they work with any module's
# logger.

def log_upstream_request(
    logger: logging.Logger, url: str, image_id: int | None, attempt: int
) -> None:
    logger.debug(
        'upstream.request',
        extra={'url': url, 'image_id': image_id, 'attempt': attempt},
    )


def log_upstream_response(
    logger: logging.Logger,
    url: str,
    status: int,
    image_id: int | None,
) -> None:
    logger.debug(
        'upstream.response',
        extra={'url': url, 'status': status, 'image_id': image_id},
    )


def log_upstream_retry(
    logger: logging.Logger,
    url: str,
    attempt: int,
    backoff: float,
    image_id: int | None,
) -> None:
    logger.debug(
        'upstream.retry',
        extra={
            'url': url,
            'attempt': attempt,
            'backoff_seconds': backoff,
            'image_id': image_id,
        },
    )


def log_upstream_error(
    logger: logging.Logger,
    event: str,
    url: str,
    image_id: int | None,
    **extra,
) -> None:
    logger.warning(event, extra={'url': url, 'image_id': image_id, **extra})


def log_cache_hit(
    logger: logging.Logger, key: str, image_id: int
) -> None:
    logger.debug('cache.hit', extra={'key': key, 'image_id': image_id})


def log_cache_miss(
    logger: logging.Logger, key: str, image_id: int
) -> None:
    logger.debug('cache.miss', extra={'key': key, 'image_id': image_id})


def log_cache_stored(
    logger: logging.Logger, key: str, image_id: int
) -> None:
    logger.debug('cache.stored', extra={'key': key, 'image_id': image_id})


def log_cache_fallback_hit(
    logger: logging.Logger,
    key: str,
    image_id: int,
    upstream_error: str,
) -> None:
    logger.warning(
        'cache.fallback_hit',
        extra={'key': key, 'image_id': image_id, 'upstream_error': upstream_error},
    )


def log_cache_no_fallback(
    logger: logging.Logger, key: str, image_id: int
) -> None:
    logger.error('cache.no_fallback', extra={'key': key, 'image_id': image_id})
