"""Unit tests for gallery.services.gallery_service."""

import pytest
from unittest.mock import MagicMock, patch
from django.test import override_settings

from gallery.cache.cache_service import CacheService
from gallery.domain.transformations import ImageTransform
from gallery.domain.validation import GalleryParams
from gallery.errors import NoFallbackError, UpstreamUnavailableError
from gallery.services.gallery_service import GalleryService
from gallery.types import GalleryPage, ImageItem


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _params(page=1, per_page=10, size='medium', grayscale=False, blur=0):
    return GalleryParams(page=page, per_page=per_page, size=size,
                         grayscale=grayscale, blur=blur)


def _item(image_id: int, size='medium') -> ImageItem:
    t = ImageTransform(size)
    return ImageItem(image_id=image_id, url=f'https://x/{image_id}',
                     width=400, height=400, transform=t)


def _mock_provider(ids: list[int], size='medium'):
    """Provider mock that returns ImageItems for given IDs."""
    provider = MagicMock()
    provider.fetch_image.side_effect = lambda iid, t: _item(iid, size)
    return provider


def _mock_cache_passthrough():
    """CacheService mock that always calls fetch_fn (no caching)."""
    cache = MagicMock(spec=CacheService)
    cache.get_or_fetch.side_effect = lambda iid, t, fn: fn()
    return cache


# ---------------------------------------------------------------------------
# Page index calculation
# ---------------------------------------------------------------------------

class TestComputeImageIds:
    def _svc(self, max_id=1000):
        svc = GalleryService()
        svc._max_image_id = max_id
        return svc

    def test_page1_per10(self):
        assert self._svc()._compute_image_ids(1, 10) == list(range(1, 11))

    def test_page2_per10(self):
        assert self._svc()._compute_image_ids(2, 10) == list(range(11, 21))

    def test_page3_per10(self):
        assert self._svc()._compute_image_ids(3, 10) == list(range(21, 31))

    def test_page1_per5(self):
        assert self._svc()._compute_image_ids(1, 5) == [1, 2, 3, 4, 5]

    def test_page2_per5(self):
        assert self._svc()._compute_image_ids(2, 5) == [6, 7, 8, 9, 10]

    def test_last_page_clamped_to_max(self):
        ids = self._svc(max_id=15)._compute_image_ids(2, 10)
        assert ids == [11, 12, 13, 14, 15]

    def test_page_beyond_max_returns_empty(self):
        ids = self._svc(max_id=10)._compute_image_ids(2, 10)
        assert ids == []

    def test_page1_per_page_equals_max(self):
        ids = self._svc(max_id=5)._compute_image_ids(1, 5)
        assert ids == [1, 2, 3, 4, 5]

    def test_ids_are_contiguous(self):
        ids = GalleryService()._compute_image_ids(4, 7)
        assert ids == list(range(ids[0], ids[-1] + 1))


# ---------------------------------------------------------------------------
# GalleryService.get_page — happy path
# ---------------------------------------------------------------------------

