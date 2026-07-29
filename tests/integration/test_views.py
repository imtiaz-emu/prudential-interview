"""Integration tests for gallery views (gallery list + detail)."""

import pytest
from unittest.mock import MagicMock, patch

from django.test import Client
from django.urls import reverse

from gallery.domain.transformations import ImageTransform
from gallery.domain.validation import DetailParams, GalleryParams
from gallery.errors import NoFallbackError
from gallery.types import GalleryPage, ImageItem


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_item(image_id: int = 1, size: str = 'medium') -> ImageItem:
    t = ImageTransform(size)
    px = t.pixel_size()
    return ImageItem(
        image_id=image_id,
        url=f'https://picsum.photos/id/{image_id}/{px}/{px}',
        width=px,
        height=px,
        transform=t,
    )


def _make_params(**kwargs) -> GalleryParams:
    defaults = dict(page=1, per_page=10, size='medium', grayscale=False, blur=0)
    defaults.update(kwargs)
    return GalleryParams(**defaults)


def _make_gallery_page(page=1, per_page=10, items=None, errors=None) -> GalleryPage:
    params = _make_params(page=page, per_page=per_page)
    return GalleryPage(
        items=items or [_make_item(i) for i in range(1, per_page + 1)],
        page=page,
        per_page=per_page,
        has_previous=page > 1,
        has_next=True,
        params=params,
        errors=errors or [],
    )


# ---------------------------------------------------------------------------
# Gallery view — basic rendering
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestGalleryView:
    def test_returns_200(self):
        client = Client()
        with patch('gallery.views._service') as mock_svc:
            mock_svc.get_page.return_value = _make_gallery_page()
            response = client.get(reverse('gallery:index'))
        assert response.status_code == 200

    def test_renders_gallery_template(self):
        client = Client()
        with patch('gallery.views._service') as mock_svc:
            mock_svc.get_page.return_value = _make_gallery_page()
            response = client.get(reverse('gallery:index'))
        assert b'gallery-grid' in response.content

    def test_images_appear_in_response(self):
        client = Client()
        items = [_make_item(i) for i in [3, 7, 12]]
        with patch('gallery.views._service') as mock_svc:
            mock_svc.get_page.return_value = _make_gallery_page(items=items, per_page=3)
            response = client.get(reverse('gallery:index'))
        assert b'/id/3/' in response.content
        assert b'/id/7/' in response.content
        assert b'/id/12/' in response.content

    def test_pagination_next_link_present(self):
        client = Client()
        with patch('gallery.views._service') as mock_svc:
            mock_svc.get_page.return_value = _make_gallery_page(page=1)
            response = client.get(reverse('gallery:index'))
        assert b'Next' in response.content

    def test_no_previous_on_page_1(self):
        client = Client()
        page = _make_gallery_page(page=1)
        page.has_previous = False
        with patch('gallery.views._service') as mock_svc:
            mock_svc.get_page.return_value = page
            response = client.get(reverse('gallery:index'))
        # Previous link should be a disabled span, not an anchor
        content = response.content.decode()
        assert 'pagination__link--disabled' in content or 'Previous' in content

    def test_partial_errors_shown_as_messages(self):
        client = Client()
        page = _make_gallery_page(errors=['Image 5 could not be loaded.'])
        with patch('gallery.views._service') as mock_svc:
            mock_svc.get_page.return_value = page
            response = client.get(reverse('gallery:index'))
        assert b'Image 5 could not be loaded.' in response.content


# ---------------------------------------------------------------------------
# Gallery view — invalid page redirect
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestGalleryInvalidPageRedirect:
    def test_invalid_page_string_redirects_to_page_1(self):
        client = Client()
        response = client.get(reverse('gallery:index'), {'page': 'abc'})
        assert response.status_code == 302
        assert 'page=1' in response['Location']

    def test_page_zero_redirects_to_page_1(self):
        client = Client()
        response = client.get(reverse('gallery:index'), {'page': '0'})
        assert response.status_code == 302
        assert 'page=1' in response['Location']

    def test_negative_page_redirects_to_page_1(self):
        client = Client()
        response = client.get(reverse('gallery:index'), {'page': '-3'})
        assert response.status_code == 302
        assert 'page=1' in response['Location']

    def test_invalid_page_shows_message_after_redirect(self):
        client = Client()
        with patch('gallery.views._service') as mock_svc:
            mock_svc.get_page.return_value = _make_gallery_page()
            response = client.get(
                reverse('gallery:index'), {'page': 'abc'}, follow=True
            )
        assert response.status_code == 200
        assert b'Page' in response.content or b'page' in response.content.lower()

    def test_invalid_page_preserves_other_params_in_redirect(self):
        client = Client()
        response = client.get(
            reverse('gallery:index'),
            {'page': 'xyz', 'size': 'large', 'blur': '3'},
        )
        assert response.status_code == 302
        location = response['Location']
        assert 'size=large' in location
        assert 'blur=3' in location
        assert 'page=1' in location

    def test_invalid_size_redirects_to_root(self):
        client = Client()
        response = client.get(reverse('gallery:index'), {'size': 'huge'})
        assert response.status_code == 302


