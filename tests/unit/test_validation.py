"""Unit tests for gallery.domain.validation."""

import pytest
from django.test import override_settings

from gallery.domain.validation import (
    DetailParams,
    GalleryParams,
    ValidationError,
    validate_detail_params,
    validate_gallery_params,
)


# ---------------------------------------------------------------------------
# validate_gallery_params — happy paths
# ---------------------------------------------------------------------------


class TestGalleryParamsDefaults:
    def test_all_none_returns_defaults(self):
        params = validate_gallery_params()
        assert params.page == 1
        assert params.per_page == 10
        assert params.size == 'medium'
        assert params.grayscale is False
        assert params.blur == 0

    def test_explicit_valid_values(self):
        params = validate_gallery_params(
            page_raw='3',
            per_page_raw='20',
            size_raw='large',
            grayscale_raw='1',
            blur_raw='5',
        )
        assert params == GalleryParams(page=3, per_page=20, size='large', grayscale=True, blur=5)

    @override_settings(IMAGE_DEFAULT_SIZE='small', IMAGES_PER_PAGE=5)
    def test_settings_defaults_respected(self):
        params = validate_gallery_params()
        assert params.size == 'small'
        assert params.per_page == 5


# ---------------------------------------------------------------------------
# validate_gallery_params — blur boundaries
# ---------------------------------------------------------------------------


class TestBlurBoundaries:
    def test_blur_zero_is_valid(self):
        params = validate_gallery_params(blur_raw='0')
        assert params.blur == 0

    def test_blur_ten_is_valid(self):
        params = validate_gallery_params(blur_raw='10')
        assert params.blur == 10

    def test_blur_negative_raises(self):
        with pytest.raises(ValidationError) as exc:
            validate_gallery_params(blur_raw='-1')
        assert exc.value.field == 'blur'

    def test_blur_eleven_raises(self):
        with pytest.raises(ValidationError) as exc:
            validate_gallery_params(blur_raw='11')
        assert exc.value.field == 'blur'

    def test_blur_non_numeric_raises(self):
        with pytest.raises(ValidationError) as exc:
            validate_gallery_params(blur_raw='heavy')
        assert exc.value.field == 'blur'


# ---------------------------------------------------------------------------
# validate_gallery_params — size allow-list
# ---------------------------------------------------------------------------


class TestSizeAllowList:
    @pytest.mark.parametrize('size', ['small', 'medium', 'large'])
    def test_allowed_sizes_pass(self, size):
        params = validate_gallery_params(size_raw=size)
        assert params.size == size

    def test_unknown_size_raises(self):
        with pytest.raises(ValidationError) as exc:
            validate_gallery_params(size_raw='huge')
        assert exc.value.field == 'size'

    def test_size_is_case_normalised(self):
        params = validate_gallery_params(size_raw='LARGE')
        assert params.size == 'large'


# ---------------------------------------------------------------------------
# validate_gallery_params — page validation
# ---------------------------------------------------------------------------


class TestPageValidation:
    def test_page_zero_raises(self):
        with pytest.raises(ValidationError) as exc:
            validate_gallery_params(page_raw='0')
        assert exc.value.field == 'page'

    def test_page_negative_raises(self):
        with pytest.raises(ValidationError) as exc:
            validate_gallery_params(page_raw='-5')
        assert exc.value.field == 'page'

    def test_page_non_numeric_raises(self):
        with pytest.raises(ValidationError) as exc:
            validate_gallery_params(page_raw='abc')
        assert exc.value.field == 'page'

    def test_page_empty_string_defaults_to_one(self):
        params = validate_gallery_params(page_raw='')
        assert params.page == 1


# ---------------------------------------------------------------------------
# validate_gallery_params — per_page bounds
# ---------------------------------------------------------------------------


class TestPerPageBounds:
    def test_per_page_zero_raises(self):
        with pytest.raises(ValidationError) as exc:
            validate_gallery_params(per_page_raw='0')
        assert exc.value.field == 'per_page'

    def test_per_page_over_max_raises(self):
        with pytest.raises(ValidationError) as exc:
            validate_gallery_params(per_page_raw='51')
        assert exc.value.field == 'per_page'

    def test_per_page_at_max_is_valid(self):
        params = validate_gallery_params(per_page_raw='50')
        assert params.per_page == 50

    def test_per_page_at_min_is_valid(self):
        params = validate_gallery_params(per_page_raw='1')
        assert params.per_page == 1


# ---------------------------------------------------------------------------
# validate_gallery_params — grayscale + blur combination
# ---------------------------------------------------------------------------


class TestCombinations:
    def test_grayscale_and_blur_together(self):
        params = validate_gallery_params(grayscale_raw='true', blur_raw='7')
        assert params.grayscale is True
        assert params.blur == 7

    @pytest.mark.parametrize('flag', ['1', 'true', 'yes', 'on'])
    def test_truthy_grayscale_values(self, flag):
        params = validate_gallery_params(grayscale_raw=flag)
        assert params.grayscale is True

    @pytest.mark.parametrize('flag', ['0', 'false', 'no', 'off', None])
    def test_falsy_grayscale_values(self, flag):
        params = validate_gallery_params(grayscale_raw=flag)
        assert params.grayscale is False


# ---------------------------------------------------------------------------
# validate_detail_params
# ---------------------------------------------------------------------------


class TestDetailParams:
    def test_valid_detail_params(self):
        params = validate_detail_params(
            image_id_raw='42',
            size_raw='small',
            grayscale_raw='1',
            blur_raw='3',
        )
        assert params == DetailParams(image_id=42, size='small', grayscale=True, blur=3)

    def test_invalid_image_id_raises(self):
        with pytest.raises(ValidationError) as exc:
            validate_detail_params(image_id_raw='0')
        assert exc.value.field == 'image_id'

    def test_non_numeric_image_id_raises(self):
        with pytest.raises(ValidationError) as exc:
            validate_detail_params(image_id_raw='abc')
        assert exc.value.field == 'image_id'

    def test_detail_defaults_applied(self):
        params = validate_detail_params(image_id_raw='1')
        assert params.size == 'medium'
        assert params.grayscale is False
        assert params.blur == 0

    def test_detail_invalid_size_raises(self):
        with pytest.raises(ValidationError) as exc:
            validate_detail_params(image_id_raw='1', size_raw='xl')
        assert exc.value.field == 'size'

    def test_detail_blur_out_of_range_raises(self):
        with pytest.raises(ValidationError) as exc:
            validate_detail_params(image_id_raw='1', blur_raw='15')
        assert exc.value.field == 'blur'
