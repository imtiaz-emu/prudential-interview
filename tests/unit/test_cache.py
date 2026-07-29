"""Unit tests for gallery.cache.keys and gallery.cache.cache_service."""

import pytest
from unittest.mock import MagicMock, call, patch

from django.test import override_settings

from gallery.cache.keys import make_fallback_key, make_image_key
from gallery.cache.cache_service import CacheService
from gallery.domain.transformations import ImageTransform
from gallery.errors import NoFallbackError, UpstreamTimeoutError, UpstreamUnavailableError
from gallery.types import ImageItem


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _item(image_id: int = 1, size: str = 'medium') -> ImageItem:
    t = ImageTransform(size)
    return ImageItem(image_id=image_id, url=f'https://x/id/{image_id}',
                     width=400, height=400, transform=t)


# ---------------------------------------------------------------------------
# Cache key uniqueness and stability
# ---------------------------------------------------------------------------

class TestCacheKeys:
    def test_primary_key_format(self):
        key = make_image_key(42, ImageTransform('medium'))
        assert key == 'gallery:img:42:size:medium'

    def test_primary_key_with_grayscale_and_blur(self):
        key = make_image_key(1, ImageTransform('small', grayscale=True, blur=3))
        assert key == 'gallery:img:1:size:small,grayscale:1,blur:3'

    def test_fallback_key_format(self):
        key = make_fallback_key(42, ImageTransform('medium'))
        assert key == 'gallery:img:fallback:42:size:medium'

    def test_primary_and_fallback_keys_differ(self):
        t = ImageTransform('medium')
        assert make_image_key(1, t) != make_fallback_key(1, t)

    def test_key_is_stable(self):
        t = ImageTransform('large', grayscale=True, blur=5)
        assert make_image_key(7, t) == make_image_key(7, t)

    def test_different_image_ids_produce_different_keys(self):
        t = ImageTransform('medium')
        assert make_image_key(1, t) != make_image_key(2, t)

    def test_different_transforms_produce_different_keys(self):
        assert make_image_key(1, ImageTransform('small')) != \
               make_image_key(1, ImageTransform('large'))

    def test_grayscale_changes_key(self):
        a = make_image_key(1, ImageTransform('medium', grayscale=True))
        b = make_image_key(1, ImageTransform('medium', grayscale=False))
        assert a != b

    def test_blur_changes_key(self):
        a = make_image_key(1, ImageTransform('medium', blur=3))
        b = make_image_key(1, ImageTransform('medium', blur=4))
        assert a != b


# ---------------------------------------------------------------------------
# CacheService — cache hit
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestCacheHit:
    def test_returns_cached_item_without_calling_fetch(self):
        svc = CacheService()
        t = ImageTransform('medium')
        expected = _item(1)
        fetch_fn = MagicMock(return_value=expected)

        with override_settings(CACHES={'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'
        }}):
            from django.core.cache import cache
            cache.clear()
            cache.set(make_image_key(1, t), expected)

            result = svc.get_or_fetch(1, t, fetch_fn)

        assert result == expected
        fetch_fn.assert_not_called()

    def test_hit_does_not_overwrite_cache(self):
        svc = CacheService()
        t = ImageTransform('medium')
        stored = _item(1)
        fetch_fn = MagicMock()

        with override_settings(CACHES={'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'
        }}):
            from django.core.cache import cache
            cache.clear()
            cache.set(make_image_key(1, t), stored)
            svc.get_or_fetch(1, t, fetch_fn)
            # cache unchanged
            assert cache.get(make_image_key(1, t)) == stored


