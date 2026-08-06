"""Unit tests for gallery.services.url_builder and gallery.services.image_provider."""

import pytest
from django.test import override_settings
from unittest.mock import MagicMock

import requests

from gallery.domain.transformations import ImageTransform
from gallery.services.url_builder import PicsumUrlBuilder
from gallery.services.image_provider import ImageProvider, PicsumImageProvider
from gallery.types import ImageItem


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(status_code: int = 200) -> MagicMock:
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
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


def _provider_with_mock_session():
    """Return a provider whose session always responds with a valid info response."""
    builder = PicsumUrlBuilder(base_url='https://picsum.photos')
    p = PicsumImageProvider(url_builder=builder, _sleep=MagicMock())
    p.session = MagicMock()
    p.session.get.return_value = _make_info_response()
    return p


# ---------------------------------------------------------------------------
# PicsumUrlBuilder — URL generation
# ---------------------------------------------------------------------------


class TestPicsumUrlBuilder:
    def setup_method(self):
        self.builder = PicsumUrlBuilder(base_url='https://picsum.photos')

    def test_normal_image_url(self):
        t = ImageTransform('medium')  # 400px
        url = self.builder.image_url(1, t)
        assert url == 'https://picsum.photos/id/1/400/400'

    def test_small_image_url(self):
        t = ImageTransform('small')   # 200px
        url = self.builder.image_url(5, t)
        assert url == 'https://picsum.photos/id/5/200/200'

    def test_large_image_url(self):
        t = ImageTransform('large')   # 800px
        url = self.builder.image_url(99, t)
        assert url == 'https://picsum.photos/id/99/800/800'

    def test_grayscale_appended(self):
        t = ImageTransform('medium', grayscale=True)
        url = self.builder.image_url(10, t)
        assert url == 'https://picsum.photos/id/10/400/400?grayscale'

    def test_blur_appended(self):
        t = ImageTransform('medium', blur=5)
        url = self.builder.image_url(10, t)
        assert url == 'https://picsum.photos/id/10/400/400?blur=5'

    def test_grayscale_and_blur_combined(self):
        t = ImageTransform('medium', grayscale=True, blur=3)
        url = self.builder.image_url(10, t)
        assert url == 'https://picsum.photos/id/10/400/400?grayscale&blur=3'

    def test_blur_zero_not_appended(self):
        t = ImageTransform('medium', blur=0)
        url = self.builder.image_url(10, t)
        assert 'blur' not in url

    def test_grayscale_false_not_appended(self):
        t = ImageTransform('medium', grayscale=False)
        url = self.builder.image_url(10, t)
        assert 'grayscale' not in url

    def test_trailing_slash_on_base_url_stripped(self):
        builder = PicsumUrlBuilder(base_url='https://picsum.photos/')
        url = builder.image_url(1, ImageTransform('medium'))
        assert '//id' not in url
        assert url == 'https://picsum.photos/id/1/400/400'

    @override_settings(PICSUM_BASE_URL='https://example-provider.com')
    def test_base_url_from_settings(self):
        builder = PicsumUrlBuilder()   # reads from settings
        url = builder.image_url(1, ImageTransform('medium'))
        assert url.startswith('https://example-provider.com')

    def test_different_ids_produce_different_urls(self):
        t = ImageTransform('medium')
        assert self.builder.image_url(1, t) != self.builder.image_url(2, t)

    def test_same_inputs_produce_same_url(self):
        t = ImageTransform('large', grayscale=True, blur=2)
        assert self.builder.image_url(7, t) == self.builder.image_url(7, t)


# ---------------------------------------------------------------------------
# PicsumImageProvider — fetch_image
# ---------------------------------------------------------------------------


class TestPicsumImageProvider:
    def setup_method(self):
        self.provider = _provider_with_mock_session()

    def test_fetch_image_returns_image_item(self):
        item = self.provider.fetch_image(1, ImageTransform('medium'))
        assert isinstance(item, ImageItem)

    def test_fetch_image_correct_id(self):
        item = self.provider.fetch_image(42, ImageTransform('medium'))
        assert item.image_id == 42

    def test_fetch_image_url_contains_id(self):
        item = self.provider.fetch_image(42, ImageTransform('medium'))
        assert '/id/42/' in item.url

    def test_fetch_image_dimensions_from_provider(self):
        # width/height come from the info endpoint, not from the transform size
        item = self.provider.fetch_image(1, ImageTransform('small'))
        assert item.width == 5616
        assert item.height == 3744

    def test_fetch_image_transform_preserved(self):
        t = ImageTransform('large', grayscale=True, blur=4)
        item = self.provider.fetch_image(1, t)
        assert item.transform == t

    def test_fetch_images_returns_correct_count(self):
        items = self.provider.fetch_images([1, 2, 3, 4, 5], ImageTransform('medium'))
        assert len(items) == 5

    def test_fetch_images_preserves_order(self):
        ids = [3, 7, 1, 9]
        items = self.provider.fetch_images(ids, ImageTransform('medium'))
        assert [i.image_id for i in items] == ids

    def test_fetch_images_empty_list(self):
        items = self.provider.fetch_images([], ImageTransform('medium'))
        assert items == []


# ---------------------------------------------------------------------------
# Provider Protocol — structural conformance
# ---------------------------------------------------------------------------


class TestImageProviderProtocol:
    def test_picsum_provider_satisfies_protocol(self):
        provider = PicsumImageProvider()
        assert isinstance(provider, ImageProvider)

    def test_mock_satisfies_protocol_when_methods_present(self):
        mock = MagicMock(spec=ImageProvider)
        assert hasattr(mock, 'fetch_image')
        assert hasattr(mock, 'fetch_images')

    def test_swapped_provider_same_return_shape(self):
        """A stub provider returns the same ImageItem shape — views need no changes."""
        class StubProvider:
            def fetch_image(self, image_id, transform):
                size = transform.pixel_size()
                return ImageItem(
                    image_id=image_id,
                    url=f'https://stub.example/img/{image_id}',
                    width=size,
                    height=size,
                    transform=transform,
                )

            def fetch_images(self, image_ids, transform):
                return [self.fetch_image(i, transform) for i in image_ids]

        stub = StubProvider()
        item = stub.fetch_image(5, ImageTransform('medium'))
        assert item.image_id == 5
        assert item.width == 400
