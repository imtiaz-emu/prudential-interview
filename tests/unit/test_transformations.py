"""Unit tests for gallery.domain.transformations."""

import pytest
from django.test import override_settings

from gallery.domain.transformations import ImageTransform
from gallery.domain.validation import DetailParams, GalleryParams


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _gallery(size='medium', grayscale=False, blur=0, page=1, per_page=10):
    return GalleryParams(page=page, per_page=per_page, size=size,
                         grayscale=grayscale, blur=blur)


def _detail(image_id=1, size='medium', grayscale=False, blur=0):
    return DetailParams(image_id=image_id, size=size,
                        grayscale=grayscale, blur=blur)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestConstruction:
    def test_from_gallery_params(self):
        t = ImageTransform.from_gallery_params(_gallery(size='large', grayscale=True, blur=3))
        assert t.size == 'large'
        assert t.grayscale is True
        assert t.blur == 3

    def test_from_detail_params(self):
        t = ImageTransform.from_detail_params(_detail(size='small', blur=7))
        assert t.size == 'small'
        assert t.blur == 7

    def test_defaults(self):
        t = ImageTransform(size='medium')
        assert t.grayscale is False
        assert t.blur == 0

    def test_is_frozen(self):
        t = ImageTransform(size='medium')
        with pytest.raises((AttributeError, TypeError)):
            t.blur = 5  # type: ignore[misc]


# ---------------------------------------------------------------------------
# pixel_size
# ---------------------------------------------------------------------------

class TestPixelSize:
    @override_settings(IMAGE_SIZES={'small': 200, 'medium': 400, 'large': 800})
    def test_small(self):
        assert ImageTransform('small').pixel_size() == 200

    @override_settings(IMAGE_SIZES={'small': 200, 'medium': 400, 'large': 800})
    def test_medium(self):
        assert ImageTransform('medium').pixel_size() == 400

    @override_settings(IMAGE_SIZES={'small': 200, 'medium': 400, 'large': 800})
    def test_large(self):
        assert ImageTransform('large').pixel_size() == 800


# ---------------------------------------------------------------------------
# is_normal
# ---------------------------------------------------------------------------

class TestIsNormal:
    def test_plain_image_is_normal(self):
        assert ImageTransform('medium').is_normal() is True

    def test_grayscale_is_not_normal(self):
        assert ImageTransform('medium', grayscale=True).is_normal() is False

    def test_blur_is_not_normal(self):
        assert ImageTransform('medium', blur=3).is_normal() is False

    def test_grayscale_and_blur_is_not_normal(self):
        assert ImageTransform('medium', grayscale=True, blur=5).is_normal() is False


# ---------------------------------------------------------------------------
# cache_key_segment — correctness
# ---------------------------------------------------------------------------

class TestCacheKeySegment:
    def test_normal_image(self):
        assert ImageTransform('medium').cache_key_segment() == 'size:medium'

    def test_grayscale_only(self):
        assert ImageTransform('small', grayscale=True).cache_key_segment() == 'size:small,grayscale:1'

    def test_blur_only(self):
        assert ImageTransform('large', blur=4).cache_key_segment() == 'size:large,blur:4'

    def test_grayscale_and_blur(self):
        key = ImageTransform('medium', grayscale=True, blur=7).cache_key_segment()
        assert key == 'size:medium,grayscale:1,blur:7'

    def test_blur_zero_excluded(self):
        key = ImageTransform('medium', blur=0).cache_key_segment()
        assert 'blur' not in key

    def test_grayscale_false_excluded(self):
        key = ImageTransform('medium', grayscale=False).cache_key_segment()
        assert 'grayscale' not in key


# ---------------------------------------------------------------------------
# cache_key_segment — determinism
# ---------------------------------------------------------------------------

class TestCacheKeyDeterminism:
    def test_same_inputs_same_key(self):
        a = ImageTransform('large', grayscale=True, blur=5).cache_key_segment()
        b = ImageTransform('large', grayscale=True, blur=5).cache_key_segment()
        assert a == b

    def test_different_blur_different_key(self):
        a = ImageTransform('medium', blur=3).cache_key_segment()
        b = ImageTransform('medium', blur=4).cache_key_segment()
        assert a != b

    def test_different_size_different_key(self):
        a = ImageTransform('small').cache_key_segment()
        b = ImageTransform('large').cache_key_segment()
        assert a != b

    def test_grayscale_differs_from_no_grayscale(self):
        a = ImageTransform('medium', grayscale=True).cache_key_segment()
        b = ImageTransform('medium', grayscale=False).cache_key_segment()
        assert a != b

    def test_canonical_order_is_stable(self):
        # Constructing with same values in any order yields same key.
        t1 = ImageTransform(size='large', grayscale=True, blur=2)
        t2 = ImageTransform(blur=2, grayscale=True, size='large')
        assert t1.cache_key_segment() == t2.cache_key_segment()


# ---------------------------------------------------------------------------
# as_provider_params
# ---------------------------------------------------------------------------

class TestAsProviderParams:
    def test_normal_has_only_size(self):
        params = ImageTransform('medium').as_provider_params()
        assert params == {'size': 'medium'}

    def test_grayscale_included_when_true(self):
        params = ImageTransform('medium', grayscale=True).as_provider_params()
        assert params['grayscale'] is True

    def test_grayscale_absent_when_false(self):
        params = ImageTransform('medium', grayscale=False).as_provider_params()
        assert 'grayscale' not in params

    def test_blur_included_when_nonzero(self):
        params = ImageTransform('large', blur=6).as_provider_params()
        assert params['blur'] == 6

    def test_blur_absent_when_zero(self):
        params = ImageTransform('large', blur=0).as_provider_params()
        assert 'blur' not in params

    def test_combined_transform(self):
        params = ImageTransform('small', grayscale=True, blur=9).as_provider_params()
        assert params == {'size': 'small', 'grayscale': True, 'blur': 9}
