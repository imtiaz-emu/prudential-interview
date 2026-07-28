"""Integration-style tests for resilience policies in PicsumImageProvider."""

import pytest
from unittest.mock import MagicMock, patch, call
from django.test import override_settings

import requests

from gallery.domain.transformations import ImageTransform
from gallery.errors import (
    UpstreamError,
    UpstreamTimeoutError,
    UpstreamUnavailableError,
)
from gallery.services.image_provider import PicsumImageProvider
from gallery.services.url_builder import PicsumUrlBuilder
from gallery.types import ImageItem


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(status_code: int) -> MagicMock:
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    if status_code >= 400:
        http_err = requests.HTTPError(response=resp)
        resp.raise_for_status.side_effect = http_err
    else:
        resp.raise_for_status.return_value = None
    return resp


def _provider(retry_count=2, timeout=1.0, backoff=0.0):
    """Build a provider with a mock sleep and controlled settings."""
    sleep_mock = MagicMock()
    builder = PicsumUrlBuilder(base_url='https://picsum.photos')
    p = PicsumImageProvider(url_builder=builder, _sleep=sleep_mock)
    p._timeout = timeout
    p._retry_count = retry_count
    p._backoff = backoff
    return p, sleep_mock


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------

class TestSuccessPath:
    def test_fetch_image_returns_item_on_200(self):
        provider, _ = _provider()
        provider.session = MagicMock()
        provider.session.head.return_value = _make_response(200)

        item = provider.fetch_image(1, ImageTransform('medium'))

        assert isinstance(item, ImageItem)
        assert item.image_id == 1

    def test_session_head_called_with_timeout(self):
        provider, _ = _provider(timeout=3.5)
        provider.session = MagicMock()
        provider.session.head.return_value = _make_response(200)

        provider.fetch_image(1, ImageTransform('medium'))

        _, kwargs = provider.session.head.call_args
        assert kwargs['timeout'] == 3.5

    def test_redirects_followed(self):
        provider, _ = _provider()
        provider.session = MagicMock()
        provider.session.head.return_value = _make_response(200)

        provider.fetch_image(1, ImageTransform('medium'))

        _, kwargs = provider.session.head.call_args
        assert kwargs['allow_redirects'] is True


# ---------------------------------------------------------------------------
# Timeout handling
# ---------------------------------------------------------------------------

class TestTimeoutHandling:
    def test_single_timeout_is_retried(self):
        provider, sleep_mock = _provider(retry_count=2, backoff=1.0)
        provider.session = MagicMock()
        provider.session.head.side_effect = [
            requests.Timeout(),
            _make_response(200),
        ]

        item = provider.fetch_image(1, ImageTransform('medium'))
        assert item.image_id == 1
        assert provider.session.head.call_count == 2

    def test_all_timeouts_raise_upstream_timeout_error(self):
        provider, _ = _provider(retry_count=2)
        provider.session = MagicMock()
        provider.session.head.side_effect = requests.Timeout()

        with pytest.raises(UpstreamTimeoutError):
            provider.fetch_image(1, ImageTransform('medium'))

        assert provider.session.head.call_count == 3  # 1 initial + 2 retries

    def test_timeout_error_carries_image_id(self):
        provider, _ = _provider(retry_count=0)
        provider.session = MagicMock()
        provider.session.head.side_effect = requests.Timeout()

        with pytest.raises(UpstreamTimeoutError) as exc_info:
            provider.fetch_image(42, ImageTransform('medium'))

        assert exc_info.value.image_id == 42


# ---------------------------------------------------------------------------
# Transient failure then success
# ---------------------------------------------------------------------------