# ---------------------------------------------------------------------------
# CacheService — cache miss → upstream success
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestCacheMissSuccess:
    def test_calls_fetch_fn_on_miss(self):
        svc = CacheService()
        t = ImageTransform('medium')
        item = _item(1)
        fetch_fn = MagicMock(return_value=item)

        with override_settings(CACHES={'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'
        }}):
            from django.core.cache import cache
            cache.clear()
            result = svc.get_or_fetch(1, t, fetch_fn)

        assert result == item
        fetch_fn.assert_called_once()

    def test_result_stored_in_primary_cache(self):
        svc = CacheService()
        t = ImageTransform('medium')
        item = _item(1)

        with override_settings(CACHES={'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'
        }}):
            from django.core.cache import cache
            cache.clear()
            svc.get_or_fetch(1, t, lambda: item)
            assert cache.get(make_image_key(1, t)) == item

    def test_result_stored_in_fallback_cache(self):
        svc = CacheService()
        t = ImageTransform('medium')
        item = _item(1)

        with override_settings(CACHES={'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'
        }}):
            from django.core.cache import cache
            cache.clear()
            svc.get_or_fetch(1, t, lambda: item)
            assert cache.get(make_fallback_key(1, t)) == item

    def test_second_call_does_not_hit_upstream(self):
        svc = CacheService()
        t = ImageTransform('medium')
        item = _item(2)
        fetch_fn = MagicMock(return_value=item)

        with override_settings(CACHES={'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'
        }}):
            from django.core.cache import cache
            cache.clear()
            svc.get_or_fetch(2, t, fetch_fn)
            svc.get_or_fetch(2, t, fetch_fn)

        fetch_fn.assert_called_once()  # upstream called exactly once


# ---------------------------------------------------------------------------
# CacheService — fallback path
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestFallbackPath:
    def test_serves_stale_fallback_when_upstream_fails(self):
        svc = CacheService()
        t = ImageTransform('medium')
        stale = _item(3)
        upstream_err = UpstreamUnavailableError("down", image_id=3)

        with override_settings(CACHES={'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'
        }}):
            from django.core.cache import cache
            cache.clear()
            # pre-populate fallback as if a previous request succeeded
            cache.set(make_fallback_key(3, t), stale, timeout=None)

            result = svc.get_or_fetch(3, t, lambda: (_ for _ in ()).throw(upstream_err))

        assert result == stale

    def test_raises_no_fallback_when_nothing_cached(self):
        svc = CacheService()
        t = ImageTransform('medium')
        err = UpstreamTimeoutError("timeout", image_id=4)

        with override_settings(CACHES={'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'
        }}):
            from django.core.cache import cache
            cache.clear()

            with pytest.raises(NoFallbackError) as exc_info:
                svc.get_or_fetch(4, t, lambda: (_ for _ in ()).throw(err))

            assert exc_info.value.image_id == 4

    def test_no_fallback_error_chains_upstream_cause(self):
        svc = CacheService()
        t = ImageTransform('medium')
        upstream_err = UpstreamTimeoutError("timeout", image_id=5)

        with override_settings(CACHES={'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'
        }}):
            from django.core.cache import cache
            cache.clear()

            with pytest.raises(NoFallbackError) as exc_info:
                svc.get_or_fetch(5, t, lambda: (_ for _ in ()).throw(upstream_err))

            assert exc_info.value.__cause__ is upstream_err


# ---------------------------------------------------------------------------
# CacheService — reduced upstream calls (repeated equivalent requests)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestReducedUpstreamCalls:
    def test_ten_identical_requests_call_upstream_once(self):
        svc = CacheService()
        t = ImageTransform('large', grayscale=True, blur=2)
        item = _item(10, 'large')
        fetch_fn = MagicMock(return_value=item)

        with override_settings(CACHES={'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'
        }}):
            from django.core.cache import cache
            cache.clear()
            for _ in range(10):
                svc.get_or_fetch(10, t, fetch_fn)

        fetch_fn.assert_called_once()

    def test_different_transforms_each_call_upstream_once(self):
        svc = CacheService()
        t1 = ImageTransform('small')
        t2 = ImageTransform('large', grayscale=True)
        item1 = _item(1, 'small')
        item2 = _item(1, 'large')
        fn1 = MagicMock(return_value=item1)
        fn2 = MagicMock(return_value=item2)

        with override_settings(CACHES={'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'
        }}):
            from django.core.cache import cache
            cache.clear()
            for _ in range(5):
                svc.get_or_fetch(1, t1, fn1)
                svc.get_or_fetch(1, t2, fn2)

        fn1.assert_called_once()
        fn2.assert_called_once()