class TestGetPageSuccess:
    def test_returns_gallery_page(self):
        svc = GalleryService(
            provider=_mock_provider(list(range(1, 11))),
            cache_service=_mock_cache_passthrough(),
        )
        page = svc.get_page(_params(page=1))
        assert isinstance(page, GalleryPage)

    def test_correct_number_of_items(self):
        svc = GalleryService(
            provider=_mock_provider(list(range(1, 11))),
            cache_service=_mock_cache_passthrough(),
        )
        page = svc.get_page(_params(page=1, per_page=10))
        assert len(page.items) == 10

    def test_item_ids_match_page_range(self):
        svc = GalleryService(
            provider=_mock_provider([]),
            cache_service=_mock_cache_passthrough(),
        )
        page = svc.get_page(_params(page=2, per_page=10))
        assert [i.image_id for i in page.items] == list(range(11, 21))

    def test_page_metadata_correct(self):
        svc = GalleryService(
            provider=_mock_provider([]),
            cache_service=_mock_cache_passthrough(),
        )
        page = svc.get_page(_params(page=3, per_page=5))
        assert page.page == 3
        assert page.per_page == 5

    def test_has_previous_false_on_page1(self):
        svc = GalleryService(
            provider=_mock_provider([]),
            cache_service=_mock_cache_passthrough(),
        )
        page = svc.get_page(_params(page=1))
        assert page.has_previous is False

    def test_has_previous_true_on_page2(self):
        svc = GalleryService(
            provider=_mock_provider([]),
            cache_service=_mock_cache_passthrough(),
        )
        page = svc.get_page(_params(page=2))
        assert page.has_previous is True

    def test_has_next_true_when_more_images(self):
        svc = GalleryService(
            provider=_mock_provider([]),
            cache_service=_mock_cache_passthrough(),
        )
        svc._max_image_id = 100
        page = svc.get_page(_params(page=1, per_page=10))
        assert page.has_next is True

    def test_has_next_false_on_last_page(self):
        svc = GalleryService(
            provider=_mock_provider([]),
            cache_service=_mock_cache_passthrough(),
        )
        svc._max_image_id = 10
        page = svc.get_page(_params(page=1, per_page=10))
        assert page.has_next is False

    def test_params_preserved_in_page(self):
        params = _params(page=2, per_page=5, size='large', grayscale=True, blur=3)
        svc = GalleryService(
            provider=_mock_provider([]),
            cache_service=_mock_cache_passthrough(),
        )
        page = svc.get_page(params)
        assert page.params is params

    def test_no_errors_on_full_success(self):
        svc = GalleryService(
            provider=_mock_provider([]),
            cache_service=_mock_cache_passthrough(),
        )
        page = svc.get_page(_params())
        assert page.errors == []


# ---------------------------------------------------------------------------
# GalleryService — cache-first behaviour
# ---------------------------------------------------------------------------

class TestCacheFirstBehaviour:
    def test_cache_get_or_fetch_called_per_image(self):
        cache_mock = MagicMock(spec=CacheService)
        cache_mock.get_or_fetch.side_effect = lambda iid, t, fn: fn()
        provider = _mock_provider([])

        svc = GalleryService(provider=provider, cache_service=cache_mock)
        svc.get_page(_params(page=1, per_page=5))

        assert cache_mock.get_or_fetch.call_count == 5

    def test_transform_built_from_params(self):
        cache_mock = MagicMock(spec=CacheService)
        captured_transforms = []

        def capture(iid, t, fn):
            captured_transforms.append(t)
            return fn()

        cache_mock.get_or_fetch.side_effect = capture
        provider = _mock_provider([])

        params = _params(size='large', grayscale=True, blur=4)
        svc = GalleryService(provider=provider, cache_service=cache_mock)
        svc.get_page(params)

        assert all(t.size == 'large' for t in captured_transforms)
        assert all(t.grayscale is True for t in captured_transforms)
        assert all(t.blur == 4 for t in captured_transforms)


# ---------------------------------------------------------------------------
# GalleryService — partial failure / fallback
# ---------------------------------------------------------------------------

class TestPartialFailure:
    def test_unavailable_image_omitted_from_items(self):
        cache_mock = MagicMock(spec=CacheService)

        def side_effect(iid, t, fn):
            if iid == 5:
                raise NoFallbackError("unavailable", image_id=5)
            return fn()

        cache_mock.get_or_fetch.side_effect = side_effect
        svc = GalleryService(
            provider=_mock_provider([]),
            cache_service=cache_mock,
        )
        page = svc.get_page(_params(page=1, per_page=10))

        image_ids = [i.image_id for i in page.items]
        assert 5 not in image_ids
        assert len(page.items) == 9

    def test_error_recorded_for_unavailable_image(self):
        cache_mock = MagicMock(spec=CacheService)
        cache_mock.get_or_fetch.side_effect = lambda iid, t, fn: (
            (_ for _ in ()).throw(NoFallbackError("down", image_id=iid))
            if iid == 3 else fn()
        )
        svc = GalleryService(
            provider=_mock_provider([]),
            cache_service=cache_mock,
        )
        page = svc.get_page(_params(page=1, per_page=5))

        assert len(page.errors) == 1
        assert '3' in page.errors[0]

    def test_all_images_unavailable_returns_empty_items(self):
        cache_mock = MagicMock(spec=CacheService)
        cache_mock.get_or_fetch.side_effect = NoFallbackError("all down")

        svc = GalleryService(
            provider=_mock_provider([]),
            cache_service=cache_mock,
        )
        page = svc.get_page(_params(page=1, per_page=5))

        assert page.items == []
        assert len(page.errors) == 5