class TestTransientFailureThenSuccess:
    def test_5xx_then_success_returns_item(self):
        provider, sleep_mock = _provider(retry_count=2, backoff=0.5)
        provider.session = MagicMock()
        provider.session.head.side_effect = [
            _make_response(503),
            _make_response(200),
        ]

        item = provider.fetch_image(5, ImageTransform('medium'))
        assert item.image_id == 5
        assert provider.session.head.call_count == 2

    def test_connection_error_then_success(self):
        provider, _ = _provider(retry_count=2)
        provider.session = MagicMock()
        provider.session.head.side_effect = [
            requests.ConnectionError('connection refused'),
            _make_response(200),
        ]

        item = provider.fetch_image(3, ImageTransform('medium'))
        assert item.image_id == 3

    def test_two_failures_then_success(self):
        provider, _ = _provider(retry_count=3)
        provider.session = MagicMock()
        provider.session.head.side_effect = [
            requests.Timeout(),
            _make_response(500),
            _make_response(200),
        ]

        item = provider.fetch_image(7, ImageTransform('medium'))
        assert item.image_id == 7
        assert provider.session.head.call_count == 3


# ---------------------------------------------------------------------------
# Backoff behaviour
# ---------------------------------------------------------------------------

class TestBackoffBehaviour:
    def test_backoff_called_between_retries(self):
        provider, sleep_mock = _provider(retry_count=2, backoff=1.0)
        provider.session = MagicMock()
        provider.session.head.side_effect = requests.Timeout()

        with pytest.raises(UpstreamTimeoutError):
            provider.fetch_image(1, ImageTransform('medium'))

        # sleep called once per retry (not on first attempt)
        assert sleep_mock.call_count == 2

    def test_backoff_doubles_each_retry(self):
        provider, sleep_mock = _provider(retry_count=3, backoff=1.0)
        provider.session = MagicMock()
        provider.session.head.side_effect = requests.Timeout()

        with pytest.raises(UpstreamTimeoutError):
            provider.fetch_image(1, ImageTransform('medium'))

        sleep_calls = [c.args[0] for c in sleep_mock.call_args_list]
        assert sleep_calls == [1.0, 2.0, 4.0]

    def test_no_sleep_on_first_attempt(self):
        provider, sleep_mock = _provider(retry_count=1, backoff=1.0)
        provider.session = MagicMock()
        provider.session.head.side_effect = [
            requests.Timeout(),
            _make_response(200),
        ]

        provider.fetch_image(1, ImageTransform('medium'))
        # sleep is called once (before the second attempt only)
        assert sleep_mock.call_count == 1


# ---------------------------------------------------------------------------
# Non-retriable errors
# ---------------------------------------------------------------------------

class TestNonRetriableErrors:
    def test_404_not_retried(self):
        provider, _ = _provider(retry_count=3)
        provider.session = MagicMock()
        provider.session.head.return_value = _make_response(404)

        with pytest.raises(UpstreamError) as exc_info:
            provider.fetch_image(1, ImageTransform('medium'))

        # Only one attempt — 4xx is not retried
        assert provider.session.head.call_count == 1
        assert exc_info.value.status_code == 404

    def test_400_not_retried(self):
        provider, _ = _provider(retry_count=3)
        provider.session = MagicMock()
        provider.session.head.return_value = _make_response(400)

        with pytest.raises(UpstreamError):
            provider.fetch_image(1, ImageTransform('medium'))

        assert provider.session.head.call_count == 1


# ---------------------------------------------------------------------------
# Repeated failure mapping
# ---------------------------------------------------------------------------

class TestRepeatedFailureMapping:
    @override_settings(UPSTREAM_RETRY_COUNT=2)
    def test_repeated_5xx_raises_upstream_unavailable(self):
        provider, _ = _provider(retry_count=2)
        provider.session = MagicMock()
        provider.session.head.return_value = _make_response(500)

        with pytest.raises(UpstreamUnavailableError):
            provider.fetch_image(1, ImageTransform('medium'))

        assert provider.session.head.call_count == 3

    def test_repeated_connection_errors_raise_upstream_unavailable(self):
        provider, _ = _provider(retry_count=2)
        provider.session = MagicMock()
        provider.session.head.side_effect = requests.ConnectionError()

        with pytest.raises(UpstreamUnavailableError):
            provider.fetch_image(1, ImageTransform('medium'))

    def test_error_carries_image_id(self):
        provider, _ = _provider(retry_count=0)
        provider.session = MagicMock()
        provider.session.head.side_effect = requests.ConnectionError()

        with pytest.raises(UpstreamUnavailableError) as exc_info:
            provider.fetch_image(99, ImageTransform('medium'))

        assert exc_info.value.image_id == 99
