"""Tests for gallery.logging.events (formatter) and gallery.health endpoint."""

import json
import logging
import pytest
from unittest.mock import MagicMock, patch

from django.test import Client, override_settings
from django.urls import reverse

from gallery.logging.events import (
    StructuredFormatter,
    log_cache_hit,
    log_cache_miss,
    log_upstream_error,
    log_upstream_request,
    log_upstream_response,
)


# ---------------------------------------------------------------------------
# StructuredFormatter
# ---------------------------------------------------------------------------

class TestStructuredFormatter:
    def _record(self, msg='test.event', level=logging.DEBUG, **extra):
        record = logging.LogRecord(
            name='gallery.test',
            level=level,
            pathname='',
            lineno=0,
            msg=msg,
            args=(),
            exc_info=None,
        )
        for k, v in extra.items():
            setattr(record, k, v)
        return record

    def test_output_is_valid_json(self):
        formatter = StructuredFormatter()
        record = self._record('cache.hit')
        line = formatter.format(record)
        parsed = json.loads(line)
        assert isinstance(parsed, dict)

    def test_contains_required_fields(self):
        formatter = StructuredFormatter()
        record = self._record('cache.hit')
        parsed = json.loads(formatter.format(record))
        assert 'time' in parsed
        assert 'level' in parsed
        assert 'logger' in parsed
        assert 'event' in parsed

    def test_extra_fields_included(self):
        formatter = StructuredFormatter()
        record = self._record('cache.hit', image_id=42, key='gallery:img:42:size:medium')
        parsed = json.loads(formatter.format(record))
        assert parsed['image_id'] == 42
        assert parsed['key'] == 'gallery:img:42:size:medium'

    def test_event_matches_message(self):
        formatter = StructuredFormatter()
        record = self._record('upstream.timeout')
        parsed = json.loads(formatter.format(record))
        assert parsed['event'] == 'upstream.timeout'

    def test_level_name_correct(self):
        formatter = StructuredFormatter()
        record = self._record('x', level=logging.WARNING)
        parsed = json.loads(formatter.format(record))
        assert parsed['level'] == 'WARNING'

    def test_logger_name_correct(self):
        formatter = StructuredFormatter()
        record = self._record('x')
        parsed = json.loads(formatter.format(record))
        assert parsed['logger'] == 'gallery.test'

    def test_standard_attrs_not_duplicated(self):
        formatter = StructuredFormatter()
        record = self._record('x')
        parsed = json.loads(formatter.format(record))
        # These should not appear as extra top-level keys
        assert 'msg' not in parsed
        assert 'args' not in parsed
        assert 'lineno' not in parsed


# ---------------------------------------------------------------------------
# Typed log helpers — smoke tests (verify they don't raise)
# ---------------------------------------------------------------------------

class TestLogHelpers:
    def setup_method(self):
        self.logger = MagicMock(spec=logging.Logger)

    def test_log_cache_hit(self):
        log_cache_hit(self.logger, 'gallery:img:1:size:medium', 1)
        self.logger.debug.assert_called_once()

    def test_log_cache_miss(self):
        log_cache_miss(self.logger, 'gallery:img:1:size:medium', 1)
        self.logger.debug.assert_called_once()

    def test_log_upstream_request(self):
        log_upstream_request(self.logger, 'https://example.com/1', 1, attempt=0)
        self.logger.debug.assert_called_once()

    def test_log_upstream_response(self):
        log_upstream_response(self.logger, 'https://example.com/1', 200, 1)
        self.logger.debug.assert_called_once()

    def test_log_upstream_error(self):
        log_upstream_error(self.logger, 'upstream.timeout', 'https://x', 1, attempt=0)
        self.logger.warning.assert_called_once()


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestHealthEndpoint:
    def test_returns_200(self):
        client = Client()
        with patch('gallery.health.PicsumImageProvider') as mock_cls:
            mock_cls.return_value._verify_url.return_value = None
            response = client.get(reverse('health'))
        assert response.status_code == 200

    def test_response_is_json(self):
        client = Client()
        with patch('gallery.health.PicsumImageProvider') as mock_cls:
            mock_cls.return_value._verify_url.return_value = None
            response = client.get(reverse('health'))
        assert response['Content-Type'] == 'application/json'

    def test_body_contains_status(self):
        client = Client()
        with patch('gallery.health.PicsumImageProvider') as mock_cls:
            mock_cls.return_value._verify_url.return_value = None
            response = client.get(reverse('health'))
        body = json.loads(response.content)
        assert 'status' in body

    def test_body_contains_timestamp(self):
        client = Client()
        with patch('gallery.health.PicsumImageProvider') as mock_cls:
            mock_cls.return_value._verify_url.return_value = None
            response = client.get(reverse('health'))
        body = json.loads(response.content)
        assert 'timestamp' in body

    def test_body_contains_checks(self):
        client = Client()
        with patch('gallery.health.PicsumImageProvider') as mock_cls:
            mock_cls.return_value._verify_url.return_value = None
            response = client.get(reverse('health'))
        body = json.loads(response.content)
        assert 'checks' in body
        assert 'cache' in body['checks']
        assert 'upstream' in body['checks']

    def test_status_ok_when_upstream_healthy(self):
        client = Client()
        with patch('gallery.health.PicsumImageProvider') as mock_cls:
            mock_cls.return_value._verify_url.return_value = None
            response = client.get(reverse('health'))
        body = json.loads(response.content)
        assert body['status'] == 'ok'

    def test_status_degraded_when_upstream_fails(self):
        from gallery.errors import UpstreamUnavailableError
        client = Client()
        with patch('gallery.health.PicsumImageProvider') as mock_cls:
            mock_cls.return_value._verify_url.side_effect = UpstreamUnavailableError("down")
            response = client.get(reverse('health'))
        assert response.status_code == 200   # still 200 for container health
        body = json.loads(response.content)
        assert body['status'] == 'degraded'
        assert 'upstream' in body['checks']

    def test_cache_check_ok(self):
        client = Client()
        with patch('gallery.health.PicsumImageProvider') as mock_cls:
            mock_cls.return_value._verify_url.return_value = None
            response = client.get(reverse('health'))
        body = json.loads(response.content)
        assert body['checks']['cache'] == 'ok'
