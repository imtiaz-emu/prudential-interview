"""Unit tests for resilience policies in PicsumImageProvider._verify_url.

``fetch_image`` is a URL builder (no HTTP calls).
``_verify_url`` owns all resilience logic — it is tested directly here.
"""

import pytest
from unittest.mock import MagicMock, call
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

TEST_URL = 'https://picsum.photos/id/1/400/400'


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


def _make_info_response(image_id: int = 1, width: int = 5616, height: int = 3744) -> MagicMock:
    resp = MagicMock(spec=requests.Response)
    resp.status_code = 200
    resp.raise_for_status.return_value = None
    resp.json.return_value = {
        'id': str(image_id),
        'author': 'Test Author',
        'width': width,
        'height': height,
        'url': 'https://unsplash.com/photos/test',
        'download_url': f'https://picsum.photos/id/{image_id}/5616/3744',
    }
    return resp


def _provider(retry_count=2, timeout=1.0, backoff=0.0):
    sleep_mock = MagicMock()
    builder = PicsumUrlBuilder(base_url='https://picsum.photos')
    p = PicsumImageProvider(url_builder=builder, _sleep=sleep_mock)
    p._timeout = timeout
    p._retry_count = retry_count
    p._backoff = backoff
    p.session = MagicMock()
    return p, sleep_mock


# ---------------------------------------------------------------------------
# fetch_image — makes upstream HTTP call per image
# ---------------------------------------------------------------------------

class TestFetchImageHttp:
    def test_returns_image_item(self):
        p, _ = _provider()
        p.session.get.return_value = _make_info_response(1, 5616, 3744)
        item = p.fetch_image(1, ImageTransform('medium'))
        assert isinstance(item, ImageItem)
        assert item.image_id == 1

    def test_makes_http_call(self):
        p, _ = _provider()
        p.session.get.return_value = _make_info_response()
        p.fetch_image(42, ImageTransform('medium'))
        p.session.get.assert_called_once()

    def test_calls_info_endpoint(self):
        p, _ = _provider()
        p.session.get.return_value = _make_info_response(42)
        p.fetch_image(42, ImageTransform('medium'))
        call_url = p.session.get.call_args[0][0]
        assert '/id/42/info' in call_url

    def test_dimensions_from_info_response(self):
        p, _ = _provider()
        p.session.get.return_value = _make_info_response(1, 1920, 1080)
        item = p.fetch_image(1, ImageTransform('small'))
        assert item.width == 1920
        assert item.height == 1080

    def test_transform_preserved(self):
        p, _ = _provider()
        p.session.get.return_value = _make_info_response()
        t = ImageTransform('large', grayscale=True, blur=4)
        item = p.fetch_image(1, t)
        assert item.transform == t

    def test_timeout_raises_upstream_timeout_error(self):
        p, _ = _provider(retry_count=0)
        p.session.get.side_effect = requests.Timeout()
        with pytest.raises(UpstreamTimeoutError):
            p.fetch_image(1, ImageTransform('medium'))

    def test_upstream_failure_raises_upstream_unavailable(self):
        p, _ = _provider(retry_count=0)
        p.session.get.side_effect = requests.ConnectionError()
        with pytest.raises(UpstreamUnavailableError):
            p.fetch_image(1, ImageTransform('medium'))


# ---------------------------------------------------------------------------
# _verify_url — success path
# ---------------------------------------------------------------------------

class TestVerifyUrlSuccess:
    def test_succeeds_on_200(self):
        p, _ = _provider()
        p.session.get.return_value = _make_response(200)
        p._verify_url(TEST_URL)  # no exception

    def test_uses_get_method(self):
        p, _ = _provider()
        p.session.get.return_value = _make_response(200)
        p._verify_url(TEST_URL)
        p.session.get.assert_called_once()

    def test_passes_timeout(self):
        p, _ = _provider(timeout=3.5)
        p.session.get.return_value = _make_response(200)
        p._verify_url(TEST_URL)
        _, kwargs = p.session.get.call_args
        assert kwargs['timeout'] == 3.5

    def test_stream_true(self):
        p, _ = _provider()
        p.session.get.return_value = _make_response(200)
        p._verify_url(TEST_URL)
        _, kwargs = p.session.get.call_args
        assert kwargs.get('stream') is True

    def test_closes_response(self):
        p, _ = _provider()
        resp = _make_response(200)
        p.session.get.return_value = resp
        p._verify_url(TEST_URL)
        resp.close.assert_called_once()


# ---------------------------------------------------------------------------
# _verify_url — timeout handling
# ---------------------------------------------------------------------------