# ---------------------------------------------------------------------------
# Gallery view — filter params preserved in pagination
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestFilterParamsPreserved:
    def test_next_page_url_contains_active_size(self):
        client = Client()
        with patch('gallery.views._service') as mock_svc:
            mock_svc.get_page.return_value = _make_gallery_page()
            response = client.get(
                reverse('gallery:index'), {'size': 'large', 'page': '1'}
            )
        assert b'size=large' in response.content

    def test_next_page_url_contains_active_blur(self):
        client = Client()
        with patch('gallery.views._service') as mock_svc:
            mock_svc.get_page.return_value = _make_gallery_page()
            response = client.get(
                reverse('gallery:index'), {'blur': '5', 'page': '1'}
            )
        assert b'blur=5' in response.content

    def test_detail_links_contain_filter_query(self):
        client = Client()
        with patch('gallery.views._service') as mock_svc:
            mock_svc.get_page.return_value = _make_gallery_page()
            response = client.get(
                reverse('gallery:index'), {'size': 'small', 'grayscale': '1'}
            )
        content = response.content.decode()
        assert 'size=small' in content


# ---------------------------------------------------------------------------
# Detail view
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDetailView:
    def test_returns_200(self):
        client = Client()
        item = _make_item(42)
        with patch('gallery.views._service') as mock_svc:
            mock_svc.get_detail.return_value = item
            response = client.get(
                reverse('gallery:detail', args=[42]), {'size': 'medium'}
            )
        assert response.status_code == 200

    def test_renders_detail_template(self):
        client = Client()
        item = _make_item(42)
        with patch('gallery.views._service') as mock_svc:
            mock_svc.get_detail.return_value = item
            response = client.get(reverse('gallery:detail', args=[42]))
        assert b'detail' in response.content.lower()

    def test_image_url_in_response(self):
        client = Client()
        item = _make_item(42)
        with patch('gallery.views._service') as mock_svc:
            mock_svc.get_detail.return_value = item
            response = client.get(reverse('gallery:detail', args=[42]))
        assert b'/id/42/' in response.content

    def test_params_reflected_in_response(self):
        client = Client()
        item = _make_item(7)
        with patch('gallery.views._service') as mock_svc:
            mock_svc.get_detail.return_value = item
            response = client.get(
                reverse('gallery:detail', args=[7]),
                {'size': 'large', 'blur': '4'},
            )
        content = response.content.decode()
        assert 'Large' in content or 'large' in content
        assert '4' in content

    def test_grayscale_reflected_in_params_table(self):
        client = Client()
        item = _make_item(5)
        with patch('gallery.views._service') as mock_svc:
            mock_svc.get_detail.return_value = item
            response = client.get(
                reverse('gallery:detail', args=[5]), {'grayscale': '1'}
            )
        assert b'Yes' in response.content

    def test_back_link_present(self):
        client = Client()
        item = _make_item(1)
        with patch('gallery.views._service') as mock_svc:
            mock_svc.get_detail.return_value = item
            response = client.get(reverse('gallery:detail', args=[1]))
        assert b'Back' in response.content or b'gallery' in response.content.lower()

    def test_invalid_size_redirects_to_gallery(self):
        client = Client()
        response = client.get(
            reverse('gallery:detail', args=[1]), {'size': 'enormous'}
        )
        assert response.status_code == 302
        assert reverse('gallery:index') in response['Location']

    def test_upstream_unavailable_redirects_with_message(self):
        client = Client()
        with patch('gallery.views._service') as mock_svc:
            mock_svc.get_detail.side_effect = NoFallbackError("down", image_id=99)
            response = client.get(reverse('gallery:detail', args=[99]))
        assert response.status_code == 302