class TestTimeoutHandling:
    def test_single_timeout_is_retried(self):
        p, _ = _provider(retry_count=2)
        p.session.get.side_effect = [requests.Timeout(), _make_response(200)]
        p._verify_url(TEST_URL)
        assert p.session.get.call_count == 2

    def test_all_timeouts_raise_upstream_timeout_error(self):
        p, _ = _provider(retry_count=2)
        p.session.get.side_effect = requests.Timeout()
        with pytest.raises(UpstreamTimeoutError):
            p._verify_url(TEST_URL, image_id=1)
        assert p.session.get.call_count == 3  # 1 + 2 retries

    def test_timeout_error_carries_image_id(self):
        p, _ = _provider(retry_count=0)
        p.session.get.side_effect = requests.Timeout()
        with pytest.raises(UpstreamTimeoutError) as exc_info:
            p._verify_url(TEST_URL, image_id=42)
        assert exc_info.value.image_id == 42


# ---------------------------------------------------------------------------
# _verify_url — transient failure then success
# ---------------------------------------------------------------------------

class TestTransientFailureThenSuccess:
    def test_5xx_then_success(self):
        p, _ = _provider(retry_count=2)
        p.session.get.side_effect = [_make_response(503), _make_response(200)]
        p._verify_url(TEST_URL)
        assert p.session.get.call_count == 2

    def test_connection_error_then_success(self):
        p, _ = _provider(retry_count=2)
        p.session.get.side_effect = [
            requests.ConnectionError('refused'),
            _make_response(200),
        ]
        p._verify_url(TEST_URL)

    def test_two_failures_then_success(self):
        p, _ = _provider(retry_count=3)
        p.session.get.side_effect = [
            requests.Timeout(),
            _make_response(500),
            _make_response(200),
        ]
        p._verify_url(TEST_URL)
        assert p.session.get.call_count == 3


# ---------------------------------------------------------------------------
# _verify_url — backoff
# ---------------------------------------------------------------------------

class TestBackoffBehaviour:
    def test_backoff_called_between_retries(self):
        p, sleep_mock = _provider(retry_count=2, backoff=1.0)
        p.session.get.side_effect = requests.Timeout()
        with pytest.raises(UpstreamTimeoutError):
            p._verify_url(TEST_URL)
        assert sleep_mock.call_count == 2

    def test_backoff_doubles_each_retry(self):
        p, sleep_mock = _provider(retry_count=3, backoff=1.0)
        p.session.get.side_effect = requests.Timeout()
        with pytest.raises(UpstreamTimeoutError):
            p._verify_url(TEST_URL)
        assert [c.args[0] for c in sleep_mock.call_args_list] == [1.0, 2.0, 4.0]

    def test_no_sleep_on_first_attempt(self):
        p, sleep_mock = _provider(retry_count=1, backoff=1.0)
        p.session.get.side_effect = [requests.Timeout(), _make_response(200)]
        p._verify_url(TEST_URL)
        assert sleep_mock.call_count == 1


# ---------------------------------------------------------------------------
# _verify_url — non-retriable errors
# ---------------------------------------------------------------------------

class TestNonRetriableErrors:
    def test_404_not_retried(self):
        p, _ = _provider(retry_count=3)
        p.session.get.return_value = _make_response(404)
        with pytest.raises(UpstreamError) as exc_info:
            p._verify_url(TEST_URL)
        assert p.session.get.call_count == 1
        assert exc_info.value.status_code == 404

    def test_400_not_retried(self):
        p, _ = _provider(retry_count=3)
        p.session.get.return_value = _make_response(400)
        with pytest.raises(UpstreamError):
            p._verify_url(TEST_URL)
        assert p.session.get.call_count == 1


# ---------------------------------------------------------------------------
# _verify_url — repeated failure mapping
# ---------------------------------------------------------------------------

class TestRepeatedFailureMapping:
    def test_repeated_5xx_raises_upstream_unavailable(self):
        p, _ = _provider(retry_count=2)
        p.session.get.return_value = _make_response(500)
        with pytest.raises(UpstreamUnavailableError):
            p._verify_url(TEST_URL)
        assert p.session.get.call_count == 3

    def test_repeated_connection_errors_raise_upstream_unavailable(self):
        p, _ = _provider(retry_count=2)
        p.session.get.side_effect = requests.ConnectionError()
        with pytest.raises(UpstreamUnavailableError):
            p._verify_url(TEST_URL)

    def test_error_carries_image_id(self):
        p, _ = _provider(retry_count=0)
        p.session.get.side_effect = requests.ConnectionError()
        with pytest.raises(UpstreamUnavailableError) as exc_info:
            p._verify_url(TEST_URL, image_id=99)
        assert exc_info.value.image_id == 99
